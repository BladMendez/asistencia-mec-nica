import time
import functools
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# --- Retry con backoff exponencial para manejar errores 429 ---
def with_backoff(max_retries=5, base=0.7):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except gspread.exceptions.APIError as e:
                    if "429" not in str(e):
                        raise
                    sleep_s = base * (2 ** i)
                    time.sleep(sleep_s)
            return fn(*args, **kwargs)
        return wrapper
    return deco

# --- Cachear cliente ---
@st.cache_resource
def get_gs_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["service_account"], scope)
    return gspread.authorize(creds)

# --- Cachear Spreadsheet ---
@st.cache_resource
def get_sheet(spreadsheet_name: str):
    client = get_gs_client()
    return client.open(spreadsheet_name)

# --- Leer worksheet como DataFrame ---
@st.cache_data(ttl=30, show_spinner=False)
@with_backoff()
def read_ws_df(spreadsheet_name: str, worksheet_title: str) -> pd.DataFrame:
    sh = get_sheet(spreadsheet_name)
    ws = sh.worksheet(worksheet_title)
    records = ws.get_all_records()
    return pd.DataFrame(records)
