import streamlit as st
import pandas as pd
import numpy as np


# ==========================
# Helper & page appearance
# ==========================


def _norm_tecnico(s: pd.Series) -> pd.Series:
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
st.image("LogoEuroirte.jpg", width=180)
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")


# ==========================
# Loaders (GIACENZA & REWORKPD)
# ==========================


@st.cache_data(ttl=0)
def load_giacenza_full() -> pd.DataFrame:
"""Legge giacenza.xlsx e restituisce colonne normalizzate:
Data (datetime), DataStr (dd/mm/YYYY), Tecnico (MAIUSC),
TT_iniziali (da colonna 'Giacenza iniziale'),
TT_lavorati (da colonna 'TT lavorati (esclusi codici G-M-P-S)').
"""
try:
g = pd.read_excel(
"giacenza.xlsx",
dtype={"Tecnico": "string"},
)
except Exception as e:
st.error(f"Errore lettura giacenza.xlsx: {e}")
return pd.DataFrame(columns=["Data", "DataStr", "Tecnico", "TT_iniziali", "TT_lavorati"])


# Rinomina robusta
rename = {}
for c in g.columns:
k = str(c).strip().lower()
if k.startswith("data"): rename[c] = "Data"
elif k.startswith("tecn"): rename[c] = "Tecnico"
elif "giacenza" in k: rename[c] = "Giacenza iniziale"
elif "tt lavorati" in k: rename[c] = "TT lavorati (esclusi codici G-M-P-S)"
if rename:
g = g.rename(columns=rename)


req = {"Data", "Tecnico", "Giacenza iniziale", "TT lavorati (esclusi codici G-M-P-S)"}
if not req.issubset(set(g.columns)):
st.warning(
"Il file giacenza.xlsx non contiene tutte le colonne attese: "
"Data, Tecnico, Giacenza iniziale, TT lavorati (esclusi codici G-M-P-S)."
)
# Prova a continuare con le colonne presenti
for c in req - set(g.columns):
g[c] = 0


g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
g = g.dropna(subset=["Data"]).copy()
g["DataStr"] = g["Data"].dt.strftime("%d/%m/%Y")
g["Tecnico"] = _norm_tecnico(g["Tecnico"]).dropna()


g["Giacenza iniziale"] = pd.to_numeric(g["Giacenza iniziale"], errors="coerce").fillna(0)
g["TT lavorati (esclusi codici G-M-P-S)"] = pd.to_numeric(
g["TT lavorati (esclusi codici G-M-P-S)"], errors="coerce"
).fillna(0)


g = g.rename(
columns={
"Giacenza iniziale": "TT_iniziali",
"TT lavorati (esclusi codici G-M-P-S)": "TT_lavorati",
}
)
