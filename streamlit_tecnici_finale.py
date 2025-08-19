
import streamlit as st
import pandas as pd
import requests, base64, io

st.set_page_config(layout="wide")

# Imposta sfondo bianco e testo nero
st.markdown("""
    <style>
    html, body, [data-testid="stApp"] {
        background-color: white !important;
        color: black !important;
    }

    /* Forza colore dei testi nei menu a discesa */
    .stSelectbox div[data-baseweb="select"] {
        background-color: white !important;
        color: black !important;
    }

    .stSelectbox span, .stSelectbox label {
        color: black !important;
        font-weight: 500;
    }

    /* Forza stile nelle tabelle */
    .stDataFrame, .stDataFrame table, .stDataFrame th, .stDataFrame td {
        background-color: white !important;
        color: black !important;
    }

    /* Pulsanti */
    .stButton > button {
        background-color: white !important;
        color: black !important;
        border: 1px solid #999 !important;
        border-radius: 6px;
    }

    /* Radio button */
    div[data-baseweb="radio"] label span {
        color: black !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
        header [data-testid="theme-toggle"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)


# --- Titolo ---
st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")

# Intestazione con logo e bottone
# Logo in alto
st.image("LogoEuroirte.jpg", width=180)

# Bottone sotto il logo
st.link_button("🏠 Torna alla Home", url="https://homeeuroirte.streamlit.app/")

def pulisci_tecnici(df):
    """Rimuove righe senza tecnico e normalizza i nomi"""
    df["Tecnico"] = (
        df["Tecnico"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )
    # Elimina righe vuote o 'NAN'
    df = df[df["Tecnico"].notna() & (df["Tecnico"] != "") & (df["Tecnico"] != "NAN")]
    return df

def load_giacenze():
    """
    Carica la giacenza mattutina per (Data, Tecnico).
    Priorità:
      1) file locale 'giacenze.xlsx'
      2) GitHub via API se presenti i secrets GIACENZA_REPO e GIACENZA_PATH (+ github_token opzionale)
    Ritorna un DataFrame con colonne: Data (datetime), Tecnico (UPPER), Giacenza (int)
    """
    # 1) Prova file locale
    try:
        g = pd.read_excel("giacenze.xlsx")
        g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
        g = g.dropna(subset=["Data"])
        g = pulisci_tecnici(g)
        if "Giacenza" not in g.columns:
            raise ValueError("Manca la colonna 'Giacenza' nel file giacenze.xlsx")
        g["Giacenza"] = pd.to_numeric(g["Giacenza"], errors="coerce").fillna(0).astype("Int64")
        return g[["Data", "Tecnico", "Giacenza"]]
    except Exception:
        pass  # passa al piano 2

    # 2) Prova GitHub API (repo esterno)
    repo  = st.secrets.get("GIACENZA_REPO", None)   # es: "utente/nome-repo"
    path  = st.secrets.get("GIACENZA_PATH", None)   # es: "giacenze.xlsx"
    token = st.secrets.get("github_token", None)

    if not repo or not path:
        st.error("Impossibile caricare giacenze: specifica giacenze.xlsx locale oppure secrets GIACENZA_REPO/GIACENZA_PATH.")
        return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    content = j.get("content")
    encoding = j.get("encoding")
    if not content or encoding != "base64":
        st.error("Risposta GitHub inattesa per giacenze.")
        return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])

    xls_bytes = base64.b64decode(content)
    g = pd.read_excel(io.BytesIO(xls_bytes))
    g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
    g = g.dropna(subset=["Data"])
    g = pulisci_tecnici(g)
    if "Giacenza" not in g.columns:
        st.error("Nel file giacenze manca la colonna 'Giacenza'.")
        return pd.DataFrame(columns=["Data", "Tecnico", "Giacenza"])
    g["Giacenza"] = pd.to_numeric(g["Giacenza"], errors="coerce").fillna(0).astype("Int64")
    return g[["Data", "Tecnico", "Giacenza"]]

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

    # --- Merge con giacenze (Data, Tecnico) ---
    g = load_giacenze()
    if not g.empty:
        df = df.merge(g, on=["Data", "Tecnico"], how="left")
    else:
        df["Giacenza"] = 0
    df["Giacenza"] = df["Giacenza"].fillna(0).astype("Int64")
   
    # Aggiungi ultima data aggiornamento sistema
    ultima_data = df["Data"].max()
    if pd.notna(ultima_data):
        st.markdown(f"🕒 **Dati aggiornati al: {ultima_data.strftime('%d/%m/%Y')}**")

    df["Produttivo"] = (
    (df["Rework"] != 1) &
    (df["PostDelivery"] != 1) &
    (~df["CodFine"].astype(str).str.upper().isin(["G", "M", "P", "S"]))
    )
    df["Totale"] = 1
    return df

df = load_data()

# Dopo aver caricato il DataFrame
mesi_italiani = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}

df["Mese"] = df["Data"].apply(lambda x: f"{mesi_italiani[x.month]}")

# Ricava lista mesi unici
mesi_disponibili = sorted(df["Mese"].unique())

# Menu a tendina per selezionare il mese
mese_selezionato = st.selectbox("📆 Seleziona un mese:", ["Tutti i mesi"] + mesi_disponibili)

# Filtro per il mese selezionato
if mese_selezionato != "Tutti i mesi":
    df = df[df["Mese"] == mese_selezionato]

# Filtri
tecnici = ["Tutti"] + sorted(df["Tecnico"].dropna().unique().tolist())
date_uniche = ["Tutte"] + sorted(df["Data"].dropna().dt.strftime("%d/%m/%Y").unique().tolist())

col1, col2 = st.columns(2)
filtro_data = col1.selectbox("📅 Seleziona una data:", date_uniche)
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico:", tecnici)

# Applica filtri
df["DataStr"] = df["Data"].dt.strftime("%d/%m/%Y")
if filtro_data != "Tutte":
    df = df[df["DataStr"] == filtro_data]
if filtro_tecnico != "Tutti":
    df = df[df["Tecnico"] == filtro_tecnico]

# Raggruppamento giornaliero (con giacenza)
daily = df.groupby([df["Data"].dt.strftime("%d/%m/%Y").rename("Data"), "Tecnico"]).agg(
    GiacenzaIniziale=("Giacenza", "max"),      # 1 riga per (Data,Tecnico) → max/first sono equivalenti
    Totale=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

# Metriche derivate
daily["Gestiti"] = daily["GiacenzaIniziale"].fillna(0) + daily["Totale"].fillna(0)
daily["% Espletamento"] = (
    (daily["Totale"] / daily["Gestiti"]).where(daily["Gestiti"] > 0, 0.0)
)
daily["% Rework"] = (daily["ReworkCount"] / daily["Totale"]).where(daily["Totale"] > 0, 0.0).fillna(0)
daily["% PostDelivery"] = (daily["PostDeliveryCount"] / daily["Totale"]).where(daily["Totale"] > 0, 0.0).fillna(0)
daily["% Produttivi"] = (daily["ProduttiviCount"] / daily["Totale"]).where(daily["Totale"] > 0, 0.0).fillna(0)
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

st.subheader("📆 Dettaglio Giornaliero")
st.dataframe(
    daily.style
        .format({
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
            "% Espletamento": "{:.2%}"
        })
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)

# Riepilogo mensile per tecnico (sommando i giornalieri → nessuna duplicazione giacenza)
riepilogo = daily.groupby("Tecnico").agg(
    Giacenza=("GiacenzaIniziale", "sum"),
    Totale=("Totale", "sum"),
    ReworkCount=("ReworkCount", "sum"),
    PostDeliveryCount=("PostDeliveryCount", "sum"),
    ProduttiviCount=("ProduttiviCount", "sum")
).reset_index()

riepilogo["Gestiti"] = riepilogo["Giacenza"].fillna(0) + riepilogo["Totale"].fillna(0)
riepilogo["% Espletamento"] = (
    (riepilogo["Totale"] / riepilogo["Gestiti"]).where(riepilogo["Gestiti"] > 0, 0.0)
)

riepilogo["% Rework"] = (riepilogo["ReworkCount"] / riepilogo["Totale"]).where(riepilogo["Totale"] > 0, 0.0).fillna(0)
riepilogo["% PostDelivery"] = (riepilogo["PostDeliveryCount"] / riepilogo["Totale"]).where(riepilogo["Totale"] > 0, 0.0).fillna(0)
riepilogo["% Produttivi"] = (riepilogo["ProduttiviCount"] / riepilogo["Totale"]).where(riepilogo["Totale"] > 0, 0.0).fillna(0)

st.subheader("📅 Riepilogo Mensile per Tecnico")
st.dataframe(
    riepilogo.style
        .format({
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
            "% Espletamento": "{:.2%}"
        })
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)

