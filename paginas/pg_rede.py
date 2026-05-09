"""
IPCSO-S — Página da Rede Multiplex de Grafos
Visualização interativa das 3 camadas: Subfunções, Ações, Execução
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx
from auth import get_cliente

SUBFUNCOES = {
    1: "Atenção Básica", 2: "Assist. Hosp.", 3: "Suporte Profilático",
    4: "Vig. Sanitária", 5: "Vig. Epidemiológica", 6: "Alimentação",
    7: "Gestão do SUS",  8: "Outras Ações",
}

COR_SEMAFORO = {
    "vermelho": "#dc3545", "amarelo": "#ffc107", "verde": "#28a745"
}

CONEXOES_FUNCIONAIS = [(1,3),(1,5),(1,6),(2,4),(3,4),(5,6),(7,8)]

def carregar_dados():
    cliente = get_cliente()
    acoes  = pd.DataFrame(cliente.table("acoes_orcamentarias").select("*").execute().data or [])
    ipcso  = pd.DataFrame(cliente.table("resultados_ipcso").select("*").execute().data or [])
    lagging = pd.DataFrame(cliente.table("sinais_lagging_siops").select("*").execute().data or [])
    return acoes, ipcso, lagging

def construir_grafo_subfuncoes(df_ipcso):
    """Camada L1 — nós = subfunções, arestas = relação funcional."""
    G = nx.Graph()
    for sf in SUBFUNCOES:
        row = df_ipcso[df_ipcso["subfuncao_id"] == sf]
        sem   = str(row["semaforo_cvi"].iloc[0]).lower() if not row.empty else "verde"
        ipcso = float(row["ipcso_s"].iloc[0]) if not row.empty else 0.0
        G.add_node(sf, nome=SUBFUNCOES[sf], semaforo=sem, ipcso=ipcso)
    for a, b in CONEXOES_FUNCIONAIS:
        if a in G.nodes and b in G.nodes:
            G.add_edge(a, b)
    return G

def construir_grafo_acoes(df_acoes, df_ipcso):
    """Camada L2 — nós = ações, arestas = mesma subfunção."""
    G = nx.Graph()
    for _, ac in df_acoes.iterrows():
        sf = int(ac["subfuncao_id"])
        row = df_ipcso[df_ipcso["subfuncao_id"] == sf]
        sem = str(row["semaforo_cvi"].iloc[0]).lower() if not row.empty else "verde"
        G.add_node(int(ac["id"]),
                   nome=str(ac.get("titulo",""))[:30],
                   codigo=str(ac.get("codigo_acao","")),
                   subfuncao=sf,
                   semaforo=sem)
    for sf in df_acoes["subfuncao_id"].unique():
        ids = df_acoes[df_acoes["subfuncao_id"]==sf]["id"].tolist()
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                G.add_edge(int(ids[i]), int(ids[j]), peso=0.8)
    return G

def construir_grafo_execucao(df_acoes, df_lagging, df_ipcso):
    """Camada L3 — arestas ponderadas por execução financeira."""
    G = nx.DiGraph()
    for _, ac in df_acoes.iterrows():
        sf = int(ac["subfuncao_id"])
        row = df_ipcso[df_ipcso["subfuncao_id"] == sf]
        ipcso = float(row["ipcso_s"].iloc[0]) if not row.empty else 0.0
        G.add_node(int(ac["id"]),
                   nome=str(ac.get("titulo",""))[:30],
                   subfuncao=sf,
                   ipcso=ipcso)

    if not df_lagging.empty and "acao_id" in df_lagging.columns:
        exec_por_acao = df_lagging.groupby("acao_id")["liquidado"].sum()
        total = exec_por_acao.sum() or 1
        for sf in df_acoes["subfuncao_id"].unique():
            ids_sf = df_acoes[df_acoes["subfuncao_id"]==sf]["id"].tolist()
            sf_dest = {1:3, 2:4, 5:6}.get(int(sf), int(sf))
            ids_dest = df_acoes[df_acoes["subfuncao_id"]==sf_dest]["id"].tolist()
            for ac_id in ids_sf:
                peso = float(exec_por_acao.get(ac_id, 0)) / total
                for dest in ids_dest[:1]:
                    if int(ac_id) != int(dest):
                        G.add_edge(int(ac_id), int(dest), peso=round(peso*100, 2))
    return G

def layout_circular(G, escala=2.0):
    pos = nx.circular_layout(G, scale=escala)
    return {n: (float(p[0]), float(p[1])) for n, p in pos.items()}

def layout_spring(G, escala=2.0, seed=42):
    pos = nx.spring_layout(G, scale=escala, seed=seed)
    return {n: (float(p[0]), float(p[1])) for n, p in pos.items()}

def plotar_grafo_l1(G):
    pos = layout_circular(G, escala=2.0)
    fig = go.Figure()

    # Arestas
    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color="#CCCCCC", width=1.5),
            hoverinfo="none", showlegend=False
        ))

    # Nós
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        sem   = data.get("semaforo","verde")
        ipcso = data.get("ipcso", 0)
        cor   = COR_SEMAFORO.get(sem, "#28a745")
        tamanho = 30 + ipcso * 40

        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=tamanho, color=cor,
                        line=dict(color="white", width=2)),
            text=data.get("nome",""),
            textposition="bottom center",
            textfont=dict(size=11, color="#1F4E79"),
            hovertemplate=f"<b>{data.get('nome','')}</b><br>"
                          f"IPCSO-S: {ipcso:.4f}<br>"
                          f"Semáforo: {sem.upper()}<extra></extra>",
            showlegend=False
        ))

    fig.update_layout(
        title="🔵 Camada L1 — Rede de Subfunções",
        height=500, plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

def plotar_grafo_l2(G):
    pos = layout_spring(G, escala=2.5)
    fig = go.Figure()

    # Arestas por subfunção (cor diferente por grupo)
    cores_sf = {1:"#2196F3",2:"#4CAF50",3:"#FF9800",4:"#9C27B0",
                5:"#F44336",6:"#00BCD4",7:"#795548",8:"#607D8B"}

    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        sf = G.nodes[u].get("subfuncao", 1)
        cor = cores_sf.get(sf, "#CCCCCC")
        fig.add_trace(go.Scatter(
            x=[x0,x1,None], y=[y0,y1,None], mode="lines",
            line=dict(color=cor, width=1.0), opacity=0.5,
            hoverinfo="none", showlegend=False
        ))

    # Nós agrupados por subfunção
    sf_plotados = set()
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        sf  = data.get("subfuncao", 1)
        sem = data.get("semaforo","verde")
        cor = COR_SEMAFORO.get(sem, "#28a745")
        nome_sf = SUBFUNCOES.get(sf, f"SF{sf}")
        legend = nome_sf not in sf_plotados
        sf_plotados.add(nome_sf)

        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=18, color=cor,
                        line=dict(color="white", width=1.5)),
            text=data.get("codigo",""),
            textposition="top center",
            textfont=dict(size=9),
            name=nome_sf if legend else "",
            hovertemplate=f"<b>{data.get('nome','')}</b><br>"
                          f"Código: {data.get('codigo','')}<br>"
                          f"Subfunção: {nome_sf}<br>"
                          f"Semáforo: {sem.upper()}<extra></extra>",
            showlegend=legend,
            legendgroup=nome_sf
        ))

    fig.update_layout(
        title="🟢 Camada L2 — Rede de Ações Orçamentárias",
        height=500, plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        legend=dict(orientation="v", x=1.01, y=1),
        margin=dict(l=20, r=150, t=50, b=20)
    )
    return fig

def plotar_grafo_l3(G):
    pos = layout_spring(G, escala=2.5, seed=99)
    fig = go.Figure()

    # Arestas com espessura proporcional ao peso
    pesos = [d.get("peso",0) for _,_,d in G.edges(data=True)]
    max_peso = max(pesos) if pesos else 1

    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]; x1, y1 = pos[v]
        peso = data.get("peso", 0)
        espessura = 1 + (peso / max(max_peso, 0.001)) * 6
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode="lines",
            line=dict(color="#2E75B6", width=espessura), opacity=0.6,
            hovertemplate=f"Fluxo: {peso:.2f}%<extra></extra>",
            showlegend=False
        ))

    # Nós com tamanho proporcional ao IPCSO-S
    for node, data in G.nodes(data=True):
        x, y = pos[node]
        ipcso    = data.get("ipcso", 0)
        tamanho  = 15 + ipcso * 35
        sf       = data.get("subfuncao", 1)
        nome_sf  = SUBFUNCOES.get(sf, f"SF{sf}")

        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers",
            marker=dict(size=tamanho, color="#2E75B6",
                        line=dict(color="white", width=2)),
            hovertemplate=f"<b>{data.get('nome','')}</b><br>"
                          f"Subfunção: {nome_sf}<br>"
                          f"IPCSO-S: {ipcso:.4f}<br>"
                          f"(tamanho ∝ IPCSO-S)<extra></extra>",
            showlegend=False
        ))

    fig.update_layout(
        title="🔷 Camada L3 — Fluxo de Execução Financeira (arestas ∝ liquidado)",
        height=500, plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

def metricas_rede(G1, G2, G3):
    """Calcula métricas de rede para exibição."""
    cd = nx.degree_centrality(G2)
    cb = nx.betweenness_centrality(G2, normalized=True)
    try:
        ce = nx.eigenvector_centrality(G2, max_iter=500)
    except:
        ce = {n: 0 for n in G2.nodes}

    # Agrega por subfunção
    acoes_por_sf = {}
    for node, data in G2.nodes(data=True):
        sf = data.get("subfuncao", 0)
        if sf not in acoes_por_sf:
            acoes_por_sf[sf] = []
        acoes_por_sf[sf].append(node)

    rows = []
    for sf, nos in sorted(acoes_por_sf.items()):
        rows.append({
            "Subfunção":    SUBFUNCOES.get(sf, f"SF{sf}"),
            "Nº Ações":     len(nos),
            "CD médio":     round(np.mean([cd.get(n,0) for n in nos]), 4),
            "CB médio":     round(np.mean([cb.get(n,0) for n in nos]), 4),
            "CE médio":     round(np.mean([ce.get(n,0) for n in nos]), 4),
        })
    return pd.DataFrame(rows)

def render():
    st.title("🕸️ Rede Multiplex — Estrutura do IPCSO-S")
    st.caption("Visualização interativa das 3 camadas da rede de grafos")
    st.divider()

    with st.spinner("Carregando dados e construindo grafos..."):
        try:
            df_acoes, df_ipcso, df_lagging = carregar_dados()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

        if df_acoes.empty or df_ipcso.empty:
            st.warning("Execute o Módulo 3 antes de visualizar a rede.")
            return

        G1 = construir_grafo_subfuncoes(df_ipcso)
        G2 = construir_grafo_acoes(df_acoes, df_ipcso)
        G3 = construir_grafo_execucao(df_acoes, df_lagging, df_ipcso)

    # Métricas gerais
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Subfunções (L1)", G1.number_of_nodes())
    with c2: st.metric("Ações (L2)", G2.number_of_nodes())
    with c3: st.metric("Arestas L2", G2.number_of_edges())
    with c4: st.metric("Fluxos L3", G3.number_of_edges())

    st.divider()

    # Seletor de camada
    camada = st.radio("Selecione a camada da rede multiplex:",
                      ["L1 — Subfunções", "L2 — Ações Orçamentárias",
                       "L3 — Fluxo Financeiro", "📊 Métricas de Centralidade"],
                      horizontal=True)

    st.divider()

    if camada == "L1 — Subfunções":
        st.markdown("""
        **Camada L1** representa as 8 subfunções da função saúde conectadas por relações
        funcionais (ex: Atenção Básica → Vigilância Epidemiológica).
        O **tamanho** do nó é proporcional ao IPCSO-S e a **cor** indica o semáforo.
        """)
        st.plotly_chart(plotar_grafo_l1(G1), use_container_width=True)

        st.subheader("Legenda de Semáforo")
        c1, c2, c3 = st.columns(3)
        with c1: st.error("🔴 VERMELHO — IPCSO-S ≥ 0.70 — Crítico")
        with c2: st.warning("🟡 AMARELO — 0.40 ≤ IPCSO-S < 0.70 — Alerta")
        with c3: st.success("🟢 VERDE — IPCSO-S < 0.40 — Normal")

    elif camada == "L2 — Ações Orçamentárias":
        st.markdown("""
        **Camada L2** representa as 16 ações orçamentárias LOA 2024.
        Ações da mesma subfunção são conectadas. A **cor** indica o semáforo da subfunção.
        """)
        st.plotly_chart(plotar_grafo_l2(G2), use_container_width=True)

    elif camada == "L3 — Fluxo Financeiro":
        st.markdown("""
        **Camada L3** representa o fluxo de execução financeira entre ações.
        A **espessura** da aresta é proporcional ao valor liquidado.
        O **tamanho** do nó é proporcional ao IPCSO-S da subfunção.
        """)
        if df_lagging.empty:
            st.info("ℹ️ Dados de execução financeira (SIOPS) ainda não carregados. "
                    "A rede L3 está sendo exibida com dados simulados do Módulo 3.")
        st.plotly_chart(plotar_grafo_l3(G3), use_container_width=True)

    elif camada == "📊 Métricas de Centralidade":
        st.markdown("""
        **Centralidades** calculadas sobre a Camada L2 (ações orçamentárias),
        agregadas por subfunção. Usadas no cálculo do **ICS**.
        - **CD** — Centralidade de Grau: conectividade da subfunção
        - **CB** — Betweenness: papel de intermediação na rede
        - **CE** — Eigenvector: influência global na rede
        """)
        df_met = metricas_rede(G1, G2, G3)
        st.dataframe(df_met, use_container_width=True, hide_index=True)

        # Gráfico de barras das centralidades
        fig_cent = go.Figure()
        for col, cor in [("CD médio","#2196F3"),("CB médio","#FF9800"),("CE médio","#9C27B0")]:
            fig_cent.add_trace(go.Bar(
                name=col, x=df_met["Subfunção"], y=df_met[col],
                marker_color=cor
            ))
        fig_cent.update_layout(
            barmode="group", height=350, plot_bgcolor="white",
            xaxis_tickangle=-30, yaxis_title="Centralidade",
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_cent, use_container_width=True)
