import streamlit as st
import pandas as pd
import pymongo
from pymongo import MongoClient, UpdateOne
import bcrypt
import datetime

# --- CONEXÃO COM MONGODB ---
# Usa st.cache_resource para manter a conexão aberta e não reconectar a cada clique
@st.cache_resource
def init_connection():
    # Tenta pegar dos segredos (Nuvem) ou usa string vazia para forçar erro amigável
    uri = st.secrets.get("MONGO_URI", "")
    if not uri:
        return None
    return MongoClient(uri)

def get_db():
    client = init_connection()
    if client:
        return client.get_database("financeiro_db") # Nome do seu banco
    return None

# --- AUTENTICAÇÃO ---
def verificar_login(email, senha):
    db = get_db()
    if db is None: return False
    
    usuario = db.users.find_one({"email": email})
    if usuario:
        # Verifica a senha criptografada
        if bcrypt.checkpw(senha.encode('utf-8'), usuario['password']):
            return usuario['name']
    return None

def criar_usuario_admin(nome, email, senha):
    """Função auxiliar para criar o primeiro usuário via script"""
    db = get_db()
    if db is None: return False
    
    hashed = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
    
    # Upsert: atualiza se existir, cria se não existir
    db.users.update_one(
        {"email": email},
        {"$set": {"name": nome, "password": hashed, "email": email}},
        upsert=True
    )
    return True

# --- FUNÇÕES FINANCEIRAS (Substituindo Firestore) ---

def salvar_dados_mongo(df):
    db = get_db()
    if db is None: return 0
    
    collection = db.folha_eventos
    operations = []
    
    # Prepara operações em lote (Bulk Write) para alta performance
    for _, row in df.iterrows():
        # Cria um ID único igual ao que você usava no Firestore
        comp_safe = str(row['Competência']).replace('/', '-')
        evento_safe = "".join(c for c in str(row['Tipo de Evento']) if c.isalnum())
        doc_id = f"{row['Empresa']}_{comp_safe}_{row['ID Func']}_{evento_safe}"
        
        dados = row.to_dict()
        dados['_id'] = doc_id # Define o ID do MongoDB
        
        # ReplaceOne com upsert=True substitui o documento se o ID já existir
        operations.append(UpdateOne({'_id': doc_id}, {'$set': dados}, upsert=True))
    
    if operations:
        result = collection.bulk_write(operations)
        return result.upserted_count + result.modified_count
    return 0

@st.cache_data(ttl=600)
def carregar_filtros_mongo():
    db = get_db()
    if db is None: return [], []
    
    # Distinct é muito rápido no Mongo
    empresas = db.folha_eventos.distinct("Empresa")
    competencias = db.folha_eventos.distinct("Competência")
    
    return sorted(empresas), sorted(competencias)

@st.cache_data(ttl=600)
def carregar_dados_mongo(empresas_sel, competencias_sel):
    db = get_db()
    if db is None: return pd.DataFrame()
    
    if not empresas_sel or not competencias_sel:
        return pd.DataFrame()
    
    # Query otimizada com operador $in
    query = {
        "Empresa": {"$in": empresas_sel},
        "Competência": {"$in": competencias_sel}
    }
    
    cursor = db.folha_eventos.find(query)
    df = pd.DataFrame(list(cursor))
    
    # Remove a coluna interna do mongo _id para não atrapalhar
    if not df.empty and '_id' in df.columns:
        df = df.drop(columns=['_id'])
        
    return df

# --- CONFIGURAÇÕES (CARGOS E EXCEÇÕES) ---
# Salvamos isso em uma coleção chamada 'parametros'

def carregar_mapa_cargos_mongo():
    db = get_db()
    if db is None: return {}
    doc = db.parametros.find_one({"_id": "mapeamento_areas"})
    return doc.get('mapa', {}) if doc else {}

def salvar_mapa_cargos_mongo(novo_mapa):
    db = get_db()
    if db is None: return
    db.parametros.update_one(
        {"_id": "mapeamento_areas"},
        {"$set": {"mapa": novo_mapa}},
        upsert=True
    )

def carregar_mapa_excecoes_mongo():
    db = get_db()
    if db is None: return {}
    doc = db.parametros.find_one({"_id": "mapeamento_excecoes"})
    return doc.get('mapa', {}) if doc else {}

def salvar_mapa_excecoes_mongo(novo_mapa):
    db = get_db()
    if db is None: return
    db.parametros.update_one(
        {"_id": "mapeamento_excecoes"},
        {"$set": {"mapa": novo_mapa}},
        upsert=True
    )
