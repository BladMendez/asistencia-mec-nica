import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from typing import List, Dict
import altair as alt 
import math

# [NUEVO] Utilidades cacheadas para evitar 429 (del módulo utils que te compartí)
from gsheets_utils import get_sheet, read_ws_df  # usa cache_resource + cache_data

# === Config ===
st.set_page_config(page_title="Comparativo de Materias", layout="wide")
SHEET_NAME = st.secrets.get("SHEET_NAME", "Seguimiento_Asistencia_2025_2")
zona = pytz.timezone("America/Mexico_City")

st.title(" Comparativo de Asistencia por Materia")

# ============ HELPERS ============

@st.cache_data(ttl=300, show_spinner=False)
def get_worksheet_titles(spreadsheet_name: str) -> List[str]:
    """Lista de títulos de worksheets (materias) una sola vez cada 5 min."""
    sh = get_sheet(spreadsheet_name)
    return [ws.title for ws in sh.worksheets()]

def is_attendance_column(col: str) -> bool:
    """Columnas de asistencia: 'Unidad ...', 'Propedéutico', 'Tutoría' (con o sin acentos/guiones)."""
    if not isinstance(col, str):
        return False
    low = col.lower()
    return (
        low.startswith("unidad ") or
        low.startswith("unidad-") or
        low.startswith("u") and any(ch.isdigit() for ch in low) or
        low.startswith("proped") or     # propedeutico/propedéutico
        low.startswith("tutor")         # tutoria/tutoría
    )


def normalize_attendance(value: str) -> Dict[str, int]:
    """
    Normaliza un valor de celda a {present, tardy, absent}.
    ✓ presente | ~ o r = retardo | ✗ ausente | otro => 0
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

def melt_attendance(df: pd.DataFrame, materia: str) -> pd.DataFrame:
    """
    Convierte el wide de asistencia a formato largo por materia:
    columnas: 'Unidad X - dd/mm/aaaa HH:MM' -> filas (fecha_col)
    """
    import re
    cols_min = [c for c in ["No de control", "Nombre"] if c in df.columns]
    att_cols = [c for c in df.columns if is_attendance_column(c)]
    if not att_cols:
        return pd.DataFrame(columns=["materia","fecha_col","No de control","Nombre","present","tardy","absent","unidad","dt"])

    long_df = df[cols_min + att_cols].melt(
        id_vars=cols_min,
        value_vars=att_cols,
        var_name="fecha_col",
        value_name="raw"
    )

    # Normaliza valores a 0/1
    norm = long_df["raw"].apply(normalize_attendance).apply(pd.Series)
    long_df = pd.concat([long_df.drop(columns=["raw"]), norm], axis=1)
    long_df["materia"] = materia

    # Parsear datetime y unidad
    def parse_unidad(s: str):
        import re, unicodedata

        txt = str(s or "")
        # Tomar la parte antes del primer " - " (suele ser "Unidad X" o "Propedéutico")
        prefix = txt.split(" - ", 1)[0].strip()

        # Normalizar (quitar acentos) para comparar
        def norm(x):
            return "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn").lower()

        n = norm(prefix)

        # 1) Propedéutico / Tutoría (con o sin acentos, mayúsculas, etc.)
        if "propedeutico" in n:
            return "Propedéutico"
        if "tutoria" in n:
            return "Tutoría"

        # 2) Unidad numérica: "Unidad 3", "Unidad-3", "U3", "u-3", "Unidad03", etc.
        m = re.search(r"(?:unidad|u)\s*-?\s*(\d+)", n)
        if m:
            return f"Unidad {int(m.group(1))}"

        return None

    # Agregar columna 'unidad' usando la función parse_unidad
    long_df["unidad"] = long_df["fecha_col"].apply(parse_unidad)


@st.cache_data(ttl=60, show_spinner=False)
def load_materias_long(spreadsheet_name: str, materias: List[str]) -> pd.DataFrame:
    """
    Lee múltiples materias (cacheada 60s), convierte a formato largo,
    y las concatena en un solo DataFrame.
    """
    frames = []
    for m in materias:
        df = read_ws_df(spreadsheet_name, m)  # cacheado 30s en utils -> minimiza lecturas
        if df is None or df.empty:
            continue
        frames.append(melt_attendance(df, m))
    if not frames:
        return pd.DataFrame(columns=["materia", "fecha_col", "No de control", "Nombre", "present", "tardy", "absent", "dt"])
    return pd.concat(frames, ignore_index=True)

def build_aggregates(long_df: pd.DataFrame):
    if long_df.empty:
        return (
            pd.DataFrame(columns=["materia","present_rate","tardy_rate","absent_rate"]),
            pd.DataFrame(columns=["materia","dt","present_rate"])
        )

    mat_group = (long_df
                 .groupby("materia", as_index=False)[["present","tardy","absent"]]
                 .mean()
                 .rename(columns={"present":"present_rate","tardy":"tardy_rate","absent":"absent_rate"}))

    for c in ["present_rate","tardy_rate","absent_rate"]:
        mat_group[c] = pd.to_numeric(mat_group[c], errors="coerce").fillna(0.0).astype(float)

    if "dt" in long_df.columns:
        evo = (long_df.dropna(subset=["dt"])
               .groupby(["materia","dt"], as_index=False)[["present"]]
               .mean()
               .rename(columns={"present":"present_rate"}))
        evo["present_rate"] = pd.to_numeric(evo["present_rate"], errors="coerce").fillna(0.0).astype(float)
    else:
        evo = pd.DataFrame(columns=["materia","dt","present_rate"])

    return mat_group, evo


# ============ UI ============

# -- Inicializa estado para persistir selección --
if "comp_ready" not in st.session_state:
    st.session_state["comp_ready"] = False
if "comp_sel" not in st.session_state:
    st.session_state["comp_sel"] = []

ws_titles = get_worksheet_titles(SHEET_NAME)
if not ws_titles:
    st.error("No se encontraron worksheets en la hoja.")
    st.stop()

with st.form(key="form_comp", clear_on_submit=False):
    st.subheader("Selecciona materias a comparar")
    # Usa la selección persistida como default si existe; si no, toma algunas por defecto
    default_opts = st.session_state["comp_sel"] or ws_titles[:1]
    sel = st.multiselect("Materias", options=ws_titles, default=default_opts)
    ver = st.form_submit_button("👀 Ver")

# Si se presiona Ver, guardamos en session_state y activamos modo “listo”
if ver:
    st.session_state["comp_sel"] = sel
    st.session_state["comp_ready"] = True

# Si aún no hay selección confirmada, muestra ayuda y no cortes si ya había una previa
if not st.session_state["comp_ready"]:
    st.info("Selecciona una o varias materias y presiona **Ver**.")
    st.stop()

# --------- Ya hay selección persistida ---------
sel_final = st.session_state["comp_sel"]
if not sel_final:
    st.warning("No hay materias seleccionadas. Vuelve a presionar **Ver** con al menos una materia.")
    st.stop()

# ============ CARGA & PROCESAMIENTO ============
with st.spinner("Cargando datos..."):
    long_df = load_materias_long(SHEET_NAME, sel_final)

if long_df.empty:
    st.warning("No hay datos de asistencia en las materias seleccionadas.")
    st.stop()

# ----- Filtro por Unidad (reactivo, sin botón) -----
raw_opts = [u for u in long_df["unidad"].dropna().unique().tolist()]

# Orden: Unidad 1, Unidad 2, ... luego Propedéutico, Tutoría
def sort_key(u):
    if isinstance(u, str) and u.startswith("Unidad "):
        try:
            return (0, int(u.split(" ", 1)[1]))
        except Exception:
            return (0, 999999)
    if u == "Propedéutico":
        return (1, 0)
    if u == "Tutoría":
        return (1, 1)
    return (2, str(u))

unidades_disp = sorted(raw_opts, key=sort_key)

st.subheader("Filtrar por Unidad (opcional)")
sel_unidades = st.multiselect(
    "Unidad(es)",
    options=unidades_disp,
    default=[],  # vacío => general
    placeholder="Si no seleccionas nada, se muestra el general."
)

if sel_unidades:
    long_df = long_df[long_df["unidad"].isin(sel_unidades)]
    st.caption(f"Filtrando por unidad: {', '.join(sel_unidades)}")
else:
    st.caption("Mostrando **todas** las unidades (general).")

# === AGREGADOS (después del posible filtro) ===
with st.spinner("Generando comparativos..."):
    mat_group, evo = build_aggregates(long_df)

# ============ VISTAS / GRÁFICAS ============

# 1) Tabla resumen (tasa de asistencia por materia)
st.subheader("Resumen por materia (% asistencia / retardos / ausencias)")

resumen = mat_group.copy()
rate_cols = ["present_rate", "tardy_rate", "absent_rate"]
for c in rate_cols:
    if c not in resumen.columns:
        resumen[c] = 0.0
    resumen[c] = pd.to_numeric(resumen[c], errors="coerce").fillna(0.0).astype(float)

tabla = resumen.copy()
tabla[rate_cols] = (tabla[rate_cols] * 100.0).round(1)
st.dataframe(tabla, use_container_width=True)

# 2) Gráfica de barras: % asistencia por materia (sin heatmap)
import altair as alt

st.subheader("Asistencia por materia (%)")

bar_df = resumen[["materia", "present_rate"]].copy()
if bar_df.empty:
    st.info("No hay datos para graficar barras.")
else:
    # % en float y etiqueta
    bar_df["pct"] = (pd.to_numeric(bar_df["present_rate"], errors="coerce")
                     .fillna(0.0) * 100.0).round(1)

    # Bandas de color por umbral
    def color_band(p):
        if p >= 95: return "Alta (≥95%)"
        if p >= 85: return "Media (85–94.9%)"
        return "Baja (<85%)"
    bar_df["nivel"] = bar_df["pct"].apply(color_band)

    scale = alt.Scale(
        domain=["Alta (≥95%)","Media (85–94.9%)","Baja (<85%)"],
        range=["#22c55e","#f59e0b","#ef4444"]
    )

    # Altura dinámica: ~28px por materia (ajusta si quieres más compacto)
    chart_height = max(320, 28 * len(bar_df))

    # BARRAS HORIZONTALES (muestra nombres completos sin truncar)
    bars = alt.Chart(bar_df).mark_bar().encode(
        y=alt.Y("materia:N",
                sort="-x",
                axis=alt.Axis(title=None, labelLimit=10000)),  # sin truncar
        x=alt.X("pct:Q",
                title="Asistencia (%)",
                scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("nivel:N", scale=scale, legend=alt.Legend(title="Nivel")),
        tooltip=[
            alt.Tooltip("materia:N", title="Materia"),
            alt.Tooltip("pct:Q", title="% Asistencia", format=".1f"),
            alt.Tooltip("nivel:N", title="Nivel")
        ]
    ).properties(height=chart_height)

    # ETIQUETA DENTRO de la barra (alineada al extremo derecho)
    labels = alt.Chart(bar_df).mark_text(
        align="right", baseline="middle", dx=-6, color="white", fontWeight="bold"
    ).encode(
        y="materia:N",
        x="pct:Q",
        text=alt.Text("pct:Q", format=".1f")
    )

    st.altair_chart(bars + labels, use_container_width=True)

