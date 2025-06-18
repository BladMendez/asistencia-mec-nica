import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIGURACIÓN DE ACCESO ===
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

# === HOJA DE CÁLCULO ===
SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)

# === INTERFAZ EN STREAMLIT ===
st.set_page_config(page_title="Seguimiento Asistencia", layout="wide")
st.title("📘 Seguimiento de Asistencia - Ingeniería Mecánica")

# === MATERIA Y UNIDAD ===
materias = [ws.title for ws in sh.worksheets()]
materia = st.selectbox("Selecciona la materia", materias)
unidad = st.selectbox("Selecciona la unidad", ["1", "2", "3", "4"])

# === VALIDAR FECHA ===
hoy = datetime.today()
if hoy.weekday() >= 5:
    st.warning("⚠️ Hoy no es un día hábil. Solo puedes registrar asistencia de lunes a viernes.")
    st.stop()

fecha_col = f"Unidad {unidad} - {hoy.strftime('%d/%m/%Y')}"
ws = sh.worksheet(materia)

# === CARGAR DATOS EXISTENTES ===
df = pd.DataFrame(ws.get_all_records())

if df.empty:
    st.info("No hay alumnos registrados.")
    st.stop()

# === CREAR COLUMNA SI NO EXISTE ===
if fecha_col not in df.columns:
    ws.update_cell(1, len(df.columns) + 1, fecha_col)
    df[fecha_col] = ""

# === LISTA DE ASISTENCIA ===
st.subheader("📋 Lista de alumnos")
asistencia = []
for i, row in df.iterrows():
    nombre = row["Nombre"]
    nc = row["No de control"]
    marcado = st.checkbox(f"{nc} - {nombre}", key=i)
    asistencia.append("✓" if marcado else "✗")

# === GUARDAR RESULTADO ===
if st.button("✅ Guardar asistencia"):
    col_index = df.columns.get_loc(fecha_col) + 1
    for i, valor in enumerate(asistencia, start=2):  # Desde fila 2
        ws.update_cell(i, col_index, valor)
    st.success("✅ Asistencia guardada correctamente.")
