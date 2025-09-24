# -*- coding: utf-8 -*-
import streamlit as st
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import sqlite3
import hashlib
from datetime import datetime, date, timedelta
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus.flowables import HRFlowable
import psycopg2
from io import BytesIO

# ================== CONFIGURATION ==================
st.set_page_config(layout="wide")

DATABASE_URL = st.secrets.get("DATABASE_URL", "").strip()
CLOUDINARY_CLOUD_NAME = st.secrets.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = st.secrets.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = st.secrets.get("CLOUDINARY_API_SECRET")

if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )

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
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except ImportError:
            st.error("La bibliothèque psycopg2 n'est pas installée. Veuillez l'ajouter à requirements.txt.")
            st.stop()
        except Exception as e:
            st.error(f"Erreur de connexion à la base de données PostgreSQL : {e}")
            st.stop()
    else:
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
        pass

    conn.commit()
    conn.close()

# ================== FONCTIONS D'ACCÈS AUX DONNÉES ==================
def get_etablissement_count():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM etablissement")
    count = c.fetchone()[0]
    conn.close()
    return count

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


# ================== INTERFACE UTILISATEUR ==================
# Pages de l'application
def page_dashboard():
    st.title("📊 Tableau de bord")
    st.write("Bienvenue dans votre tableau de bord!")
    # Le reste du code de votre tableau de bord

def page_classes():
    st.title("🏷️ Classes")
    st.write("Gestion des classes.")
    # Le reste du code de la page des classes

def page_etudiants():
    st.title("👨‍🎓 Étudiants")
    st.write("Gestion des étudiants.")
    # Le reste du code de la page des étudiants

def page_notes():
    st.title("📝 Notes")
    st.write("Saisie des notes.")
    # Le reste du code de la page des notes

def page_modalites():
    st.title("💰 Modalités")
    st.write("Gestion des modalités de paiement.")
    # Le reste du code de la page des modalités

def page_paiements():
    st.title("💳 Paiements")
    st.write("Suivi des paiements.")
    # Le reste du code de la page des paiements

def page_matieres():
    st.title("📘 Matières")
    st.write("Gestion des matières.")
    # Le reste du code de la page des matières

def page_presences():
    st.title("✍️ Présences & Absences")
    st.write("Gestion des présences.")
    # Le reste du code de la page des présences

def page_bulletins():
    st.title("📄 Bulletins & Relevés")
    st.write("Génération des bulletins.")
    # Le reste du code de la page des bulletins

def page_listes():
    st.title("📄 Listes d'étudiants")
    st.write("Listes des étudiants.")
    # Le reste du code de la page des listes


def page_inscription():
    st.title("Inscription d'un nouvel établissement")
    st.info("Veuillez remplir ce formulaire pour créer votre établissement et votre compte administrateur.")

    with st.form("form_inscription"):
        st.subheader("Informations de l'établissement")
        col1, col2 = st.columns(2)
        with col1:
            nom_etab = st.text_input("Nom de l'établissement", placeholder="Nom de l'école")
            adresse_etab = st.text_input("Adresse de l'établissement", placeholder="Adresse complète")
            telephone_etab = st.text_input("Téléphone de l'établissement", placeholder="Numéro de téléphone")
        with col2:
            directeur_etab = st.text_input("Nom du directeur", placeholder="Nom du directeur")
            email_etab = st.text_input("Email de contact de l'établissement", placeholder="info@etablissement.com")
            logo_upload = st.file_uploader("Logo de l'établissement (optionnel)", type=["png", "jpg", "jpeg"])

        st.subheader("Création du compte administrateur")
        col3, col4 = st.columns(2)
        with col3:
            email_admin = st.text_input("Email de l'administrateur", placeholder="admin@votre-etablissement.com")
        with col4:
            password_admin = st.text_input("Mot de passe de l'administrateur", type="password", placeholder="Mot de passe")

        submitted = st.form_submit_button("S'inscrire et créer l'établissement")

        if submitted:
            if not all([nom_etab, directeur_etab, email_admin, password_admin]):
                st.error("Veuillez remplir tous les champs obligatoires.")
            else:
                logo_url = handle_logo_upload(logo_upload)
                try:
                    etablissement_id = add_etablissement(nom_etab, adresse_etab, telephone_etab, directeur_etab, email_etab, logo_url)
                    create_user(email_admin, password_admin, 'admin', etablissement_id)
                    st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
                    st.session_state['show_login'] = True
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Une erreur est survenue lors de l'inscription : {e}")

def login_page():
    st.title("Connexion")
    with st.container():
        st.subheader("Connectez-vous à votre compte")
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


# ================== MAIN APP ==================
def main():
    if LOCAL_STORAGE_MODE:
        init_db()
        ensure_dirs()
    
    etablissements_count = get_etablissement_count()
    
    if 'logged_in' not in st.session_state:
        # Affiche la page de connexion par défaut si l'utilisateur n'est pas connecté
        login_page()
    else:
        user_role = st.session_state['user_role']
        st.sidebar.title("Navigation")
        if st.sidebar.button("Déconnexion"):
            st.session_state.clear()
            st.experimental_rerun()

        # Construction du dictionnaire de pages avec la page d'inscription si moins de 5 établissements
        pages = {}
        if etablissements_count < 5:
            pages["➕ Inscription Établissement"] = page_inscription

        if user_role == "admin" or user_role == "direction":
            pages.update({
                "📊 Tableau de bord": page_dashboard,
                "🏷️ Classes": page_classes,
                "👨‍🎓 Étudiants": page_etudiants,
                "📝 Notes": page_notes,
                "✍️ Présences & Absences": page_presences,
                "📄 Bulletins & Relevés": page_bulletins,
                "📄 Listes d'étudiants": page_listes
            })
        elif user_role == "comptable" or user_role == "economat":
            pages.update({
                "📊 Tableau de bord": page_dashboard,
                "💰 Modalités": page_modalites,
                "💳 Paiements": page_paiements,
                "📄 Listes d'étudiants": page_listes
            })
        elif user_role == "teacher":
            pages.update({
                "🏷️ Classes": page_classes,
                "📘 Matières": page_matieres,
                "👨‍🎓 Étudiants": page_etudiants,
                "📝 Notes": page_notes,
                "✍️ Présences & Absences": page_presences,
                "📄 Bulletins & Relevés": page_bulletins,
                "📄 Listes d'étudiants": page_listes
            })
        elif user_role == "student":
            pages.update({
                "📄 Bulletins & Relevés": page_bulletins,
                "📄 Listes d'étudiants": page_listes
            })
        else:
            st.warning("Votre rôle n'a pas de pages attribuées.")
            return

        choix = st.sidebar.radio("Menu de navigation", list(pages.keys()))
        pages[choix]()


if __name__ == "__main__":
    main()