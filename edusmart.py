import streamlit as st
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import sqlite3
import hashlib
from datetime import datetime, date, timedelta
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ================== CONFIGURATION ==================
# Utilise les secrets de Streamlit pour les connexions cloud
DATABASE_URL = st.secrets.get("DATABASE_URL", "").strip()
CLOUDINARY_CLOUD_NAME = st.secrets.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = st.secrets.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = st.secrets.get("CLOUDINARY_API_SECRET")

# Configuration de Cloudinary
if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )

# Les répertoires locaux ne sont nécessaires que pour le mode développement
LOCAL_STORAGE_MODE = not all([DATABASE_URL, CLOUDINARY_CLOUD_NAME])
DB_FILE = "edusmart.db"
UPLOAD_DIR_PHOTOS = "uploads/photos"
UPLOAD_DIR_DOCS = "uploads/docs"
UPLOAD_DIR_LOGO = "uploads/logo"
ARCHIVE_DIR_BULLETINS = "archives/bulletins"
ARCHIVE_DIR_RECU = "archives/recus"
ARCHIVE_DIR_LISTES = "archives/listes"
ARCHIVE_DIR_PRESENCES = "archives/presences"


# ================== UTILS ==================
def ensure_dirs():
    if LOCAL_STORAGE_MODE:
        os.makedirs(UPLOAD_DIR_PHOTOS, exist_ok=True)
        os.makedirs(UPLOAD_DIR_DOCS, exist_ok=True)
        os.makedirs(UPLOAD_DIR_LOGO, exist_ok=True)
        os.makedirs(ARCHIVE_DIR_BULLETINS, exist_ok=True)
        os.makedirs(ARCHIVE_DIR_RECU, exist_ok=True)
        os.makedirs(ARCHIVE_DIR_LISTES, exist_ok=True)
        os.makedirs(ARCHIVE_DIR_PRESENCES, exist_ok=True)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def handle_photo_upload(uploaded_file):
    if not uploaded_file:
        return None
    if not LOCAL_STORAGE_MODE:
        try:
            result = cloudinary.uploader.upload(uploaded_file, folder="photos", resource_type="image")
            return result['secure_url']
        except Exception as e:
            st.error(f"Erreur lors du téléchargement de la photo sur Cloudinary: {e}")
            return None
    else:
        path = os.path.join(UPLOAD_DIR_PHOTOS, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return path

def handle_doc_upload(uploaded_file):
    if not uploaded_file:
        return None
    if not LOCAL_STORAGE_MODE:
        try:
            result = cloudinary.uploader.upload(uploaded_file, folder="docs", resource_type="raw")
            return result['secure_url']
        except Exception as e:
            st.error(f"Erreur lors du téléchargement du document sur Cloudinary: {e}")
            return None
    else:
        path = os.path.join(UPLOAD_DIR_DOCS, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return path

def handle_logo_upload(uploaded_file):
    if not uploaded_file:
        return None
    if not LOCAL_STORAGE_MODE:
        try:
            public_id = "logo_" + datetime.now().strftime("%Y%m%d%H%M%S")
            result = cloudinary.uploader.upload(uploaded_file, folder="logo", public_id=public_id, resource_type="image")
            return result['secure_url']
        except Exception as e:
            st.error(f"Erreur lors du téléchargement du logo sur Cloudinary: {e}")
            return None
    else:
        path = os.path.join(UPLOAD_DIR_LOGO, uploaded_file.name)
        with open(path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return path

# ================== DATABASE ==================
def get_conn():
    if DATABASE_URL:
        # Mode production (PostgreSQL)
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except ImportError:
            st.error("La bibliothèque psycopg2 n'est pas installée. Veuillez l'ajouter à requirements.txt.")
            st.stop()
        except Exception as e:
            st.error(f"Erreur de connexion à la base de données PostgreSQL : {e}")
            st.stop()
    else:
        # Mode local (SQLite)
        conn = sqlite3.connect(DB_FILE)
        return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS etablissement (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        adresse TEXT,
        telephone TEXT,
        directeur TEXT,
        type TEXT DEFAULT 'classique',
        actif INTEGER DEFAULT 1,
        email TEXT,
        logo TEXT
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS abonnements (
        id SERIAL PRIMARY KEY,
        etablissement_id INTEGER NOT NULL REFERENCES etablissement(id) ON DELETE CASCADE,
        date_debut DATE NOT NULL,
        date_fin DATE NOT NULL,
        statut TEXT DEFAULT 'actif'
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        etablissement_id INTEGER REFERENCES etablissement(id) ON DELETE CASCADE
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS annees (
        id SERIAL PRIMARY KEY,
        nom TEXT NOT NULL UNIQUE
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        niveau TEXT,
        annee_id INTEGER REFERENCES annees(id) ON DELETE SET NULL,
        etablissement_id INTEGER REFERENCES etablissement(id) ON DELETE CASCADE
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS matieres (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        coefficient INTEGER DEFAULT 1,
        classe_id INTEGER REFERENCES classes(id) ON DELETE CASCADE,
        note_de_passage REAL DEFAULT 65.0,
        intra_weight REAL DEFAULT 0.3
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS etudiants (
        id SERIAL PRIMARY KEY,
        nom TEXT,
        prenom TEXT,
        matricule TEXT,
        date_naissance TEXT,
        lieu_naissance TEXT,
        adresse TEXT,
        telephone TEXT,
        email TEXT,
        photo TEXT,
        document_scanne TEXT,
        classe_id INTEGER REFERENCES classes(id) ON DELETE SET NULL
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY,
        etudiant_id INTEGER REFERENCES etudiants(id) ON DELETE CASCADE,
        matiere_id INTEGER REFERENCES matieres(id) ON DELETE CASCADE,
        session INTEGER,
        type TEXT,
        controle INTEGER,
        note REAL
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS modalites_paiement (
        id SERIAL PRIMARY KEY,
        etablissement_id INTEGER NOT NULL REFERENCES etablissement(id) ON DELETE CASCADE,
        nom TEXT,
        montant REAL,
        frequence TEXT
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS paiements (
        id SERIAL PRIMARY KEY,
        etudiant_id INTEGER NOT NULL REFERENCES etudiants(id) ON DELETE CASCADE,
        modalite_id INTEGER NOT NULL REFERENCES modalites_paiement(id) ON DELETE CASCADE,
        date_paiement DATE NOT NULL,
        montant_paye REAL,
        methode TEXT
    );""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS presences (
        id SERIAL PRIMARY KEY,
        etudiant_id INTEGER NOT NULL REFERENCES etudiants(id) ON DELETE CASCADE,
        date DATE NOT NULL,
        statut TEXT NOT NULL,
        motif TEXT
    );""")

    # Fonctions de migration pour ajouter les nouvelles colonnes
    if LOCAL_STORAGE_MODE:
        c.execute("PRAGMA table_info(matieres)")
        columns = [info[1] for info in c.fetchall()]
        if 'note_de_passage' not in columns:
            c.execute("ALTER TABLE matieres ADD COLUMN note_de_passage REAL DEFAULT 65.0")
        if 'intra_weight' not in columns:
            c.execute("ALTER TABLE matieres ADD COLUMN intra_weight REAL DEFAULT 0.3")

        c.execute("PRAGMA table_info(etablissement)")
        columns = [info[1] for info in c.fetchall()]
        if 'email' not in columns:
            c.execute("ALTER TABLE etablissement ADD COLUMN email TEXT")
        if 'logo' not in columns:
            c.execute("ALTER TABLE etablissement ADD COLUMN logo TEXT")

        c.execute("PRAGMA table_info(etudiants)")
        columns = [info[1] for info in c.fetchall()]
        if 'matricule' not in columns:
            c.execute("ALTER TABLE etudiants ADD COLUMN matricule TEXT")
    else:
        # Pour PostgreSQL, nous utilisons une approche différente pour vérifier l'existence des colonnes
        # Cette logique n'est plus nécessaire car vous l'avez exécutée manuellement
        pass

    conn.commit()
    conn.close()

# Reste du code de votre application (fonctions de gestion des données, interface utilisateur Streamlit, etc.)
# ...

# ================== FONCTIONS D'ACCÈS AUX DONNÉES ==================
def get_user_by_email(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = c.fetchone()
    conn.close()
    return user

def add_etablissement(nom, adresse, telephone, directeur, email, logo):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO etablissement (nom, adresse, telephone, directeur, email, logo) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
              (nom, adresse, telephone, directeur, email, logo))
    etablissement_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return etablissement_id

def create_user(email, password, role, etablissement_id):
    conn = get_conn()
    c = conn.cursor()
    hashed_password = hash_password(password)
    c.execute("INSERT INTO users (email, password, role, etablissement_id) VALUES (%s, %s, %s, %s)",
              (email, hashed_password, role, etablissement_id))
    conn.commit()
    conn.close()

def get_etablissement_info(etablissement_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nom, adresse, telephone, directeur, email, logo FROM etablissement WHERE id = %s", (etablissement_id,))
    info = c.fetchone()
    conn.close()
    return info

def get_etudiants_par_classe(classe_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM etudiants WHERE classe_id = %s", (classe_id,))
    etudiants = c.fetchall()
    conn.close()
    return etudiants

def get_classes_etablissement(etablissement_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nom, niveau FROM classes WHERE etablissement_id = %s", (etablissement_id,))
    classes = c.fetchall()
    conn.close()
    return classes

def get_matieres_classe(classe_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nom, coefficient FROM matieres WHERE classe_id = %s", (classe_id,))
    matieres = c.fetchall()
    conn.close()
    return matieres

def add_etudiant(nom, prenom, matricule, date_naissance, lieu_naissance, adresse, telephone, email, photo, document_scanne, classe_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO etudiants (nom, prenom, matricule, date_naissance, lieu_naissance, adresse, telephone, email, photo, document_scanne, classe_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
              (nom, prenom, matricule, date_naissance, lieu_naissance, adresse, telephone, email, photo, document_scanne, classe_id))
    conn.commit()
    conn.close()

def add_note(etudiant_id, matiere_id, session, type_note, controle, note):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO notes (etudiant_id, matiere_id, session, type, controle, note) VALUES (%s, %s, %s, %s, %s, %s)",
              (etudiant_id, matiere_id, session, type_note, controle, note))
    conn.commit()
    conn.close()

# Reste des fonctions pour les paiements, présences, etc.
# ...


# ================== INTERFACE UTILISATEUR ==================
def login_page():
    st.title("Connexion")
    email = st.text_input("Email")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        user = get_user_by_email(email)
        if user and user[2] == hash_password(password):
            st.session_state['logged_in'] = True
            st.session_state['user_id'] = user[0]
            st.session_state['user_role'] = user[3]
            st.session_state['etablissement_id'] = user[4]
            st.success("Connexion réussie!")
            st.experimental_rerun()
        else:
            st.error("Email ou mot de passe incorrect.")

def dashboard():
    st.sidebar.title("Navigation")
    if st.sidebar.button("Déconnexion"):
        st.session_state.clear()
        st.experimental_rerun()

    st.title(f"Tableau de bord - Rôle : {st.session_state['user_role']}")
    # ... UI pour chaque rôle (Admin, Professeur, etc.)

# ================== MAIN APP ==================
def main():
    if 'logged_in' not in st.session_state:
        login_page()
    else:
        dashboard()

if __name__ == "__main__":
    if LOCAL_STORAGE_MODE:
        init_db()
        ensure_dirs()
    main()