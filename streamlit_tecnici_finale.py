
import streamlit as st
import pandas as pd
import numpy as np
import base64
from pathlib import Path

def set_page_background(image_path: str):
    """Imposta un'immagine di sfondo full-screen come background dell'app Streamlit."""
    p = Path(image_path)
    if not p.exists():
        st.warning(f"Background non trovato: {image_path}")
        return
    encoded = base64.b64encode(p.read_bytes()).decode()
    css = f"""
    <style>
    /* Contenitore principale */
    [data-testid="stAppViewContainer"] {{
        background: url("data:image/png;base64,{encoded}") center/cover no-repeat fixed;
    }}
    /* Header e Sidebar trasparenti */
    [data-testid="stHeader"], [data-testid="stSidebar"] {{
        background-color: rgba(255,255,255,0.0) !important;
    }}

    /* Colori testo di base scuri per contrasto sul bianco */
    html, body, [data-testid="stApp"] {{
        color: #0b1320 !important;
    }}

    /* “Card” bianche per leggibilità di tabelle, select ecc. */
    .stDataFrame, .stTable, .stSelectbox div[data-baseweb="select"],
    .stTextInput, .stNumberInput, .stDateInput, .stMultiSelect,
    .stRadio, .stCheckbox, .stSlider, .stFileUploader, .stTextArea {{
        background-color: rgba(255,255,255,0.88) !important;
        border-radius: 10px;
        backdrop-filter: blur(0.5px);
    }}

    /* Celle delle DataFrame: testo scuro su fondo chiaro */
    .stDataFrame table, .stDataFrame th, .stDataFrame td {{
        color: #0b1320 !important;
        background-color: rgba(255,255,255,0.0) !important; /* lasciamo il wrapper a fare il fondo */
    }}

    /* Pulsanti: stile chiaro con bordo */
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {{
        background-color: #ffffff !important;
        color: #0b1320 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

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

# --- COLORI PER SOGLIE ---
def _style_espletamento(s: pd.Series):
    out = []
    for v in s:
        if pd.isna(v): out.append("")
        elif v >= 0.80: out.append("background-color:#ccffcc")   # verde
        elif v >= 0.70: out.append("background-color:#fff3cd")   # giallo
        else: out.append("background-color:#ff9999")             # rosso
    return out

def _style_rework(s: pd.Series):
    out = []
    for v in s:
        if pd.isna(v): out.append("")
        elif v <= 0.05: out.append("background-color:#ccffcc")
        elif v <= 0.07: out.append("background-color:#fff3cd")
        else: out.append("background-color:#ff9999")
    return out

def _style_post(s: pd.Series):
    out = []
    for v in s:
        if pd.isna(v): out.append("")
        elif v <= 0.08: out.append("background-color:#ccffcc")
        elif v <= 0.09: out.append("background-color:#fff3cd")
        else: out.append("background-color:#ff9999")
    return out

st.set_page_config(layout="wide")
st.set_page_config(layout="wide")
set_page_background("sfondo.png")  # 👈 imposta lo sfondo

st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")
try:
    st.image("LogoEuroirte.png", width=180)
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
    TT_lavorati (da colonna 'TT lavorati').
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
            rename[c] = "TT lavorati"
    if rename:
        g = g.rename(columns=rename)

    req = {"Data", "Tecnico", "Giacenza iniziale", "TT lavorati"}
    for c in req - set(g.columns):
        g[c] = 0

    g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
    g = g.dropna(subset=["Data"]).copy()
    g["DataStr"] = g["Data"].dt.strftime("%d/%m/%Y")
    g["Tecnico"] = _norm_tecnico(g["Tecnico"]).dropna()

    
    g["Giacenza iniziale"] = pd.to_numeric(g["Giacenza iniziale"], errors="coerce").fillna(0)
    g["TT lavorati"] = pd.to_numeric(
        g["TT lavorati"], errors="coerce"
    ).fillna(0).astype(int)

    g = g.rename(columns={
        "Giacenza iniziale": "TT_iniziali",
        "TT lavorati": "TT_lavorati",
    })

    return g[["Data", "DataStr", "Tecnico", "TT_iniziali", "TT_lavorati"]]

def _pick_tecnico_assegnato_column(df: pd.DataFrame):
    # 1) preferisci match esatto (case-insensitive)
    for c in df.columns:
        if str(c).strip().lower() == "tecnico assegnato":
            return c
    # 2) contiene entrambe le parole
    candidates = [c for c in df.columns if "tecnico" in str(c).lower() and "assegn" in str(c).lower()]
    if candidates:
        nn = df[candidates].notna().sum().sort_values(ascending=False)
        return nn.index[0]
    return None

@st.cache_data(ttl=0)
def load_reworkpd() -> pd.DataFrame:
    """
    Legge reworkpd.xlsx e restituisce:
    Data (dalla colonna 'Data/Ora Arrivo Pratica'), Tecnico (da 'Tecnico Assegnato'), Rework (bool), PostDelivery (bool).
    """
    try:
        r = pd.read_excel("reworkpd.xlsx")
    except Exception as e:
        st.error(f"Errore lettura reworkpd.xlsx: {e}")
        return pd.DataFrame(columns=["Data", "Tecnico", "Rework", "PostDelivery"])

    # --- DATA: usa SOLO 'Data/Ora Arrivo Pratica' ---
    col_data = None
    for c in r.columns:
        if str(c).strip().lower() == "data/ora arrivo pratica":
            col_data = c
            break
    if col_data is None:
        for c in r.columns:
            if "arrivo" in str(c).lower() and "pratica" in str(c).lower():
                col_data = c
                break
    if col_data is not None:
        r["Data"] = pd.to_datetime(r[col_data], dayfirst=True, errors="coerce")
    else:
        r["Data"] = pd.NaT

    # --- TECNICO ASSEGNATO ---
    col_tecnico = _pick_tecnico_assegnato_column(r)
    if col_tecnico is None:
        st.warning("reworkpd.xlsx: colonna 'Tecnico Assegnato' non trovata.")
        r["Tecnico"] = pd.NA
    else:
        r["Tecnico"] = _norm_tecnico(r[col_tecnico])

    # --- FLAG booleane ---
    def _to_bool(x):
        if pd.isna(x):
            return False
        if isinstance(x, (int, float, np.integer, np.floating)):
            return bool(int(x))
        s = str(x).strip().lower()
        return s in ("true", "t", "si", "sì", "1", "y", "yes", "x")

    col_rework = None
    for c in r.columns:
        if str(c).strip().lower() == "rework":
            col_rework = c; break
    if col_rework is None:
        for c in r.columns:
            if "rework" in str(c).lower():
                col_rework = c; break

    col_post = None
    for c in r.columns:
        if str(c).strip().lower() in ("tt post delivery","post delivery"):
            col_post = c; break
    if col_post is None:
        for c in r.columns:
            cl = str(c).lower()
            if "post" in cl and "delivery" in cl:
                col_post = c; break

    r["Rework"] = r[col_rework].apply(_to_bool) if col_rework in r.columns else False
    r["PostDelivery"] = r[col_post].apply(_to_bool) if col_post in r.columns else False

    return r[["Data", "Tecnico", "Rework", "PostDelivery"]]

# ==========================
# Data sources
# ==========================

g = load_giacenza_full()
rw = load_reworkpd()

# Mesi IT
mesi_italiani = {1:"Gennaio",2:"Febbraio",3:"Marzo",4:"Aprile",5:"Maggio",6:"Giugno",7:"Luglio",8:"Agosto",9:"Settembre",10:"Ottobre",11:"Novembre",12:"Dicembre"}

g = g.assign(Mese=g["Data"].dt.month.map(mesi_italiani))
rw = rw.assign(Mese=rw["Data"].dt.month.map(mesi_italiani))

# ==========================
# Filtri
# ==========================
mesi_disponibili = sorted([m for m in g["Mese"].dropna().unique()])
mese_selezionato = st.selectbox("📆 Seleziona un mese:", ["Tutti i mesi"] + mesi_disponibili)

# tecnici = unione giacenza ∪ rework
tec_set = set(g["Tecnico"].dropna().unique()) | set(rw["Tecnico"].dropna().unique())
tecnici = ["Tutti"] + sorted(tec_set)


# --- COSTRUZIONE ELENCO DATE ORDINATO E FILTRATO PER MESE ---
# Garantiamo la presenza della colonna "Mese" (es. "Settembre")
if "Mese" not in g.columns:
    g["Mese"] = g["Data"].dt.strftime("%B").str.capitalize()

# Filtra le date in base al mese selezionato e ordinale cronologicamente (dal più vecchio al più recente)
if mese_selezionato != "Tutti i mesi":
    _date_list = (
        g.loc[g["Mese"] == mese_selezionato]
         .sort_values("Data")["DataStr"]
         .dropna()
         .unique()
         .tolist()
    )
else:
    _date_list = (
        g.sort_values("Data")["DataStr"]
         .dropna()
         .unique()
         .tolist()
    )

# Opzioni del menù a tendina
date_uniche = ["Tutte"] + _date_list

col1, col2 = st.columns(2)
filtro_data = col1.selectbox("📅 Seleziona una data:", date_uniche, index=0)
# <- qui era il refuso
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico:", tecnici)


# Applichiamo il filtro per mese e data, imponendo l'ordinamento cronologico
base_daily = g.copy()

if mese_selezionato != "Tutti i mesi":
    base_daily = base_daily[base_daily["Mese"] == mese_selezionato]

# Filtra per data selezionata
if filtro_data != "Tutte":
    base_daily = base_daily[base_daily["DataStr"] == filtro_data]

# Ordina dalla più vecchia alla più recente
base_daily = base_daily.sort_values(["Data", "Tecnico"], kind="stable").reset_index(drop=True)

# Mantieni anche una copia per riepilogo mensile (senza filtro data)
base_month = base_daily.copy()
# Applica filtri
base_daily = g.copy()
if mese_selezionato != "Tutti i mesi":
    base_daily = base_daily[base_daily["Mese"] == mese_selezionato]

base_month = base_daily.copy()  # per riepilogo mensile (no filtro data)

if filtro_tecnico != "Tutti":
    base_daily = base_daily[base_daily["Tecnico"] == filtro_tecnico]
    base_month = base_month[base_month["Tecnico"] == filtro_tecnico]

if filtro_data != "Tutte":
    base_daily = base_daily[base_daily["DataStr"] == filtro_data]

# ==========================
# 📆 Riepilogo Giornaliero (per Data e Tecnico)
# ==========================

if base_daily.empty:
    daily_tbl = pd.DataFrame(columns=[
        "Data", "Tecnico", "TT iniziali",
        "TT lavorati", "% espletamento"
    ])
else:
    daily_agg = (
        base_daily
        .groupby(["DataStr", "Tecnico"], as_index=False)
        .agg(
            TT_iniziali=("TT_iniziali", "sum"),
            TT_lavorati=("TT_lavorati", "sum"),
        )
    )
    daily_agg["% espletamento"] = np.where(
        daily_agg["TT_iniziali"].eq(0), 1.0,
        daily_agg["TT_lavorati"] / daily_agg["TT_iniziali"]
    )
    daily_tbl = daily_agg.rename(columns={
        "DataStr": "Data",
        "TT_lavorati": "TT lavorati",
    }).sort_values(["Data", "Tecnico"])

st.subheader("📆 Riepilogo Giornaliero")
st.dataframe(
    daily_tbl.style
        .format({"% espletamento": "{:.0%}"})               # percentuali intere
        .apply(_style_espletamento, subset=["% espletamento"]),  # colori
    use_container_width=True,
)

# ==========================
# 📅 Riepilogo Mensile per Tecnico (include tecnici solo in rework/post)
# ==========================

# TT dal file giacenza (può essere vuoto)
month_tt = (
    base_month.groupby("Tecnico", as_index=False).agg(
        TT_iniziali=("TT_iniziali", "sum"),
        TT_lavorati=("TT_lavorati", "sum"),
    )
    if not base_month.empty
    else pd.DataFrame(columns=["Tecnico", "TT_iniziali", "TT_lavorati"])
)

# Rework/Post filtrati per mese (da rw) e per eventuale tecnico selezionato
if mese_selezionato != "Tutti i mesi" and rw["Mese"].notna().any():
    rw_month = rw[rw["Mese"] == mese_selezionato].copy()
else:
    rw_month = rw.copy()

if filtro_tecnico != "Tutti":
    rw_month = rw_month[rw_month["Tecnico"] == filtro_tecnico]

rework_counts = (
    rw_month.groupby("Tecnico", as_index=False).agg(
        Rework=("Rework", "sum"),
        PostDelivery=("PostDelivery", "sum"),
    )
    if not rw_month.empty
    else pd.DataFrame(columns=["Tecnico", "Rework", "PostDelivery"])
)

# 👇 OUTER merge: tiene anche chi compare solo in rework/post
riepilogo = pd.merge(month_tt, rework_counts, on="Tecnico", how="outer").fillna(0)

# Percentuali
riepilogo["% espletamento"] = np.where(
    riepilogo["TT_iniziali"].eq(0), 1.0,
    riepilogo["TT_lavorati"] / riepilogo["TT_iniziali"]
)

den = riepilogo["TT_lavorati"].astype(float)

# Se den==0 e ci sono Rework/PD -> 100%, altrimenti 0%
riepilogo["% Rework"] = np.where(
    den > 0, riepilogo["Rework"] / den,
    np.where(riepilogo["Rework"] > 0, 1.0, 0.0)
)
riepilogo["% Post Delivery"] = np.where(
    den > 0, riepilogo["PostDelivery"] / den,
    np.where(riepilogo["PostDelivery"] > 0, 1.0, 0.0)
)

# Rename finale per l'output
riepilogo = riepilogo.rename(columns={
    "TT_iniziali": "TT iniziali",
    "TT_lavorati": "TT lavorati",
    "PostDelivery": "Post Delivery",
})

# Tipi interi sulle colonne di conteggio
for c in ["TT iniziali", "TT lavorati", "Rework", "Post Delivery"]:
    riepilogo[c] = pd.to_numeric(riepilogo[c], errors="coerce").fillna(0).astype(int)

# Colonna Mese e ordinamento
riepilogo.insert(0, "Mese", mese_selezionato if mese_selezionato != "Tutti i mesi" else "Tutti")
riepilogo = riepilogo.sort_values("Tecnico")

# ---- Stampa tabella mensile ----
st.subheader("📅 Riepilogo Mensile per Tecnico")
cols_order = [
    "Mese", "Tecnico",
    "TT iniziali", "TT lavorati", "% espletamento",
    "Rework", "% Rework", "Post Delivery", "% Post Delivery",
]

# Assicura la presenza di tutte le colonne anche se DF vuoto
for c in cols_order:
    if c not in riepilogo.columns:
        riepilogo[c] = 0 if c not in ("Mese", "Tecnico") else ""

df_out = riepilogo[cols_order]

if not df_out.empty:
    styled = (
        df_out.style
            .format({
                "% espletamento": "{:.0%}",
                "% Rework": "{:.0%}",
                "% Post Delivery": "{:.0%}",
            })
            .apply(_style_espletamento, subset=["% espletamento"])
            .apply(_style_rework, subset=["% Rework"])
            .apply(_style_post, subset=["% Post Delivery"])
    )
    st.dataframe(styled, use_container_width=True)
else:
    # Mostra comunque header/colonne quando non ci sono righe
    st.dataframe(df_out, use_container_width=True)
