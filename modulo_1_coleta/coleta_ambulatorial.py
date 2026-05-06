"""
Modulo 1 - Coleta e processamento de dados
Projeto: Modelo Preditivo de Decisao Orcamentaria - Funcao Saude
Municipio: Campo Largo/PR

Este modulo faz tres coisas:
1. Conecta ao Supabase
2. Baixa dados de producao ambulatorial do SIA-SUS (DATASUS)
3. Salva os dados na tabela sinais_leading_ambulatorial
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variaveis de ambiente do arquivo .env
load_dotenv()

# ============================================================
# CONFIGURACAO DA CONEXAO COM SUPABASE
# ============================================================

def conectar_supabase() -> Client:
    """
    Cria e retorna a conexao com o Supabase.
    As credenciais vem do arquivo .env - nunca hardcoded no codigo.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError(
            "Credenciais do Supabase nao encontradas. "
            "Verifique se o arquivo .env existe e tem SUPABASE_URL e SUPABASE_KEY."
        )

    cliente = create_client(url, key)
    print(f"Conectado ao Supabase: {url}")
    return cliente


# ============================================================
# MAPEAMENTO DE SUBFUNCOES
# Conecta os grupos de procedimentos do SIA-SUS as subfuncoes
# do projeto baseado na classificacao funcional
# ============================================================

MAPEAMENTO_GRUPOS_SUBFUNCAO = {
    # Atencao Basica (codigo subfuncao 301)
    "atencao_basica": {
        "subfuncao_codigo": "301",
        "grupos_sia": ["01", "02", "03", "04"],  # grupos AB no SIA-SUS
        "descricao": "Consultas, curativos, vacinas, visitas ACS"
    },
    # Media Complexidade (parte da subfuncao 302)
    "media_complexidade": {
        "subfuncao_codigo": "302",
        "grupos_sia": ["05", "06", "07", "08"],
        "descricao": "Consultas especializadas, exames, pequenas cirurgias"
    },
    # Urgencia e Emergencia (parte da subfuncao 302)
    "urgencia_emergencia": {
        "subfuncao_codigo": "302",
        "grupos_sia": ["03"],  # atendimentos de urgencia no SIA
        "descricao": "Atendimentos UPA e SAMU"
    },
    # Alta Complexidade (parte da subfuncao 302)
    "alta_complexidade": {
        "subfuncao_codigo": "302",
        "grupos_sia": ["09", "10", "11", "12"],
        "descricao": "Procedimentos de alta complexidade"
    },
}


# ============================================================
# DADOS SIMULADOS PARA DESENVOLVIMENTO
# Usados enquanto os dados reais do SIA-SUS nao estao disponiveis
# Serao substituidos pela funcao de download real no Ano 1
# ============================================================

def gerar_dados_simulados(
    ano_inicio: int = 2010,
    ano_fim: int = 2024,
    municipio_id: int = 1
) -> pd.DataFrame:
    """
    Gera dados simulados de producao ambulatorial para desenvolvimento.

    Os dados simulam:
    - Tendencia de crescimento de ~3% ao ano
    - Sazonalidade tipica da demanda em saude (pico no inverno)
    - Choque em 2020-2021 simulando a pandemia COVID-19
    - Ruido aleatorio realista

    Parametros:
        ano_inicio: primeiro ano da serie (default 2010)
        ano_fim:    ultimo ano da serie (default 2024)
        municipio_id: id do municipio no banco (default 1 = Campo Largo)

    Retorna:
        DataFrame com colunas prontas para inserir na tabela
        sinais_leading_ambulatorial
    """
    registros = []
    np.random.seed(42)  # reproducibilidade

    # Subfuncoes para simular
    subfuncoes = {
        1: {"nome": "Atencao Basica",       "base": 3500, "sazonal": 0.08},
        2: {"nome": "Assist. Hosp. e Amb.", "base": 1800, "sazonal": 0.12},
        3: {"nome": "Sup. Profilatico",     "base":  800, "sazonal": 0.05},
        4: {"nome": "Vig. Sanitaria",       "base":  200, "sazonal": 0.03},
        5: {"nome": "Vig. Epidemiologica",  "base":  300, "sazonal": 0.15},
    }

    for subfuncao_id, config in subfuncoes.items():
        base = config["base"]
        amp_sazonal = config["sazonal"]
        valor_acumulado = base

        for ano in range(ano_inicio, ano_fim + 1):
            for mes in range(1, 13):

                # Tendencia de crescimento anual de 3%
                tendencia = base * (1.03 ** (ano - ano_inicio))

                # Sazonalidade: pico em junho/julho (inverno)
                # usando seno para curva suave
                fase = (mes - 1) / 12 * 2 * np.pi
                sazonal = tendencia * amp_sazonal * np.sin(fase + np.pi / 2)

                # Choque COVID-19 em 2020 (queda) e 2021 (recuperacao)
                choque = 0
                if ano == 2020 and mes >= 3:
                    choque = -tendencia * 0.35  # queda de 35%
                elif ano == 2021 and mes <= 6:
                    choque = -tendencia * 0.15  # recuperacao gradual

                # Ruido aleatorio (+/- 5%)
                ruido = np.random.normal(0, tendencia * 0.05)

                # Total de procedimentos
                total = max(0, int(tendencia + sazonal + choque + ruido))

                # Distribuicao interna (consultas, exames, outros)
                consultas = int(total * 0.45)
                exames    = int(total * 0.35)
                outros    = total - consultas - exames

                periodo = date(ano, mes, 1)

                registros.append({
                    "municipio_id":      municipio_id,
                    "subfuncao_id":      subfuncao_id,
                    "periodo":           periodo.isoformat(),
                    "ano":               ano,
                    "mes":               mes,
                    "total_procedimentos": total,
                    "total_consultas":   consultas,
                    "total_exames":      exames,
                    "total_outros":      outros,
                    "fonte":             "SIMULADO - substituir por SIA-SUS real",
                })

    df = pd.DataFrame(registros)
    print(f"Dados simulados gerados: {len(df)} registros ({ano_inicio} a {ano_fim})")
    return df


def calcular_indicadores_derivados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula os indicadores derivados por Feature Engineering.

    Para cada subfuncao, calcula:
    - Variacao percentual mensal
    - Media movel de 3 e 6 meses
    - Desvio em relacao a media historica

    Parametros:
        df: DataFrame com os dados brutos de producao

    Retorna:
        DataFrame com colunas adicionais de indicadores derivados
    """
    df = df.copy()
    df["periodo"] = pd.to_datetime(df["periodo"])
    df = df.sort_values(["municipio_id", "subfuncao_id", "periodo"])

    resultados = []

    for (municipio_id, subfuncao_id), grupo in df.groupby(["municipio_id", "subfuncao_id"]):
        grupo = grupo.copy().reset_index(drop=True)

        # Variacao percentual mensal
        grupo["variacao_mensal_pct"] = (
            grupo["total_procedimentos"].pct_change() * 100
        ).round(4)

        # Medias moveis
        grupo["media_movel_3m"] = (
            grupo["total_procedimentos"].rolling(window=3, min_periods=1).mean()
        ).round(2)

        grupo["media_movel_6m"] = (
            grupo["total_procedimentos"].rolling(window=6, min_periods=1).mean()
        ).round(2)

        # Desvio em relacao a media historica
        media_historica = grupo["total_procedimentos"].mean()
        grupo["desvio_historico"] = (
            (grupo["total_procedimentos"] - media_historica) / media_historica * 100
        ).round(4)

        resultados.append(grupo)

    df_resultado = pd.concat(resultados, ignore_index=True)
    df_resultado["periodo"] = df_resultado["periodo"].dt.date.astype(str)

    print(f"Indicadores derivados calculados para {len(df_resultado)} registros")
    return df_resultado


# ============================================================
# FUNCOES DE BANCO DE DADOS
# ============================================================

def buscar_municipio_id(cliente: Client, codigo_ibge: str) -> int:
    """
    Busca o ID do municipio no banco pelo codigo IBGE.
    """
    resposta = (
        cliente.table("municipios")
        .select("id")
        .eq("codigo_ibge", codigo_ibge)
        .single()
        .execute()
    )

    if not resposta.data:
        raise ValueError(f"Municipio com codigo IBGE {codigo_ibge} nao encontrado no banco.")

    return resposta.data["id"]


def inserir_sinais_ambulatorial(
    cliente: Client,
    df: pd.DataFrame,
    substituir_existentes: bool = False
) -> dict:
    """
    Insere os sinais de producao ambulatorial no banco de dados.

    Usa upsert (insert or update) para evitar duplicatas.
    A combinacao (municipio_id, subfuncao_id, periodo) e unica.

    Parametros:
        cliente:              conexao com o Supabase
        df:                   DataFrame com os dados a inserir
        substituir_existentes: se True, atualiza registros existentes

    Retorna:
        dicionario com estatisticas da insercao
    """
    registros = df.to_dict("records")
    total = len(registros)
    inseridos = 0
    erros = 0

    # Insere em lotes de 100 para evitar timeout
    tamanho_lote = 100

    print(f"Inserindo {total} registros no banco...")

    for i in range(0, total, tamanho_lote):
        lote = registros[i:i + tamanho_lote]

        try:
            if substituir_existentes:
                resposta = (
                    cliente.table("sinais_leading_ambulatorial")
                    .upsert(lote, on_conflict="municipio_id,subfuncao_id,periodo")
                    .execute()
                )
            else:
                resposta = (
                    cliente.table("sinais_leading_ambulatorial")
                    .insert(lote)
                    .execute()
                )

            inseridos += len(lote)
            print(f"  Lote {i//tamanho_lote + 1}: {len(lote)} registros inseridos")

        except Exception as e:
            erros += len(lote)
            print(f"  ERRO no lote {i//tamanho_lote + 1}: {e}")

    resultado = {
        "total":    total,
        "inseridos": inseridos,
        "erros":    erros,
        "sucesso":  erros == 0
    }

    print(f"\nResultado: {inseridos} inseridos, {erros} erros")
    return resultado


def buscar_sinais_ambulatorial(
    cliente: Client,
    municipio_id: int,
    subfuncao_id: int = None,
    ano_inicio: int = 2010,
    ano_fim: int = 2024
) -> pd.DataFrame:
    """
    Busca os sinais de producao ambulatorial do banco.

    Parametros:
        cliente:      conexao com o Supabase
        municipio_id: ID do municipio
        subfuncao_id: ID da subfuncao (None = todas)
        ano_inicio:   primeiro ano da consulta
        ano_fim:      ultimo ano da consulta

    Retorna:
        DataFrame com os dados de producao ambulatorial
    """
    query = (
        cliente.table("sinais_leading_ambulatorial")
        .select("*")
        .eq("municipio_id", municipio_id)
        .gte("ano", ano_inicio)
        .lte("ano", ano_fim)
        .order("subfuncao_id")
        .order("periodo")
    )

    if subfuncao_id:
        query = query.eq("subfuncao_id", subfuncao_id)

    resposta = query.execute()

    if not resposta.data:
        print("Nenhum dado encontrado para os filtros informados.")
        return pd.DataFrame()

    df = pd.DataFrame(resposta.data)
    df["periodo"] = pd.to_datetime(df["periodo"])
    print(f"Dados recuperados: {len(df)} registros")
    return df


# ============================================================
# FUNCAO PRINCIPAL - executa o pipeline completo
# ============================================================

def executar_pipeline_coleta(
    usar_dados_simulados: bool = True,
    substituir_existentes: bool = True
) -> dict:
    """
    Executa o pipeline completo de coleta de dados.

    Passos:
    1. Conecta ao Supabase
    2. Gera ou baixa dados de producao ambulatorial
    3. Calcula indicadores derivados
    4. Insere no banco de dados

    Parametros:
        usar_dados_simulados: True = usa dados simulados (desenvolvimento)
                              False = baixa dados reais do SIA-SUS (producao)
        substituir_existentes: True = atualiza registros existentes

    Retorna:
        dicionario com resultado do pipeline
    """
    print("=" * 60)
    print("MODULO 1 - Coleta de Dados de Producao Ambulatorial")
    print("=" * 60)

    # Conecta ao banco
    cliente = conectar_supabase()

    # Busca ID do municipio
    codigo_ibge = os.getenv("MUNICIPIO_CODIGO_IBGE", "4104204")
    municipio_id = buscar_municipio_id(cliente, codigo_ibge)
    print(f"Municipio: {os.getenv('MUNICIPIO_NOME')} (ID: {municipio_id})")

    # Gera ou baixa os dados
    if usar_dados_simulados:
        print("\n[MODO DESENVOLVIMENTO] Usando dados simulados")
        print("Para usar dados reais: usar_dados_simulados=False")
        df = gerar_dados_simulados(municipio_id=municipio_id)
    else:
        print("\n[MODO PRODUCAO] Baixando dados reais do SIA-SUS/DATASUS")
        # TODO Ano 1: implementar download real do DATASUS
        # df = baixar_sia_sus(codigo_ibge, ano_inicio=2010, ano_fim=2024)
        raise NotImplementedError(
            "Download do SIA-SUS ainda nao implementado. "
            "Use usar_dados_simulados=True para desenvolvimento."
        )

    # Calcula indicadores derivados
    print("\nCalculando indicadores derivados...")
    df = calcular_indicadores_derivados(df)

    # Insere no banco
    print("\nInserindo dados no banco de dados...")
    resultado = inserir_sinais_ambulatorial(
        cliente, df,
        substituir_existentes=substituir_existentes
    )

    print("\n" + "=" * 60)
    print("Pipeline concluido!")
    print(f"Status: {'SUCESSO' if resultado['sucesso'] else 'COM ERROS'}")
    print("=" * 60)

    return resultado


# ============================================================
# EXECUCAO DIRETA
# ============================================================

if __name__ == "__main__":
    resultado = executar_pipeline_coleta(
        usar_dados_simulados=True,
        substituir_existentes=True
    )
