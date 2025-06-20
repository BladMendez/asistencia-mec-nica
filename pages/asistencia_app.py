import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime

from oauth2client.service_account import ServiceAccountCredentials


# === Validación de acceso desde home.py ===
if "materia" not in st.session_state or "unidad" not in st.session_state:
    st.error("⚠️ Accede desde la página principal para registrar asistencia.")
    st.stop()

from datetime import datetime, timedelta
import pytz

# === Cargar datos desde session_state ===
materia = st.session_state["materia"]
unidad = st.session_state["unidad"]

# Obtener hora local de México con fallback seguro
try:
    zona = pytz.timezone("America/Mexico_City")
    hora_local = datetime.now(zona)
except Exception:
    hora_local = datetime.utcnow() - timedelta(hours=5)  # Fallback UTC-5 si falla

# Guardar hora para mostrar y para usar en el encabezado de la columna
hora_captura = hora_local.strftime("%H:%M")
fecha_col = f"Unidad {unidad} - {hora_local.strftime('%d/%m/%Y %H:%M')}"

# === Configuración de acceso a Google Sheets desde secrets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = st.secrets["service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)

client = gspread.authorize(creds)

SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)
ws = sh.worksheet(materia)

# === Interfaz ===
st.set_page_config(page_title="Registro de Asistencia", layout="wide")
st.title(f"📋 Asistencia: {materia}")
st.caption(f"Unidad: {unidad} | Hora de captura: {hora_captura}")

# === Cargar datos ===
df = pd.DataFrame(ws.get_all_records())

if df.empty:
    st.info("No hay alumnos registrados.")
    st.stop()



# === Crear columna si no existe ===
if fecha_col not in df.columns:
    ws.update_cell(1, len(df.columns) + 1, fecha_col)
    df[fecha_col] = ""

# === Lista de asistencia ===
st.subheader("📋 Lista de alumnos")
asistencia = []
for i, row in df.iterrows():
    nombre = row["Nombre"]
    nc = row["No de control"]
    marcado = st.checkbox(f"{nc} - {nombre}", key=i)
    asistencia.append("✓" if marcado else "✗")

# === Guardar resultado ===
if st.button("✅ Guardar asistencia"):
    col_index = df.columns.get_loc(fecha_col) + 1
    for i, valor in enumerate(asistencia, start=2):  # Desde fila 2
        ws.update_cell(i, col_index, valor)
    st.success("✅ Asistencia guardada correctamente.")
