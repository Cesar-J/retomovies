import streamlit as st
import pandas as pd
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import ResourceExhausted

# --- CONFIGURACIÓN E INICIALIZACIÓN DE FIREBASE ---
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        firebase_config = dict(st.secrets["firebase"])
        if "private_key" in firebase_config:
            firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# --- CARGA DE DATOS DESDE FIRESTORE ---
@st.cache_data
def load_data():
    movies_ref = db.collection(u'movies')
    docs = movies_ref.stream()
    movies_list = [doc.to_dict() for doc in docs]
    return pd.DataFrame(movies_list)

data = load_data()

# Listas para los filtros y selectbox
companies_list = sorted(data['company'].dropna().unique().tolist()) if 'company' in data.columns else []
directors_list = sorted(data['director'].dropna().unique().tolist()) if 'director' in data.columns else []
genres_list = sorted(data['genre'].dropna().unique().tolist()) if 'genre' in data.columns else []
directors_form_list = directors_list.copy()

# --- INTERFAZ PRINCIPAL ---
st.title("Film Navigator")

# Checkbox para mostrar todos los filmes
sidebar_show_all = st.sidebar.checkbox("Mostrar todos los filmes", value=True)

# Filtro por Título
st.sidebar.subheader("Buscar filmes por título")
search_title = st.sidebar.text_input("Titulo del filme:", key="search_title_input")
btn_search_title = st.sidebar.button("Buscar filmes")

# Filtro por Director
st.sidebar.subheader("Seleccionar Director")
selected_director = st.sidebar.selectbox("Seleccionar Director", directors_list if directors_list else ["Sin directores"])
btn_search_director = st.sidebar.button("Filtrar director")

# --- FORMULARIO PARA CREAR NUEVO FILME ---
st.sidebar.subheader("Nuevo filme")

# clear_on_submit=True limpia los campos automáticamente al enviar sin tocar st.session_state
with st.sidebar.form("nuevo_filme_form", clear_on_submit=True):
    new_name = st.text_input("Name:")
    new_company = st.selectbox("Company", companies_list)
    new_director = st.selectbox("Director", directors_form_list)
    new_genre = st.selectbox("Genre", genres_list)
    
    submit_button = st.form_submit_button(label="Crear nuevo filme")
    
    if submit_button:
        clean_name = new_name.strip()
        if clean_name != "":
            existing_names = data['name'].astype(str).str.lower().values if 'name' in data.columns else []
            if clean_name.lower() in existing_names:
                st.sidebar.warning(f"El filme '{clean_name}' ya existe en la base de datos.")
            else:
                doc_id = clean_name.replace('/', '_').replace('.', '_')
                doc_ref = db.collection(u'movies').document(doc_id)
                new_data = {
                    "name": clean_name,
                    "company": new_company,
                    "director": new_director,
                    "genre": new_genre
                }
                try:
                    doc_ref.set(new_data)
                    st.cache_data.clear()
                    st.session_state["success_msg"] = f"¡Filme '{clean_name}' agregado exitosamente!"
                    st.rerun()
                except ResourceExhausted:
                    st.sidebar.error("No se pudo agregar: la cuota diaria de Firestore ha sido excedida.")
        else:
            st.sidebar.error("El nombre del filme no puede estar vacío.")

# Mostrar mensaje de éxito si existe en el estado
if "success_msg" in st.session_state:
    st.success(st.session_state["success_msg"])
    del st.session_state["success_msg"]

# --- MOSTRAR RESULTADOS ---
if btn_search_title and search_title:
    filtered_data = data[data['name'].astype(str).str.contains(search_title, case=False, na=False)]
    st.subheader(f"Filmes que contienen: '{search_title}'")
    st.write(f"Total encontrado: {len(filtered_data)}")
    st.dataframe(filtered_data)
elif btn_search_director and selected_director:
    filtered_data = data[data['director'] == selected_director]
    st.subheader(f"Filmes dirigidos por: '{selected_director}'")
    st.write(f"Total encontrado: {len(filtered_data)}")
    st.dataframe(filtered_data)
elif sidebar_show_all:
    st.subheader("Todos los filmes")
    st.write(f"Total de filmes: {len(data)}")
    st.dataframe(data)
