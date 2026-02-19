import streamlit as st
import pandas as pd
import pymongo
from pymongo import MongoClient, UpdateOne
import bcrypt
import certifi  # <--- NOVA IMPORTAÇÃO ESSENCIAL

# --- CONEXÃO COM MONGODB ---
@st.cache_resource
def init_connection():
    uri = st.secrets.get("MONGO_URI", "")
    if not uri: return None
    
    # CORREÇÃO DO ERRO DE SSL:
    # Adicionamos tlsCAFile=certifi.where() para garantir que o Streamlit
    # tenha os certificados de segurança corretos para falar com o Atlas.
    return MongoClient(uri, tlsCAFile=certifi.where())

def get_db():
    client = init_connection()
    if client: return client.get_database("financeiro_db")
    return None

# --- GESTÃO DE USUÁRIOS (CRUD COMPLETO) ---

def criar_usuario(nome, email, senha, cargo='usuario', ativo=True):
    db = get_db()
    if db is None: return False
    
    hashed = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
    
    try:
        db.users.update_one(
            {"email": email},
            {"$set": {
                "name": nome, 
                "password": hashed, 
                "email": email,
                "role": cargo,   # 'admin' ou 'usuario'
                "active": ativo
            }},
            upsert=True
        )
        return True
    except Exception as e:
        return False

def verificar_login(email, senha):
    db = get_db()
    if db is None: return None
    
    try:
        usuario = db.users.find_one({"email": email})
        
        if usuario:
            # Verifica se está ativo
            if not usuario.get('active', True):
                return "BLOQUEADO"
                
            if bcrypt.checkpw(senha.encode('utf-8'), usuario['password']):
                # Retorna um dicionário com os dados do usuário
                return {
                    "name": usuario['name'],
                    "role": usuario.get('role', 'usuario'),
                    "email": usuario['email']
                }
    except Exception:
        return None
    return None

def listar_todos_usuarios():
    db = get_db()
    if db is None: return []
    try:
        return list(db.users.find({}, {"password": 0, "_id": 0}))
    except: return []

def atualizar_status_usuario(email, novo_status_ativo):
    """Ativa ou Desativa um usuário"""
    db = get_db()
    if db is None: return
    try:
        db.users.update_one({"email": email}, {"$set": {"active": novo_status_ativo}})
    except: pass

def atualizar_dados_usuario(email_antigo, novo_nome, novo_email, novo_cargo, nova_senha=None):
    db = get_db()
    if db is None: return False
    
    dados_atualizar = {
        "name": novo_nome,
        "email": novo_email,
        "role": novo_cargo
    }
    
    if nova_senha and len(nova_senha.strip()) > 0:
        hashed = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt())
        dados_atualizar["password"] = hashed
    
    try:
        db.users.update_one({"email": email_antigo}, {"$set": dados_atualizar})
        return True
    except: return False

# --- FUNÇÕES FINANCEIRAS ---

def salvar_dados_mongo(df):
    db = get_db()
    if db is None: return 0
    collection = db.folha_eventos
    operations = []
    for _, row in df.iterrows():
        comp_safe = str(row['Competência']).replace('/', '-')
        evento_safe = "".join(c for c in str(row['Tipo de Evento']) if c.isalnum())
        doc_id = f"{row['Empresa']}_{comp_safe}_{row['ID Func']}_{evento_safe}"
        dados = row.to_dict()
        dados['_id'] = doc_id
        operations.append(UpdateOne({'_id': doc_id}, {'$set': dados}, upsert=True))
    if operations:
        try:
            result = collection.bulk_write(operations)
            return result.upserted_count + result.modified_count
        except: return 0
    return 0

@st.cache_data(ttl=600)
def carregar_filtros_mongo():
    db = get_db()
    if db is None: return [], []
    try:
        empresas = db.folha_eventos.distinct("Empresa")
        competencias = db.folha_eventos.distinct("Competência")
        return sorted(empresas), sorted(competencias)
    except:
        return [], []

@st.cache_data(ttl=600)
def carregar_dados_mongo(empresas_sel, competencias_sel):
    db = get_db()
    if db is None: return pd.DataFrame()
    if not empresas_sel or not competencias_sel: return pd.DataFrame()
    
    try:
        query = {"Empresa": {"$in": empresas_sel}, "Competência": {"$in": competencias_sel}}
        cursor = db.folha_eventos.find(query)
        df = pd.DataFrame(list(cursor))
        if not df.empty and '_id' in df.columns: df = df.drop(columns=['_id'])
        return df
    except: return pd.DataFrame()

# --- CONFIGURAÇÕES (CARGOS E EXCEÇÕES) ---

def carregar_mapa_cargos_mongo():
    db = get_db()
    if db is None: return {}
    try:
        doc = db.parametros.find_one({"_id": "mapeamento_areas"})
        return doc.get('mapa', {}) if doc else {}
    except: return {}

def salvar_mapa_cargos_mongo(novo_mapa):
    db = get_db()
    if db is None: return
    try:
        db.parametros.update_one({"_id": "mapeamento_areas"}, {"$set": {"mapa": novo_mapa}}, upsert=True)
    except: pass

def carregar_mapa_excecoes_mongo():
    db = get_db()
    if db is None: return {}
    try:
        doc = db.parametros.find_one({"_id": "mapeamento_excecoes"})
        return doc.get('mapa', {}) if doc else {}
    except: return {}

def salvar_mapa_excecoes_mongo(novo_mapa):
    db = get_db()
    if db is None: return
    try:
        db.parametros.update_one({"_id": "mapeamento_excecoes"}, {"$set": {"mapa": novo_mapa}}, upsert=True)
    except: pass
