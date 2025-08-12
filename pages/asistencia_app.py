import streamlit as st
import gspread
import pandas as pd
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import pytz


# === Validación de acceso desde home.py ===
if "materia" not in st.session_state or "unidad" not in st.session_state:
    st.error("⚠️ Accede desde la página principal para registrar asistencia.")
    st.stop()



# === Cargar datos desde session_state ===
materia = st.session_state["materia"]
unidad = st.session_state["unidad"]

# === Interfaz ===
# [NUEVO] Mantenemos la configuración de página al inicio visual de la UI
st.set_page_config(page_title="Registro de Asistencia", layout="wide")
st.title(f"📋 Asistencia: {materia}")

# [NUEVO] Mostramos última hora fija de captura, si existe (no dispara nuevas columnas)
ultima_hora = st.session_state.get("ultima_hora_captura", "—")
st.caption(f"Unidad: {unidad} | Última captura: {ultima_hora}")


# === Configuración de acceso a Google Sheets desde secrets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
service_account_info = st.secrets["service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)
client = gspread.authorize(creds)



SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)
ws = sh.worksheet(materia)


# === Cargar datos ===
df = pd.DataFrame(ws.get_all_records())

if df.empty:
    st.info("No hay alumnos registrados.")
    st.stop()

# === Obtener hora local de México con conversión desde UTC ===
# [CAMBIO] Antes aquí se calculaba la hora_local/hora_captura/fecha_col.
#          Ahora SOLO definimos la zona; el cálculo REAL se hace al pulsar Guardar.
zona = pytz.timezone("America/Mexico_City")

# === Guardar hora para mostrar y para usar en el encabezado de la columna ===
# [CAMBIO] Este bloque se movió al evento de Guardar para “congelar” la hora.
# hora_captura / fecha_col ahora se calculan dentro del submit.



# === Lista de asistencia ===
# [NUEVO] Usamos st.form para que la app NO ejecute guardados hasta pulsar el botón.
with st.form(key="form_asistencia", clear_on_submit=False):
    st.subheader("📋 Lista de alumnos")
    asistencia = []
    for i, row in df.iterrows():
        nombre = row["Nombre"]
        nc = row["No de control"]
        # [CAMBIO] clave única por alumno para evitar colisiones al re-renderizar
        marcado = st.checkbox(f"{nc} - {nombre}", key=f"al_{i}")
        asistencia.append("✓" if marcado else "✗")

 # === Guardar resultado ===
    btn_guardar = st.form_submit_button("✅ Guardar asistencia")

if btn_guardar:
    # [NUEVO] Tomar la hora local SOLO aquí (se “congela” en el clic)
    ahora = datetime.now(zona)  # hora MX
    hora_captura = ahora.strftime("%H:%M")
    # [NUEVO] Incluye fecha y hora en el nombre de la columna, pero ya fijo al momento del clic
    fecha_col = f"Unidad {unidad} - {ahora.strftime('%d/%m/%Y %H:%M')}"

    # [NUEVO] Guardar en session_state para mostrar después sin crear columnas nuevas
    st.session_state["ultima_hora_captura"] = hora_captura
    st.session_state["ultima_columna"] = fecha_col

    # === Crear columna si no existe ===
    # [MOVIDO] Este chequeo estaba antes de la UI y creaba columnas por minuto.
    #          Ahora se hace aquí, solo al guardar.
    headers = ws.row_values(1)
    if fecha_col in headers:
        col_idx = headers.index(fecha_col) + 1
    else:
        col_idx = len(headers) + 1
        ws.update_cell(1, col_idx, fecha_col)

    # === Guardar asistencia en la hoja ===
    # Las filas de datos empiezan en la 2 (fila 1 = encabezados)
    for i, valor in enumerate(asistencia, start=2):
        ws.update_cell(i, col_idx, valor)

    st.success(f"✅ Asistencia guardada correctamente en: {fecha_col} (hora: {hora_captura})")

# --- NOTAS ---
# 1) El uso de st.form impide que cada interacción con los checkboxes regenere la columna.
# 2) La hora/columna se calculan SOLO cuando presionas “Guardar asistencia”.  