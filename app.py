"""
IPCSO-S — Dashboard Principal v2
Com autenticação Supabase Auth + entrada de dados
"""

import os
import warnings
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from auth import (inicializar_sessao, tela_login, widget_usuario_sidebar,
                  requer_autenticacao)

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="IPCSO-S | Campo Largo",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa sessão
inicializar_sessao()

# Se não autenticado, mostra login
if not st.session_state.autenticado:
    tela_login()
    st.stop()

# ============================================================
# CREDENCIAIS
# ============================================================

def get_credenciais():
    try:
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except:
        pass
    try:
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if url and key:
            return url, key
    except:
        pass
    return None, None

@st.cache_resource
def conectar():
    from supabase import create_client
    url, key = get_credenciais()
    if not url or not key:
        st.error("❌ Credenciais não encontradas.")
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

@st.cache_data(ttl=300)
def carregar_resultados_ipcso():
    cliente = conectar()
    r = cliente.table("resultados_ipcso").select("*").order("ipcso_s", desc=True).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame()

# ============================================================
# CONSTANTES
# ============================================================

SUBFUNCOES = {
    1: "Atenção Básica", 2: "Assist. Hosp. e Ambulatorial",
    3: "Suporte Profilático", 4: "Vigilância Sanitária",
    5: "Vigilância Epidemiológica", 6: "Alimentação e Nutrição",
    7: "Gestão do SUS", 8: "Outras Ações",
}
CORES = {
    1: "#2196F3", 2: "#4CAF50", 3: "#FF9800", 4: "#9C27B0",
    5: "#F44336", 6: "#00BCD4", 7: "#795548", 8: "#607D8B",
}
MODELOS = {
    "A": "Previne Brasil", "B": "Tabela SUS",
    "C": "Custo misto",   "D": "Repasse programa"
}
COR_SEMAFORO   = {"vermelho": "#dc3545", "amarelo": "#ffc107", "verde": "#28a745"}
EMOJI_SEMAFORO = {"vermelho": "🔴", "amarelo": "🟡", "verde": "🟢"}

# ============================================================
# SIDEBAR
# ============================================================

perfil = st.session_state.perfil

with st.sidebar:
    st.title("🏥 IPCSO-S")
    st.caption("Índice de Prioridade Composta para Suplementação Orçamentária da Saúde")
    st.divider()
    st.markdown("**Município:** Campo Largo/PR")
    st.markdown("**Programa:** PPGPGP/UTFPR")
    st.markdown("**Pesquisador:** Karl Horst Heinrichs")
    st.divider()

    # Páginas disponíveis por perfil
    paginas_base = ["📊 Painel Geral", "📈 Séries Temporais",
                    "🔔 Alertas MSM", "🎯 IPCSO-S", "🗄️ Estrutura do Banco"]
    paginas_gestor = paginas_base + ["📥 Entrada de Dados"]
    paginas_admin  = paginas_gestor + ["👑 Administração"]

    if perfil == "admin":
        opcoes = paginas_admin
    elif perfil == "gestor":
        opcoes = paginas_gestor
    else:
        opcoes = paginas_base

    pagina = st.radio("Navegação", opcoes)
    widget_usuario_sidebar()

# ============================================================
# CARREGA DADOS
# ============================================================

df    = carregar_dados_ambulatorial()
df_sf = carregar_subfuncoes()
df_ac = carregar_acoes()

# ============================================================
# ROTEAMENTO DE PÁGINAS
# ============================================================

if pagina == "📥 Entrada de Dados":
    from paginas.pg_entrada import render
    render()

elif pagina == "👑 Administração":
    from paginas.pg_admin import render
    render()

elif pagina == "📊 Painel Geral":
    st.title("🏥 IPCSO-S — Painel de Monitoramento da Saúde Municipal")
    st.caption("Modelo Preditivo de Decisão Orçamentária | Campo Largo/PR | 2010–2024")
    st.divider()

    if df.empty:
        st.warning("Nenhum dado encontrado.")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("📋 Registros", f"{len(df):,}")
    with col2: st.metric("🔼 Subfunções", df["subfuncao_id"].nunique())
    with col3: st.metric("📅 Série", f"{df['periodo'].min().year}–{df['periodo'].max().year}")
    with col4:
        df_msm = df[df["regime_msm"].notna()]
        alertas = 0
        if not df_msm.empty:
            ult = df_msm["periodo"].max()
            alertas = int((df_msm[df_msm["periodo"]==ult]["regime_msm"] != "equilibrio").sum())
        st.metric("⚠️ Alertas", alertas, delta="Y1=1" if alertas > 0 else "Y1=0",
                  delta_color="inverse" if alertas > 0 else "normal")

    st.divider()
    st.subheader("📊 Produção Ambulatorial por Subfunção (2010–2024)")
    df_g = df.groupby(["periodo","subfuncao_id"])["total_procedimentos"].sum().reset_index()
    fig = go.Figure()
    for sf_id, sf_nome in SUBFUNCOES.items():
        d = df_g[df_g["subfuncao_id"]==sf_id]
        if not d.empty:
            fig.add_trace(go.Scatter(
                x=d["periodo"], y=d["total_procedimentos"], name=sf_nome,
                line=dict(color=CORES.get(sf_id,"#333"), width=2),
                hovertemplate=f"<b>{sf_nome}</b><br>%{{x|%b %Y}}<br>%{{y:,.0f}}<extra></extra>"
            ))
    fig.add_vrect(x0="2020-03-01", x1="2021-06-01", fillcolor="red", opacity=0.08,
                  annotation_text="COVID-19", annotation_position="top left")
    fig.update_layout(height=450, xaxis_title="Período", yaxis_title="Procedimentos",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02),
                      hovermode="x unified", plot_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    st.plotly_chart(fig, use_container_width=True)

elif pagina == "📈 Séries Temporais":
    st.title("📈 Análise de Séries Temporais de Demanda")
    st.divider()
    if df.empty:
        st.warning("Nenhum dado.")
        st.stop()

    c1, c2 = st.columns(2)
    with c1:
        sf_opcoes = {k: v for k, v in SUBFUNCOES.items() if k in df["subfuncao_id"].unique()}
        sf_sel = st.selectbox("Subfunção", list(sf_opcoes.keys()),
                              format_func=lambda x: sf_opcoes[x])
    with c2:
        anos = sorted(df["ano"].unique())
        ano_range = st.select_slider("Período", options=anos, value=(min(anos), max(anos)))

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
    fig2.update_layout(title=f"Produção — {SUBFUNCOES.get(sf_sel, sf_sel)}",
                       height=400, plot_bgcolor="white", hovermode="x unified")
    st.plotly_chart(fig2, use_container_width=True)

    if "variacao_mensal_pct" in dff.columns:
        st.subheader("Variação Mensal (%)")
        dv = dff[dff["variacao_mensal_pct"].notna()].copy()
        cores_bar = ["#dc3545" if v < 0 else "#28a745" for v in dv["variacao_mensal_pct"]]
        fig3 = go.Figure(go.Bar(x=dv["periodo"], y=dv["variacao_mensal_pct"],
                                marker_color=cores_bar))
        fig3.update_layout(height=250, plot_bgcolor="white", yaxis_title="%")
        st.plotly_chart(fig3, use_container_width=True)

elif pagina == "🔔 Alertas MSM":
    st.title("🔔 Alertas Markov-switching — IPCSO-S")
    st.caption("Probabilidades de regime | Treinamento: 2010–2020")
    st.divider()

    df_msm = df[df["regime_msm"].notna()].copy()
    if df_msm.empty:
        st.warning("Probabilidades MSM não calculadas ainda.")
        st.stop()

    st.subheader("🚦 Semáforo por Subfunção")
    sf_com_dados = [sf for sf in SUBFUNCOES if sf in df_msm["subfuncao_id"].unique()]
    cols = st.columns(len(sf_com_dados))
    for idx, sf_id in enumerate(sf_com_dados):
        d = df_msm[df_msm["subfuncao_id"]==sf_id]
        if d.empty: continue
        ult = d.sort_values("periodo").iloc[-1]
        regime   = ult.get("regime_msm","equilibrio") or "equilibrio"
        prob_al  = float(ult.get("prob_alerta",  0) or 0)
        prob_col = float(ult.get("prob_colapso", 0) or 0)
        emoji = "🟢" if regime=="equilibrio" else ("🟡" if regime=="alerta" else "🔴")
        with cols[idx]:
            st.markdown(f"**{SUBFUNCOES[sf_id]}**")
            st.markdown(f"### {emoji} {regime.upper()}")
            st.caption(f"P(alerta): {prob_al:.2%}")
            st.caption(f"P(colapso): {prob_col:.2%}")

    st.divider()
    sf_opcoes_msm = {k: v for k, v in SUBFUNCOES.items() if k in df_msm["subfuncao_id"].unique()}
    sf_sel2 = st.selectbox("Subfunção para análise detalhada",
                           list(sf_opcoes_msm.keys()), format_func=lambda x: sf_opcoes_msm[x])
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
            title=f"Probabilidades de Regime — {SUBFUNCOES.get(sf_sel2, sf_sel2)}",
            height=400, yaxis=dict(tickformat=".0%", range=[0,1]),
            plot_bgcolor="white", hovermode="x unified")
        st.plotly_chart(fig_msm, use_container_width=True)

elif pagina == "🎯 IPCSO-S":
    st.title("🎯 IPCSO-S — Recomendações de Suplementação Orçamentária")
    st.caption("Índice de Prioridade Composta | Campo Largo/PR")
    st.divider()

    df_ipcso = carregar_resultados_ipcso()
    if df_ipcso.empty:
        st.warning("Nenhum resultado encontrado. Execute o Módulo 3 primeiro.")
        st.stop()

    total   = len(df_ipcso)
    critico = len(df_ipcso[df_ipcso["semaforo_cvi"] == "vermelho"])
    alerta  = len(df_ipcso[df_ipcso["semaforo_cvi"] == "amarelo"])
    normal  = len(df_ipcso[df_ipcso["semaforo_cvi"] == "verde"])
    y2_total = df_ipcso["y2_estimado"].fillna(0).sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("📋 Subfunções", total)
    with c2: st.metric("🔴 Crítico",    critico)
    with c3: st.metric("🟡 Alerta",     alerta)
    with c4: st.metric("🟢 Normal",     normal)
    with c5: st.metric("💰 Y2 Total",   f"R$ {y2_total:,.2f}")

    st.divider()
    st.subheader("🚦 Semáforo IPCSO-S por Subfunção")
    cols = st.columns(min(total, 4))
    for idx, (_, row) in enumerate(df_ipcso.sort_values("ipcso_s", ascending=False).iterrows()):
        sf_id = int(row["subfuncao_id"])
        nome  = SUBFUNCOES.get(sf_id, f"Subfunção {sf_id}")
        sem   = str(row.get("semaforo_cvi", "verde")).lower()
        emoji = EMOJI_SEMAFORO.get(sem, "⚪")
        with cols[idx % 4]:
            st.markdown(f"**{nome}**")
            st.markdown(f"### {emoji} {sem.upper()}")
            st.metric("IPCSO-S", f"{float(row.get('ipcso_s',0)):.4f}")
            st.caption(f"Y1: {'⚠ ALERTA' if row.get('y1_previsto') else '✓ Normal'}")
            st.caption(f"Y2: R$ {float(row.get('y2_estimado',0)):,.2f}")
            st.divider()

    st.subheader("📊 Ranking IPCSO-S por Subfunção")
    df_plot = df_ipcso.copy()
    df_plot["nome"] = df_plot["subfuncao_id"].apply(lambda x: SUBFUNCOES.get(int(x), f"SF{x}"))
    df_plot["cor"]  = df_plot["semaforo_cvi"].map(COR_SEMAFORO).fillna("#607D8B")
    df_plot = df_plot.sort_values("ipcso_s", ascending=True)
    fig_bar = go.Figure(go.Bar(
        x=df_plot["ipcso_s"], y=df_plot["nome"], orientation="h",
        marker_color=df_plot["cor"],
        text=df_plot["ipcso_s"].apply(lambda x: f"{x:.4f}"),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>IPCSO-S: %{x:.4f}<extra></extra>"
    ))
    fig_bar.add_vline(x=0.70, line_dash="dash", line_color="#dc3545",
                      annotation_text="Limiar crítico (0.70)")
    fig_bar.add_vline(x=0.40, line_dash="dash", line_color="#ffc107",
                      annotation_text="Limiar alerta (0.40)")
    fig_bar.update_layout(height=400, plot_bgcolor="white",
                          xaxis=dict(range=[0,1.1], title="IPCSO-S"), yaxis_title="")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()
    st.subheader("🔬 Decomposição dos Componentes")
    componentes = ["iam","icd","ics","pna","ipcso_s"]
    cols_disp   = [c for c in componentes if c in df_ipcso.columns]
    df_comp = df_ipcso[["subfuncao_id"] + cols_disp].copy()
    df_comp["Subfunção"] = df_comp["subfuncao_id"].apply(
        lambda x: SUBFUNCOES.get(int(x), f"SF{x}"))
    df_comp = df_comp.drop(columns=["subfuncao_id"]).set_index("Subfunção")
    df_comp.columns = [c.upper() for c in df_comp.columns]
    fig_heat = px.imshow(df_comp.astype(float), color_continuous_scale="RdYlGn_r",
                         aspect="auto", text_auto=".3f", zmin=0, zmax=1)
    fig_heat.update_layout(height=350)
    st.plotly_chart(fig_heat, use_container_width=True)

elif pagina == "🗄️ Estrutura do Banco":
    st.title("🗄️ Estrutura do Banco de Dados")
    st.caption("Supabase PostgreSQL — saude_campo_largo")
    st.divider()

    st.subheader("📋 Ações Orçamentárias — LOA 2024")
    if not df_ac.empty:
        cols_disp = [c for c in ["codigo_acao","titulo","modelo_financiamento","valor_loa_2024"]
                     if c in df_ac.columns]
        d = df_ac[cols_disp].copy()
        if "modelo_financiamento" in d.columns:
            d["modelo_financiamento"] = d["modelo_financiamento"].map(MODELOS)
        if "valor_loa_2024" in d.columns:
            d["valor_loa_2024"] = d["valor_loa_2024"].apply(
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
        "perfis_usuarios":              "Gestores e administradores do sistema",
    }.items():
        st.markdown(f"**`{tabela}`** — {desc}")
