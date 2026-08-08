import streamlit as st
import pandas as pd
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import ResourceExhausted

# --- CONFIGURACIÓN E INICIALIZACIÓN DE FIREBASE ---
#PATH_DATA = "/content/"
#FIREBASE_CREDENTIALS_FILE = PATH_DATA + "reto-movies-firebase-adminsdk-fbsvc-b973f457ad.json"

@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        # Carga las credenciales desde los Secrets de Streamlit
        firebase_config = dict(st.secrets["firebase"])
        # En caso de que las llaves privadas tengan saltos de línea escapados
        if "private_key" in firebase_config:
            firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
            
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firebase()

# --- FUNCIÓN DE CARGA OPTIMIZADA CON CACHÉ ---
DATE_COLUMN = 'name'

@st.cache_data
def load_data():
    try:
        docs = db.collection(u'movies').stream()
        data_dict = [doc.to_dict() for doc in docs]
        return pd.DataFrame(data_dict)
    except ResourceExhausted:
        st.error("Se ha alcanzado la cuota diaria de lectura en Firestore.")
        return pd.DataFrame(columns=['name', 'company', 'director', 'genre'])

# Carga inicial de datos
data_load_state = st.text('Loading movies data...')
data = load_data()
data_load_state.text("Done! (using st.cache)")

# --- INTERFAZ PRINCIPAL ---
st.title('Film Navigator')

# 1. Checkbox en sidebar para mostrar todos los filmes
if st.sidebar.checkbox('Mostrar todos los filmes'):
    st.subheader('Todos los filmes')
    st.dataframe(data)

# 2. Búsqueda de filmes por título
st.sidebar.subheader("Buscar filmes por título")
with st.sidebar.form("search_form"):
    title_query = st.text_input("Titulo del filme :")
    search_submitted = st.form_submit_button("Buscar filmes")

if search_submitted:
    if title_query.strip():
        filtered_title = data[data['name'].astype(str).str.contains(title_query, case=False, na=False)]
        st.subheader('Resultados de búsqueda')
        st.write(f"Total filmes mostrados : {len(filtered_title)}")
        st.dataframe(filtered_title)
    else:
        st.warning("Por favor, ingresa un título para buscar.")

# 3. Selectbox para filtrar por Director
st.sidebar.subheader("Seleccionar Director")
if 'director' in data.columns and not data.empty:
    directors_list = sorted(data['director'].dropna().unique().tolist())
    selected_director = st.sidebar.selectbox("Seleccionar Director", directors_list)
    if st.sidebar.button("Filtrar director"):
        filtered_director = data[data['director'] == selected_director]
        st.subheader(f'Filmes dirigidos por {selected_director}')
        st.write(f"Total filmes : {len(filtered_director)}")
        st.dataframe(filtered_director)

# --- INICIALIZACIÓN Y CONTROL DEL ESTADO EN SESSION STATE ---
if "new_movie_name" not in st.session_state:
    st.session_state["new_movie_name"] = ""

# Mostrar mensaje de éxito si se agregó un filme en el render anterior
if "success_msg" in st.session_state:
    st.sidebar.success(st.session_state["success_msg"])
    del st.session_state["success_msg"]

# Opciones para listas de selección
companies_list = sorted(data['company'].dropna().unique().tolist()) if 'company' in data.columns and not data.empty else ["Independent"]
directors_form_list = sorted(data['director'].dropna().unique().tolist()) if 'director' in data.columns and not data.empty else ["Unknown"]
genres_list = sorted(data['genre'].dropna().unique().tolist()) if 'genre' in data.columns and not data.empty else ["Drama"]

# 4. Formulario para insertar un nuevo filme desde el Sidebar
st.sidebar.subheader("Nuevo filme")
with st.sidebar.form("nuevo_filme_form"):
    new_name = st.text_input("Name:", value=st.session_state["new_movie_name"], key="new_movie_name")
    new_company = st.selectbox("Company", companies_list, key="new_company_key")
    new_director = st.selectbox("Director", directors_form_list, key="new_director_key")
    new_genre = st.selectbox("Genre", genres_list, key="new_genre_key")
    
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
                    
                    # Restablecer valores de forma segura asignando la primera opción de cada lista
                    st.session_state["new_movie_name"] = ""
                    st.session_state["new_company_key"] = companies_list[0]
                    st.session_state["new_director_key"] = directors_form_list[0]
                    st.session_state["new_genre_key"] = genres_list[0]

                    st.session_state["success_msg"] = f"¡Filme '{clean_name}' agregado exitosamente!"
                    
                    st.rerun()
                except ResourceExhausted:
                    st.sidebar.error("No se pudo agregar: la cuota diaria de Firestore ha sido excedida.")
        else:
            st.sidebar.error("El nombre del filme no puede estar vacío.")
