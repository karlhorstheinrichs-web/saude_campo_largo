"""
IPCSO-S — Módulo 3
Rede Multiplex de Grafos + ICS + PNA (AHP-Gaussiano) + IPCSO-S
Projeto: Modelo Preditivo de Decisão Orçamentária — Função Saúde
Município: Campo Largo/PR
"""

import os
import warnings
import numpy as np
import pandas as pd
import networkx as nx
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

warnings.filterwarnings("ignore")
load_dotenv()

# ============================================================
# 0. CONEXÃO SUPABASE
# ============================================================

def conectar():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL / SUPABASE_KEY não encontrados no .env")
    return create_client(url, key)

# ============================================================
# 1. CARGA DE DADOS
# ============================================================

def carregar_acoes(cliente):
    """Carrega ações orçamentárias do Supabase."""
    resp = cliente.table("acoes_orcamentarias").select("*").execute()
    df = pd.DataFrame(resp.data)
    print(f"[OK] acoes_orcamentarias: {len(df)} registros")
    return df

def carregar_leading(cliente):
    """Carrega sinais leading ambulatoriais."""
    resp = cliente.table("sinais_leading_ambulatorial").select("*").execute()
    df = pd.DataFrame(resp.data)
    df["periodo"] = pd.to_datetime(df["periodo"])
    print(f"[OK] sinais_leading_ambulatorial: {len(df)} registros")
    return df

def carregar_parametros_custo(cliente):
    """Carrega parâmetros de custo."""
    resp = cliente.table("parametros_custo").select("*").execute()
    df = pd.DataFrame(resp.data)
    print(f"[OK] parametros_custo: {len(df)} registros")
    return df

# ============================================================
# 2. SIMULAÇÃO DE SINAIS LAGGING (SIOPS)
#    Usado até a tabela sinais_lagging_siops ser populada
# ============================================================

def simular_lagging(df_acoes, periodos=12, seed=42):
    """
    Simula execução orçamentária realista para cada ação,
    baseado nos valores LOA 2024 de acoes_orcamentarias.
    Gera 12 meses (jan-dez 2024).
    """
    np.random.seed(seed)
    registros = []
    inicio = date(2024, 1, 1)

    for _, acao in df_acoes.iterrows():
        valor_loa = float(acao.get("valor_loa_2024") or 0)
        valor_mensal = valor_loa / 12 if valor_loa > 0 else 50000

        for m in range(periodos):
            periodo = date(2024, m + 1, 1)
            # Sazonalidade: pico no meio do ano
            sazo = 1 + 0.15 * np.sin(np.pi * m / 6)
            # Execução: 70–100% da dotação mensal
            pct = np.clip(np.random.normal(0.85, 0.10), 0.60, 1.00)
            liquidado = valor_mensal * sazo * pct
            empenhado = liquidado * np.random.uniform(1.00, 1.05)
            pago = liquidado * np.random.uniform(0.90, 1.00)
            dotacao = valor_mensal * sazo
            houve_sup = bool(pct > 0.97)
            valor_sup = (liquidado - dotacao) * 1.05 if houve_sup else 0.0

            registros.append({
                "municipio_id":    int(acao.get("municipio_id", 1)),
                "acao_id":         int(acao["id"]),
                "subfuncao_id":    int(acao["subfuncao_id"]),
                "periodo":         periodo,
                "ano":             2024,
                "mes":             m + 1,
                "dotacao_inicial": dotacao,
                "dotacao_atualizada": dotacao + valor_sup,
                "empenhado":       empenhado,
                "liquidado":       liquidado,
                "pago":            pago,
                "houve_suplementacao": houve_sup,
                "valor_suplementado":  valor_sup,
                "pct_execucao":    pct,
                "fonte":           acao.get("modelo_financiamento", "A"),
            })

    df = pd.DataFrame(registros)
    print(f"[SIM] sinais_lagging simulados: {len(df)} registros")
    return df

# ============================================================
# 3. MSM SIMPLIFICADO — recalcula IAM por subfunção
#    (usa dados leading já coletados no Módulo 1/2)
# ============================================================

def calcular_iam(df_leading):
    """
    Calcula IAM (Índice de Anomalia por Markov-switching) por subfunção.
    Versão simplificada: usa z-score da demanda para estimar
    P(regime_colapso) sem dependência do statsmodels.
    """
    resultados = {}

    colunas_demanda = [c for c in df_leading.columns
                   if c in ("total_procedimentos","total_consultas",
                            "total_exames","total_outros")]

    subfuncoes = df_leading["subfuncao_id"].unique() if "subfuncao_id" in df_leading.columns else [1]

    for sf in sorted(subfuncoes):
        if "subfuncao_id" in df_leading.columns:
            sub = df_leading[df_leading["subfuncao_id"] == sf].copy()
        else:
            sub = df_leading.copy()

        if sub.empty or not colunas_demanda:
            resultados[sf] = 0.3
            continue

        # Série de demanda total — força conversão numérica
        sub = sub.copy()
        for col in colunas_demanda:
            sub[col] = pd.to_numeric(sub[col], errors="coerce").fillna(0)
        sub["demanda_total"] = sub[colunas_demanda].sum(axis=1)
        serie = sub.sort_values("periodo")["demanda_total"].values

        if len(serie) < 4:
            resultados[sf] = 0.3
            continue

        media = np.mean(serie)
        std   = np.std(serie) if np.std(serie) > 0 else 1
        ultimo = serie[-1]
        z = (ultimo - media) / std

        # P(colapso) via função logística do z-score
        prob_colapso = 1 / (1 + np.exp(-z))
        resultados[sf] = round(float(prob_colapso), 4)

    print(f"[OK] IAM calculado para {len(resultados)} subfunções")
    return resultados  # {subfuncao_id: prob_colapso}

# ============================================================
# 4. ICD — Índice de Confiança da Detecção
# ============================================================

def calcular_icd(iam_dict, alpha=0.65):
    """
    ICD(s) = alpha * IAM(s) + (1 - alpha) * IF(s)
    IF simulado como perturbação do IAM (Isolation Forest ausente neste módulo).
    alpha calibrado empiricamente (padrão 0.65).
    """
    icd_dict = {}
    for sf, iam in iam_dict.items():
        np.random.seed(int(sf) * 7)
        if_score = float(np.clip(iam + np.random.normal(0, 0.05), 0, 1))
        icd = alpha * iam + (1 - alpha) * if_score
        icd_dict[sf] = round(icd, 4)
    print(f"[OK] ICD calculado (alpha={alpha})")
    return icd_dict

# ============================================================
# 5. REDE MULTIPLEX — 3 camadas
# ============================================================

def construir_rede_multiplex(df_acoes, df_lagging):
    """
    Constrói grafo multiplex com 3 camadas:
      L1 — Subfunções (nós = subfuncoes, arestas = relação funcional)
      L2 — Ações orçamentárias (nós = acoes, arestas = mesma subfunção)
      L3 — Execução financeira (arestas ponderadas por liquidado)
    Retorna dicionário de grafos por camada.
    """
    grafos = {}

    # --- Camada L1: Subfunções ---
    G1 = nx.Graph()
    subfuncoes = df_acoes["subfuncao_id"].unique()
    for sf in subfuncoes:
        G1.add_node(f"SF{sf}", tipo="subfuncao", id=int(sf))

    # Conecta subfunções com relação funcional (hierarquia saúde)
    # Atenção primária (SF1) conecta-se a media (SF3) e vigilância (SF5)
    conexoes_funcionais = [(1,3),(1,5),(1,6),(2,4),(3,4),(5,6),(7,8)]
    for a, b in conexoes_funcionais:
        if f"SF{a}" in G1.nodes and f"SF{b}" in G1.nodes:
            G1.add_edge(f"SF{a}", f"SF{b}", peso=1.0)

    grafos["L1_subfuncoes"] = G1

    # --- Camada L2: Ações ---
    G2 = nx.Graph()
    for _, ac in df_acoes.iterrows():
        G2.add_node(f"AC{ac['id']}",
                    tipo="acao",
                    subfuncao=int(ac["subfuncao_id"]),
                    codigo=str(ac.get("codigo_acao","")),
                    modelo=str(ac.get("modelo_financiamento","")))

    # Conecta ações da mesma subfunção
    for sf in subfuncoes:
        acoes_sf = df_acoes[df_acoes["subfuncao_id"] == sf]["id"].tolist()
        for i in range(len(acoes_sf)):
            for j in range(i+1, len(acoes_sf)):
                G2.add_edge(f"AC{acoes_sf[i]}", f"AC{acoes_sf[j]}", peso=0.8)

    grafos["L2_acoes"] = G2

    # --- Camada L3: Execução financeira ---
    G3 = nx.DiGraph()
    for _, ac in df_acoes.iterrows():
        G3.add_node(f"AC{ac['id']}", subfuncao=int(ac["subfuncao_id"]))

    # Agrega execução por ação
    if not df_lagging.empty and "acao_id" in df_lagging.columns:
        exec_por_acao = df_lagging.groupby("acao_id")["liquidado"].sum()
        total = exec_por_acao.sum() if exec_por_acao.sum() > 0 else 1

        # Arestas ponderadas: fluxo de recursos entre subfunções via ações
        for sf in subfuncoes:
            acoes_sf = df_acoes[df_acoes["subfuncao_id"] == sf]["id"].tolist()
            for ac_id in acoes_sf:
                peso = float(exec_por_acao.get(ac_id, 0)) / total
                # Fluxo saúde primária → média complexidade (simplificado)
                sf_destino = {1:3, 2:4, 5:6}.get(int(sf), int(sf))
                acoes_dest = df_acoes[df_acoes["subfuncao_id"] == sf_destino]["id"].tolist()
                for ac_dest in acoes_dest[:1]:  # conexão principal
                    G3.add_edge(f"AC{ac_id}", f"AC{ac_dest}", peso=peso)

    grafos["L3_execucao"] = G3

    print(f"[OK] Rede multiplex: L1={G1.number_of_nodes()}nós/{G1.number_of_edges()}arestas | "
          f"L2={G2.number_of_nodes()}nós/{G2.number_of_edges()}arestas | "
          f"L3={G3.number_of_nodes()}nós/{G3.number_of_edges()}arestas")
    return grafos

# ============================================================
# 6. ICS — Índice de Contágio Sistêmico
# ============================================================

def calcular_ics(grafos, df_acoes):
    """
    ICS(s,t) = delta*CD(s) + epsilon*CB(s) + zeta*CE(s)
    Pesos: delta=0.4, epsilon=0.35, zeta=0.25 (calibração inicial)
    Centralidades calculadas sobre L2 (ações) e agregadas por subfunção.
    """
    delta, epsilon, zeta = 0.40, 0.35, 0.25
    G2 = grafos["L2_acoes"]
    ics_dict = {}

    # Centralidades em L2
    try:
        cd = nx.degree_centrality(G2)
    except:
        cd = {n: 0 for n in G2.nodes}

    try:
        cb = nx.betweenness_centrality(G2, normalized=True)
    except:
        cb = {n: 0 for n in G2.nodes}

    try:
        ce = nx.eigenvector_centrality(G2, max_iter=500)
    except:
        ce = {n: 0 for n in G2.nodes}

    # Agrega por subfunção (média das ações da subfunção)
    subfuncoes = df_acoes["subfuncao_id"].unique()
    for sf in sorted(subfuncoes):
        acoes_sf = df_acoes[df_acoes["subfuncao_id"] == sf]["id"].tolist()
        nos = [f"AC{a}" for a in acoes_sf if f"AC{a}" in G2.nodes]

        if not nos:
            ics_dict[sf] = 0.0
            continue

        cd_sf  = np.mean([cd.get(n, 0)  for n in nos])
        cb_sf  = np.mean([cb.get(n, 0)  for n in nos])
        ce_sf  = np.mean([ce.get(n, 0)  for n in nos])

        ics = delta * cd_sf + epsilon * cb_sf + zeta * ce_sf
        ics_dict[sf] = round(float(ics), 4)

    # Normaliza 0–1
    max_ics = max(ics_dict.values()) if max(ics_dict.values()) > 0 else 1
    ics_dict = {sf: round(v / max_ics, 4) for sf, v in ics_dict.items()}

    print(f"[OK] ICS calculado (delta={delta}, epsilon={epsilon}, zeta={zeta})")
    return ics_dict

# ============================================================
# 7. PNA — Peso Normativo AHP-Gaussiano por subfunção
# ============================================================

def calcular_pna(df_acoes, df_parametros):
    """
    PNA(s) = Soma_k [ wk * ck(s) ]
    Critérios normativos (AHP):
      C1 — Participação LOA (peso 0.40): quanto a subfunção representa no total
      C2 — Modelo de financiamento SUS (peso 0.35): A/B = maior dependência federal
      C3 — Número de ações (peso 0.25): complexidade de gestão
    Normalização Gaussiana: ck(s) = exp(-(xk - media)^2 / (2*sigma^2))
    """
    w1, w2, w3 = 0.40, 0.35, 0.25
    pna_dict = {}

    total_loa = df_acoes["valor_loa_2024"].fillna(0).astype(float).sum()
    if total_loa == 0:
        total_loa = 1

    # Mapa modelo → dependência federal (0–1)
    dep_federal = {"A": 0.90, "B": 0.85, "C": 0.60, "D": 0.70}

    subfuncoes = df_acoes["subfuncao_id"].unique()

    raw = {}
    for sf in subfuncoes:
        sub = df_acoes[df_acoes["subfuncao_id"] == sf]
        # C1: participação LOA
        loa_sf = sub["valor_loa_2024"].fillna(0).astype(float).sum()
        c1 = loa_sf / total_loa

        # C2: dependência federal média dos modelos da subfunção
        modelos = sub["modelo_financiamento"].fillna("C").tolist()
        c2 = np.mean([dep_federal.get(m, 0.5) for m in modelos])

        # C3: número de ações (normalizar depois)
        c3_raw = len(sub)
        raw[sf] = (c1, c2, c3_raw)

    # Normalização Gaussiana de C3
    c3_vals = np.array([v[2] for v in raw.values()], dtype=float)
    c3_media = np.mean(c3_vals)
    c3_sigma = np.std(c3_vals) if np.std(c3_vals) > 0 else 1

    for sf, (c1, c2, c3_raw) in raw.items():
        c3 = float(np.exp(-((c3_raw - c3_media)**2) / (2 * c3_sigma**2)))
        pna = w1 * c1 + w2 * c2 + w3 * c3
        pna_dict[sf] = round(pna, 4)

    # Normaliza 0–1
    max_pna = max(pna_dict.values()) if max(pna_dict.values()) > 0 else 1
    pna_dict = {sf: round(v / max_pna, 4) for sf, v in pna_dict.items()}

    print(f"[OK] PNA calculado (w1={w1}, w2={w2}, w3={w3})")
    return pna_dict

# ============================================================
# 8. IPCSO-S — composição final
# ============================================================

def calcular_ipcso(icd_dict, ics_dict, pna_dict, df_acoes, df_lagging):
    """
    IPCSO-S_n(s,t) = [ICD(s) * ICS(s) * PNA(s)] / max{ICD * ICS * PNA}
    Gera recomendação completa por subfunção.
    """
    THETA = 0.50  # limiar Y1

    subfuncoes = sorted(set(icd_dict) | set(ics_dict) | set(pna_dict))
    brutos = {}

    for sf in subfuncoes:
        icd = icd_dict.get(sf, 0)
        ics = ics_dict.get(sf, 0)
        pna = pna_dict.get(sf, 0)
        brutos[sf] = icd * ics * pna if (ics > 0 or pna > 0) else icd

    max_bruto = max(brutos.values()) if max(brutos.values()) > 0 else 1

    # Execução por ação (para Y2)
    if not df_lagging.empty and "acao_id" in df_lagging.columns:
        exec_acao = df_lagging.groupby("acao_id")["liquidado"].sum().to_dict()
        dot_acao  = df_lagging.groupby("acao_id")["dotacao_inicial"].sum().to_dict()
    else:
        exec_acao, dot_acao = {}, {}

    resultados = []
    hoje = date.today()

    for sf in subfuncoes:
        ipcso_n = round(brutos[sf] / max_bruto, 4)
        icd     = icd_dict.get(sf, 0)
        ics     = ics_dict.get(sf, 0)
        pna     = pna_dict.get(sf, 0)

        y1 = bool(icd >= THETA)

        # Y2: gap de execução das ações da subfunção
        acoes_sf = df_acoes[df_acoes["subfuncao_id"] == sf]["id"].tolist()
        y2 = 0.0
        for ac_id in acoes_sf:
            exec_v = exec_acao.get(ac_id, 0)
            dot_v  = dot_acao.get(ac_id, 0)
            gap    = max(exec_v - dot_v, 0)
            y2    += gap
        y2 = round(y2, 2)

        # Cenário e fonte
        if y2 > 0:
            cenario = "intra_orcamentario"
            fonte   = "superavit_financeiro"
        else:
            cenario = "extra_orcamentario"
            fonte   = "transferencia_federal"

        # Semáforo
        if ipcso_n >= 0.70:
            semaforo = "vermelho"
        elif ipcso_n >= 0.40:
            semaforo = "amarelo"
        else:
            semaforo = "verde"

        # Modelo de versão
        modelo = "MSM+MDS+Multiplex+PNA"

        resultados.append({
            "municipio_id":        1,
            "subfuncao_id":        int(sf),
            "periodo_alerta":      hoje,
            "periodo_previsto":    date(hoje.year, hoje.month, 1) + timedelta(days=32),
            "iam":                 icd_dict.get(sf, 0),   # IAM ≈ base do ICD
            "icd":                 icd,
            "ics":                 ics,
            "pna":                 pna,
            "ipcso_s":             ipcso_n,
            "y1_previsto":         y1,
            "y2_estimado":         y2,
            "modelo_financiamento": df_acoes[df_acoes["subfuncao_id"]==sf]["modelo_financiamento"].iloc[0]
                                    if not df_acoes[df_acoes["subfuncao_id"]==sf].empty else "A",
            "cenario":             cenario,
            "fonte_recomendada":   fonte,
            "saldo_credito":       y2 * 1.10,
            "semaforo_cvi":                      semaforo,
            "modelo_versao":       "MSM+MDS+Multiplex",
                              "mlflow_run_id":       f"mod3_{hoje.strftime('%Y%m%d')}",
        })

    df_result = pd.DataFrame(resultados)
    print(f"[OK] IPCSO-S calculado: {len(df_result)} subfunções")
    return df_result

# ============================================================
# 9. SALVAR NO SUPABASE
# ============================================================

def salvar_resultados(cliente, df_result):
    colunas_aceitas = [
        "municipio_id", "subfuncao_id", "periodo_alerta", "periodo_previsto",
        "iam", "icd", "ics", "pna", "ipcso_s", "y1_previsto", "y2_estimado",
        "modelo_financiamento", "cenario", "fonte_recomendada", "saldo_credito",
        "semaforo_cvi", "modelo_versao", "mlflow_run_id"
    ]
    registros = df_result[[c for c in colunas_aceitas if c in df_result.columns]].copy()
    for col in ["periodo_alerta", "periodo_previsto"]:
        if col in registros.columns:
            registros[col] = registros[col].astype(str)
    registros = registros.where(pd.notnull(registros), None)
    dados = registros.to_dict(orient="records")
    for d in dados:
        for k, v in d.items():
            if isinstance(v, (np.integer,)): d[k] = int(v)
            elif isinstance(v, (np.floating,)): d[k] = float(v)
            elif isinstance(v, (np.bool_,)): d[k] = bool(v)
    resp = cliente.table("resultados_ipcso").insert(dados).execute()
    print(f"[OK] {len(dados)} registros salvos em resultados_ipcso")
    return resp

# ============================================================
# 10. RELATÓRIO FINAL
# ============================================================

def exibir_relatorio(df_result):
    print("\n" + "="*60)
    print("IPCSO-S — RELATÓRIO DE RECOMENDAÇÕES")
    print(f"Campo Largo/PR | {date.today().isoformat()}")
    print("="*60)

    nomes_sf = {
        1: "Atenção Básica",
        2: "Assistência Hospitalar",
        3: "Suporte Profilático",
        4: "Vigilância Sanitária",
        5: "Vigilância Epidemiológica",
        6: "Alimentação e Nutrição",
        7: "Gestão do SUS",
        8: "Outras Ações",
    }

    df_ord = df_result.sort_values("ipcso_s", ascending=False)

    for _, row in df_ord.iterrows():
        sf   = int(row["subfuncao_id"])
        nome = nomes_sf.get(sf, f"Subfunção {sf}")
        sem  = row["semaforo_cvi"]
        icon = {"vermelho": "🔴", "amarelo": "🟡", "verde": "🟢"}.get(sem, "⚪")

        print(f"\n{icon} SF{sf} — {nome}")
        print(f"   IPCSO-S : {row['ipcso_s']:.4f}  |  Semáforo: {sem}")
        print(f"   ICD     : {row['icd']:.4f}  |  ICS: {row['ics']:.4f}  |  PNA: {row['pna']:.4f}")
        print(f"   Y1      : {'⚠ ALERTA' if row['y1_previsto'] else '✓ Normal'}")
        print(f"   Y2 est. : R$ {row['y2_estimado']:,.2f}")
        print(f"   Cenário : {row['cenario']}  |  Fonte: {row['fonte_recomendada']}")

    print("\n" + "="*60)
    alertas = df_result[df_result["semaforo_cvi"] == "vermelho"]
    print(f"RESUMO: {len(alertas)} subfunção(ões) em estado CRÍTICO")
    print("="*60)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("IPCSO-S — MÓDULO 3: Rede Multiplex + ICS + PNA + IPCSO-S")
    print("="*60 + "\n")

    # Conexão
    cliente = conectar()

    # Carga
    df_acoes      = carregar_acoes(cliente)
    df_leading    = carregar_leading(cliente)
    df_parametros = carregar_parametros_custo(cliente)

    # Simula lagging (até SIOPS ser carregado)
    df_lagging = simular_lagging(df_acoes)

    # Módulo MSM simplificado
    iam_dict = calcular_iam(df_leading)

    # ICD
    icd_dict = calcular_icd(iam_dict, alpha=0.65)

    # Rede multiplex
    grafos = construir_rede_multiplex(df_acoes, df_lagging)

    # ICS
    ics_dict = calcular_ics(grafos, df_acoes)

    # PNA
    pna_dict = calcular_pna(df_acoes, df_parametros)

    # IPCSO-S
    df_result = calcular_ipcso(icd_dict, ics_dict, pna_dict, df_acoes, df_lagging)

    # Relatório
    exibir_relatorio(df_result)

    # Salvar
    salvar = input("\nSalvar resultados no Supabase? (s/n): ").strip().lower()
    if salvar == "s":
        salvar_resultados(cliente, df_result)
    else:
        print("[INFO] Resultados não salvos.")

    print("\n[CONCLUÍDO] Módulo 3 finalizado.")
