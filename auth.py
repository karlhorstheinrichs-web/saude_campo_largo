"""
IPCSO-S — Módulo de Autenticação
Gerenciamento de sessão, login e controle de acesso
"""

import streamlit as st
from supabase import create_client
import os

def get_credenciais():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return url, key
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

def get_cliente(service=False):
    url, key = get_credenciais()
    if service:
        try:
            service_key = st.secrets["SUPABASE_SERVICE_KEY"]
        except:
            service_key = os.getenv("SUPABASE_SERVICE_KEY", key)
        return create_client(url, service_key)
    return create_client(url, key)

def inicializar_sessao():
    """Inicializa variáveis de sessão."""
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "usuario" not in st.session_state:
        st.session_state.usuario = None
    if "perfil" not in st.session_state:
        st.session_state.perfil = None
    if "access_token" not in st.session_state:
        st.session_state.access_token = None

def fazer_login(email, senha):
    """Autentica usuário via Supabase Auth."""
    try:
        cliente = get_cliente()
        resp = cliente.auth.sign_in_with_password({"email": email, "password": senha})
        
        if resp.user:
            # Busca perfil do usuário
            perfil_resp = cliente.table("perfis_usuarios")\
                .select("*").eq("id", resp.user.id).single().execute()
            
            if perfil_resp.data and perfil_resp.data.get("ativo"):
                st.session_state.autenticado = True
                st.session_state.usuario = perfil_resp.data
                st.session_state.perfil = perfil_resp.data.get("perfil")
                st.session_state.access_token = resp.session.access_token
                
                # Registra último acesso
                cliente.table("perfis_usuarios")\
                    .update({"ultimo_acesso": "now()"})\
                    .eq("id", resp.user.id).execute()
                return True, "Login realizado com sucesso!"
            else:
                return False, "Usuário inativo ou sem perfil cadastrado."
        return False, "Email ou senha incorretos."
    except Exception as e:
        msg = str(e)
        if "Invalid login" in msg:
            return False, "Email ou senha incorretos."
        return False, f"Erro ao fazer login: {msg}"

def fazer_logout():
    """Encerra sessão."""
    try:
        get_cliente().auth.sign_out()
    except:
        pass
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.perfil = None
    st.session_state.access_token = None
    st.rerun()

def requer_autenticacao(perfis_permitidos=None):
    """
    Decorator de proteção de página.
    perfis_permitidos: lista ex. ['admin', 'gestor']
    Se None, qualquer usuário autenticado pode acessar.
    """
    inicializar_sessao()
    if not st.session_state.autenticado:
        return False
    if perfis_permitidos and st.session_state.perfil not in perfis_permitidos:
        st.error("⛔ Acesso negado. Você não tem permissão para esta página.")
        return False
    return True

def tela_login():
    """Renderiza tela de login."""
    inicializar_sessao()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        # Logo/título
        st.markdown("""
        <div style='text-align:center; padding: 2rem; background: linear-gradient(135deg, #1F4E79, #2E75B6);
                    border-radius: 12px; margin-bottom: 1.5rem;'>
            <h1 style='color:white; margin:0; font-size:2rem;'>🏥 IPCSO-S</h1>
            <p style='color:#D6E4F0; margin:0.5rem 0 0 0; font-size:0.95rem;'>
                Índice de Prioridade Composta para<br>Suplementação Orçamentária da Saúde
            </p>
            <p style='color:#A8D4F5; margin:0.5rem 0 0 0; font-size:0.8rem;'>
                Campo Largo/PR | PPGPGP/UTFPR
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("form_login"):
            st.markdown("#### 🔐 Acesso ao Sistema")
            email = st.text_input("Email", placeholder="seu@email.com")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if submit:
            if not email or not senha:
                st.error("Preencha email e senha.")
            else:
                with st.spinner("Autenticando..."):
                    ok, msg = fazer_login(email, senha)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("🔒 Acesso restrito a gestores autorizados. "
                   "Em caso de dúvidas, contate o administrador do sistema.")

def widget_usuario_sidebar():
    """Exibe info do usuário e botão logout na sidebar."""
    if st.session_state.get("autenticado"):
        usuario = st.session_state.usuario
        perfil  = st.session_state.perfil
        nome    = usuario.get("nome", "Usuário")

        emoji_perfil = {"admin": "👑", "gestor": "👤", "visualizador": "👁️"}.get(perfil, "👤")

        st.sidebar.divider()
        st.sidebar.markdown(f"**{emoji_perfil} {nome}**")
        st.sidebar.caption(f"Perfil: {perfil.capitalize()}")
        if st.sidebar.button("🚪 Sair", use_container_width=True):
            fazer_logout()
