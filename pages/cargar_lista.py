import streamlit as st
import fitz  # PyMuPDF
import re
import pandas as pd
import gspread
import os
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound, APIError

# === Config de página ===
st.set_page_config(page_title="Cargar Lista de Alumnos", layout="wide")
st.title("📄 Cargar lista de asistencia (PDF)")

# --- helpers ---
def sanitize_title(title: str) -> str:
    for ch in [":", "\\", "/", "?", "*", "[", "]"]:
        title = title.replace(ch, "-")
    return title.strip()[:95]

def create_or_replace_worksheet(sh, title: str, df: pd.DataFrame):
    title = sanitize_title(title)
    try:
        ws = sh.worksheet(title)
        ws.clear()
    except WorksheetNotFound:
        rows = max(len(df) + 5, 100)
        cols = max(len(df.columns) + 5, 20)
        ws = sh.add_worksheet(title=title, rows=rows, cols=cols)

    # escribe encabezados + datos
    values = [list(df.columns)] + df.astype(str).values.tolist()
    ws.update("A1", values)
    return ws

def _get_spreadsheet_id():
    # Acepta [general].spreadsheet_id o raíz
    if "general" in st.secrets and "spreadsheet_id" in st.secrets["general"]:
        return st.secrets["general"]["spreadsheet_id"]
    if "spreadsheet_id" in st.secrets:
        return st.secrets["spreadsheet_id"]
    disponibles = list(st.secrets.keys())
    raise KeyError(
        f'No encontré "spreadsheet_id" en secrets. Claves disponibles: {disponibles}. '
        'En Cloud agrega [general]\\nspreadsheet_id="..." en Settings → Secrets.'
    )

def subir_a_google_sheets(nombre_hoja: str, df: pd.DataFrame):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(
            st.secrets["service_account"], scopes=scopes
        )
        client = gspread.authorize(creds)

        spreadsheet_id = _get_spreadsheet_id()
        sh = client.open_by_key(spreadsheet_id)

        ws = create_or_replace_worksheet(sh, nombre_hoja, df)
        st.success(f"✅ Hoja '{ws.title}' creada/actualizada en Google Sheets.")

        # Limpieza opcional del PDF temporal
        if os.path.exists("doc.pdf"):
            os.remove("doc.pdf")
    except KeyError as e:
        st.error(f"❌ Falta clave en secrets: {e}")
    except APIError as e:
        st.error(f"❌ Error Google API (revisa ID y permisos): {e}")
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")

# === Subir archivo PDF ===
archivo_pdf = st.file_uploader("📎 Sube la lista en PDF descargada del SII:", type=["pdf"])

# Si aún no suben nada, salimos (evita NameError)
if not archivo_pdf:
    st.info("Sube un PDF para continuar.")
    st.stop()

# Abre y lee el PDF
doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
texto = "".join(p.get_text() for p in doc)
lineas = texto.split("\n")

materia, grupo, docente = "", "", ""

# === Analizar encabezado ===
for i, linea in enumerate(lineas):
    u = linea.upper().strip()
    if "MATERIA" in u and i + 3 < len(lineas):
        materia = lineas[i + 3].strip()
    elif "GRUPO" in u:
        for l in lineas[i:i + 5]:
            s = l.strip()
            if re.match(r"^\d{3}$", s):  # p. ej. 611, 053
                grupo = s
                break
    elif "CATEDRATICO" in u and i + 2 < len(lineas):
        docente = lineas[i + 2].strip()

# === Extraer alumnos (robusto con R/E/**, etc.) ===
alumnos = []

# Patrones
NUM_RE = re.compile(r"^\d+$")                                     # "1", "2", ...
NUM_MAS_MARCA_RE = re.compile(r"^\d+\s+(?:[A-ZÁÉÍÓÚÑ]|\*{1,3})$")  # "10 R" o "20 **"
MARCA_SOLO_RE = re.compile(r"^(?:[A-ZÁÉÍÓÚÑ]|\*{1,3})$")          # "R", "E", "*", "**", "***"
NC_RE = re.compile(r"^[C]?\d{8}$")                                # Cdddddddd o dddddddd

i, N = 0, len(lineas)
while i < N:
    linea = lineas[i].strip()

    # Inicio de fila por número o "número + marca"
    if NUM_RE.match(linea) or NUM_MAS_MARCA_RE.match(linea):
        i += 1
        if i >= N:
            break

        # Saltar marcas sueltas en la columna intermedia
        while i < N and MARCA_SOLO_RE.match(lineas[i].strip()):
            i += 1
            if i >= N:
                break
        if i >= N:
            break

        # Nombre (tolerar línea vacía extra)
        nombre = lineas[i].strip()
        if nombre == "" and i + 1 < N:
            i += 1
            nombre = lineas[i].strip()

        # Limpiar marca pegada al nombre (p. ej. "R ORTIZ..." o "** TORRES...")
        nombre = re.sub(r"^(?:[A-ZÁÉÍÓÚÑ]|\*{1,3})\s+", "", nombre)
        # Colapsar espacios dobles
        nombre = re.sub(r"\s{2,}", " ", nombre).strip()

        # Buscar No. de control en las siguientes 3 líneas
        no_control = ""
        j = i + 1
        while j < min(N, i + 4) and no_control == "":
            cand = lineas[j].strip()
            if NC_RE.match(cand):
                no_control = cand
                i = j + 1
                break
            j += 1

        if no_control:
            alumnos.append({"nombre": nombre, "no_control": no_control})
            continue
        else:
            i += 1
            continue
    else:
        i += 1

# ---------- A PARTIR DE AQUÍ TODO VA *FUERA* DEL WHILE ----------

st.success(f"✅ Lista detectada con éxito: {len(alumnos)} alumnos")
st.write(f"📘 Materia: `{materia}`")
st.write(f"👥 Grupo: `{grupo}`")
st.write(f"👨‍🏫 Docente: `{docente}`")

# === DataFrame con ENCABEZADOS EXACTOS que esperan tus gráficas ===
df = pd.DataFrame(
    [["", "", "", a["no_control"], a["nombre"], grupo, docente] for a in alumnos],
    columns=["Dirección", "Telefono", "Correo", "No de control", "Nombre", "Grupo", "Docente"]
)
st.dataframe(df, use_container_width=True)

# === Subir a Google Sheets (NOMBRE DE PESTAÑA = grupo - materia) ===
titulo_hoja = f"{grupo} - {materia}".strip()

if st.button("📤 Crear/actualizar pestaña en Google Sheets", key=f"btn_subir_{titulo_hoja}"):
    subir_a_google_sheets(nombre_hoja=titulo_hoja, df=df)

# (Opcional) Verificar encabezados sin modificar nada
if st.button("🔎 Verificar en Google Sheets", key=f"btn_verificar_{titulo_hoja}"):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        sh = client.open_by_key(_get_spreadsheet_id())
        ws = sh.worksheet(titulo_hoja)
        headers = ws.row_values(1)
        st.write("**Encabezados en A1..:**", headers)
        st.write("**(Deben ser exactamente)**:",
                 ["Dirección","Telefono","Correo","No de control","Nombre","Grupo","Docente"])
    except Exception as e:
        st.error(f"❌ No se pudo verificar: {e}")
