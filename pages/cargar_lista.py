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

def subir_a_google_sheets(nombre_hoja: str, df: pd.DataFrame):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(st.secrets["service_account"], scopes=scopes)
        client = gspread.authorize(creds)

        spreadsheet_id = st.secrets["general"]["spreadsheet_id"]
        sh = client.open_by_key(spreadsheet_id)

        ws = create_or_replace_worksheet(sh, nombre_hoja, df)
        st.success(f"✅ Hoja '{ws.title}' creada/actualizada en Google Sheets.")

        # Limpieza opcional del PDF temporal
        if os.path.exists("doc.pdf"):
            os.remove("doc.pdf")
    except KeyError as e:
        st.error(f"❌ Falta clave en secrets.toml: {e}")
    except APIError as e:
        st.error(f"❌ Error Google API (revisa ID y permisos): {e}")
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")

# === Subir archivo PDF ===
archivo_pdf = st.file_uploader("📎 Sube la lista en PDF descargada del SII:", type=["pdf"])

if archivo_pdf:
    doc = fitz.open(stream=archivo_pdf.read(), filetype="pdf")
    texto = "".join(p.get_text() for p in doc)
    lineas = texto.split("\n")

    materia, grupo, docente = "", "", ""
    alumnos = []

    # === Encabezado ===
    for i, linea in enumerate(lineas):
        u = linea.upper().strip()
        if "MATERIA" in u and i + 3 < len(lineas):
            materia = lineas[i + 3].strip()
        elif "GRUPO" in u:
            for l in lineas[i:i + 5]:
                s = l.strip()
                # tu grupo real es un código de 3 dígitos (p.ej. 611, 051, etc.)
                if re.match(r"^\d{3}$", s):
                    grupo = s
                    break
        elif "CATEDRATICO" in u and i + 2 < len(lineas):
            docente = lineas[i + 2].strip()

    # === Alumnos ===
    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()
        if linea.isdigit() and i + 2 < len(lineas):
            nombre = lineas[i + 1].strip()
            no_control = lineas[i + 2].strip()
            if re.match(r'^[C]?\d{8}$', no_control):
                alumnos.append({"nombre": nombre, "no_control": no_control})
                i += 3
            else:
                i += 1
        else:
            i += 1

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
    if st.button("📤 Crear/actualizar pestaña en Google Sheets"):
        titulo_hoja = f"{grupo} - {materia}".strip()
        subir_a_google_sheets(nombre_hoja=titulo_hoja, df=df)

    # (Opcional) Verificar encabezados sin modificar nada
    if st.button("🔎 Verificar en Google Sheets"):
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(st.secrets["service_account"], scopes=scopes)
            client = gspread.authorize(creds)
            sh = client.open_by_key(st.secrets["general"]["spreadsheet_id"])
            ws = sh.worksheet(f"{grupo} - {materia}".strip())
            headers = ws.row_values(1)
            st.write("**Encabezados en A1..:**", headers)
            st.write("**(Deben ser exactamente)**:",
                    ["Dirección","Telefono","Correo","No de control","Nombre","Grupo","Docente"])
        except Exception as e:
            st.error(f"❌ No se pudo verificar: {e}")
