import streamlit as st
import pandas as pd

def _norm_tecnico(s: pd.Series) -> pd.Series:
    # stringa, trim, un solo spazio, maiuscolo
    s = s.astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
    # "" e "NAN" diventano NA veri
    s = s.mask(s.isin(["", "NAN"]))
    return s

st.set_page_config(layout="wide")

# Imposta sfondo bianco e testo nero
st.markdown("""
    <style>
    html, body, [data-testid="stApp"] {
        background-color: white !important;
        color: black !important;
    }
    .stSelectbox div[data-baseweb="select"] { background-color: white !important; color: black !important; }
    .stSelectbox span, .stSelectbox label { color: black !important; font-weight: 500; }
    .stDataFrame, .stDataFrame table, .stDataFrame th, .stDataFrame td { background-color: white !important; color: black !important; }
    .stButton > button { background-color: white !important; color: black !important; border: 1px solid #999 !important; border-radius: 6px; }
    div[data-baseweb="radio"] label span { color: black !important; font-weight: 600 !important; }
    header [data-testid="theme-toggle"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- Titolo ---
st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")
st.image("LogoEuroirte.jpg", width=180)
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")

# -------------------- Loader GIACENZA (locale) --------------------
@st.cache_data(ttl=0)
def load_giacenza():
    """
    Legge giacenza.xlsx locale e restituisce un DF aggregato per (DataStr, Tecnico)
    con la colonna 'TT iniziali'.
    Accetta nomi colonna tipo: 'Data', 'Tecnico', 'Giacenza iniziale'.
    """
    try:
        g = pd.read_excel("giacenza.xlsx", usecols=["Data", "Tecnico", "Giacenza iniziale"])
    except Exception:
        g = pd.read_excel("giacenza.xlsx")

    # rinomina robusta
    rename = {}
    for c in g.columns:
        k = str(c).strip().lower()
        if k.startswith("data"):
            rename[c] = "Data"
        elif k.startswith("tecn"):
            rename[c] = "Tecnico"
        elif "giacenza" in k:
            rename[c] = "Giacenza iniziale"
    if rename:
        g = g.rename(columns=rename)

    if not {"Data", "Tecnico", "Giacenza iniziale"}.issubset(g.columns):
        st.warning("Il file giacenza.xlsx non contiene le colonne attese: Data, Tecnico, Giacenza iniziale.")
        return pd.DataFrame(columns=["DataStr", "Tecnico", "TT iniziali"])

    g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
    g = g.dropna(subset=["Data"])
    g["Tecnico"] = (
        g["Tecnico"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
    )
    g["Giacenza iniziale"] = pd.to_numeric(g["Giacenza iniziale"], errors="coerce").fillna(0)
    g["DataStr"] = g["Data"].dt.strftime("%d/%m/%Y")
    g = g.groupby(["DataStr", "Tecnico"], as_index=False)["Giacenza iniziale"].sum()
    g = g.rename(columns={"Giacenza iniziale": "TT iniziali"})
    return g[["DataStr", "Tecnico", "TT iniziali"]]
    g["Tecnico"] = _norm_tecnico(g["Tecnico"])
    g = g.dropna(subset=["Tecnico"])

# -------------------- Loader ASSURANCE --------------------
@st.cache_data(ttl=0)
def load_data():
    df = pd.read_excel("assurance.xlsx", usecols=[
        "Data Esec. Lavoro",
        "Tecnico Assegnato",
        "Rework",
        "TT Post Delivery",
        "Ultimo Cod. Fine Disservizio"
    ])
    df.rename(columns={
        "Data Esec. Lavoro": "Data",
        "Tecnico Assegnato": "Tecnico",
        "TT Post Delivery": "PostDelivery",
        "Ultimo Cod. Fine Disservizio": "CodFine"
    }, inplace=True)

    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Data"])

    # Normalizza i nomi tecnici
    df["Tecnico"] = _norm_tecnico(df["Tecnico"])
    df = df.dropna(subset=["Tecnico"])

    # Flag e conteggio TT chiusi (lavorati)
    df["Produttivo"] = (
        (df["Rework"] != 1) &
        (df["PostDelivery"] != 1) &
        (~df["CodFine"].astype(str).str.upper().isin(["G", "M", "P", "S"]))
    )
    df["Totale"] = 1

    # Info ultimo aggiornamento
    ultima_data = df["Data"].max()
    if pd.notna(ultima_data):
        st.markdown(f"🕒 **Dati aggiornati al: {ultima_data.strftime('%d/%m/%Y')}**")

    return df

df = load_data()

# -------------------- Filtri --------------------
mesi_italiani = {1:"Gennaio",2:"Febbraio",3:"Marzo",4:"Aprile",5:"Maggio",6:"Giugno",7:"Luglio",8:"Agosto",9:"Settembre",10:"Ottobre",11:"Novembre",12:"Dicembre"}
df["Mese"] = df["Data"].apply(lambda x: f"{mesi_italiani[x.month]}")

mesi_disponibili = sorted(df["Mese"].unique())
mese_selezionato = st.selectbox("📆 Seleziona un mese:", ["Tutti i mesi"] + mesi_disponibili)

if mese_selezionato != "Tutti i mesi":
    df = df[df["Mese"] == mese_selezionato]

tecnici = ["Tutti"] + sorted(df["Tecnico"].dropna().unique().tolist())
date_uniche = ["Tutte"] + sorted(df["Data"].dropna().dt.strftime("%d/%m/%Y").unique().tolist())

col1, col2 = st.columns(2)
filtro_data = col1.selectbox("📅 Seleziona una data:", date_uniche)
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico:", tecnici)

df["DataStr"] = df["Data"].dt.strftime("%d/%m/%Y")
if filtro_data != "Tutte":
    df = df[df["DataStr"] == filtro_data]
if filtro_tecnico != "Tutti":
    df = df[df["Tecnico"] == filtro_tecnico]

# ======================================================================
# 📆 DETTAGLIO GIORNALIERO – con righe solo-giacenza e ordine colonne
# ======================================================================

# 1) Giornaliero dai TT chiusi (assurance)
daily = df.groupby([df["Data"].dt.strftime("%d/%m/%Y").rename("Data"), "Tecnico"]).agg(
    TotChiusure=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

# 2) Giacenze iniziali dal file locale
g_iniz = load_giacenza()   # DataStr, Tecnico, TT iniziali

# 3) Outer merge per includere anche tecnici con sola giacenza (nessun lavorato)
daily = daily.merge(
    g_iniz,
    left_on=["Data", "Tecnico"],
    right_on=["DataStr", "Tecnico"],
    how="outer"
)
daily["Data"] = daily["Data"].fillna(daily["DataStr"])
daily.drop(columns=["DataStr"], inplace=True)

# 4) Riempie NaN e calcola le colonne
for c in ["TotChiusure", "ReworkCount", "PostDeliveryCount", "ProduttiviCount", "TT iniziali"]:
    if c not in daily.columns:
        daily[c] = 0
    daily[c] = pd.to_numeric(daily[c], errors="coerce").fillna(0)

daily["TT lavorati"]     = daily["TotChiusure"]
daily["% espletamento"]  = (daily["TT lavorati"] / daily["TT iniziali"]).where(daily["TT iniziali"] > 0, 0.0)

den = daily["TT lavorati"].replace(0, pd.NA)
daily["% Rework"]        = (daily["ReworkCount"] / den).fillna(0)
daily["% PostDelivery"]  = (daily["PostDeliveryCount"] / den).fillna(0)
daily["% Produttivi"]    = (daily["ProduttiviCount"] / den).fillna(0)

# 4b) Forza interi sui contatori
daily["TT iniziali"]       = daily["TT iniziali"].fillna(0).astype(int)
daily["TT lavorati"]       = daily["TT lavorati"].fillna(0).astype(int)
daily["ReworkCount"]       = daily["ReworkCount"].fillna(0).astype(int)
daily["PostDeliveryCount"] = daily["PostDeliveryCount"].fillna(0).astype(int)
daily["ProduttiviCount"]   = daily["ProduttiviCount"].fillna(0).astype(int)

# 5) Ordine colonne (conteggi prima delle rispettive %)
ordine_giorno = [
    "Data", "Tecnico",
    "TT iniziali", "TT lavorati", "% espletamento",
    "ReworkCount", "% Rework",
    "PostDeliveryCount", "% PostDelivery",
    "ProduttiviCount", "% Produttivi",
]
for col in ordine_giorno:
    if col not in daily.columns:
        daily[col] = 0

daily_display = daily[ordine_giorno].sort_values(["Data", "Tecnico"]).reset_index(drop=True)

## -------- Soglie e colori (modificabili) --------
ESPL_GREEN   = 0.75   # >= 80% verde
ESPL_YELLOW  = 0.60   # 70–80% giallo, <70% rosso

REWORK_GREEN = 0.05   # <= 5% verde
REWORK_YELL  = 0.08   # 5–7% giallo,  >7% rosso

POST_GREEN   = 0.085  # <= 8.5% verde
POST_YELL    = 0.12   # 8.5–10% giallo, >10% rosso

PROD_GREEN   = 0.80   # >= 80% verde
PROD_YELL    = 0.65   # 70–80% giallo,  <70% rosso

COL_GREEN = '#ccffcc'
COL_YELL  = '#fff5ba'
COL_RED   = '#ff9999'

def _fmt_espl(v):
    try:
        if pd.isna(v): return ''
        if v >= ESPL_GREEN: return f'background-color: {COL_GREEN}'
        if v >= ESPL_YELLOW: return f'background-color: {COL_YELL}'
        return f'background-color: {COL_RED}'
    except: return ''

def _fmt_rework(v):
    try:
        if pd.isna(v): return ''
        if v <= REWORK_GREEN: return f'background-color: {COL_GREEN}'
        if v <= REWORK_YELL:  return f'background-color: {COL_YELL}'
        return f'background-color: {COL_RED}'
    except: return ''

def _fmt_post(v):
    try:
        if pd.isna(v): return ''
        if v <= POST_GREEN: return f'background-color: {COL_GREEN}'
        if v <= POST_YELL:  return f'background-color: {COL_YELL}'
        return f'background-color: {COL_RED}'
    except: return ''

def _fmt_prod(v):
    try:
        if pd.isna(v): return ''
        if v >= PROD_GREEN: return f'background-color: {COL_GREEN}'
        if v >= PROD_YELL:  return f'background-color: {COL_YELL}'
        return f'background-color: {COL_RED}'
    except: return ''

# 7) Render Giornaliero
st.subheader("📆 Dettaglio Giornaliero")
style_day = (
    daily_display.style
        .format({
            "% espletamento": "{:.2%}",
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
        })
        .applymap(_fmt_espl,   subset=["% espletamento"])
        .applymap(_fmt_rework, subset=["% Rework"])
        .applymap(_fmt_post,   subset=["% PostDelivery"])
        .applymap(_fmt_prod,   subset=["% Produttivi"])
)
st.dataframe(style_day, use_container_width=True)

# ======================================================================
# 📅 RIEPILOGO MENSILE PER TECNICO – stessa logica/visualizzazione
# ======================================================================

# Aggrega dal giornaliero (già contiene TT iniziali/lavorati e i conteggi)
riepilogo = daily.groupby("Tecnico").agg(
    TT_iniziali=("TT iniziali", "sum"),
    TT_lavorati=("TT lavorati", "sum"),
    ReworkCount=("ReworkCount", "sum"),
    PostDeliveryCount=("PostDeliveryCount", "sum"),
    ProduttiviCount=("ProduttiviCount", "sum"),
).reset_index()

# Percentuali mensili
den_m = riepilogo["TT_lavorati"].replace(0, pd.NA)
riepilogo["% espletamento"] = (riepilogo["TT_lavorati"] / riepilogo["TT_iniziali"]).where(riepilogo["TT_iniziali"] > 0, 0.0)
riepilogo["% Rework"]       = (riepilogo["ReworkCount"] / den_m).fillna(0)
riepilogo["% PostDelivery"] = (riepilogo["PostDeliveryCount"] / den_m).fillna(0)
riepilogo["% Produttivi"]   = (riepilogo["ProduttiviCount"] / den_m).fillna(0)

# Forza interi sui contatori mensili
riepilogo["TT_iniziali"]       = riepilogo["TT_iniziali"].fillna(0).astype(int)
riepilogo["TT_lavorati"]       = riepilogo["TT_lavorati"].fillna(0).astype(int)
riepilogo["ReworkCount"]       = riepilogo["ReworkCount"].fillna(0).astype(int)
riepilogo["PostDeliveryCount"] = riepilogo["PostDeliveryCount"].fillna(0).astype(int)
riepilogo["ProduttiviCount"]   = riepilogo["ProduttiviCount"].fillna(0).astype(int)

# Ordine colonne mensile (conteggi prima delle %)
ordine_mese = [
    "Tecnico",
    "TT_iniziali", "TT_lavorati", "% espletamento",
    "ReworkCount", "% Rework",
    "PostDeliveryCount", "% PostDelivery",
    "ProduttiviCount", "% Produttivi",
]
for col in ordine_mese:
    if col not in riepilogo.columns:
        riepilogo[col] = 0

riepilogo_display = riepilogo[ordine_mese].sort_values(["Tecnico"]).reset_index(drop=True)

# Render Mensile
st.subheader("📅 Riepilogo Mensile per Tecnico")
style_month = (
    riepilogo_display.style
        .format({
            "% espletamento": "{:.2%}",
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
        })
        .applymap(_fmt_espl,   subset=["% espletamento"])
        .applymap(_fmt_rework, subset=["% Rework"])
        .applymap(_fmt_post,   subset=["% PostDelivery"])
        .applymap(_fmt_prod,   subset=["% Produttivi"])
)
st.dataframe(style_month, use_container_width=True)
