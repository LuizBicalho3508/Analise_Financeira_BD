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
from relatorios import gerar_pdf_analitico, gerar_excel_personalizado

# --- Configuração da Página ---
st.set_page_config(
    page_title="Brasil Digital - Financeiro", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Personalizado (Cores e Tema Light) ---
st.markdown("""
    <style>
        /* Forçar Tema Claro no Fundo */
        .stApp {
            background-color: #FFFFFF;
            color: #000000;
        }
        
        /* Sidebar Levemente Cinza */
        [data-testid="stSidebar"] {
            background-color: #F8F9FA;
        }

        /* Botões Padrão (Verde Brasil Digital) */
        div.stButton > button {
            background-color: #009639; /* Verde */
            color: white;
            border: none;
            border-radius: 5px;
            font-weight: bold;
        }
        div.stButton > button:hover {
            background-color: #007a2e;
            color: white;
            border-color: #007a2e;
        }
        
        /* Botões Primários (Azul Brasil Digital - Login, Salvar, Baixar) */
        div.stButton > button[kind="primary"] {
            background-color: #002776; /* Azul */
            color: white;
            border: none;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #001b52;
            color: white;
        }

        /* Estilo da caixa de exportação */
        .export-box {
            border: 2px solid #002776;
            padding: 20px;
            border-radius: 10px;
            background-color: #f0f8ff;
            margin-bottom: 25px;
        }

        /* Ajuste de Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #FFFFFF;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            background-color: #FFFFFF;
            border-bottom: 2px solid #009639;
            color: #009639;
        }
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
        
        st.markdown("<h3 style='text-align: center; color: #002776;'>Acesso Restrito</h3>", unsafe_allow_html=True)
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
# FUNÇÕES DE PROCESSAMENTO
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
    if 'Cargo' not in df_out.columns: df_out['Cargo'] = ''
    if 'Nome' not in df_out.columns: df_out['Nome'] = ''

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

abas_titulos = ["📈 Dashboard Analítico", "🔮 Cenários", "⚙️ Configuração de Áreas"]
if is_admin: abas_titulos.append("🔐 Administração")
abas = st.tabs(abas_titulos)

# ==============================================================================
# ABA 1: DASHBOARD
# ==============================================================================
with abas[0]:
    modo_uso = st.radio("Fonte de Dados:", ["🗄️ Consultar Banco de Dados", "📂 Fazer Upload (Novos Dados)"], horizontal=True)
    
    if modo_uso == "🗄️ Consultar Banco de Dados":
        with st.spinner("Conectando ao banco..."):
            opcoes_empresas, opcoes_competencias = carregar_filtros_mongo()
        c1, c2 = st.columns(2)
        filtro_empresa_db = c1.multiselect("Empresas", opcoes_empresas, default=opcoes_empresas)
        filtro_competencia_db = c2.multiselect("Competências", opcoes_competencias, default=[opcoes_competencias[-1]] if opcoes_competencias else [])
        if st.button("🔍 Buscar Dados", type="primary"): 
            if not filtro_empresa_db or not filtro_competencia_db:
                st.warning("Selecione Empresa e Competência.")
            else:
                with st.spinner("Buscando..."):
                    df_temp = carregar_dados_mongo(filtro_empresa_db, filtro_competencia_db)
                    if not df_temp.empty:
                        st.session_state['df_financeiro'] = df_temp
                        st.success(f"{len(df_temp)} registros carregados!")
                    else: st.warning("Nenhum dado encontrado.")
    else:
        uploaded_files = st.file_uploader("Carregar CSVs", type=["csv"], accept_multiple_files=True)
        if uploaded_files:
            dfs = []
            for file in uploaded_files: dfs.append(processar_csv_financeiro(file.getvalue(), file.name))
            if dfs:
                df_temp = pd.concat(dfs, ignore_index=True)
                if not df_temp.empty:
                    st.session_state['df_financeiro'] = df_temp
                    st.success(f"{len(df_temp)} processados.")
                    if st.button("💾 SALVAR NO BANCO", type="primary"): 
                        with st.spinner("Salvando..."):
                            total = salvar_dados_mongo(df_temp)
                        st.success(f"{total} salvos!")
                        carregar_filtros_mongo.clear()

    if 'df_financeiro' in st.session_state and not st.session_state['df_financeiro'].empty:
        mapa_cargos = carregar_mapa_cargos_mongo()
        mapa_excecoes = carregar_mapa_excecoes_mongo()
        df_full = aplicar_areas_otimizado(st.session_state['df_financeiro'], mapa_cargos, mapa_excecoes)
        st.session_state['df_com_areas'] = df_full

        st.divider()
        with st.expander("🔎 Filtros Locais", expanded=True):
            f1, f2, f3 = st.columns(3)
            areas_disp = sorted(df_full['Area'].unique())
            sel_areas = f1.multiselect("Filtrar Áreas", areas_disp, default=areas_disp)
            
            df_filtered = df_full[df_full['Area'].isin(sel_areas)] if sel_areas else df_full
            cargos_disp = sorted(df_filtered['Cargo'].unique())
            sel_cargos = f2.multiselect("Filtrar Cargos", cargos_disp, default=cargos_disp)
            
            eventos_disp = sorted(df_full['Tipo de Evento'].unique())
            sel_eventos = f3.multiselect("Filtrar Eventos", eventos_disp, default=eventos_disp)

        df = df_full.copy()
        if sel_areas: df = df[df['Area'].isin(sel_areas)]
        if sel_cargos: df = df[df['Cargo'].isin(sel_cargos)]
        if sel_eventos: df = df[df['Tipo de Evento'].isin(sel_eventos)]

        if not df.empty:
            # Métricas
            total_custo = df['Valor (R$)'].sum()
            total_horas = df['Horas Decimais'].sum()
            qtd_colab = df['ID Func'].nunique()
            media = total_custo / qtd_colab if qtd_colab else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("💰 Custo Total", f"R$ {total_custo:,.2f}")
            k2.metric("⏱️ Horas Totais", f"{total_horas:,.1f}")
            k3.metric("👥 Colaboradores", qtd_colab)
            k4.metric("📊 Ticket Médio", f"R$ {media:,.2f}")

            # --- PREPARAÇÃO DOS GRÁFICOS ---
            fig_area = px.bar(
                df.groupby('Area')['Valor (R$)'].sum().reset_index().sort_values('Valor (R$)'), 
                x='Valor (R$)', y='Area', orientation='h', title="Custo por Área",
                color_discrete_sequence=['#002776']
            )
            
            fig_emp = px.pie(
                df.groupby('Empresa')['Valor (R$)'].sum().reset_index(), 
                values='Valor (R$)', names='Empresa', title="Custo por Empresa",
                color_discrete_sequence=px.colors.sequential.Blues_r
            )

            df_line = df.groupby('Competência')['Valor (R$)'].sum().reset_index()
            try:
                df_line['Data_Ord'] = pd.to_datetime(df_line['Competência'], format='%m/%Y', errors='coerce')
                df_line = df_line.sort_values('Data_Ord')
            except: pass 
            
            fig_line = px.line(
                df_line, x='Competência', y='Valor (R$)', markers=True, 
                title="Evolução Mensal (Custo Total)",
                color_discrete_sequence=['#009639']
            )
            fig_line.update_layout(xaxis=dict(type='category'))

            # --- ÁREA DE EXPORTAÇÃO ---
            with st.container():
                st.markdown("<div class='export-box'>", unsafe_allow_html=True)
                st.markdown("### 📤 Central de Exportação")
                col_exp1, col_exp2 = st.columns(2)
                
                metrics_export = {
                    "Custo Total": f"R$ {total_custo:,.2f}",
                    "Horas Totais": f"{total_horas:,.1f}",
                    "Colaboradores": str(qtd_colab),
                    "Ticket Medio": f"R$ {media:,.2f}"
                }
                
                with col_exp1:
                    if st.button("📄 Baixar Relatório PDF (Analítico)", type="primary", use_container_width=True):
                        with st.spinner("Renderizando gráficos para PDF..."):
                            pdf_bytes = gerar_pdf_analitico(df, metrics_export, [fig_area, fig_emp, fig_line], user['name'])
                            st.download_button("⬇️ Clique para Download PDF", data=pdf_bytes, file_name="relatorio_financeiro.pdf", mime="application/pdf", key="pdf_down")
                
                with col_exp2:
                    if st.button("📊 Baixar Excel Completo (XLSX)", type="primary", use_container_width=True):
                        with st.spinner("Gerando Excel..."):
                            xls_bytes = gerar_excel_personalizado(df)
                            st.download_button("⬇️ Clique para Download Excel", data=xls_bytes, file_name="dados_financeiros.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="xls_down")
                st.markdown("</div>", unsafe_allow_html=True)

            st.divider()
            subtab1, subtab2, subtab3 = st.tabs(["Visão Geral", "Inteligência", "Detalhado"])
            
            with subtab1:
                c_viz1, c_viz2 = st.columns(2)
                c_viz1.plotly_chart(fig_area, use_container_width=True)
                c_viz2.plotly_chart(fig_emp, use_container_width=True)
                st.plotly_chart(fig_line, use_container_width=True)

            with subtab2:
                limite_horas = st.number_input("Alerta Horas >", value=100)
                outliers = df.groupby(['Nome', 'Empresa', 'Area'])['Horas Decimais'].sum().reset_index()
                outliers = outliers[outliers['Horas Decimais'] > limite_horas].sort_values('Horas Decimais', ascending=False)
                if not outliers.empty:
                    st.warning(f"{len(outliers)} pessoas acima do limite.")
                    st.dataframe(outliers, use_container_width=True)
                else: st.success("Tudo OK.")

            with subtab3:
                def cat_evento(e):
                    e = str(e).upper()
                    if "60%" in e: return "60%"
                    if "DSR" in e: return "DSR"
                    return "OUTROS"
                
                df_detalhe = df.copy()
                df_detalhe['Cat'] = df_detalhe['Tipo de Evento'].apply(cat_evento)
                
                pivot = df_detalhe.pivot_table(
                    index=['ID Func', 'Nome', 'Cargo'], columns='Cat', 
                    values=['Horas Decimais', 'Valor (R$)'], aggfunc='sum', fill_value=0
                )
                pivot.columns = [f'{c[0]}|{c[1]}' for c in pivot.columns]
                pivot = pivot.reset_index()
                
                cols_check = ['Horas Decimais|60%', 'Valor (R$)|60%', 'Horas Decimais|DSR', 'Valor (R$)|DSR']
                for c in cols_check:
                    if c not in pivot.columns: pivot[c] = 0.0
                
                cols_valor = [c for c in pivot.columns if 'Valor (R$)|' in c]
                pivot['Total Geral (R$)'] = pivot[cols_valor].sum(axis=1)
                
                pivot['Banco 60%'] = pivot['Horas Decimais|60%'].apply(formatar_horas_decimal_para_str)
                pivot['Horas DSR'] = pivot['Horas Decimais|DSR'].apply(formatar_horas_decimal_para_str)
                
                cols_final = ['ID Func', 'Nome', 'Cargo', 'Banco 60%', 'Valor (R$)|60%', 'Horas DSR', 'Valor (R$)|DSR', 'Total Geral (R$)']
                cols_final = [c for c in cols_final if c in pivot.columns]
                
                st.dataframe(pivot[cols_final].style.format({"Valor (R$)|60%": "R$ {:,.2f}", "Valor (R$)|DSR": "R$ {:,.2f}", "Total Geral (R$)": "R$ {:,.2f}"}), use_container_width=True, hide_index=True)

# ==============================================================================
# ABA 2: CENÁRIOS
# ==============================================================================
with abas[1]:
    st.header("🔮 Simulador")
    if 'df_com_areas' in st.session_state:
        df_base = st.session_state['df_com_areas'].copy()
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                areas = sorted(df_base['Area'].unique())
                target = st.multiselect("Áreas Alvo", areas, default=areas)
                th = st.number_input("Saldo > X horas:", value=40)
            with c2:
                pcash = st.slider("% Pagar", 0, 100, 50)
                mcash = st.number_input("Parcelas Pagamento", 1, 24, 3)
            with c3:
                pfolga = 100 - pcash
                st.info(f"% Folgar: {pfolga}%")
                mfolga = st.number_input("Meses Folga", 1, 24, 6)
        
        agg = df_base.groupby(['Nome', 'Empresa', 'Area']).agg({'Horas Decimais': 'sum', 'Valor (R$)': 'sum'}).reset_index()
        final = agg[(agg['Horas Decimais'] >= th) & (agg['Area'].isin(target))].copy()
        
        if not final.empty:
            final['Pagar'] = final['Valor (R$)'] * (pcash/100)
            final['Mensal'] = final['Pagar'] / mcash
            final['Dias'] = (final['Horas Decimais'] * (pfolga/100)) / 8
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Custo Total", f"R$ {final['Pagar'].sum():,.2f}")
            k2.metric("Mensalidade", f"R$ {final['Mensal'].sum():,.2f}")
            k3.metric("Dias Off", f"{final['Dias'].sum():,.1f}")
            
            st.dataframe(final.style.format({'Pagar': 'R$ {:,.2f}', 'Mensal': 'R$ {:,.2f}', 'Dias': '{:.1f}'}), use_container_width=True)
    else: st.info("Carregue dados no Dashboard primeiro.")

# ==============================================================================
# ABA 3: CONFIGURAÇÃO DE ÁREAS (Com filtro restaurado)
# ==============================================================================
with abas[2]:
    c1, c2 = st.columns(2)
    df_cur = st.session_state.get('df_financeiro', pd.DataFrame())
    
    # --- 1. CONFIGURAÇÃO POR CARGO ---
    with c1:
        st.subheader("1. Configuração por Cargos")
        mcargos = carregar_mapa_cargos_mongo()
        cexist = list(df_cur['Cargo'].unique()) if not df_cur.empty and 'Cargo' in df_cur.columns else []
        all_c = sorted(list(set(cexist) | set(mcargos.keys())))
        
        if all_c:
            edit = st.data_editor(
                pd.DataFrame([{"Cargo": c, "Area": mcargos.get(c, "")} for c in all_c]), 
                use_container_width=True, 
                hide_index=True
            )
            if st.button("💾 Salvar Regras de Cargos", type="primary"):
                salvar_mapa_cargos_mongo({r['Cargo']: r['Area'] for _, r in edit.iterrows() if r['Area']})
                st.success("Regras de Cargos atualizadas!")
                time.sleep(1)
                st.rerun()
        else:
            st.info("Nenhum cargo encontrado (carregue dados primeiro).")
    
    # --- 2. CONFIGURAÇÃO POR EXCEÇÃO (PESSOAS) COM FILTRO ---
    with c2:
        st.subheader("2. Exceções (Por Pessoa)")
        mexc = carregar_mapa_excecoes_mongo()
        
        if not df_cur.empty and 'Nome' in df_cur.columns and 'Cargo' in df_cur.columns:
            # Dropdown de Filtro de Cargos
            cargos_disponiveis = sorted(df_cur['Cargo'].unique())
            cargo_filtro = st.selectbox("Selecione um Cargo para filtrar:", ["Todos"] + cargos_disponiveis)
            
            # Pega lista única de pessoas
            df_pessoas = df_cur[['Nome', 'Cargo']].drop_duplicates().sort_values('Nome')
            
            # Aplica o filtro se não for "Todos"
            if cargo_filtro != "Todos":
                df_pessoas = df_pessoas[df_pessoas['Cargo'] == cargo_filtro]
            
            # Prepara os dados para o editor
            lista_pessoas = []
            for _, row in df_pessoas.iterrows():
                nome = row['Nome']
                lista_pessoas.append({
                    "Nome": nome, 
                    "Cargo": row['Cargo'], 
                    "Área (Exceção)": mexc.get(nome, "")
                })
                
            df_editor_pessoas = pd.DataFrame(lista_pessoas)
            
            edit_exc = st.data_editor(
                df_editor_pessoas, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Nome": st.column_config.TextColumn(disabled=True),
                    "Cargo": st.column_config.TextColumn(disabled=True)
                }
            )
            
            if st.button("💾 Salvar Exceções", type="primary"):
                # Cria uma cópia do mapa atual para não deletar quem ficou escondido no filtro
                mapa_final = mexc.copy()
                
                for _, r in edit_exc.iterrows():
                    nome_pessoa = r['Nome']
                    area_exc = r['Área (Exceção)']
                    
                    if area_exc and str(area_exc).strip() != "":
                        mapa_final[nome_pessoa] = area_exc
                    elif nome_pessoa in mapa_final:
                        del mapa_final[nome_pessoa] # Remove do banco se o usuário apagou no editor
                        
                salvar_mapa_excecoes_mongo(mapa_final)
                st.success("Exceções atualizadas com sucesso!")
                time.sleep(1)
                st.rerun()
        else: 
            st.info("Carregue dados no Dashboard para configurar exceções.")

# ==============================================================================
# ABA 4: ADMINISTRAÇÃO
# ==============================================================================
if is_admin:
    with abas[3]:
        st.header("🔐 Usuários")
        c_add, c_list = st.columns([1, 2])
        with c_add:
            with st.form("new_user"):
                nn = st.text_input("Nome")
                ne = st.text_input("Email")
                np = st.text_input("Senha", type="password")
                nr = st.selectbox("Cargo", ["usuario", "admin"])
                if st.form_submit_button("Criar", type="primary"):
                    if criar_usuario(nn, ne, np, nr): st.success("Criado!"); time.sleep(1); st.rerun()
                    else: st.error("Erro")
        
        with c_list:
            usrs = listar_todos_usuarios()
            for u in usrs:
                with st.expander(f"{u['name']} ({u['role']}) {'🟢' if u.get('active', True) else '🔴'}"):
                    ce1, ce2 = st.columns(2)
                    with ce1:
                        with st.form(f"ed_{u['email']}"):
                            en = st.text_input("Nome", u['name'])
                            er = st.selectbox("Cargo", ["usuario", "admin"], index=0 if u['role']=='usuario' else 1)
                            ep = st.text_input("Nova Senha", type="password")
                            if st.form_submit_button("Salvar", type="primary"):
                                atualizar_dados_usuario(u['email'], en, u['email'], er, ep)
                                st.success("OK!"); time.sleep(1); st.rerun()
                    with ce2:
                        act = u.get('active', True)
                        if u['email'] != user['email']:
                            if st.button("🚫 Desativar" if act else "✅ Ativar", key=f"btn_{u['email']}"):
                                atualizar_status_usuario(u['email'], not act)
                                st.rerun()
