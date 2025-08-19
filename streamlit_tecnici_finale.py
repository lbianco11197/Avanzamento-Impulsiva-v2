import streamlit as st
import pandas as pd
import requests, base64, io
from datetime import datetime

st.set_page_config(layout="wide")

# ---------- STILE ----------
st.markdown("""
    <style>
    html, body, [data-testid="stApp"] { background-color: white !important; color: black !important; }
    .stSelectbox div[data-baseweb="select"] { background-color: white !important; color: black !important; }
    .stSelectbox span, .stSelectbox label { color: black !important; font-weight: 500; }
    .stDataFrame, .stDataFrame table, .stDataFrame th, .stDataFrame td { background-color: white !important; color: black !important; }
    .stButton > button { background-color: white !important; color: black !important; border: 1px solid #999 !important; border-radius: 6px; }
    div[data-baseweb="radio"] label span { color: black !important; font-weight: 600 !important; }
    header [data-testid="theme-toggle"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# ---------- HEADER ----------
st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")
st.image("LogoEuroirte.jpg", width=180)
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")

# ---------- UTILS ----------
def pulisci_tecnici(df: pd.DataFrame) -> pd.DataFrame:
    if "Tecnico" not in df.columns:
        return df
    df["Tecnico"] = (
        df["Tecnico"].astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )
    df = df[df["Tecnico"].notna() & (df["Tecnico"] != "") & (df["Tecnico"] != "NAN")]
    return df

def parse_giacenze_excel(file_like) -> pd.DataFrame:
    """Parsa un Excel di giacenze con colonne: Data | Tecnico | Giacenza"""
    g = pd.read_excel(file_like)
    rename = {}
    for c in g.columns:
        key = str(c).strip().lower().replace(" ", "")
        if key.startswith("data"):      rename[c] = "Data"
        elif key.startswith("tecnico"): rename[c] = "Tecnico"
        elif key.startswith("giac"):    rename[c] = "Giacenza"
    if rename: g = g.rename(columns=rename)
    if not set(["Data","Tecnico","Giacenza"]).issubset(g.columns):
        return pd.DataFrame(columns=["Data","Tecnico","Giacenza"])
    g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
    g = g.dropna(subset=["Data"])
    g = pulisci_tecnici(g)
    g["Giacenza"] = pd.to_numeric(g["Giacenza"], errors="coerce").fillna(0).astype("Int64")
    # consolida eventuali duplicati per (Data, Tecnico)
    g = g.groupby(["Data","Tecnico"], as_index=False)["Giacenza"].sum()
    return g[["Data","Tecnico","Giacenza"]]

# ---------- GITHUB READ-ONLY ----------
def gh_headers():
    token = st.secrets.get("GITHUB_TOKEN", None)
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h

def gh_paths():
    repo   = st.secrets.get("GIACENZA_REPO")   # es. "owner/repo"
    path   = st.secrets.get("GIACENZA_PATH")   # es. "giacenze.xlsx" o "cartella/giacenze.xlsx"
    branch = st.secrets.get("GIACENZA_BRANCH", "main")
    return repo, path, branch

@st.cache_data(ttl=300, show_spinner=False)
def load_giacenze_from_github() -> pd.DataFrame:
    repo, path, branch = gh_paths()
    if not (repo and path):
        return pd.DataFrame(columns=["Data","Tecnico","Giacenza"])
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        r = requests.get(url, headers=gh_headers(), params={"ref": branch}, timeout=30)
        if r.status_code == 404:
            return pd.DataFrame(columns=["Data","Tecnico","Giacenza"])
        r.raise_for_status()
        j = r.json()
        if j.get("encoding") != "base64" or not j.get("content"):
            return pd.DataFrame(columns=["Data","Tecnico","Giacenza"])
        xls_bytes = base64.b64decode(j["content"])
        return parse_giacenze_excel(io.BytesIO(xls_bytes))
    except Exception:
        return pd.DataFrame(columns=["Data","Tecnico","Giacenza"])

# ---------- ASSURANCE ----------
@st.cache_data(ttl=0)
def load_assurance() -> pd.DataFrame:
    df = pd.read_excel("assurance.xlsx", usecols=[
        "Data Esec. Lavoro",
        "Tecnico Assegnato",
        "Rework",
        "TT Post Delivery",
        "Ultimo Cod. Fine Disservizio"
    ])
    df = df.rename(columns={
        "Data Esec. Lavoro": "Data",
        "Tecnico Assegnato": "Tecnico",
        "TT Post Delivery": "PostDelivery",
        "Ultimo Cod. Fine Disservizio": "CodFine"
    })
    df["Data"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Data"])
    df = pulisci_tecnici(df)

    df["Produttivo"] = (
        (df["Rework"] != 1) &
        (df["PostDelivery"] != 1) &
        (~df["CodFine"].astype(str).str.upper().isin(["G", "M", "P", "S"]))
    )
    df["Totale"] = 1  # TT chiusi nel giorno → useremo come "TT assegnati"
    return df

# Pulsante refresh cache
if st.button("🔄 Aggiorna dati dal repo"):
    st.cache_data.clear()

df  = load_assurance()
gdf = load_giacenze_from_github()
if gdf.empty:
    st.info("Giacenze non trovate nel repo GitHub (o secrets non configurati). Uso giacenza = 0.")
    df["Giacenza"] = 0
else:
    df = df.merge(gdf, on=["Data","Tecnico"], how="left")
    df["Giacenza"] = df["Giacenza"].fillna(0)

# Info data ultimo record assurance
ultima_data = df["Data"].max()
if pd.notna(ultima_data):
    st.markdown(f"🕒 **Dati aggiornati al: {ultima_data.strftime('%d/%m/%Y')}**")

# ---------- FILTRI ----------
mesi_italiani = {1:"Gennaio",2:"Febbraio",3:"Marzo",4:"Aprile",5:"Maggio",6:"Giugno",7:"Luglio",8:"Agosto",9:"Settembre",10:"Ottobre",11:"Novembre",12:"Dicembre"}
df["Mese"] = df["Data"].dt.month.map(mesi_italiani)

mese_selezionato = st.selectbox("📆 Seleziona un mese:", ["Tutti i mesi"] + sorted(df["Mese"].dropna().unique().tolist()))
if mese_selezionato != "Tutti i mesi":
    df = df[df["Mese"] == mese_selezionato]

tecnici = ["Tutti"] + sorted(df["Tecnico"].dropna().unique().tolist())
date_uniche = ["Tutte"] + sorted(df["Data"].dropna().dt.strftime("%d/%m/%Y").unique().tolist())

col1, col2 = st.columns(2)
filtro_data    = col1.selectbox("📅 Seleziona una data:", date_uniche)
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico:", tecnici)

df["DataStr"] = df["Data"].dt.strftime("%d/%m/%Y")
if filtro_data != "Tutte":
    df = df[df["DataStr"] == filtro_data]
if filtro_tecnico != "Tutti":
    df = df[df["Tecnico"] == filtro_tecnico]

# ---------- SEMAFORICA ----------
def color_semaforo(val, tipo):
    try:
        if pd.isna(val): return ''
        if tipo == "rework":
            return 'background-color: #ccffcc' if val <= 0.05 else 'background-color: #ff9999'
        elif tipo == "postdelivery":
            return 'background-color: #ccffcc' if val <= 0.085 else 'background-color: #ff9999'
        elif tipo == "produttivi":
            return 'background-color: #ccffcc' if val >= 0.80 else 'background-color: #ff9999'
        elif tipo == "espletamento":
            return 'background-color: #ccffcc' if val >= 0.75 else 'background-color: #ff9999'
        return ''
    except:
        return ''

# ---------- 📆 DETTAGLIO GIORNALIERO ----------
daily = df.groupby([df["Data"].dt.strftime("%d/%m/%Y").rename("Data"), "Tecnico"]).agg(
    GiacenzaIniziale=("Giacenza", "max"),   # una riga per (Data, Tecnico)
    TotChiusure=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

# Nuove colonne richieste
daily["TT assegnati"]   = daily["TotChiusure"].fillna(0).astype("Int64")
daily["TT gestiti"]     = (daily["GiacenzaIniziale"].fillna(0) + daily["TT assegnati"]).astype("Int64")
daily["% Espletamento"] = (daily["TT assegnati"] / daily["TT gestiti"]).where(daily["TT gestiti"] > 0, 0.0)

# Percentuali classiche sui TT assegnati (chiusi)
den = daily["TT assegnati"].replace(0, pd.NA)
daily["% Rework"]       = (daily["ReworkCount"] / den).fillna(0)
daily["% PostDelivery"] = (daily["PostDeliveryCount"] / den).fillna(0)
daily["% Produttivi"]   = (daily["ProduttiviCount"] / den).fillna(0)

# Nascondi colonne di servizio
daily = daily.drop(columns=["TotChiusure", "GiacenzaIniziale"], errors="ignore")

st.subheader("📆 Dettaglio Giornaliero")
st.dataframe(
    daily.style
        .format({
            "% Espletamento": "{:.2%}",
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
        })
        .applymap(lambda v: color_semaforo(v, "espletamento"), subset=["% Espletamento"])
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)

# ---------- 📅 RIEPILOGO MENSILE PER TECNICO ----------
riepilogo = daily.groupby("Tecnico").agg(
    TT_assegnati=("TT assegnati", "sum"),
    TT_gestiti=("TT gestiti", "sum"),
    ReworkCount=("ReworkCount", "sum"),
    PostDeliveryCount=("PostDeliveryCount", "sum"),
    ProduttiviCount=("ProduttiviCount", "sum")
).reset_index()

den_m = riepilogo["TT_assegnati"].replace(0, pd.NA)
riepilogo["% Espletamento"] = (riepilogo["TT_assegnati"] / riepilogo["TT_gestiti"]).where(riepilogo["TT_gestiti"] > 0, 0.0)
riepilogo["% Rework"]       = (riepilogo["ReworkCount"] / den_m).fillna(0)
riepilogo["% PostDelivery"] = (riepilogo["PostDeliveryCount"] / den_m).fillna(0)
riepilogo["% Produttivi"]   = (riepilogo["ProduttiviCount"] / den_m).fillna(0)

st.subheader("📅 Riepilogo Mensile per Tecnico")
st.dataframe(
    riepilogo.style
        .format({
            "% Espletamento": "{:.2%}",
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
        })
        .applymap(lambda v: color_semaforo(v, "espletamento"), subset=["% Espletamento"])
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)
