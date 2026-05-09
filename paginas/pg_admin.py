"""
IPCSO-S — Página de Administração
Cadastro e gestão de usuários (perfil: admin)
"""

import streamlit as st
from auth import get_cliente, requer_autenticacao

def render():
    if not requer_autenticacao(["admin"]):
        st.warning("⛔ Acesso exclusivo para administradores.")
        return

    st.title("👑 Administração — Gestão de Usuários")
    st.caption("Cadastre e gerencie os gestores do sistema IPCSO-S")
    st.divider()

    cliente = get_cliente()

    st.subheader("➕ Cadastrar Novo Gestor")
    with st.form("form_novo_usuario"):
        c1, c2 = st.columns(2)
        with c1:
            nome  = st.text_input("Nome completo *")
            email = st.text_input("Email *")
        with c2:
            senha  = st.text_input("Senha inicial *", type="password")
            perfil = st.selectbox("Perfil *", ["gestor", "visualizador", "admin"])

        subfuncoes_map = {
            0: "Todas (sem restrição)", 1: "Atenção Básica",
            2: "Assist. Hosp. e Ambulatorial", 3: "Suporte Profilático",
            4: "Vigilância Sanitária", 5: "Vigilância Epidemiológica",
            6: "Alimentação e Nutrição", 7: "Gestão do SUS", 8: "Outras Ações",
        }
        sf_sel = st.selectbox("Subfunção (opcional)",
                              list(subfuncoes_map.keys()),
                              format_func=lambda x: subfuncoes_map[x])
        submit = st.form_submit_button("Cadastrar usuário", type="primary")

    if submit:
        if not nome or not email or not senha:
            st.error("Preencha todos os campos obrigatórios (*)")
        else:
            try:
                resp = cliente.auth.admin.create_user({
                    "email": email, "password": senha, "email_confirm": True
                })
                if resp.user:
                    cliente.table("perfis_usuarios").insert({
                        "id": resp.user.id, "nome": nome, "email": email,
                        "perfil": perfil,
                        "subfuncao_id": int(sf_sel) if sf_sel > 0 else None,
                        "ativo": True,
                    }).execute()
                    st.success(f"✅ Usuário **{nome}** cadastrado com sucesso!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

    st.divider()
    st.subheader("👥 Usuários Cadastrados")

    try:
        resp = cliente.table("perfis_usuarios").select("*").order("nome").execute()
        usuarios = resp.data or []
    except:
        usuarios = []

    if not usuarios:
        st.info("Nenhum usuário cadastrado além do admin.")
        return

    subfuncoes_map2 = {
        None: "Todas", 1: "At. Básica", 2: "Hosp.", 3: "Profilático",
        4: "Vig. San.", 5: "Vig. Epid.", 6: "Alimentação", 7: "Gestão", 8: "Outras"
    }
    emoji_perfil = {"admin": "👑", "gestor": "👤", "visualizador": "👁️"}

    for u in usuarios:
        with st.expander(f"{emoji_perfil.get(u['perfil'],'👤')} {u['nome']} — {u['email']}"):
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.caption(f"**Perfil:** {u['perfil'].capitalize()}")
            with c2: st.caption(f"**Subfunção:** {subfuncoes_map2.get(u.get('subfuncao_id'))}")
            with c3: st.caption(f"**Ativo:** {'✅' if u['ativo'] else '❌'}")
            with c4: st.caption(f"**Último acesso:** {str(u.get('ultimo_acesso','—'))[:10]}")

            c1, c2 = st.columns(2)
            with c1:
                label = "❌ Desativar" if u["ativo"] else "✅ Ativar"
                if st.button(label, key=f"toggle_{u['id']}"):
                    cliente.table("perfis_usuarios")\
                        .update({"ativo": not u["ativo"]}).eq("id", u["id"]).execute()
                    st.rerun()
            with c2:
                if u["perfil"] != "admin":
                    if st.button("🗑️ Remover", key=f"del_{u['id']}"):
                        try:
                            cliente.auth.admin.delete_user(u["id"])
                            cliente.table("perfis_usuarios").delete().eq("id", u["id"]).execute()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
