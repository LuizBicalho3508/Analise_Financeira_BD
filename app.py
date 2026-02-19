import streamlit as st
import pandas as pd
import io
import plotly.express as px
from db_utils import (
    verificar_login, 
    salvar_dados_mongo, 
    carregar_filtros_mongo, 
    carregar_dados_mongo,
    carregar_mapa_cargos_mongo,
    salvar_mapa_cargos_mongo,
    carregar_mapa_excecoes_mongo,
    salvar_mapa_excecoes_mongo,
    listar_todos_usuarios,
    criar_usuario,
    atualizar_status_usuario,
    atualizar_dados_usuario
)

# --- Configuração da Página ---
st.set_page_config(page_title="Brasil Digital - Financeiro", page_icon="📈", layout="wide")

# --- CSS Personalizado ---
st.markdown("""
    <style>
        [data-testid="stSidebar"] { background-color: #f0f2f6; }
        .stButton>button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- SESSÃO ---
if 'auth_status' not in st.session_state: st.session_state['auth_status'] = False
if 'user_info' not in st.session_state: st.session_state['user_info'] = {}

# ==============================================================================
# TELA DE LOGIN
# ==============================================================================
if not st.session_state['auth_status']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try: st.image("logo-brasil-digital.png", width=300)
        except: st.header("Brasil Digital")
        
        st.markdown("### Acesso Restrito")
        with st.form("login_form"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar", type="primary")
            
            if submit:
                if not st.secrets.get("MONGO_URI"):
                    st.error("ERRO: MONGO_URI não configurada.")
                else:
                    user_data = verificar_login(email, senha)
                    if user_data == "BLOQUEADO":
                        st.error("Este usuário foi desativado pelo administrador.")
                    elif user_data:
                        st.session_state['auth_status'] = True
                        st.session_state['user_info'] = user_data
                        st.rerun()
                    else:
                        st.error("E-mail ou senha incorretos.")
    st.stop()

# ==============================================================================
# ÁREA LOGADA
# ==============================================================================
user = st.session_state['user_info']
is_admin = user.get('role') == 'admin'

# Sidebar
with st.sidebar:
    try: st.image("logo-brasil-digital.png", use_container_width=True)
    except: st.write("**Brasil Digital**")
    
    st.write(f"👤 **{user['name']}**")
    st.caption(f"Cargo: {user['role'].upper()}")
    
    if st.button("Sair"):
        st.session_state['auth_status'] = False
        st.session_state['user_info'] = {}
        st.rerun()
    st.divider()

# Define abas dependendo da permissão
abas_titulos = ["📈 Dashboard Analítico", "🔮 Cenários", "⚙️ Áreas"]
if is_admin:
    abas_titulos.append("🔐 Administração")

abas = st.tabs(abas_titulos)

# --- ABA 1, 2 e 3 (FUNÇÕES EXISTENTES RESUMIDAS PARA ECONOMIZAR ESPAÇO AQUI) ---
# ... (Mantenha o código original das abas Dashboard, Cenários e Configuração de Áreas aqui) ...
# ...
# Vou colocar apenas a lógica da NOVA ABA DE ADMINISTRAÇÃO abaixo
# O restante do código das abas 1, 2 e 3 permanece idêntico ao anterior.

# --- FUNÇÕES AUXILIARES DE CSV (COPIAR DO ANTERIOR) ---
@st.cache_data
def converter_valor_monetario(v):
    try: return float(str(v).replace('.', '').replace(',', '.'))
    except: return 0.0

@st.cache_data
def converter_horas(h):
    try:
        parts = str(h).lower().replace('hs', '').strip().split(':')
        return int(parts[0]) + (int(parts[1])/60)
    except: return 0.0

@st.cache_data(show_spinner=False)
def processar_csv_financeiro(content, name):
    # ... (Copiar função processar_csv_financeiro do código anterior) ...
    # Para brevidade, assuma que esta função está aqui como no código anterior
    # Se precisar que eu repita ela inteira, me avise.
    try:
        decoded = content.decode("utf-8")
    except:
        decoded = content.decode("latin-1")
    stringio = io.StringIO(decoded)
    # Lógica simplificada de processamento para exemplo:
    return pd.DataFrame() # Substitua pelo código real

def aplicar_areas_otimizado(df, m_cargos, m_excecoes):
    if df.empty: return df
    df['Area'] = df['Cargo'].map(m_cargos)
    df['Area'] = df['Nome'].map(m_excecoes).combine_first(df['Area']).fillna('Não Definido')
    return df

# ==============================================================================
# PREENCHENDO AS ABAS ORIGINAIS (MÍNIMO NECESSÁRIO PARA RODAR)
# ==============================================================================
with abas[0]: # Dashboard
    st.info("Aqui vai o conteúdo do Dashboard (Código original)")
    # Cole aqui todo o conteúdo de 'with tab_dashboard:' do código anterior

with abas[1]: # Cenários
    st.info("Aqui vai o conteúdo de Cenários (Código original)")
    # Cole aqui todo o conteúdo de 'with tab_cenarios:' do código anterior

with abas[2]: # Configuração Áreas
    st.info("Aqui vai o conteúdo de Configuração de Áreas (Código original)")
    # Cole aqui todo o conteúdo de 'with tab_config:' do código anterior

# ==============================================================================
# ABA 4: ADMINISTRAÇÃO (NOVA)
# ==============================================================================
if is_admin:
    with abas[3]:
        st.header("🔐 Gestão de Usuários")
        
        col_add, col_list = st.columns([1, 2])
        
        # --- CRIAR NOVO USUÁRIO ---
        with col_add:
            with st.form("add_user_form"):
                st.subheader("Novo Usuário")
                new_name = st.text_input("Nome")
                new_email = st.text_input("E-mail")
                new_pass = st.text_input("Senha", type="password")
                new_role = st.selectbox("Cargo", ["usuario", "admin"])
                if st.form_submit_button("Criar Usuário"):
                    if len(new_pass) < 6:
                        st.error("Senha muito curta.")
                    else:
                        if criar_usuario(new_name, new_email, new_pass, new_role):
                            st.success(f"Usuário {new_name} criado!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Erro ao criar (E-mail já existe?).")

        # --- LISTAR E EDITAR USUÁRIOS ---
        with col_list:
            st.subheader("Usuários Existentes")
            users = listar_todos_usuarios()
            
            if users:
                df_users = pd.DataFrame(users)
                
                for index, row in df_users.iterrows():
                    with st.expander(f"{row['name']} ({row['role']}) {'🔴' if not row.get('active', True) else '🟢'}"):
                        c1, c2 = st.columns(2)
                        
                        # Edição
                        with c1:
                            with st.form(f"edit_{index}"):
                                ed_nome = st.text_input("Nome", row['name'])
                                ed_role = st.selectbox("Cargo", ["usuario", "admin"], index=0 if row['role']=="usuario" else 1)
                                ed_pass = st.text_input("Nova Senha (deixe vazio para manter)", type="password")
                                
                                if st.form_submit_button("💾 Atualizar Dados"):
                                    atualizar_dados_usuario(row['email'], ed_nome, row['email'], ed_role, ed_pass)
                                    st.success("Atualizado!")
                                    time.sleep(1)
                                    st.rerun()
                        
                        # Status (Banir/Ativar)
                        with c2:
                            is_active = row.get('active', True)
                            st.write(f"Status: **{'Ativo' if is_active else 'Desativado'}**")
                            
                            if row['email'] == st.session_state['user_info']['email']:
                                st.warning("Você não pode desativar a si mesmo.")
                            else:
                                if is_active:
                                    if st.button(f"🚫 Desativar Usuário", key=f"ban_{index}"):
                                        atualizar_status_usuario(row['email'], False)
                                        st.rerun()
                                else:
                                    if st.button(f"✅ Reativar Usuário", key=f"unban_{index}"):
                                        atualizar_status_usuario(row['email'], True)
                                        st.rerun()
            else:
                st.info("Nenhum usuário encontrado.")
