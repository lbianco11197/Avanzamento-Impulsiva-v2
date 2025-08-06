
import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.image("LogoEuroirte.jpg", width=180)
st.title("📊 Avanzamento Produzione Assurance - Euroirte s.r.l.")

@st.cache_data
def load_data():
    df = pd.read_excel("provagiacenza_copy.xlsx", usecols=[
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
df["Mese"] = df["Data"].dt.strftime('%m/%Y')  # Esempio: "07/2025", "08/2025"

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
filtro_data = col1.selectbox("📅 Seleziona una data (opzionale):", date_uniche)
filtro_tecnico = col2.selectbox("🧑‍🔧 Seleziona un tecnico (opzionale):", tecnici)

# Applica filtri
df["DataStr"] = df["Data"].dt.strftime("%d/%m/%Y")
if filtro_data != "Tutte":
    df = df[df["DataStr"] == filtro_data]
if filtro_tecnico != "Tutti":
    df = df[df["Tecnico"] == filtro_tecnico]

# Raggruppamento giornaliero
daily = df.groupby(["DataStr", "Tecnico"]).agg(
    Totale=("Totale", "sum"),
    ReworkCount=("Rework", "sum"),
    PostDeliveryCount=("PostDelivery", "sum"),
    ProduttiviCount=("Produttivo", "sum")
).reset_index()

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
st.dataframe(
    daily.style
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
