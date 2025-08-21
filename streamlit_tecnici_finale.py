import streamlit as st
import pandas as pd
import numpy as np


# ==========================
# Helper & page appearance
# ==========================


def _ensure_series(x):
# Se x è un DataFrame (es. per colonne duplicate), prendi la prima colonna
if isinstance(x, pd.DataFrame):
if x.shape[1] == 0:
return pd.Series(dtype="string")
x = x.iloc[:, 0]
# Se non è una Series, converti a Series
if not isinstance(x, pd.Series):
return pd.Series(x, dtype="string")
return x


def _norm_tecnico(s) -> pd.Series:
s = _ensure_series(s)
s = s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
s = s.mask(s.isin(["", "NAN"]))
return s


st.set_page_config(layout="wide")
st.markdown(
"""
<style>
html, body, [data-testid="stApp"] { background-color: white !important; color: black !important; }
.stSelectbox div[data-baseweb="select"] { background-color: white !important; color: black !important; }
.stSelectbox span, .stSelectbox label { color: black !important; font-weight: 500; }
.stDataFrame, .stDataFrame table, .stDataFrame th, .stDataFrame td { background-color: white !important; color: black !important; }
.stButton > button { background-color: white !important; color: black !important; border: 1px solid #999 !important; border-radius: 6px; }
div[data-baseweb="radio"] label span { color: black !important; font-weight: 600 !important; }
header [data-testid="theme-toggle"] { display: none; }
</style>
""",
unsafe_allow_html=True,
)


st.title("📊 Avanzamento Produzione - Euroirte s.r.l.")
try:
st.image("LogoEuroirte.jpg", width=180)
except Exception:
pass
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")


# ==========================
# Loaders (GIACENZA & REWORKPD)
# ==========================


@st.cache_data(ttl=0)
def load_giacenza_full() -> pd.DataFrame:
"""
Legge giacenza.xlsx e restituisce colonne normalizzate:
Data (datetime), DataStr (dd/mm/YYYY), Tecnico (MAIUSC),
TT_iniziali (da colonna 'Giacenza iniziale'),
TT_lavorati (da colonna 'TT lavorati (esclusi codici G-M-P-S)').
"""
try:
g = pd.read_excel("giacenza.xlsx", dtype={"Tecnico": "string"})
except Exception as e:
st.error(f"Errore lettura giacenza.xlsx: {e}")
return pd.DataFrame(columns=["Data", "DataStr", "Tecnico", "TT_iniziali", "TT_lavorati"])


# Rinomina robusta
rename = {}
for c in g.columns:
k = str(c).strip().lower()
if k.startswith("data"):
rename[c] = "Data"
elif k.startswith("tecn"):
rename[c] = "Tecnico"
elif "giacenza" in k:
rename[c] = "Giacenza iniziale"
elif "tt lavorati" in k:
rename[c] = "TT lavorati (esclusi codici G-M-P-S)"
if rename:
g = g.rename(columns=rename)


req = {"Data", "Tecnico", "Giacenza iniziale", "TT lavorati (esclusi codici G-M-P-S)"}
for c in req - set(g.columns):
g[c] = 0


g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
g = g.dropna(subset=["Data"]).copy()
g["DataStr"] = g["Data"].dt.strftime("%d/%m/%Y")
g["Tecnico"] = _norm_tecnico(g["Tecnico"]).dropna()


st.dataframe(out, use_container_width=True)
