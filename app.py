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
from dotenv import load_dotenv
from supabase import create_client

warnings.filterwarnings('ignore')
load_dotenv()

# ============================================================
# CONFIGURACAO DA PAGINA
# ============================================================

st.set_page_config(
    page_title="IPCSO-S | Campo Largo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card {
        background: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .alerta-verde  { color: #28a745; font-weight: bold; font-size: 20px; }
    .alerta-amarelo{ color: #ffc107; font-weight: bold; font-size: 20px; }
    .alerta-vermelho{color: #dc3545; font-weight: bold; font-size: 20px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CONEXAO COM SUPABASE
# ============================================================

@st.cache_resource
def conectar():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        st.error("Credenciais do Supabase nao encontradas. Verifique o arquivo .env")
        st.stop()
    return create_client(url, key)

# ============================================================
# CARREGA DADOS
# ============================================================

@st.cache_data(ttl=300)
def carregar_dados_ambulatorial():
    cliente = conectar()
    r = cliente.table("sinais_leading_ambulatorial")\
        .select("*")\
        .order("subfuncao_id")\
        .order("periodo")\
        .execute()
    if not r.data:
        return pd.DataFrame()
    df = pd.DataFrame(r.data)
    df["periodo"] = pd.to_datetime(df["periodo"])
    return df

@st.cache_data(ttl=300)
def carregar_subfuncoes():
    cliente = conectar()
    r = cliente.table("subfuncoes").select("*").execute()
    if not r.data:
        return pd.DataFrame()
    return pd.DataFrame(r.data)

@st.cache_data(ttl=300)
def carregar_acoes():
    cliente = conectar()
    r = cliente.table("acoes_orcamentarias").select("*").execute()
    if not r.data:
        return pd.DataFrame()
    return pd.DataFrame(r.data)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Bras%C3%A3o_de_Campo_Largo.png/200px-Bras%C3%A3o_de_Campo_Largo.png", width=80)
    st.title("IPCSO-S")
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

df = carregar_dados_ambulatorial()
df_sf = carregar_subfuncoes()
df_ac = carregar_acoes()

SUBFUNCOES = {
    1: "Atenção Básica",
    2: "Assist. Hosp. e Ambulatorial",
    3: "Suporte Profilático",
    4: "Vigilância Sanitária",
    5: "Vigilância Epidemiológica",
}

CORES = {
    1: "#2196F3",
    2: "#4CAF50",
    3: "#FF9800",
    4: "#9C27B0",
    5: "#F44336",
}

# ============================================================
# PAGINA 1 — PAINEL GERAL
# ============================================================

if pagina == "📊 Painel Geral":
    st.title("🏥 IPCSO-S — Painel de Monitoramento da Saúde Municipal")
    st.caption("Modelo Preditivo de Decisão Orçamentária | Campo Largo/PR | 2010–2024")
    st.divider()

    if df.empty:
        st.warning("Nenhum dado encontrado no banco de dados.")
        st.stop()

    # Metricas gerais
    col1, col2, col3, col4 = st.columns(4)

    total_registros = len(df)
    subfuncoes_monitoradas = df["subfuncao_id"].nunique()
    periodo_inicio = df["periodo"].min().strftime("%Y")
    periodo_fim    = df["periodo"].max().strftime("%Y")

    # Calcula alertas ativos (IAM >= 0.30)
    df_com_iam = df[df["prob_alerta"].notna() & df["prob_colapso"].notna()].copy()
    alertas_ativos = 0
    if not df_com_iam.empty:
        ultimo_periodo = df_com_iam["periodo"].max()
        df_ultimo = df_com_iam[df_com_iam["periodo"] == ultimo_periodo]
        for _, row in df_ultimo.iterrows():
            prob_al  = row.get("prob_alerta",  0) or 0
            prob_col = row.get("prob_colapso", 0) or 0
            iam = float(prob_al) * float(prob_col) if prob_al and prob_col else 0
            if iam >= 0.09:
                alertas_ativos += 1

    with col1:
        st.metric("📋 Registros no banco", f"{total_registros:,}")
    with col2:
        st.metric("🔬 Subfunções monitoradas", subfuncoes_monitoradas)
    with col3:
        st.metric("📅 Série histórica", f"{periodo_inicio}–{periodo_fim}")
    with col4:
        st.metric("⚠️ Alertas ativos", alertas_ativos,
                  delta="Y1=1" if alertas_ativos > 0 else "Y1=0",
                  delta_color="inverse" if alertas_ativos > 0 else "normal")

    st.divider()

    # Grafico de producao total por subfuncao
    st.subheader("📊 Produção Ambulatorial por Subfunção (2010–2024)")

    df_graf = df.groupby(["periodo", "subfuncao_id"])["total_procedimentos"].sum().reset_index()

    fig = go.Figure()
    for sf_id, sf_nome in SUBFUNCOES.items():
        df_sf_plot = df_graf[df_graf["subfuncao_id"] == sf_id]
        if not df_sf_plot.empty:
            fig.add_trace(go.Scatter(
                x=df_sf_plot["periodo"],
                y=df_sf_plot["total_procedimentos"],
                name=sf_nome,
                line=dict(color=CORES.get(sf_id, "#333"), width=2),
                hovertemplate=f"<b>{sf_nome}</b><br>%{{x|%b %Y}}<br>Procedimentos: %{{y:,.0f}}<extra></extra>"
            ))

    # Marca COVID-19
    fig.add_vrect(
        x0="2020-03-01", x1="2021-06-01",
        fillcolor="red", opacity=0.08,
        annotation_text="COVID-19", annotation_position="top left"
    )

    fig.update_layout(
        height=450,
        xaxis_title="Período",
        yaxis_title="Total de Procedimentos",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

    # Tabela de subfuncoes e LOA 2024
    st.divider()
    st.subheader("💰 Subfunções — LOA 2024")
    if not df_sf.empty:
        df_sf_display = df_sf[["codigo","nome","modelo_financiamento","valor_loa_2024"]].copy()
        df_sf_display.columns = ["Código","Subfunção","Modelo","Valor LOA 2024"]
        df_sf_display["Valor LOA 2024"] = df_sf_display["Valor LOA 2024"].apply(
            lambda x: f"R$ {float(x):,.2f}" if x else "-"
        )
        modelos = {"A":"Previne Brasil","B":"Tabela SUS","C":"Custo misto","D":"Repasse programa"}
        df_sf_display["Modelo"] = df_sf_display["Modelo"].map(modelos)
        st.dataframe(df_sf_display, use_container_width=True, hide_index=True)

# ============================================================
# PAGINA 2 — SERIES TEMPORAIS
# ============================================================

elif pagina == "📈 Séries Temporais":
    st.title("📈 Análise de Séries Temporais de Demanda")
    st.divider()

    if df.empty:
        st.warning("Nenhum dado encontrado.")
        st.stop()

    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        sf_selecionada = st.selectbox(
            "Subfunção",
            options=list(SUBFUNCOES.keys()),
            format_func=lambda x: SUBFUNCOES[x]
        )
    with col_sel2:
        anos = sorted(df["ano"].unique())
        ano_range = st.select_slider(
            "Período",
            options=anos,
            value=(min(anos), max(anos))
        )

    df_filtrado = df[
        (df["subfuncao_id"] == sf_selecionada) &
        (df["ano"] >= ano_range[0]) &
        (df["ano"] <= ano_range[1])
    ].copy()

    if df_filtrado.empty:
        st.warning("Sem dados para os filtros selecionados.")
        st.stop()

    # Metricas da subfuncao
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Média mensal", f"{df_filtrado['total_procedimentos'].mean():,.0f}")
    with c2:
        st.metric("Máximo", f"{df_filtrado['total_procedimentos'].max():,.0f}")
    with c3:
        st.metric("Mínimo", f"{df_filtrado['total_procedimentos'].min():,.0f}")

    # Grafico principal com media movel
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df_filtrado["periodo"],
        y=df_filtrado["total_procedimentos"],
        name="Procedimentos",
        line=dict(color=CORES.get(sf_selecionada,"#2196F3"), width=1.5),
        opacity=0.7
    ))
    if "media_movel_6m" in df_filtrado.columns:
        fig2.add_trace(go.Scatter(
            x=df_filtrado["periodo"],
            y=df_filtrado["media_movel_6m"],
            name="Média móvel 6m",
            line=dict(color="#333", width=2.5, dash="dash")
        ))

    fig2.add_vrect(
        x0="2020-03-01", x1="2021-06-01",
        fillcolor="red", opacity=0.08,
        annotation_text="COVID-19"
    )

    fig2.update_layout(
        title=f"Produção — {SUBFUNCOES[sf_selecionada]}",
        height=400,
        xaxis_title="Período",
        yaxis_title="Procedimentos",
        plot_bgcolor="white",
        hovermode="x unified"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Variacao percentual mensal
    if "variacao_mensal_pct" in df_filtrado.columns:
        st.subheader("Variação Mensal (%)")
        df_var = df_filtrado[df_filtrado["variacao_mensal_pct"].notna()].copy()
        cores_bar = ["#dc3545" if v < 0 else "#28a745" for v in df_var["variacao_mensal_pct"]]
        fig3 = go.Figure(go.Bar(
            x=df_var["periodo"],
            y=df_var["variacao_mensal_pct"],
            marker_color=cores_bar,
            hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>"
        ))
        fig3.update_layout(height=250, plot_bgcolor="white", yaxis_title="%")
        st.plotly_chart(fig3, use_container_width=True)

# ============================================================
# PAGINA 3 — ALERTAS MSM
# ============================================================

elif pagina == "🔴 Alertas MSM":
    st.title("🔴 Alertas Markov-switching — IPCSO-S")
    st.caption("Probabilidades de regime por subfunção | Janela de treinamento: 2010–2020")
    st.divider()

    df_msm = df[df["regime_msm"].notna()].copy()

    if df_msm.empty:
        st.warning("Probabilidades MSM ainda não calculadas. Execute o Módulo 2 primeiro.")
        st.stop()

    # Semaforos por subfuncao
    st.subheader("🚦 Semáforo de Regime por Subfunção")

    cols = st.columns(len(SUBFUNCOES))
    for idx, (sf_id, sf_nome) in enumerate(SUBFUNCOES.items()):
        df_sf_msm = df_msm[df_msm["subfuncao_id"] == sf_id]
        if df_sf_msm.empty:
            continue
        ultimo = df_sf_msm.sort_values("periodo").iloc[-1]
        regime = ultimo.get("regime_msm", "equilibrio")
        prob_al  = float(ultimo.get("prob_alerta",  0) or 0)
        prob_col = float(ultimo.get("prob_colapso", 0) or 0)
        iam = prob_al * prob_col

        emoji = "🟢" if regime == "equilibrio" else ("🟡" if regime == "alerta" else "🔴")
        with cols[idx]:
            st.markdown(f"**{sf_nome}**")
            st.markdown(f"### {emoji} {regime.upper()}")
            st.caption(f"P(alerta): {prob_al:.2%}")
            st.caption(f"P(colapso): {prob_col:.2%}")

    st.divider()

    # Grafico de probabilidades por subfuncao
    sf_msm_sel = st.selectbox(
        "Subfunção para análise detalhada",
        options=list(SUBFUNCOES.keys()),
        format_func=lambda x: SUBFUNCOES[x],
        key="msm_sel"
    )

    df_plot_msm = df_msm[df_msm["subfuncao_id"] == sf_msm_sel].sort_values("periodo")

    if not df_plot_msm.empty:
        fig_msm = go.Figure()
        fig_msm.add_trace(go.Scatter(
            x=df_plot_msm["periodo"],
            y=df_plot_msm["prob_equilibrio"],
            name="P(Equilíbrio)",
            stackgroup="one",
            line=dict(color="#28a745"),
            fillcolor="rgba(40,167,69,0.4)"
        ))
        fig_msm.add_trace(go.Scatter(
            x=df_plot_msm["periodo"],
            y=df_plot_msm["prob_alerta"],
            name="P(Alerta)",
            stackgroup="one",
            line=dict(color="#ffc107"),
            fillcolor="rgba(255,193,7,0.4)"
        ))
        fig_msm.add_trace(go.Scatter(
            x=df_plot_msm["periodo"],
            y=df_plot_msm["prob_colapso"],
            name="P(Colapso)",
            stackgroup="one",
            line=dict(color="#dc3545"),
            fillcolor="rgba(220,53,69,0.4)"
        ))
        fig_msm.update_layout(
            title=f"Probabilidades de Regime — {SUBFUNCOES[sf_msm_sel]}",
            height=400,
            yaxis=dict(tickformat=".0%", range=[0,1]),
            xaxis_title="Período",
            yaxis_title="Probabilidade",
            plot_bgcolor="white",
            hovermode="x unified"
        )
        st.plotly_chart(fig_msm, use_container_width=True)

        # Distribuicao de regimes
        st.subheader("Distribuição de Regimes no Período")
        dist = df_plot_msm["regime_msm"].value_counts()
        fig_pie = px.pie(
            values=dist.values,
            names=dist.index,
            color=dist.index,
            color_discrete_map={
                "equilibrio": "#28a745",
                "alerta":     "#ffc107",
                "colapso":    "#dc3545"
            },
            hole=0.4
        )
        fig_pie.update_layout(height=300)
        col_p1, col_p2 = st.columns([1,2])
        with col_p1:
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_p2:
            st.dataframe(
                df_plot_msm[["periodo","regime_msm","prob_equilibrio","prob_alerta","prob_colapso"]]
                .tail(12)
                .rename(columns={
                    "periodo":"Período",
                    "regime_msm":"Regime",
                    "prob_equilibrio":"P(Equil.)",
                    "prob_alerta":"P(Alerta)",
                    "prob_colapso":"P(Colapso)"
                }),
                use_container_width=True,
                hide_index=True
            )

# ============================================================
# PAGINA 4 — ESTRUTURA DO BANCO
# ============================================================

elif pagina == "🗄️ Estrutura do Banco":
    st.title("🗄️ Estrutura do Banco de Dados")
    st.caption("Supabase PostgreSQL — saude_campo_largo")
    st.divider()

    st.subheader("📋 Ações Orçamentárias — LOA 2024")
    if not df_ac.empty:
        df_ac_display = df_ac[["codigo_acao","titulo","modelo_financiamento","valor_loa_2024"]].copy()
        df_ac_display.columns = ["Ação","Título","Modelo","Valor LOA 2024"]
        modelos = {"A":"Previne Brasil","B":"Tabela SUS","C":"Custo misto","D":"Repasse programa"}
        df_ac_display["Modelo"] = df_ac_display["Modelo"].map(modelos)
        df_ac_display["Valor LOA 2024"] = df_ac_display["Valor LOA 2024"].apply(
            lambda x: f"R$ {float(x):,.2f}" if x else "-"
        )
        st.dataframe(df_ac_display, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📊 Tabelas do Banco")
    tabelas = {
        "municipios":                   "Cadastro dos municípios do estudo",
        "subfuncoes":                   "8 subfunções da função saúde",
        "acoes_orcamentarias":          "16 ações orçamentárias LOA 2024",
        "sinais_leading_ambulatorial":  "Produção ambulatorial SIA-SUS (leading indicators)",
        "sinais_lagging_siops":         "Execução orçamentária SIOPS (Y1 e Y2)",
        "parametros_custo":             "Parâmetros MDS por modelo de financiamento",
        "parametros_institucionais_cvi":"Dados históricos para o CVI",
        "resultados_ipcso":             "Recomendações geradas pelo IPCSO-S",
    }
    for tabela, descricao in tabelas.items():
        st.markdown(f"**`{tabela}`** — {descricao}")

    st.divider()
    st.info(f"🔗 Supabase: `{os.getenv('SUPABASE_URL','não configurado')}`")
