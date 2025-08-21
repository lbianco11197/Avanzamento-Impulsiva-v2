
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
    """
    Legge giacenza.xlsx e restituisce colonne normalizzate:
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

    return g[["Data", "DataStr", "Tecnico", "TT_iniziali", "TT_lavorati"]]

@st.cache_data(ttl=0)
def load_reworkpd() -> pd.DataFrame:
    """
    Legge reworkpd.xlsx e restituisce:
    Data (se presente), Tecnico (da 'Tecnico Assegnato'), Rework (bool), PostDelivery (bool).
    """
    try:
        r = pd.read_excel("reworkpd.xlsx")
    except Exception as e:
        st.error(f"Errore lettura reworkpd.xlsx: {e}")
        return pd.DataFrame(columns=["Data", "Tecnico", "Rework", "PostDelivery"])    

    # Rinomina robusta
    rename = {}
    for c in r.columns:
        k = str(c).strip().lower()
        if k.startswith("data"):
            rename[c] = "Data"
        elif "tecnico" in k:
            rename[c] = "Tecnico Assegnato"
        elif k in ("rework", "rework?", "is_rework"):
            rename[c] = "Rework"
        elif "post" in k:
            rename[c] = "TT Post Delivery"
    if rename:
        r = r.rename(columns=rename)

    # Colonne minime attese
    if "Tecnico Assegnato" not in r.columns:
        st.warning("reworkpd.xlsx: colonna 'Tecnico Assegnato' mancante. Impossibile calcolare rework/post-delivery.")
        r["Tecnico Assegnato"] = np.nan

    # Parse date se presente
    if "Data/Ora Arrivo Pratica" in r.columns:
        r["Data"] = pd.to_datetime(r["Data/Ora Arrivo Pratica"], dayfirst=True, errors="coerce")
    else:
        r["Data"] = pd.NaT

    # Normalizza tecnico
    r["Tecnico"] = _norm_tecnico(r["Tecnico Assegnato"])

    # Booleans robusti
    def _to_bool(x):
        if pd.isna(x):
            return False
        if isinstance(x, (int, float)):
            return bool(int(x))
        s = str(x).strip().lower()
        return s in ("true", "t", "si", "sì", "1", "y", "yes")

    r["Rework"] = r.get("Rework", False).apply(_to_bool)
    r["PostDelivery"] = r.get("TT Post Delivery", False).apply(_to_bool)

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
# Filtri (immutati nella UX)
# ==========================

mesi_disponibili = sorted([m for m in g["Mese"].dropna().unique()])
mese_selezionato = st.selectbox("📆 Seleziona un mese:", ["Tutti i mesi"] + mesi_disponibili)

tecnici = ["Tutti"] + sorted(g["Tecnico"].dropna().unique().tolist())
date_uniche = ["Tutte"] + sorted(g["DataStr"].unique().tolist())

col1, col2 = st.columns(2)
filtro_data = col1.selectbox("📅 Seleziona una data:", date_uniche)
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico:", tecnici)

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
# 📆 Riepilogo Giornaliero (4 colonne)
# ==========================

# Aggrega (dopo filtri) SOLO per Data, sommando su tecnici eventualmente selezionati
if base_daily.empty:
    daily_tbl = pd.DataFrame(columns=["Data", "TT iniziali", "TT lavorati (esclusi codici G-M-P-S)", "% espletamento"])
else:
    daily_agg = base_daily.groupby("DataStr", as_index=False).agg(
        TT_iniziali=("TT_iniziali", "sum"),
        TT_lavorati=("TT_lavorati", "sum"),
    )
    daily_agg["% espletamento"] = np.where(
        daily_agg["TT_iniziali"].eq(0), 1.0, daily_agg["TT_lavorati"] / daily_agg["TT_iniziali"]
    )
    daily_tbl = daily_agg.rename(
        columns={
            "DataStr": "Data",
            "TT_lavorati": "TT lavorati (esclusi codici G-M-P-S)",
        }
    )

st.subheader("📆 Riepilogo Giornaliero")
st.dataframe(
    daily_tbl.style.format({"% espletamento": "{:.1%}"}),
    use_container_width=True,
)

# ==========================
# 📅 Riepilogo Mensile per Tecnico (con Rework / Post Delivery)
# ==========================

# 1) Somma per Tecnico nel mese corrente (o su tutti i mesi se selezionato "Tutti i mesi")
if base_month.empty:
    riepilogo = pd.DataFrame(columns=[
        "Mese", "Tecnico", "TT iniziali", "TT lavorati (esclusi codici G-M-P-S)", "% espletamento",
        "Rework", "% Rework", "Post Delivery", "% Post Delivery",
    ])
else:
    # TT dal file giacenza
    month_tt = base_month.groupby("Tecnico", as_index=False).agg(
        TT_iniziali=("TT_iniziali", "sum"),
        TT_lavorati=("TT_lavorati", "sum"),
    )

    # Seleziona righe rework del mese (se il mese è selezionato e la data è disponibile)
    if mese_selezionato != "Tutti i mesi" and rw["Mese"].notna().any():
        rw_month = rw[rw["Mese"] == mese_selezionato]
    else:
        rw_month = rw.copy()

    # Applica eventualmente filtro tecnico
    if filtro_tecnico != "Tutti":
        rw_month = rw_month[rw_month["Tecnico"] == filtro_tecnico]

    # Conteggi per tecnico
    rework_counts = rw_month.groupby("Tecnico", as_index=False).agg(
        Rework=("Rework", "sum"),
        PostDelivery=("PostDelivery", "sum"),
    ) if not rw_month.empty else pd.DataFrame(columns=["Tecnico", "Rework", "PostDelivery"])

    # Merge e percentuali
    riepilogo = month_tt.merge(rework_counts, on="Tecnico", how="left").fillna(0)
    riepilogo["% espletamento"] = np.where(
        riepilogo["TT_iniziali"].eq(0), 1.0, riepilogo["TT_lavorati"] / riepilogo["TT_iniziali"]
    )
    den = riepilogo["TT_lavorati"].replace(0, pd.NA)
    riepilogo["% Rework"] = (riepilogo["Rework"] / den).fillna(0)
    riepilogo["% Post Delivery"] = (riepilogo["Post Delivery"] / den).fillna(0)

    # Ordine colonne & tipi
    riepilogo = riepilogo.rename(columns={
        "TT_iniziali": "TT iniziali",
        "TT_lavorati": "TT lavorati (esclusi codici G-M-P-S)",
    })

    for c in ["TT iniziali", "TT lavorati (esclusi codici G-M-P-S)", "Rework", "Post Delivery"]:
        riepilogo[c] = riepilogo[c].fillna(0).astype(int)

    riepilogo.insert(0, "Mese", mese_selezionato if mese_selezionato != "Tutti i mesi" else "Tutti")

st.subheader("📅 Riepilogo Mensile per Tecnico")
cols_order = [
    "Mese", "Tecnico", "TT iniziali", "TT lavorati (esclusi codici G-M-P-S)", "% espletamento",
    "Rework", "% Rework", "Post Delivery", "% Post Delivery",
]
# Assicura colonne anche se DF vuoto
for c in cols_order:
    if c not in locals().get("riepilogo", pd.DataFrame()).columns.tolist() if "riepilogo" in locals() else []:
        pass  # handled after creation below

if "riepilogo" not in locals():
    riepilogo = pd.DataFrame(columns=cols_order)

# Stampa tabella
st.dataframe(
    riepilogo[cols_order].sort_values("Tecnico") if not riepilogo.empty else riepilogo,
    use_container_width=True,
)

# Applica formattazione percentuali dopo il render (Streamlit non supporta style su df vuoto facilmente)
if not riepilogo.empty:
    st.dataframe(
        riepilogo[cols_order].sort_values("Tecnico").style.format({
            "% espletamento": "{:.1%}",
            "% Rework": "{:.1%}",
            "% Post Delivery": "{:.1%}",
        }),
        use_container_width=True,
    )
