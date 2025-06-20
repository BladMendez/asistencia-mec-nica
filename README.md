# Asistencia Mecánica

Aplicación web desarrollada con **Streamlit** para registrar y visualizar gráficas de asistencia de estudiantes. Incluye análisis por unidad, por alumno y a nivel grupal.

## Características principales

* Registro de asistencias sincronizado con Google Sheets
* Visualización de datos mediante gráficas interactivas:

  * Porcentaje de asistencia por unidad
  * Total de asistencias por alumno
  * Historial individual por alumno
  * Porcentaje general de asistencia de la materia
* Clasificación visual de asistencia (riesgo, aceptable, excelente)
* Protección de credenciales mediante archivo de configuración local

## Requisitos

* Python 3.8 o superior
* Acceso a una hoja de cálculo de Google
* Archivo de credenciales (`.streamlit/secrets.toml`, no incluido en este repositorio)

## Instalación

1. Clona este repositorio:

```bash
git clone https://github.com/BladMendez/asistencia-mec-nica.git
cd asistencia-mec-nica
```

2. Crea y activa un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

4. Agrega el archivo `.streamlit/secrets.toml` con tus credenciales:

```toml
[service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n..."
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/..."
universe_domain = "googleapis.com"
```

## Cómo ejecutar

```bash
streamlit run home.py
```

## Estructura del proyecto

```
asistencia-mecanica/
├── .streamlit/           # Archivos de configuración (omitidos en el repositorio)
├── pages/
│   ├── asistencia_app.py # Registro de asistencia
│   └── graficas.py       # Visualización de estadísticas
├── requirements.txt
├── .gitignore
└── README.md
```

## Seguridad

Este repositorio ignora los archivos sensibles como las credenciales del servicio. Asegúrate de mantenerlas fuera del control de versiones.

## Autor

Bladimir Méndez Villaseñor
Ingeniería Mecánica – ITESP
[bladimirmendezv@gmail.com](bladimirmendezv@gmail.com)
