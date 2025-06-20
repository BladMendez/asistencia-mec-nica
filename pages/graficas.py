import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# === CONFIGURACIÓN DE STREAMLIT ===
st.set_page_config(page_title="Gráficas de Asistencia", layout="wide")
st.title("📊 Visualización de Asistencia")

# === AUTORIZACIÓN DE GOOGLE SHEETS DESDE SECRETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)
client = gspread.authorize(creds)

# === SELECCIÓN DE MATERIA ===
SHEET_NAME = "Seguimiento_Asistencia_2025_2"
sh = client.open(SHEET_NAME)
materias = [ws.title for ws in sh.worksheets()]
materia = st.selectbox("Selecciona la materia", materias)

# === CARGAR DATOS ===
ws = sh.worksheet(materia)
df = pd.DataFrame(ws.get_all_records())

if df.empty:
    st.warning("No hay datos en esta materia.")
    st.stop()

# === EXTRAER COLUMNAS DE ASISTENCIA ===
asistencia_cols = [col for col in df.columns if col.startswith("Unidad")]
df_asistencia = df[["Nombre", "No de control"] + asistencia_cols]

# === CONVERTIR ✓ / ✗ A 1 / 0 ===
df_numeric = df_asistencia.copy()
for col in asistencia_cols:
    df_numeric[col] = df_numeric[col].apply(lambda x: 1 if x == "✓" else 0)

import re
from collections import defaultdict

# === AGRUPAR COLUMNAS POR NOMBRE DE UNIDAD ===
unidad_map = defaultdict(list)
patron = r"(Unidad \d+)"  # extrae "Unidad 1", "Unidad 2", etc.

for col in asistencia_cols:
    match = re.match(patron, col)
    if match:
        unidad_base = match.group(1)
        unidad_map[unidad_base].append(col)

# === CALCULAR EL PROMEDIO DE ASISTENCIA POR UNIDAD (agrupada) ===
df_numeric_grouped = pd.DataFrame()
df_numeric_grouped["Nombre"] = df["Nombre"]
df_numeric_grouped["No de control"] = df["No de control"]

for unidad, columnas in unidad_map.items():
    df_numeric_grouped[unidad] = df[columnas].applymap(lambda x: 1 if x == "✓" else 0).mean(axis=1) * 100



# === GRÁFICA 1: Porcentaje de asistencia por unidad (agrupado) ===
st.subheader("📊 Porcentaje de asistencia por unidad")

# Promedio de asistencia por unidad (agrupada)
porcentaje_por_unidad = df_numeric_grouped.drop(columns=["Nombre", "No de control"]).mean().reset_index()
porcentaje_por_unidad.columns = ["Unidad", "Porcentaje"]

# Clasificar con emojis y colores
def clasificar_unidad(p):
    if p < 70:
        return "🔴 Riesgo"
    elif p < 85:
        return "🟠 Aceptable"
    else:
        return "🟢 Excelente"

porcentaje_por_unidad["Estado"] = porcentaje_por_unidad["Porcentaje"].apply(clasificar_unidad)
porcentaje_por_unidad["Texto"] = porcentaje_por_unidad["Porcentaje"].round(1).astype(str) + "% " + porcentaje_por_unidad["Estado"]

fig1 = px.bar(
    porcentaje_por_unidad,
    x="Unidad",
    y="Porcentaje",
    color="Estado",
    text="Texto",
    title="Porcentaje de asistencia por unidad (agrupada)",
    color_discrete_map={
        "🔴 Riesgo": "red",
        "🟠 Aceptable": "orange",
        "🟢 Excelente": "green"
    },
    labels={"Porcentaje": "% Asistencia"}
)

fig1.update_traces(textposition='inside', textfont_color="white")
fig1.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig1, use_container_width=True)

# === GRÁFICA 2: Total por alumno ===
st.subheader("👥 Total de asistencias por alumno")

# Asegurarse de usar solo las columnas de asistencia (las que empiezan con "Unidad")
asistencia_cols_sin_info = [col for col in df_numeric_grouped.columns if col.startswith("Unidad")]

# Calcular total y porcentaje de asistencia
df_numeric_grouped["Total Alumno"] = df_numeric_grouped[asistencia_cols_sin_info].sum(axis=1)
# Ya que los valores están en porcentaje (0-100), no multiplicamos por 100 se multiplica por 1 o simplemente por nada 
df_numeric_grouped["% Asistencia"] = (df_numeric_grouped["Total Alumno"] / len(asistencia_cols_sin_info)) * 1

# Texto para la barra
df_numeric_grouped["Texto"] = df_numeric_grouped["% Asistencia"].round(1).astype(str) + "%"

# Clasificación por nivel de asistencia
def clasificar(asistencia):
    if asistencia <= 69:
        return "⚠️ En riesgo (< 70%)"
    elif asistencia < 85:
        return "🟠 Aceptable"
    else:
        return "🟢 Excelente"

df_numeric_grouped["Estado"] = df_numeric_grouped["% Asistencia"].apply(clasificar)
df_numeric_grouped["Texto"] = df_numeric_grouped["% Asistencia"].round(1).astype(str) + "%"

st.write("Data para gráfica:")
st.dataframe(df_numeric_grouped[["Nombre", "% Asistencia", "Texto", "Estado"]])


# Crear la gráfica
fig2 = px.bar(
    df_numeric_grouped,
    x="Nombre",
    y="% Asistencia",
    color="Estado",
    text="Texto",
    color_discrete_map={
        "⚠️ En riesgo (< 70%)": "red",
        "🟠 Aceptable": "orange",
        "🟢 Excelente": "green"
    },
    title="Porcentaje de asistencia por alumno",
    labels={"% Asistencia": "% Asistencia"}
)

fig2.update_traces(textposition='inside', textfont_color='white')
fig2.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig2, use_container_width=True)

# === GRÁFICA 3: Detalle por alumno ===
st.subheader("📈 Historial por alumno")
alumno = st.selectbox("Selecciona un alumno", df_numeric_grouped["Nombre"])
row = df_numeric_grouped[df_numeric_grouped["Nombre"] == alumno].set_index("Nombre")

# Extraer las columnas de unidad (excluyendo Nombre y No de control)
unidades = [col for col in df_numeric_grouped.columns if col.startswith("Unidad")]
valores = (row[unidades].values[0]) * 1  # Convertir 0/1 a porcentaje

# Clasificar con emojis
def clasificar_emoji(p):
    if p < 70:
        return "🔴 Riesgo"
    elif p < 85:
        return "🟠 Aceptable"
    else:
        return "🟢 Excelente"

detalle_df = pd.DataFrame({
    "Unidad": unidades,
    "Porcentaje": valores,
})
detalle_df["Estado"] = detalle_df["Porcentaje"].apply(clasificar_emoji)
detalle_df["Texto"] = detalle_df["Porcentaje"].round(1).astype(str) + "% " + detalle_df["Estado"]

fig3 = px.bar(
    detalle_df,
    x="Unidad",
    y="Porcentaje",
    color="Estado",
    text="Texto",
    title=f"Asistencia por unidad: {alumno}",
    color_discrete_map={
        "🔴 Riesgo": "red",
        "🟠 Aceptable": "orange",
        "🟢 Excelente": "green"
    },
    labels={"Porcentaje": "% Asistencia"}
)

fig3.update_traces(textposition='inside', textfont_color="white")
fig3.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig3, use_container_width=True)



# === GRÁFICA 4: Porcentaje general de asistencia de la materia ===
st.subheader("📊 Porcentaje general de asistencia de la materia")

# 1. Tomar columnas que contienen la palabra "Unidad"
unidad_cols = [col for col in df_numeric.columns if "Unidad" in col]

# 2. Calcular asistencias totales y posibles
total_asistencias = df_numeric[unidad_cols].sum().sum()
total_posibles = df_numeric.shape[0] * len(unidad_cols)
porcentaje_general = (total_asistencias / total_posibles) * 100

# 3. Clasificar visualmente
if porcentaje_general < 70:
    estado = "🔴 Riesgo"
    color = "red"
elif porcentaje_general < 85:
    estado = "🟠 Aceptable"
    color = "orange"
else:
    estado = "🟢 Excelente"
    color = "green"

# 4. Crear DataFrame para gráfica
porcentaje_df = pd.DataFrame({
    "Categoría": ["Materia"],
    "Porcentaje": [porcentaje_general],
    "Estado": [estado],
    "Texto": [f"{porcentaje_general:.1f}% {estado}"]
})

# 5. Gráfica de barra global
fig4 = px.bar(
    porcentaje_df,
    x="Categoría",
    y="Porcentaje",
    color="Estado",
    text="Texto",
    color_discrete_map={
        "🔴 Riesgo": "red",
        "🟠 Aceptable": "orange",
        "🟢 Excelente": "green"
    },
    title="Porcentaje general de asistencia en la materia",
    labels={"Porcentaje": "% Asistencia"}
)

fig4.update_traces(textposition="inside", textfont_color="white")
fig4.update_layout(yaxis_range=[0, 100])
st.plotly_chart(fig4, use_container_width=True)
