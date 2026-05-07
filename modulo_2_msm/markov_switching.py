"""
Modulo 2 - Markov-switching e deteccao de anomalias
Projeto: Modelo Preditivo de Decisao Orcamentaria - Funcao Saude
Campo Largo/PR
"""

import os, math, warnings
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import statsmodels.api as sm

warnings.filterwarnings('ignore')
load_dotenv()

LIMIAR_THETA = 0.30
SUBFUNCOES = {
    1: 'Atencao Basica',
    2: 'Assistencia Hospitalar e Ambulatorial',
    3: 'Suporte Profilatico e Terapeutico',
    4: 'Vigilancia Sanitaria',
    5: 'Vigilancia Epidemiologica',
}


def conectar_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("Credenciais nao encontradas no .env")
    return create_client(url, key)


def buscar_serie(cliente, municipio_id, subfuncao_id, ano_ini=2010, ano_fim=2020):
    r = (cliente.table("sinais_leading_ambulatorial")
         .select("periodo, total_procedimentos")
         .eq("municipio_id", municipio_id)
         .eq("subfuncao_id", subfuncao_id)
         .gte("ano", ano_ini).lte("ano", ano_fim)
         .order("periodo").execute())
    if not r.data:
        return pd.DataFrame()
    df = pd.DataFrame(r.data)
    df["periodo"] = pd.to_datetime(df["periodo"])
    return df.sort_values("periodo").reset_index(drop=True)


def inicializar_tercis(serie):
    q33, q67 = serie.quantile(0.33), serie.quantile(0.67)
    mu_eq  = float(serie[serie <= q33].median())
    mu_al  = float(serie[(serie > q33) & (serie <= q67)].median())
    mu_col = float(serie[serie > q67].median())
    print(f"    Tercis: eq={mu_eq:.0f} al={mu_al:.0f} col={mu_col:.0f}")
    return mu_eq, mu_al, mu_col


def estimar_msm(serie, nome):
    print(f"\n  MSM: {nome} ({len(serie)} meses)")

    media = float(serie.mean())
    std   = float(serie.std())
    if std == 0:
        print("  Serie constante - pulando")
        return {"convergiu": False}

    serie_norm = ((serie - media) / std).values
    inicializar_tercis(serie)

    modelo = sm.tsa.MarkovRegression(
        endog=serie_norm, k_regimes=3,
        trend='c', switching_variance=True
    )

    try:
        res = modelo.fit(em_iter=200, search_reps=10, disp=False)
        print(f"    Convergiu: llf={res.llf:.2f}")
    except Exception as e:
        print(f"    Erro na estimacao: {e}")
        return {"convergiu": False}

    # Extrai medias dos regimes via param_names
    # param_names: ['p[0->0]',..., 'const[0]', 'const[1]', 'const[2]', 'sigma2[0]',...]
    param_names = list(res.model.param_names)
    params_arr  = np.array(res.params)

    medias_norm = {}
    for i, name in enumerate(param_names):
        if name.startswith('const['):
            regime_idx = int(name.replace('const[','').replace(']',''))
            medias_norm[regime_idx] = float(params_arr[i])

    # Ordena regimes: 0=equilibrio(menor), 1=alerta, 2=colapso(maior)
    ordem = sorted(medias_norm.keys(), key=lambda k: medias_norm[k])
    col_eq  = ordem[0]   # indice do regime de equilibrio
    col_al  = ordem[1]   # indice do regime de alerta
    col_col = ordem[2]   # indice do regime de colapso

    # Probabilidades filtradas: numpy array (n_obs, 3)
    fmp = np.array(res.filtered_marginal_probabilities)

    prob_filtradas = pd.DataFrame({
        'prob_equilibrio': fmp[:, col_eq],
        'prob_alerta':     fmp[:, col_al],
        'prob_colapso':    fmp[:, col_col],
    })

    # Medias desnormalizadas
    medias = {
        'equilibrio': medias_norm[col_eq]  * std + media,
        'alerta':     medias_norm[col_al]  * std + media,
        'colapso':    medias_norm[col_col] * std + media,
    }

    # Matriz de transicao: (3,3,1) -> squeeze -> (3,3)
    # mt[i,j] = P(regime_i no t+1 | regime_j no t)
    mt = np.squeeze(np.array(res.regime_transition))
    iam = float(mt[col_col, col_al])  # P(colapso | alerta)

    print(f"    Medias: eq={medias['equilibrio']:.0f} al={medias['alerta']:.0f} col={medias['colapso']:.0f}")
    print(f"    IAM = P(colapso|alerta) = {iam:.4f}")
    print(f"    {'⚠️  ALERTA ATIVO' if iam >= LIMIAR_THETA else '✅ Sem alerta'}")

    return {
        "convergiu":      True,
        "prob_filtradas": prob_filtradas,
        "medias":         medias,
        "iam":            iam,
        "alerta":         iam >= LIMIAR_THETA,
    }


def limpar(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    except:
        return None


def salvar_banco(cliente, df_serie, prob_filtradas, municipio_id, subfuncao_id):
    n = 0
    for i, row in df_serie.iterrows():
        if i >= len(prob_filtradas):
            break
        periodo = row["periodo"].strftime("%Y-%m-%d")
        probs = prob_filtradas.iloc[i]
        regime = max(['equilibrio','alerta','colapso'],
                     key=lambda r: float(probs[f'prob_{r}']))
        try:
            cliente.table("sinais_leading_ambulatorial").update({
                "regime_msm":      regime,
                "prob_equilibrio": limpar(probs['prob_equilibrio']),
                "prob_alerta":     limpar(probs['prob_alerta']),
                "prob_colapso":    limpar(probs['prob_colapso']),
            }).eq("municipio_id", municipio_id)\
              .eq("subfuncao_id", subfuncao_id)\
              .eq("periodo", periodo).execute()
            n += 1
        except:
            pass
    return n


def executar_pipeline_msm(municipio_id=1, ano_ini=2010, ano_fim=2020, salvar=True):
    print("=" * 60)
    print("MODULO 2 - Markov-switching e Deteccao de Anomalias")
    print("=" * 60)
    print(f"Treinamento: {ano_ini} a {ano_fim} | theta={LIMIAR_THETA}")

    cliente = conectar_supabase()
    print("Conectado ao Supabase\n")

    resultados, alertas = {}, []

    for sf_id, sf_nome in SUBFUNCOES.items():
        print(f"{'='*40}")
        print(f"Subfuncao {sf_id}: {sf_nome}")

        df = buscar_serie(cliente, municipio_id, sf_id, ano_ini, ano_fim)
        if df.empty:
            print("  Sem dados")
            continue

        res = estimar_msm(df["total_procedimentos"], sf_nome)
        if not res.get("convergiu"):
            continue

        if res["alerta"]:
            alertas.append({"id": sf_id, "nome": sf_nome, "iam": res["iam"]})

        if salvar:
            n = salvar_banco(cliente, df, res["prob_filtradas"], municipio_id, sf_id)
            print(f"    {n} registros salvos")

        resultados[sf_id] = res

    print(f"\n{'='*60}")
    print("RELATORIO IPCSO-S")
    print(f"{'='*60}")
    if alertas:
        print(f"⚠️  {len(alertas)} subfuncao(oes) em ALERTA:")
        for a in alertas:
            print(f"  → {a['nome']}: IAM={a['iam']:.4f}")
        print(f"  Y1 previsto = 1 (suplementacao provavel)")
    else:
        print(f"✅  Sem alertas | Y1 previsto = 0")

    print(f"\nModulo 2 concluido! Subfuncoes: {len(resultados)} | Alertas: {len(alertas)}")
    return {"resultados": resultados, "alertas": alertas, "y1_previsto": len(alertas) > 0}


if __name__ == "__main__":
    executar_pipeline_msm(municipio_id=1, ano_ini=2010, ano_fim=2020, salvar=True)
