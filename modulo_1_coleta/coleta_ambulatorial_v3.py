"""
Modulo 1 - Coleta e processamento de dados
Projeto: Modelo Preditivo de Decisao Orcamentaria - Funcao Saude
Municipio: Campo Largo/PR
"""

import os
import math
import pandas as pd
import numpy as np
from datetime import date
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def conectar_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Credenciais do Supabase nao encontradas. Verifique o arquivo .env")
    cliente = create_client(url, key)
    print(f"Conectado ao Supabase: {url}")
    return cliente


def gerar_dados_simulados(ano_inicio=2010, ano_fim=2024, municipio_id=1):
    registros = []
    np.random.seed(42)
    subfuncoes = {
        1: {"base": 3500, "sazonal": 0.08},
        2: {"base": 1800, "sazonal": 0.12},
        3: {"base":  800, "sazonal": 0.05},
        4: {"base":  200, "sazonal": 0.03},
        5: {"base":  300, "sazonal": 0.15},
    }
    for subfuncao_id, config in subfuncoes.items():
        base = config["base"]
        amp = config["sazonal"]
        for ano in range(ano_inicio, ano_fim + 1):
            for mes in range(1, 13):
                tendencia = base * (1.03 ** (ano - ano_inicio))
                fase = (mes - 1) / 12 * 2 * np.pi
                sazonal = tendencia * amp * np.sin(fase + np.pi / 2)
                choque = 0
                if ano == 2020 and mes >= 3:
                    choque = -tendencia * 0.35
                elif ano == 2021 and mes <= 6:
                    choque = -tendencia * 0.15
                ruido = np.random.normal(0, tendencia * 0.05)
                total = max(0, int(tendencia + sazonal + choque + ruido))
                consultas = int(total * 0.45)
                exames = int(total * 0.35)
                outros = total - consultas - exames
                registros.append({
                    "municipio_id": municipio_id,
                    "subfuncao_id": subfuncao_id,
                    "periodo": date(ano, mes, 1).isoformat(),
                    "ano": ano,
                    "mes": mes,
                    "total_procedimentos": total,
                    "total_consultas": consultas,
                    "total_exames": exames,
                    "total_outros": outros,
                    "fonte": "SIMULADO",
                })
    df = pd.DataFrame(registros)
    print(f"Dados simulados gerados: {len(df)} registros ({ano_inicio} a {ano_fim})")
    return df


def limpar_valor(v):
    """Converte NaN e Infinity para None (null no banco)"""
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def calcular_indicadores_derivados(df):
    df = df.copy()
    df["periodo"] = pd.to_datetime(df["periodo"])
    df = df.sort_values(["municipio_id", "subfuncao_id", "periodo"])
    resultados = []
    for (municipio_id, subfuncao_id), grupo in df.groupby(["municipio_id", "subfuncao_id"]):
        grupo = grupo.copy().reset_index(drop=True)
        grupo["variacao_mensal_pct"] = grupo["total_procedimentos"].pct_change() * 100
        grupo["media_movel_3m"] = grupo["total_procedimentos"].rolling(window=3, min_periods=1).mean()
        grupo["media_movel_6m"] = grupo["total_procedimentos"].rolling(window=6, min_periods=1).mean()
        media_historica = grupo["total_procedimentos"].mean()
        grupo["desvio_historico"] = (grupo["total_procedimentos"] - media_historica) / media_historica * 100
        resultados.append(grupo)
    df_resultado = pd.concat(resultados, ignore_index=True)
    df_resultado["periodo"] = df_resultado["periodo"].dt.date.astype(str)
    print(f"Indicadores derivados calculados para {len(df_resultado)} registros")
    return df_resultado


def buscar_municipio_id(cliente, codigo_ibge):
    resposta = (
        cliente.table("municipios")
        .select("id")
        .eq("codigo_ibge", codigo_ibge)
        .single()
        .execute()
    )
    if not resposta.data:
        raise ValueError(f"Municipio {codigo_ibge} nao encontrado.")
    return resposta.data["id"]


def inserir_sinais_ambulatorial(cliente, df, substituir_existentes=False):
    # Converte para lista de dicts e limpa NaN/Infinity
    registros_brutos = df.to_dict("records")
    registros = [
        {k: limpar_valor(v) for k, v in r.items()}
        for r in registros_brutos
    ]

    total = len(registros)
    inseridos = 0
    erros = 0
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

    resultado = {"total": total, "inseridos": inseridos, "erros": erros, "sucesso": erros == 0}
    print(f"\nResultado: {inseridos} inseridos, {erros} erros")
    return resultado


def executar_pipeline_coleta(usar_dados_simulados=True, substituir_existentes=True):
    print("=" * 60)
    print("MODULO 1 - Coleta de Dados de Producao Ambulatorial")
    print("=" * 60)

    cliente = conectar_supabase()
    codigo_ibge = os.getenv("MUNICIPIO_CODIGO_IBGE", "4104204")
    municipio_id = buscar_municipio_id(cliente, codigo_ibge)
    print(f"Municipio: {os.getenv('MUNICIPIO_NOME')} (ID: {municipio_id})")

    if usar_dados_simulados:
        print("\n[MODO DESENVOLVIMENTO] Usando dados simulados")
        df = gerar_dados_simulados(municipio_id=municipio_id)
    else:
        raise NotImplementedError("Download real do SIA-SUS sera implementado no Ano 1.")

    print("\nCalculando indicadores derivados...")
    df = calcular_indicadores_derivados(df)

    print("\nInserindo dados no banco de dados...")
    resultado = inserir_sinais_ambulatorial(cliente, df, substituir_existentes=substituir_existentes)

    print("\n" + "=" * 60)
    print("Pipeline concluido!")
    print(f"Status: {'SUCESSO' if resultado['sucesso'] else 'COM ERROS'}")
    print("=" * 60)
    return resultado


if __name__ == "__main__":
    resultado = executar_pipeline_coleta(
        usar_dados_simulados=True,
        substituir_existentes=True
    )
