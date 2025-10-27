import streamlit as st
import pandas as pd
import altair as alt
from typing import List, Dict
import sys, os

# ---  Hacemos que Python vea la carpeta raíz del proyecto ---
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# ---  Importamos las funciones que ya usas para leer Google Sheets ---
from gsheets_utils import get_sheet, read_ws_df

# =========================
# CONFIG APP
# =========================
st.set_page_config(page_title="Comparativo de Materias", layout="wide")
SHEET_NAME = st.secrets.get("SHEET_NAME", "Seguimiento_Asistencia_2025_2")

st.title(" Comparativo de Asistencia por Materia")

# =========================
# HELPERS
# =========================

@st.cache_data(ttl=300, show_spinner=False)
def get_worksheet_titles(spreadsheet_name: str) -> List[str]:
    """Regresa lista de worksheets (cada una es una materia)."""
    sh = get_sheet(spreadsheet_name)
    return [ws.title for ws in sh.worksheets()]

def is_attendance_column(col: str) -> bool:
    """
    Decide si una columna es una sesión de asistencia.
    Heurística: columnas que empiezan con 'Unidad', 'U', 'Proped', 'Tutor'
    Ejemplo real:
    'Unidad 2 - 15/10/2025 10:00'
    """
    if not isinstance(col, str):
        return False
    low = col.lower().strip()
    if low.startswith("unidad"):
        return True
    if low.startswith("u") and any(ch.isdigit() for ch in low):
        return True
    if low.startswith("proped"):
        return True
    if low.startswith("tutor"):
        return True
    return False

def normalize_attendance(value: str) -> Dict[str, int]:
    """
    Convierte ✓, ~ / r, ✗ en indicadores binarios.
    """
    if not isinstance(value, str):
        return {"present": 0, "tardy": 0, "absent": 0}
    v = value.strip().lower()
    if v == "✓":
        return {"present": 1, "tardy": 0, "absent": 0}
    if v in ("~", "r"):
        return {"present": 0, "tardy": 1, "absent": 0}
    if v == "✗":
        return {"present": 0, "tardy": 0, "absent": 1}
    return {"present": 0, "tardy": 0, "absent": 0}

def parse_unidad(col_name: str) -> str:
    """
    Extrae la 'unidad' a partir del nombre de la columna.
    Ejemplos que intentamos mapear:
    - 'Unidad 3 - 15/10/2025 10:00' -> 'Unidad 3'
    - 'Propedéutico - 12/09/2025' -> 'Propedéutico'
    - 'Tutoría - 20/09/2025' -> 'Tutoría'
    - 'U4 - 01/10/2025' -> 'Unidad 4'
    """
    import re
    import unicodedata

    txt = str(col_name or "")
    # Parte antes del primer " - "
    prefix = txt.split(" - ", 1)[0].strip()

    # normalizar sin acentos
    def norm(x):
        return "".join(
            c for c in unicodedata.normalize("NFD", x)
            if unicodedata.category(c) != "Mn"
        ).lower()

    n = norm(prefix)

    if "propedeutico" in n:
        return "Propedéutico"
    if "tutoria" in n:
        return "Tutoría"

    # Buscar unidad numérica: "unidad 3", "u3", etc.
    m = re.search(r"(?:unidad|u)\s*-?\s*(\d+)", n)
    if m:
        return f"Unidad {int(m.group(1))}"

    # Si no encontramos nada claro, devolvemos el prefijo tal cual
    return prefix

def parse_datetime_from_col(col_name: str):
    """
    Intenta extraer la fecha/hora de la parte después de ' - ' en el header.
    Ejemplo: 'Unidad 2 - 15/10/2025 10:00'
    Devuelve un datetime (o None si no se puede).
    """
    import datetime

    txt = str(col_name or "")
    # Parte DESPUÉS del primer " - "
    parts = txt.split(" - ", 1)
    if len(parts) < 2:
        return None

    fecha_txt = parts[1].strip()

    # Probamos algunos formatos comunes
    formatos = [
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]
    for fmt in formatos:
        try:
            return datetime.datetime.strptime(fecha_txt, fmt)
        except Exception:
            pass
    return None

def melt_attendance(df: pd.DataFrame, materia: str) -> pd.DataFrame:
    """
    Pasa una hoja (wide) a formato largo estándar:
    columnas finales:
    - materia
    - No de control
    - Nombre
    - unidad
    - fecha_col  (el nombre original de la columna de asistencia)
    - dt         (datetime parseado del header si existe)
    - present / tardy / absent
    """
    # columnas base mínimas
    id_cols = []
    if "No de control" in df.columns:
        id_cols.append("No de control")
    if "Nombre" in df.columns:
        id_cols.append("Nombre")

    # columnas de asistencia
    att_cols = [c for c in df.columns if is_attendance_column(c)]

    if not att_cols or not id_cols:
        return pd.DataFrame(
            columns=[
                "materia", "No de control", "Nombre",
                "unidad", "fecha_col", "dt",
                "present", "tardy", "absent",
            ]
        )

    # pasamos a formato largo
    long_df = df[id_cols + att_cols].melt(
        id_vars=id_cols,
        value_vars=att_cols,
        var_name="fecha_col",
        value_name="raw",
    )

    # normalizamos asistencia
    norm_vals = long_df["raw"].apply(normalize_attendance).apply(pd.Series)
    long_df = pd.concat([long_df.drop(columns=["raw"]), norm_vals], axis=1)

    # agregar materia
    long_df["materia"] = materia

    # unidad
    long_df["unidad"] = long_df["fecha_col"].apply(parse_unidad)

    # dt (datetime real del encabezado)
    long_df["dt"] = long_df["fecha_col"].apply(parse_datetime_from_col)

    return long_df

@st.cache_data(ttl=60, show_spinner=False)
def load_materias_long(spreadsheet_name: str, materias: List[str]) -> pd.DataFrame:
    """
    Lee varias worksheets (materias), convierte cada una con melt_attendance,
    y concatena todo en un DataFrame largo.
    """
    frames = []
    for m in materias:
        df_raw = read_ws_df(spreadsheet_name, m)  # viene cacheado desde utils
        if df_raw is None or df_raw.empty:
            continue
        long_m = melt_attendance(df_raw, m)
        if long_m is not None and not long_m.empty:
            frames.append(long_m)

    if not frames:
        return pd.DataFrame(
            columns=[
                "materia", "No de control", "Nombre",
                "unidad", "fecha_col", "dt",
                "present", "tardy", "absent",
            ]
        )

    return pd.concat(frames, ignore_index=True)

def build_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula % de asistencia / retardo / ausencia por materia.
    (promedio de las banderas binarias)
    """
    if long_df.empty:
        return pd.DataFrame(columns=["materia","present_rate","tardy_rate","absent_rate"])

    summary = (
        long_df.groupby("materia", as_index=False)[["present","tardy","absent"]]
        .mean()
        .rename(columns={
            "present": "present_rate",
            "tardy":   "tardy_rate",
            "absent":  "absent_rate",
        })
    )

    # asegurar float
    for c in ["present_rate","tardy_rate","absent_rate"]:
        summary[c] = pd.to_numeric(summary[c], errors="coerce").fillna(0.0).astype(float)

    return summary

def build_unidades_sorted(long_df: pd.DataFrame) -> List[str]:
    """
    Devuelve lista de unidades únicas ordenadas lógicamente:
    Unidad 1, Unidad 2, ..., Propedéutico, Tutoría, etc.
    """
    raw = long_df["unidad"].dropna().unique().tolist()

    def sort_key(u):
        # Unidad X primero en orden numérico
        if isinstance(u, str) and u.lower().startswith("unidad"):
            try:
                num = int(u.split(" ", 1)[1])
                return (0, num)
            except Exception:
                return (0, 999999)
        # luego Propedéutico, luego Tutoría
        if u == "Propedéutico":
            return (1, 0)
        if u == "Tutoría":
            return (1, 1)
        # lo demás al final
        return (2, str(u))

    return sorted(raw, key=sort_key)

# =========================
# UI - Selección de materias
# =========================

ws_titles = get_worksheet_titles(SHEET_NAME)
if not ws_titles:
    st.error("No se encontraron materias / worksheets en la hoja.")
    st.stop()

st.subheader("1. Selecciona las materias que quieres comparar")
materias_sel = st.multiselect(
    "Materias",
    options=ws_titles,
    default=ws_titles[:1]  # primera materia por defecto
)

if not materias_sel:
    st.info("Selecciona al menos una materia para continuar.")
    st.stop()

# =========================
# Cargar datos largos
# =========================
with st.spinner("Cargando y normalizando asistencia..."):
    df_long = load_materias_long(SHEET_NAME, materias_sel)

if df_long.empty:
    st.warning("No hay datos de asistencia en las materias seleccionadas.")
    st.stop()

# =========================
# Filtro opcional por unidad
# =========================
st.subheader("2. Filtrar por Unidad (opcional)")
unidades_disp = build_unidades_sorted(df_long)

unidad_sel = st.multiselect(
    "Unidades / bloques",
    options=unidades_disp,
    default=[],
    placeholder="(Vacío = considerar TODAS las unidades)"
)

if unidad_sel:
    df_long_filtrado = df_long[df_long["unidad"].isin(unidad_sel)]
    st.caption(f"Mostrando sólo: {', '.join(unidad_sel)}")
else:
    df_long_filtrado = df_long.copy()
    st.caption("Mostrando TODAS las unidades.")

# =========================
# Resumen por materia
# =========================
st.subheader("3. Resumen por materia")

resumen = build_summary(df_long_filtrado)

# Mostrar tabla porcentual
tabla = resumen.copy()
for col in ["present_rate","tardy_rate","absent_rate"]:
    tabla[col] = (tabla[col] * 100.0).round(1)

st.dataframe(tabla, use_container_width=True)

# =========================
# Gráfica de barras horizontales de asistencia
# =========================
st.subheader("4. % de asistencia por materia")

if resumen.empty:
    st.info("No hay datos suficientes para graficar.")
else:
    bar_df = resumen[["materia","present_rate"]].copy()
    bar_df["pct"] = (bar_df["present_rate"] * 100.0).round(1)

    # Clasificación visual rápida
    def rango_color(p):
        if p >= 95: return "Alta (≥95%)"
        if p >= 85: return "Media (85–94.9%)"
        return "Baja (<85%)"
    bar_df["nivel"] = bar_df["pct"].apply(rango_color)

    color_scale = alt.Scale(
        domain=["Alta (≥95%)","Media (85–94.9%)","Baja (<85%)"],
        range=["#22c55e","#f59e0b","#ef4444"]  # verde / amarillo / rojo
    )

    chart_height = max(300, 28 * len(bar_df))

    bars = alt.Chart(bar_df).mark_bar().encode(
        y=alt.Y("materia:N", sort="-x",
                axis=alt.Axis(title=None, labelLimit=10000)),
        x=alt.X("pct:Q",
                title="Asistencia (%)",
                scale=alt.Scale(domain=[0,100])),
        color=alt.Color("nivel:N", scale=color_scale, legend=alt.Legend(title="Nivel")),
        tooltip=[
            alt.Tooltip("materia:N", title="Materia"),
            alt.Tooltip("pct:Q", title="% Asistencia", format=".1f"),
            alt.Tooltip("nivel:N", title="Nivel"),
        ],
    ).properties(height=chart_height)

    labels = alt.Chart(bar_df).mark_text(
        align="right", baseline="middle", dx=-6, color="white", fontWeight="bold"
    ).encode(
        y="materia:N",
        x="pct:Q",
        text=alt.Text("pct:Q", format=".1f")
    )

    st.altair_chart(bars + labels, use_container_width=True)

st.success("Listo: selección de materias ✅, filtro por unidad ✅, resumen ✅, barra horizontal ✅.")

