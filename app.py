import streamlit as st
from db_utils import criar_usuario

st.set_page_config(page_title="Setup Inicial Admin", layout="centered")

st.title("🛠️ Setup Inicial - Criar Admin")
st.warning("Atenção: Apague este arquivo do repositório após criar o primeiro usuário.")

with st.form("setup_admin"):
    st.write("Crie o Super Usuário para acessar o sistema.")
    nome = st.text_input("Nome Completo")
    email = st.text_input("E-mail (Login)")
    senha = st.text_input("Senha", type="password")
    repetir_senha = st.text_input("Repetir Senha", type="password")
    
    # Chave de segurança opcional para evitar que qualquer um crie admin se achar a URL
    secret_key = st.text_input("Chave de Segurança (Invente uma se estiver rodando local)", type="password")
    
    submit = st.form_submit_button("Criar Admin")

    if submit:
        # Você pode remover a verificação da chave se quiser, mas é recomendável
        if senha != repetir_senha:
            st.error("As senhas não conferem.")
        elif len(senha) < 6:
            st.error("A senha deve ter pelo menos 6 caracteres.")
        else:
            # Força o cargo como 'admin' e ativo=True
            sucesso = criar_usuario(nome, email, senha, cargo='admin', ativo=True)
            if sucesso:
                st.success(f"Usuário Admin **{email}** criado com sucesso! Agora você pode deletar este arquivo e usar o app.py.")
            else:
                st.error("Erro ao conectar ao banco ou criar usuário.")
