"""
IPCSO-S — Página de Entrada de Dados
Upload Excel + Formulário diário (perfil: gestor, admin)
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from auth import get_cliente, requer_autenticacao

SUBFUNCOES = {
    1: "Atenção Básica", 2: "Assist. Hosp. e Ambulatorial",
    3: "Suporte Profilático", 4: "Vigilância Sanitária",
    5: "Vigilância Epidemiológica", 6: "Alimentação e Nutrição",
    7: "Gestão do SUS", 8: "Outras Ações",
}

def render():
    if not requer_autenticacao(["admin", "gestor"]):
        st.warning("⛔ Acesso restrito a gestores.")
        return

    st.title("📥 Entrada de Dados")
    st.caption("Upload em lote (Excel) ou formulário de entrada diária")
    st.divider()

    aba = st.tabs(["📤 Upload Excel (SIOPS)", "📅 Formulário Diário", "📋 Histórico de Entradas"])

    # --------------------------------------------------------
    # ABA 1 — UPLOAD EXCEL
    # --------------------------------------------------------
    with aba[0]:
        st.subheader("📤 Upload de Execução Orçamentária — SIOPS")
        st.info("Utilize o template oficial IPCSO-S. Preencha as abas **Execucao_Mensal** e faça o upload.")

        arquivo = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])

        if arquivo:
            try:
                df_exec = pd.read_excel(arquivo, sheet_name="Execucao_Mensal",
                                        header=2, skiprows=[3,4])
                df_exec.columns = [
                    "acao_nome","codigo_acao","subfuncao_nome","ano","mes",
                    "dotacao_inicial","dotacao_atualizada","empenhado",
                    "liquidado","pago","houve_suplementacao","valor_suplementado",
                    "tipo_instrumento","fonte"
                ]
                # Remove linhas vazias
                df_exec = df_exec.dropna(subset=["ano","mes","liquidado"])
                df_exec = df_exec[df_exec["ano"].apply(lambda x: str(x).isdigit() if x else False)]

                st.success(f"✅ {len(df_exec)} registros encontrados no arquivo.")
                st.dataframe(df_exec.head(10), use_container_width=True, hide_index=True)

                if st.button("💾 Importar para o Supabase", type="primary"):
                    cliente = get_cliente()

                    # Busca mapa de ações
                    acoes_resp = cliente.table("acoes_orcamentarias").select("id,codigo_acao").execute()
                    mapa_acoes = {str(a["codigo_acao"]): a["id"] for a in (acoes_resp.data or [])}

                    registros = []
                    erros = []
                    for _, row in df_exec.iterrows():
                        cod = str(int(row["codigo_acao"])) if pd.notna(row["codigo_acao"]) else ""
                        acao_id = mapa_acoes.get(cod)
                        if not acao_id:
                            erros.append(f"Ação {cod} não encontrada")
                            continue

                        houve_sup = str(row.get("houve_suplementacao","")).strip().lower() in ["sim","s","yes","true"]
                        registros.append({
                            "municipio_id":       1,
                            "acao_id":            acao_id,
                            "periodo":            f"{int(row['ano'])}-{int(row['mes']):02d}-01",
                            "ano":                int(row["ano"]),
                            "mes":                int(row["mes"]),
                            "dotacao_inicial":    float(row.get("dotacao_inicial") or 0),
                            "dotacao_atualizada": float(row.get("dotacao_atualizada") or 0),
                            "empenhado":          float(row.get("empenhado") or 0),
                            "liquidado":          float(row.get("liquidado") or 0),
                            "pago":               float(row.get("pago") or 0),
                            "houve_suplementacao": houve_sup,
                            "valor_suplementado": float(row.get("valor_suplementado") or 0),
                            "tipo_instrumento":   str(row.get("tipo_instrumento") or ""),
                            "fonte":              str(row.get("fonte") or ""),
                            "pct_execucao":       float(row.get("liquidado") or 0) /
                                                  max(float(row.get("dotacao_inicial") or 1), 1),
                        })

                    if registros:
                        cliente.table("sinais_lagging_siops").insert(registros).execute()
                        st.success(f"✅ {len(registros)} registros importados com sucesso!")
                        if erros:
                            st.warning(f"⚠️ {len(erros)} registros ignorados: " + "; ".join(erros[:5]))
                    else:
                        st.error("Nenhum registro válido encontrado.")

            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")

    # --------------------------------------------------------
    # ABA 2 — FORMULÁRIO DIÁRIO
    # --------------------------------------------------------
    with aba[1]:
        st.subheader("📅 Registro Diário de Sinais de Demanda")

        usuario = st.session_state.usuario
        sf_usuario = usuario.get("subfuncao_id")

        with st.form("form_diario"):
            c1, c2 = st.columns(2)
            with c1:
                data_ref = st.date_input("Data de referência", value=date.today())
                if sf_usuario:
                    subfuncao_id = sf_usuario
                    st.info(f"Subfunção: **{SUBFUNCOES.get(sf_usuario)}**")
                else:
                    subfuncao_id = st.selectbox("Subfunção", list(SUBFUNCOES.keys()),
                                                format_func=lambda x: SUBFUNCOES[x])
            with c2:
                atendimentos = st.number_input("Atendimentos realizados", min_value=0, value=0)
                fila_espera  = st.number_input("Fila de espera", min_value=0, value=0)

            c1, c2, c3 = st.columns(3)
            with c1:
                procedimentos = st.number_input("Procedimentos", min_value=0, value=0)
                consultas     = st.number_input("Consultas", min_value=0, value=0)
            with c2:
                exames           = st.number_input("Exames", min_value=0, value=0)
                prof_ausentes    = st.number_input("Profissionais ausentes", min_value=0, value=0)
            with c3:
                insumos        = st.selectbox("Insumos disponíveis", ["Sim","Parcial","Não"])
                intercorrencias = st.text_area("Intercorrências", height=68,
                                               placeholder="Descreva brevemente...")

            submit = st.form_submit_button("💾 Registrar", type="primary")

        if submit:
            try:
                cliente = get_cliente()

                # Salva em sinais_leading_ambulatorial
                registro = {
                    "municipio_id":       1,
                    "subfuncao_id":       int(subfuncao_id),
                    "periodo":            data_ref.isoformat(),
                    "ano":                data_ref.year,
                    "mes":                data_ref.month,
                    "total_procedimentos": int(procedimentos),
                    "total_consultas":    int(consultas),
                    "total_exames":       int(exames),
                    "total_outros":       int(atendimentos),
                    "fonte":              f"formulario_diario|{usuario.get('nome','')}",
                }
                cliente.table("sinais_leading_ambulatorial").insert(registro).execute()
                st.success(f"✅ Registro do dia {data_ref.strftime('%d/%m/%Y')} salvo com sucesso!")

                if intercorrencias.strip():
                    st.info(f"📝 Intercorrência registrada: {intercorrencias}")

            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    # --------------------------------------------------------
    # ABA 3 — HISTÓRICO
    # --------------------------------------------------------
    with aba[2]:
        st.subheader("📋 Histórico de Entradas Recentes")

        try:
            cliente = get_cliente()
            resp = cliente.table("sinais_leading_ambulatorial")\
                .select("periodo,subfuncao_id,total_procedimentos,total_consultas,fonte")\
                .order("periodo", desc=True).limit(50).execute()

            if resp.data:
                df_hist = pd.DataFrame(resp.data)
                df_hist["subfuncao_id"] = df_hist["subfuncao_id"].map(SUBFUNCOES)
                df_hist = df_hist.rename(columns={
                    "periodo": "Período", "subfuncao_id": "Subfunção",
                    "total_procedimentos": "Procedimentos",
                    "total_consultas": "Consultas", "fonte": "Fonte"
                })
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro encontrado.")
        except Exception as e:
            st.error(f"Erro: {e}")
