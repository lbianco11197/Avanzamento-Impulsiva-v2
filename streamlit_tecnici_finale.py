import streamlit as st
import pandas as pd
import requests, base64, io  # per caricare giacenze da repo esterno

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

# --- Titolo / header ---
st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")
st.image("LogoEuroirte.jpg", width=180)
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")

# -------------------------------
# Utils: normalizza/elimina tecnici vuoti
# -------------------------------
def pulisci_tecnici(df: pd.DataFrame) -> pd.DataFrame:
    if "Tecnico" not in df.columns:
        return df
    df["Tecnico"] = (
        df["Tecnico"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )
    df = df[df["Tecnico"].notna() & (df["Tecnico"] != "") & (df["Tecnico"] != "NAN")]
    return df

# -------------------------------
# Loader GIACENZE: locale -> repo esterno (via secrets)
# Secrets attesi (opzionali):
#   GIACENZA_REPO = "owner/repo"
#   GIACENZA_PATH = "path/in/repo/giacenze.xlsx"
#   github_token  = "ghp_xxx"   (opzionale ma consigliato)
# -------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_giacenze() -> pd.DataFrame:
    # 1) tenta file locale
    try:
        g = pd.read_excel("giacenze.xlsx")
        g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
        g = g.dropna(subset=["Data"])
        g = pulisci_tecnici(g)
        if "Giacenza" not in g.columns:
            raise ValueError("Manca la colonna 'Giacenza'")
        g["Giacenza"] = pd.to_numeric(g["Giacenza"], errors="coerce").fillna(0).astype("Int64")
        return g[["Data", "Tecnico", "Giacenza"]]
    except Exception:
        pass

    # 2) tenta repo esterno via API GitHub
    repo  = st.secrets.get("GIACENZA_REPO", None)
    path  = st.secrets.get("GIACENZA_PATH", None)
    token = st.secrets.get("github_token", None)

    if not repo or not path:
        # nessun errore bloccante: procederemo con giacenza=0
        return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        j = r.json()
        content = j.get("content")
        encoding = j.get("encoding")
        if not content or encoding != "base64":
            return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])
        xls_bytes = base64.b64decode(content)
        g = pd.read_excel(io.BytesIO(xls_bytes))
        g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
        g = g.dropna(subset=["Data"])
        g = pulisci_tecnici(g)
        if "Giacenza" not in g.columns:
            return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])
        g["Giacenza"] = pd.to_numeric(g["Giacenza"], errors="coerce").fillna(0).astype("Int64")
        return g[["Data", "Tecnico", "Giacenza"]]
    except Exception:
        return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])

# -------------------------------
# Loader principale
# -------------------------------
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
    df = pulisci_tecnici(df)

    # Merge con GIACENZE (Data, Tecnico)
    g = load_giacenze()
    if g.empty:
        st.info("Giacenze non trovate (file locale o secrets non configurati). Si assume giacenza=0.")
        df["Giacenza"] = 0
    else:
        df = df.merge(g, on=["Data", "Tecnico"], how="left")
        df["Giacenza"] = df["Giacenza"].fillna(0)

    # Flag produttivo e contatori
    df["Produttivo"] = (
        (df["Rework"] != 1) &
        (df["PostDelivery"] != 1) &
        (~df["CodFine"].astype(str).str.upper().isin(["G", "M", "P", "S"]))
    )
    df["Totale"] = 1  # TT chiusi (assegnati nel giorno)
    return df

df = load_data()

# Ultima data
ultima_data = df["Data"].max()
if pd.notna(ultima_data):
    st.markdown(f"🕒 **Dati aggiornati al: {ultima_data.strftime('%d/%m/%Y')}**")

# Mesi IT
mesi_italiani = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}
df["Mese"] = df["Data"].dt.month.map(mesi_italiani)

# --- Filtri ---
mesi_disponibili = sorted(df["Mese"].dropna().unique().tolist())
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

# -------------------------------
# Semaforica (come prima)
# -------------------------------
def color_semaforo(val, tipo):
    try:
        if pd.isna(val):
            return ''
        if tipo == "rework":
            return 'background-color: #ccffcc' if val <= 0.05 else 'background-color: #ff9999'
        elif tipo == "postdelivery":
            return 'background-color: #ccffcc' if val <= 0.085 else 'background-color: #ff9999'
        elif tipo == "produttivi":
            return 'background-color: #ccffcc' if val >= 0.80 else 'background-color: #ff9999'
        return ''
    except:
        return ''

# -------------------------------
# 📆 Dettaglio Giornaliero
# -------------------------------
daily = df.groupby([df["Data"].dt.strftime("%d/%m/%Y").rename("Data"), "Tecnico"]).agg(
    GiacenzaIniziale=("Giacenza", "max"),    # una riga per (Data, Tecnico)
    TotChiusure=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

# Nuove colonne richieste
daily["TT assegnati"] = daily["TotChiusure"].fillna(0).astype("Int64")
daily["TT gestiti"]   = (daily["GiacenzaIniziale"].fillna(0) + daily["TT assegnati"]).astype("Int64")
daily["% Espletamento"] = (daily["TT assegnati"] / daily["TT gestiti"]).where(daily["TT gestiti"] > 0, 0.0)

# Percentuali classiche sul denominatore "TT assegnati" (chiusi)
den = daily["TT assegnati"].replace(0, pd.NA)
daily["% Rework"]       = (daily["ReworkCount"] / den).fillna(0)
daily["% PostDelivery"] = (daily["PostDeliveryCount"] / den).fillna(0)
daily["% Produttivi"]   = (daily["ProduttiviCount"] / den).fillna(0)

# Pulizia colonne interne
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
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)

# -------------------------------
# 📅 Riepilogo Mensile per Tecnico (sommando il giornaliero)
# -------------------------------
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
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)