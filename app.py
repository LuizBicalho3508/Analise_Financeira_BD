import streamlit as st
import pandas as pd
import io
import plotly.express as px
import time
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
if 'df_financeiro' not in st.session_state: st.session_state['df_financeiro'] = pd.DataFrame()

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
                    st.error("ERRO: MONGO_URI não configurada nos secrets.")
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
# FUNÇÕES DE PROCESSAMENTO E CALCULOS
# ==============================================================================
@st.cache_data
def converter_valor_monetario(valor_str):
    if pd.isna(valor_str): return 0.0
    try:
        limpo = str(valor_str).replace('.', '').replace(',', '.')
        return float(limpo)
    except: return 0.0

@st.cache_data
def converter_horas(hora_str):
    if pd.isna(hora_str): return 0.0
    try:
        limpo = str(hora_str).lower().replace('hs', '').strip()
        partes = limpo.split(':')
        return int(partes[0]) + (int(partes[1]) / 60)
    except: return 0.0

def formatar_horas_decimal_para_str(horas_decimal):
    try:
        horas = int(horas_decimal)
        minutos = int((horas_decimal - horas) * 60)
        return f"{horas:02d}:{minutos:02d}"
    except: return "00:00"

def extrair_metadados(linhas):
    empresa = "Empresa Desconhecida"
    competencia = "N/A"
    for linha in linhas[:20]:
        linha = linha.strip()
        if " - " in linha and ";" in linha and ("Pág:" in linha or "Pag:" in linha):
            partes = linha.split(';')
            if len(partes) > 0:
                raw_emp = partes[0].replace('"', '').strip()
                empresa = raw_emp.split(" - ", 1)[1] if " - " in raw_emp else raw_emp
        if "Período:" in linha:
            try: competencia = linha.split(':')[1].split('à')[0].replace('"', '').strip()
            except: pass
    return empresa, competencia

@st.cache_data(show_spinner=False)
def processar_csv_financeiro(file_content, file_name):
    try: decoded = file_content.decode("utf-8")
    except UnicodeDecodeError: decoded = file_content.decode("latin-1")
    
    stringio = io.StringIO(decoded)
    linhas = stringio.readlines()
    empresa_atual, competencia_atual = extrair_metadados(linhas)
    
    dados = []
    evento_atual = None
    
    for linha in linhas:
        linha_clean = linha.strip()
        if not linha_clean or linha_clean.startswith('_') or "Total" in linha_clean: continue
        
        if linha_clean.startswith('"Evento:') or linha_clean.startswith('Evento:'):
            evento_atual = linha_clean.replace('"Evento:', '').replace('Evento:', '').replace('"', '').strip()
            continue
            
        partes = linha_clean.split(';')
        if len(partes) >= 6 and partes[0].replace('"', '').strip().isdigit():
            try:
                cargo_nome = partes[-4].replace('"', '').strip()
                if cargo_nome.replace('.', '').isdigit(): cargo_nome = partes[2].replace('"', '').strip()

                dados.append({
                    'Empresa': empresa_atual,
                    'Competência': competencia_atual,
                    'ID Func': partes[0].replace('"', '').strip(),
                    'Nome': partes[1].replace('"', '').strip(),
                    'Cargo': cargo_nome,
                    'Referência Original': partes[-2].replace('"', '').strip(),
                    'Horas Decimais': converter_horas(partes[-2].replace('"', '').strip()),
                    'Valor (R$)': converter_valor_monetario(partes[-1].replace('"', '').strip()),
                    'Tipo de Evento': evento_atual,
                    'Arquivo': file_name
                })
            except: continue
    return pd.DataFrame(dados)

def aplicar_areas_otimizado(df, mapa_cargos, mapa_excecoes):
    if df.empty: return df
    df_out = df.copy()
    df_out['Area'] = df_out['Cargo'].map(mapa_cargos)
    excecoes_series = df_out['Nome'].map(mapa_excecoes)
    df_out['Area'] = excecoes_series.combine_first(df_out['Area'])
    df_out['Area'] = df_out['Area'].fillna('Não Definido')
    return df_out

# ==============================================================================
# ÁREA LOGADA
# ==============================================================================
user = st.session_state['user_info']
is_admin = user.get('role') == 'admin'

# --- Sidebar ---
with st.sidebar:
    try: st.image("logo-brasil-digital.png", use_container_width=True)
    except: st.header("Brasil Digital")
    
    st.write(f"👤 **{user['name']}**")
    st.caption(f"Cargo: {user['role'].upper()}")
    
    if st.button("Sair"):
        st.session_state['auth_status'] = False
        st.session_state['user_info'] = {}
        st.rerun()
    st.divider()

# --- Abas ---
abas_titulos = ["📈 Dashboard Analítico", "🔮 Cenários", "⚙️ Configuração de Áreas"]
if is_admin:
    abas_titulos.append("🔐 Administração")

abas = st.tabs(abas_titulos)

# ==============================================================================
# ABA 1: DASHBOARD
# ==============================================================================
with abas[0]:
    modo_uso = st.radio("Fonte de Dados:", ["🗄️ Consultar Banco de Dados", "📂 Fazer Upload (Novos Dados)"], horizontal=True)
    
    if modo_uso == "🗄️ Consultar Banco de Dados":
        with st.spinner("Conectando ao banco..."):
            opcoes_empresas, opcoes_competencias = carregar_filtros_mongo()
        
        c_filt1, c_filt2 = st.columns(2)
        filtro_empresa_db = c_filt1.multiselect("Empresas", opcoes_empresas, default=opcoes_empresas)
        filtro_competencia_db = c_filt2.multiselect("Competências", opcoes_competencias, default=[opcoes_competencias[-1]] if opcoes_competencias else [])

        if st.button("🔍 Buscar Dados"):
            if not filtro_empresa_db or not filtro_competencia_db:
                st.warning("Selecione Empresa e Competência.")
            else:
                with st.spinner("Buscando dados no MongoDB..."):
                    df_temp = carregar_dados_mongo(filtro_empresa_db, filtro_competencia_db)
                    if df_temp.empty:
                        st.warning("Nenhum dado encontrado.")
                    else:
                        st.session_state['df_financeiro'] = df_temp
                        st.success(f"{len(df_temp)} registros carregados!")
    else:
        uploaded_files = st.file_uploader("Carregar CSVs", type=["csv"], accept_multiple_files=True)
        if uploaded_files:
            dfs = []
            for file in uploaded_files:
                dfs.append(processar_csv_financeiro(file.getvalue(), file.name))
            if dfs:
                df_temp = pd.concat(dfs, ignore_index=True)
                if not df_temp.empty:
                    st.session_state['df_financeiro'] = df_temp
                    st.success(f"{len(df_temp)} processados.")
                    if st.button("💾 SALVAR NO BANCO DE DADOS", type="primary"):
                        with st.spinner("Salvando..."):
                            total = salvar_dados_mongo(df_temp)
                        st.success(f"{total} registros salvos/atualizados!")
                        carregar_filtros_mongo.clear()

    # Visualização
    if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
        mapa_cargos = carregar_mapa_cargos_mongo()
        mapa_excecoes = carregar_mapa_excecoes_mongo()
        df_full = aplicar_areas_otimizado(st.session_state['df_financeiro'], mapa_cargos, mapa_excecoes)
        st.session_state['df_com_areas'] = df_full

        st.divider()
        with st.expander("🔎 Refinar Visualização (Filtros Locais)", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            areas_disp = sorted(df_full['Area'].unique())
            sel_areas = f_col1.multiselect("Filtrar Áreas", areas_disp, default=areas_disp)
            
            df_area_filtered = df_full[df_full['Area'].isin(sel_areas)] if sel_areas else df_full
            cargos_disp = sorted(df_area_filtered['Cargo'].unique())
            sel_cargos = f_col2.multiselect("Filtrar Cargos", cargos_disp, default=cargos_disp)
            
            eventos_disp = sorted(df_full['Tipo de Evento'].unique())
            sel_eventos = f_col3.multiselect("Filtrar Eventos", eventos_disp, default=eventos_disp)

        df = df_full.copy()
        if sel_areas: df = df[df['Area'].isin(sel_areas)]
        if sel_cargos: df = df[df['Cargo'].isin(sel_cargos)]
        if sel_eventos: df = df[df['Tipo de Evento'].isin(sel_eventos)]

        if not df.empty:
            total_custo = df['Valor (R$)'].sum()
            total_horas = df['Horas Decimais'].sum()
            qtd_colab = df['ID Func'].nunique()
            media = total_custo / qtd_colab if qtd_colab else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}")
            k2.metric("⏱️ Horas Totais", f"{total_horas:,.1f}")
            k3.metric("👥 Colaboradores", qtd_colab)
            k4.metric("📊 Ticket Médio", f"R$ {media:,.2f}")

            subtab1, subtab2, subtab3 = st.tabs(["Visão Geral", "Inteligência", "Detalhado"])
            
            with subtab1:
                c_viz1, c_viz2 = st.columns(2)
                c_viz1.plotly_chart(px.bar(df.groupby('Area')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)'), x='Valor (R$)', y='Area', orientation='h', title="Custo por Área"), use_container_width=True)
                c_viz2.plotly_chart(px.pie(df.groupby('Empresa')['Valor (R$)'].sum().reset_index(), values='Valor (R$)', names='Empresa', title="Custo por Empresa"), use_container_width=True)

            with subtab2:
                limite_horas = st.number_input("Alerta Horas >", value=100)
                outliers = df.groupby(['Nome', 'Empresa', 'Area'])['Horas Decimais'].sum().reset_index()
                outliers = outliers[outliers['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
                if not outliers.empty:
                    st.warning(f"{len(outliers)} pessoas acima do limite.")
                    st.dataframe(outliers, use_container_width=True)
                else: st.success("Ninguém acima do limite.")

            with subtab3:
                st.dataframe(df, use_container_width=True)

# ==============================================================================
# ABA 2: CENÁRIOS
# ==============================================================================
with abas[1]:
    st.header("🔮 Simulador de Compensação")
    if 'df_com_areas' not in st.session_state:
        st.info("Carregue os dados no Dashboard primeiro.")
    else:
        df_base = st.session_state['df_com_areas'].copy()
        with st.container(border=True):
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                areas_sim = sorted(df_base['Area'].unique())
                area_target = st.multiselect("Áreas Alvo", areas_sim, default=areas_sim)
                threshold = st.number_input("Saldo > X horas:", value=40)
            with col_s2:
                perc_cash = st.slider("% Pagar em Dinheiro", 0, 100, 50)
                meses_cash = st.number_input("Parcelas Pagamento", 1, 24, 3)
            with col_s3:
                perc_folga = 100 - perc_cash
                st.info(f"% Compensar em Folgas: {perc_folga}%")
                meses_folga = st.number_input("Meses para Folgar", 1, 24, 6)

        df_agg = df_base.groupby(['Nome', 'Empresa', 'Area']).agg({'Horas Decimais': 'sum', 'Valor (R$)': 'sum'}).reset_index()
        df_target = df_agg[(df_agg['Horas Decimais'] >= threshold) & (df_agg['Area'].isin(area_target))].copy()

        if not df_target.empty:
            df_target['Pagar (R$)'] = df_target['Valor (R$)'] * (perc_cash/100)
            df_target['Mensal (R$)'] = df_target['Pagar (R$)'] / meses_cash
            df_target['Folgar (Dias)'] = (df_target['Horas Decimais'] * (perc_folga/100)) / 8
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Custo Total", f"R$ {df_target['Pagar (R$)'].sum():,.2f}")
            m2.metric("Mensalidade", f"R$ {df_target['Mensal (R$)'].sum():,.2f}")
            m3.metric("Dias Off Total", f"{df_target['Folgar (Dias)'].sum():,.1f}")
            
            st.dataframe(df_target.style.format({'Pagar (R$)': 'R$ {:,.2f}', 'Mensal (R$)': 'R$ {:,.2f}', 'Folgar (Dias)': '{:.1f}'}), use_container_width=True)

# ==============================================================================
# ABA 3: CONFIGURAÇÃO
# ==============================================================================
with abas[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Cargos")
        mapa_cargos = carregar_mapa_cargos_mongo()
        cargos = sorted(list(set(st.session_state.get('df_financeiro', pd.DataFrame()).get('Cargo', [])) | set(mapa_cargos.keys())))
        if cargos:
            df_cargos = pd.DataFrame([{"Cargo": c, "Area": mapa_cargos.get(c, "")} for c in cargos])
            edited = st.data_editor(df_cargos, use_container_width=True, hide_index=True)
            if st.button("Salvar Cargos"):
                novo_mapa = {row['Cargo']: row['Area'] for _, row in edited.iterrows() if row['Area']}
                salvar_mapa_cargos_mongo(novo_mapa)
                st.success("Salvo!")
    with c2:
        st.subheader("Exceções (Pessoas)")
        mapa_excecoes = carregar_mapa_excecoes_mongo()
        if 'df_financeiro' in st.session_state:
            nomes = sorted(st.session_state['df_financeiro']['Nome'].unique())
            df_exc = pd.DataFrame([{"Nome": n, "Area Excecao": mapa_excecoes.get(n, "")} for n in nomes])
            edited_exc = st.data_editor(df_exc, use_container_width=True, hide_index=True)
            if st.button("Salvar Exceções"):
                novo_mapa_exc = {row['Nome']: row['Area Excecao'] for _, row in edited_exc.iterrows() if row['Area Excecao']}
                salvar_mapa_excecoes_mongo(novo_mapa_exc)
                st.success("Salvo!")

# ==============================================================================
# ABA 4: ADMINISTRAÇÃO (Apenas Admin)
# ==============================================================================
if is_admin:
    with abas[3]:
        st.header("🔐 Gestão de Usuários")
        col_add, col_list = st.columns([1, 2])
        
        with col_add:
            with st.form("add_user_form"):
                st.subheader("Novo Usuário")
                new_name = st.text_input("Nome")
                new_email = st.text_input("E-mail")
                new_pass = st.text_input("Senha", type="password")
                new_role = st.selectbox("Cargo", ["usuario", "admin"])
                if st.form_submit_button("Criar Usuário"):
                    if len(new_pass) < 6: st.error("Senha curta (min 6).")
                    else:
                        if criar_usuario(new_name, new_email, new_pass, new_role):
                            st.success(f"Criado: {new_name}")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("Erro ao criar.")

        with col_list:
            st.subheader("Usuários Existentes")
            users = listar_todos_usuarios()
            if users:
                for user_row in users:
                    with st.expander(f"{user_row['name']} ({user_row['role']}) {'🔴' if not user_row.get('active', True) else '🟢'}"):
                        c_ed1, c_ed2 = st.columns(2)
                        with c_ed1:
                            with st.form(f"edit_{user_row['email']}"):
                                ed_nome = st.text_input("Nome", user_row['name'])
                                ed_role = st.selectbox("Cargo", ["usuario", "admin"], index=0 if user_row['role']=="usuario" else 1)
                                ed_pass = st.text_input("Nova Senha (vazio para manter)", type="password")
                                if st.form_submit_button("💾 Atualizar"):
                                    atualizar_dados_usuario(user_row['email'], ed_nome, user_row['email'], ed_role, ed_pass)
                                    st.success("Atualizado!")
                                    time.sleep(1)
                                    st.rerun()
                        with c_ed2:
                            is_active = user_row.get('active', True)
                            if user_row['email'] == st.session_state['user_info']['email']:
                                st.warning("Não pode desativar a si mesmo.")
                            elif is_active:
                                if st.button("🚫 Desativar", key=f"ban_{user_row['email']}"):
                                    atualizar_status_usuario(user_row['email'], False)
                                    st.rerun()
                            else:
                                if st.button("✅ Reativar", key=f"unban_{user_row['email']}"):
                                    atualizar_status_usuario(user_row['email'], True)
                                    st.rerun()
