
import streamlit as st
import pandas as pd

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

@st.cache_data(ttl=0)
def load_giacenza():
    """
    Legge giacenza.xlsx locale e restituisce un DF aggregato per (DataStr, Tecnico)
    con la colonna 'TT iniziali'.
    Accetta nomi colonna tipo: 'Data', 'Tecnico', 'Giacenza iniziale'.
    """
    # prova a leggere solo le colonne attese; in fallback leggi tutto
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

    # verifica colonne minime
    if not {"Data", "Tecnico", "Giacenza iniziale"}.issubset(g.columns):
        st.warning("Il file giacenza.xlsx non contiene le colonne attese: Data, Tecnico, Giacenza iniziale.")
        return pd.DataFrame(columns=["DataStr", "Tecnico", "TT iniziali"])

    # normalizza tipi/formatting
    g["Data"] = pd.to_datetime(g["Data"], dayfirst=True, errors="coerce")
    g = g.dropna(subset=["Data"])
    g["Tecnico"] = (
        g["Tecnico"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
    )
    g["Giacenza iniziale"] = pd.to_numeric(g["Giacenza iniziale"], errors="coerce").fillna(0)

    # chiave data in formato come il tuo 'daily'
    g["DataStr"] = g["Data"].dt.strftime("%d/%m/%Y")

    # aggrega in caso di duplicati (Data,Tecnico)
    g = g.groupby(["DataStr", "Tecnico"], as_index=False)["Giacenza iniziale"].sum()

    # rinomina per merge finale
    g = g.rename(columns={"Giacenza iniziale": "TT iniziali"})
    return g[["DataStr", "Tecnico", "TT iniziali"]]


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

     # Normalizza i nomi tecnici:
    df["Tecnico"] = (
        df["Tecnico"]
        .astype(str)                      # forza a stringa
        .str.strip()                      # rimuove spazi iniziali/finali
        .str.replace(r"\s+", " ", regex=True)  # rimuove spazi doppi
        .str.upper()                      # tutto maiuscolo
    )
   
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

# Raggruppamento giornaliero
daily = df.groupby([df["Data"].dt.strftime("%d/%m/%Y").rename("Data"), "Tecnico"]).agg(
    Totale=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

# --- Merge con giacenza.xlsx per ottenere 'TT iniziali'
g_iniz = load_giacenza()
daily = daily.merge(
    g_iniz,
    left_on=["Data", "Tecnico"],
    right_on=["DataStr", "Tecnico"],
    how="left"
).drop(columns=["DataStr"])

# Se non c'è riga in giacenza → 0 (come richiesto)
daily["TT iniziali"] = daily["TT iniziali"].fillna(0).astype(int)

# 'TT lavorati' = la tua colonna 'Totale'
daily["TT lavorati"] = daily["Totale"].astype(int)

# '% espletamento' = TT lavorati / TT iniziali (0 se TT iniziali = 0)
daily["% espletamento"] = (daily["TT lavorati"] / daily["TT iniziali"]).where(daily["TT iniziali"] > 0, 0.0)
# Percentuali
daily["% Rework"] = (daily["ReworkCount"] / daily["Totale"]).fillna(0)
daily["% PostDelivery"] = (daily["PostDeliveryCount"] / daily["Totale"]).fillna(0)
daily["% Produttivi"] = (daily["ProduttiviCount"] / daily["Totale"]).fillna(0)

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

style = (
    daily.style
        .format({
            "% espletamento": "{:.2%}",
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}",
        })
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"])
)

st.dataframe(style, use_container_width=True)

# Riepilogo mensile
monthly = df.copy()
monthly["Mese"] = monthly["Data"].dt.strftime("%m/%Y")
riepilogo = monthly.groupby(["Tecnico"]).agg(
    Totale=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

riepilogo["% Rework"] = (riepilogo["ReworkCount"] / riepilogo["Totale"]).fillna(0)
riepilogo["% PostDelivery"] = (riepilogo["PostDeliveryCount"] / riepilogo["Totale"]).fillna(0)
riepilogo["% Produttivi"] = (riepilogo["ProduttiviCount"] / riepilogo["Totale"]).fillna(0)

st.subheader("📅 Riepilogo Mensile per Tecnico")
st.dataframe(
    riepilogo.style
        .format({
            "% Rework": "{:.2%}",
            "% PostDelivery": "{:.2%}",
            "% Produttivi": "{:.2%}"
        })
        .applymap(lambda v: color_semaforo(v, "rework"), subset=["% Rework"])\
        .applymap(lambda v: color_semaforo(v, "postdelivery"), subset=["% PostDelivery"])
        .applymap(lambda v: color_semaforo(v, "produttivi"), subset=["% Produttivi"]),
    use_container_width=True
)
