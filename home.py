import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import pytz

# === CONFIGURACIÓN DE ACCESO A GOOGLE SHEETS CON SECRETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = st.secrets["service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)

client = gspread.authorize(creds)

SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)

# === INTERFAZ DE USUARIO ===
st.set_page_config(page_title="Inicio - Registro de Asistencia", layout="wide")
st.title("🎓 Plataforma de Registro de Asistencia - Ingeniería Mecánica")

# === SELECCIÓN DE MATERIA Y UNIDAD ===
st.subheader("Selecciona la materia que impartes")
materia = st.selectbox("Materia:", [ws.title for ws in sh.worksheets()])

st.subheader("Selecciona la unidad de captura")
unidad = st.selectbox("Unidad:", ["1", "2", "3", "4", "5","6", "7", "8","asesoria"])

# === VALIDACIÓN DE HORARIO ===
st.subheader("Hora de captura")
zona = pytz.timezone("America/Mexico_City")
hora_local = datetime.now(zona)
hora_actual = hora_local.strftime("%H:%M")
st.markdown(f"⏰ Hora actual: **{hora_actual}**")

# === BOTÓN PARA CONTINUAR ===
if st.button("Ir al registro de asistencia"):
    st.session_state["materia"] = materia
    st.session_state["unidad"] = unidad
    st.session_state["hora"] = hora_actual
    st.switch_page("pages/asistencia_app.py")  # debe coincidir con el nombre del archivo en la carpeta /pages
