"""
Modulo 5 - Dashboard IPCSO-S
Projeto: Modelo Preditivo de Decisao Orcamentaria - Funcao Saude
Campo Largo/PR
"""

import os
import math
import warnings
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURACAO DA PAGINA
# ============================================================

st.set_page_config(
    page_title="IPCSO-S | Campo Largo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CREDENCIAIS - funciona tanto local (.env) quanto Streamlit Cloud (secrets)
# ============================================================

def get_credenciais():
    """
    Tenta carregar credenciais de duas fontes:
    1. st.secrets (Streamlit Cloud)
    2. variáveis de ambiente / .env (local)
    """
    try:
        # Streamlit Cloud
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return url, key
    except:
        pass
    try:
        # Local via .env
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if url and key:
            return url, key
    except:
        pass
    return None, None

# ============================================================
# CONEXAO COM SUPABASE
# ============================================================

@st.cache_resource
def conectar():
    from supabase import create_client
    url, key = get_credenciais()
    if not url or not key:
        st.error("❌ Credenciais do Supabase não encontradas.")
        st.info("Configure SUPABASE_URL e SUPABASE_KEY nas configurações do aplicativo.")
        st.stop()
    return create_client(url, key)

# ============================================================
# CARREGA DADOS
# ============================================================

@st.cache_data(ttl=300)
def carregar_dados_ambulatorial():
    cliente = conectar()
    r = cliente.table("sinais_leading_ambulatorial")\
        .select("*").order("subfuncao_id").order("periodo").execute()
    if not r.data:
        return pd.DataFrame()
    df = pd.DataFrame(r.data)
    df["periodo"] = pd.to_datetime(df["periodo"])
    return df

@st.cache_data(ttl=300)
def carregar_subfuncoes():
    cliente = conectar()
    r = cliente.table("subfuncoes").select("*").execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_acoes():
    cliente = conectar()
    r = cliente.table("acoes_orcamentarias").select("*").execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

# ============================================================
# CONSTANTES
# ============================================================

SUBFUNCOES = {
    1: "Atenção Básica",
    2: "Assist. Hosp. e Ambulatorial",
    3: "Suporte Profilático",
    4: "Vigilância Sanitária",
    5: "Vigilância Epidemiológica",
}

CORES = {
    1: "#2196F3", 2: "#4CAF50", 3: "#FF9800", 4: "#9C27B0", 5: "#F44336",
}

MODELOS = {
    "A": "Previne Brasil", "B": "Tabela SUS",
    "C": "Custo misto",   "D": "Repasse programa"
}

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("🏥 IPCSO-S")
    st.caption("Índice de Prioridade Composta para Suplementação Orçamentária da Saúde")
    st.divider()
    st.markdown("**Município:** Campo Largo/PR")
    st.markdown("**Programa:** PPGPGP/UTFPR")
    st.markdown("**Pesquisador:** Karl Horst Heinrichs")
    st.divider()
    pagina = st.radio(
        "Navegação",
        ["📊 Painel Geral", "📈 Séries Temporais", "🔴 Alertas MSM", "🗄️ Estrutura do Banco"]
    )

# ============================================================
# CARREGA DADOS
# ============================================================

df     = carregar_dados_ambulatorial()
df_sf  = carregar_subfuncoes()
df_ac  = carregar_acoes()

# ============================================================
# PAGINA 1 — PAINEL GERAL
# ============================================================

if pagina == "📊 Painel Geral":
    st.title("🏥 IPCSO-S — Painel de Monitoramento da Saúde Municipal")
    st.caption("Modelo Preditivo de Decisão Orçamentária | Campo Largo/PR | 2010–2024")
    st.divider()

    if df.empty:
        st.warning("Nenhum dado encontrado.")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Registros", f"{len(df):,}")
    with col2:
        st.metric("🔬 Subfunções", df["subfuncao_id"].nunique())
    with col3:
        st.metric("📅 Série", f"{df['periodo'].min().year}–{df['periodo'].max().year}")
    with col4:
        df_msm = df[df["regime_msm"].notna()]
        alertas = 0
        if not df_msm.empty:
            ult = df_msm["periodo"].max()
            alertas = int((df_msm[df_msm["periodo"]==ult]["regime_msm"] != "equilibrio").sum())
        st.metric("⚠️ Alertas", alertas, delta="Y1=1" if alertas>0 else "Y1=0",
                  delta_color="inverse" if alertas>0 else "normal")

    st.divider()
    st.subheader("📊 Produção Ambulatorial por Subfunção (2010–2024)")

    df_g = df.groupby(["periodo","subfuncao_id"])["total_procedimentos"].sum().reset_index()
    fig = go.Figure()
    for sf_id, sf_nome in SUBFUNCOES.items():
        d = df_g[df_g["subfuncao_id"]==sf_id]
        if not d.empty:
            fig.add_trace(go.Scatter(
                x=d["periodo"], y=d["total_procedimentos"],
                name=sf_nome, line=dict(color=CORES.get(sf_id,"#333"), width=2),
                hovertemplate=f"<b>{sf_nome}</b><br>%{{x|%b %Y}}<br>%{{y:,.0f}}<extra></extra>"
            ))
    fig.add_vrect(x0="2020-03-01", x1="2021-06-01",
                  fillcolor="red", opacity=0.08,
                  annotation_text="COVID-19", annotation_position="top left")
    fig.update_layout(height=450, xaxis_title="Período", yaxis_title="Procedimentos",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      hovermode="x unified", plot_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("💰 Subfunções — LOA 2024")
    if not df_sf.empty:
        d = df_sf[["codigo","nome","modelo_financiamento","valor_loa_2024"]].copy()
        d.columns = ["Código","Subfunção","Modelo","Valor LOA 2024"]
        d["Modelo"] = d["Modelo"].map(MODELOS)
        d["Valor LOA 2024"] = d["Valor LOA 2024"].apply(
            lambda x: f"R$ {float(x):,.2f}" if x else "-")
        st.dataframe(d, use_container_width=True, hide_index=True)

# ============================================================
# PAGINA 2 — SERIES TEMPORAIS
# ============================================================

elif pagina == "📈 Séries Temporais":
    st.title("📈 Análise de Séries Temporais de Demanda")
    st.divider()

    if df.empty:
        st.warning("Nenhum dado.")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        sf_sel = st.selectbox("Subfunção", list(SUBFUNCOES.keys()),
                              format_func=lambda x: SUBFUNCOES[x])
    with c2:
        anos = sorted(df["ano"].unique())
        ano_range = st.select_slider("Período", options=anos,
                                     value=(min(anos), max(anos)))

    dff = df[(df["subfuncao_id"]==sf_sel) &
             (df["ano"]>=ano_range[0]) & (df["ano"]<=ano_range[1])].copy()

    if dff.empty:
        st.warning("Sem dados.")
        st.stop()

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Média mensal", f"{dff['total_procedimentos'].mean():,.0f}")
    with c2: st.metric("Máximo", f"{dff['total_procedimentos'].max():,.0f}")
    with c3: st.metric("Mínimo", f"{dff['total_procedimentos'].min():,.0f}")

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=dff["periodo"], y=dff["total_procedimentos"],
        name="Procedimentos", line=dict(color=CORES.get(sf_sel,"#2196F3"), width=1.5), opacity=0.7))
    if "media_movel_6m" in dff.columns:
        fig2.add_trace(go.Scatter(x=dff["periodo"], y=dff["media_movel_6m"],
            name="Média móvel 6m", line=dict(color="#333", width=2.5, dash="dash")))
    fig2.add_vrect(x0="2020-03-01", x1="2021-06-01",
                   fillcolor="red", opacity=0.08, annotation_text="COVID-19")
    fig2.update_layout(title=f"Produção — {SUBFUNCOES[sf_sel]}", height=400,
                       plot_bgcolor="white", hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    if "variacao_mensal_pct" in dff.columns:
        st.subheader("Variação Mensal (%)")
        dv = dff[dff["variacao_mensal_pct"].notna()].copy()
        cores_bar = ["#dc3545" if v < 0 else "#28a745" for v in dv["variacao_mensal_pct"]]
        fig3 = go.Figure(go.Bar(x=dv["periodo"], y=dv["variacao_mensal_pct"],
                                marker_color=cores_bar))
        fig3.update_layout(height=250, plot_bgcolor="white", yaxis_title="%")
        st.plotly_chart(fig3, use_container_width=True)

# ============================================================
# PAGINA 3 — ALERTAS MSM
# ============================================================

elif pagina == "🔴 Alertas MSM":
    st.title("🔴 Alertas Markov-switching — IPCSO-S")
    st.caption("Probabilidades de regime | Treinamento: 2010–2020")
    st.divider()

    df_msm = df[df["regime_msm"].notna()].copy()
    if df_msm.empty:
        st.warning("Probabilidades MSM não calculadas ainda. Execute o Módulo 2.")
        st.stop()

    st.subheader("🚦 Semáforo por Subfunção")
    cols = st.columns(len(SUBFUNCOES))
    for idx, (sf_id, sf_nome) in enumerate(SUBFUNCOES.items()):
        d = df_msm[df_msm["subfuncao_id"]==sf_id]
        if d.empty: continue
        ult = d.sort_values("periodo").iloc[-1]
        regime = ult.get("regime_msm","equilibrio") or "equilibrio"
        prob_al  = float(ult.get("prob_alerta",  0) or 0)
        prob_col = float(ult.get("prob_colapso", 0) or 0)
        emoji = "🟢" if regime=="equilibrio" else ("🟡" if regime=="alerta" else "🔴")
        with cols[idx]:
            st.markdown(f"**{sf_nome}**")
            st.markdown(f"### {emoji} {regime.upper()}")
            st.caption(f"P(alerta): {prob_al:.2%}")
            st.caption(f"P(colapso): {prob_col:.2%}")

    st.divider()
    sf_sel2 = st.selectbox("Subfunção para análise detalhada",
                           list(SUBFUNCOES.keys()), format_func=lambda x: SUBFUNCOES[x])
    dp = df_msm[df_msm["subfuncao_id"]==sf_sel2].sort_values("periodo")

    if not dp.empty:
        fig_msm = go.Figure()
        fig_msm.add_trace(go.Scatter(x=dp["periodo"], y=dp["prob_equilibrio"],
            name="P(Equilíbrio)", stackgroup="one",
            line=dict(color="#28a745"), fillcolor="rgba(40,167,69,0.4)"))
        fig_msm.add_trace(go.Scatter(x=dp["periodo"], y=dp["prob_alerta"],
            name="P(Alerta)", stackgroup="one",
            line=dict(color="#ffc107"), fillcolor="rgba(255,193,7,0.4)"))
        fig_msm.add_trace(go.Scatter(x=dp["periodo"], y=dp["prob_colapso"],
            name="P(Colapso)", stackgroup="one",
            line=dict(color="#dc3545"), fillcolor="rgba(220,53,69,0.4)"))
        fig_msm.update_layout(
            title=f"Probabilidades de Regime — {SUBFUNCOES[sf_sel2]}",
            height=400, yaxis=dict(tickformat=".0%", range=[0,1]),
            plot_bgcolor="white", hovermode="x unified")
        st.plotly_chart(fig_msm, use_container_width=True)

        c1, c2 = st.columns([1,2])
        with c1:
            dist = dp["regime_msm"].value_counts()
            fig_pie = px.pie(values=dist.values, names=dist.index,
                color=dist.index,
                color_discrete_map={"equilibrio":"#28a745","alerta":"#ffc107","colapso":"#dc3545"},
                hole=0.4)
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            st.dataframe(
                dp[["periodo","regime_msm","prob_equilibrio","prob_alerta","prob_colapso"]]
                .tail(12).rename(columns={
                    "periodo":"Período","regime_msm":"Regime",
                    "prob_equilibrio":"P(Equil.)","prob_alerta":"P(Alerta)","prob_colapso":"P(Colapso)"}),
                use_container_width=True, hide_index=True)

# ============================================================
# PAGINA 4 — ESTRUTURA DO BANCO
# ============================================================

elif pagina == "🗄️ Estrutura do Banco":
    st.title("🗄️ Estrutura do Banco de Dados")
    st.caption("Supabase PostgreSQL — saude_campo_largo")
    st.divider()

    st.subheader("📋 Ações Orçamentárias — LOA 2024")
    if not df_ac.empty:
        d = df_ac[["codigo_acao","titulo","modelo_financiamento","valor_loa_2024"]].copy()
        d.columns = ["Ação","Título","Modelo","Valor LOA 2024"]
        d["Modelo"] = d["Modelo"].map(MODELOS)
        d["Valor LOA 2024"] = d["Valor LOA 2024"].apply(
            lambda x: f"R$ {float(x):,.2f}" if x else "-")
        st.dataframe(d, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📊 Tabelas do Banco de Dados")
    for tabela, desc in {
        "municipios":                   "Cadastro dos municípios do estudo",
        "subfuncoes":                   "8 subfunções da função saúde",
        "acoes_orcamentarias":          "16 ações orçamentárias LOA 2024",
        "sinais_leading_ambulatorial":  "Produção ambulatorial SIA-SUS (leading indicators)",
        "sinais_lagging_siops":         "Execução orçamentária SIOPS (Y1 e Y2)",
        "parametros_custo":             "Parâmetros MDS por modelo de financiamento",
        "parametros_institucionais_cvi":"Dados históricos para o CVI",
        "resultados_ipcso":             "Recomendações geradas pelo IPCSO-S",
    }.items():
        st.markdown(f"**`{tabela}`** — {desc}")
