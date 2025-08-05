import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import pytz
import string

# === CONFIGURACIÓN DE STREAMLIT ===
st.set_page_config(page_title="Corrección de Inasistencias", layout="wide")
st.title("🕒 Corrección de inasistencias del día")

# === Autenticación con Google Sheets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)
client = gspread.authorize(creds)

# === Acceder al archivo de Google Sheets ===
SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)

# === Selección de materia y unidad ===
materias = [ws.title for ws in sh.worksheets()]
materia = st.selectbox("📚 Selecciona la materia:", materias)

unidad = st.selectbox("📦 Selecciona la unidad:", ["1", "2", "3", "4", "5", "6", "7", "8", "Asesoría", "Propedéutico"])

# === Obtener hora actual (zona horaria de México) ===
zona = pytz.timezone("America/Mexico_City")
hora_local = datetime.now(pytz.utc).astimezone(zona)
fecha_hoy = hora_local.strftime('%d/%m/%Y')

# === Leer datos de la hoja seleccionada ===
ws = sh.worksheet(materia)
df = pd.DataFrame(ws.get_all_records())
df.columns = df.columns.str.strip().str.lower()  # 🔧 Normaliza nombres de columnas

if df.empty:
    st.info("No hay alumnos registrados en esta materia.")
    st.stop()

# === Buscar columnas de hoy (independiente de la hora exacta) ===
columnas_de_hoy = [col for col in df.columns if f"unidad {unidad.lower()} - {fecha_hoy}" in col.lower()]

if not columnas_de_hoy:
    st.warning(f"No se encontró una columna para hoy: Unidad {unidad} - {fecha_hoy}")
    st.stop()

# === Usar la última columna registrada hoy ===
fecha_col = columnas_de_hoy[-1]
col_index = df.columns.get_loc(fecha_col) + 1  # gspread usa índices desde 1

# === Obtener letra de la columna (tipo 'H') ===
columna_actual = string.ascii_uppercase[col_index - 1]

# === Convertir DataFrame a lista de alumnos (normalizando claves) ===
alumnos = df.to_dict("records")
alumnos = [{k.strip().lower(): v for k, v in alumno.items()} for alumno in alumnos]  # 🔧 Normaliza claves

# === Mostrar contexto arriba ===
st.markdown(f"""
**📚 Materia:** `{materia}`  
**📦 Unidad:** `{unidad}`  
**🗓️ Columna seleccionada:** `{fecha_col}`
""")

# === Buscar alumnos con inasistencia (✗) ===
alumnos_con_falta = df[df[fecha_col] == "✗"]

if alumnos_con_falta.empty:
    st.success("✅ No hay inasistencias que corregir hoy.")
    st.stop()

# === Mostrar tabla de corrección de retardo ===
st.subheader("👨‍🏫 Marcar retardo en lugar de inasistencia")

retardos_seleccionados = []
col1, col2 = st.columns([4, 1])

with col1:
    for alumno in alumnos:
        nombre = alumno["nombre"]
        asistencia_actual = df.loc[df["nombre"] == nombre, fecha_col].values[0]
        if asistencia_actual == "✗":
            checked = asistencia_actual == "~"
            checkbox = st.checkbox(f"{nombre}", value=checked, key=f"retardo_{nombre}")
            if checkbox:
                retardos_seleccionados.append(nombre)

# === Botón para guardar todos los retardos seleccionados ===
if st.button("✅ Guardar retardos"):
    hoja = sh.worksheet(materia)
    for i, alumno in enumerate(alumnos, start=2):  # Asumiendo que fila 1 son encabezados
        nombre = alumno["nombre"]
        if nombre in retardos_seleccionados:
            hoja.update_acell(f"{columna_actual}{i}", "~")
    st.success("✅ Retardos registrados correctamente.")
    st.rerun()
