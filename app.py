import streamlit as st
import pandas as pd
import plotly.express as px
import utils 
from datetime import datetime

# Configurare pagină (Trebuie să fie prima comandă Streamlit)
st.set_page_config(page_title="Portofoliu Investiții", layout="wide")

# --- PAZNICUL (Codul de Securitate) ---
def check_password():
    """Returnează True dacă utilizatorul a introdus parola corectă."""

    def password_entered():
        """Verifică dacă parola introdusă e corectă."""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Ștergem parola din memorie pentru siguranță
        else:
            st.session_state["password_correct"] = False

    # Dacă parola a fost deja validată, returnăm True
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True

    # Altfel, afișăm câmpul de parolă
    st.text_input(
        "🔒 Introdu Parola de Acces:", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Parolă greșită. Mai încearcă.")

    return False

# Dacă paznicul zice NU (False), oprim aplicația aici
if not check_password():
    st.stop()

# --- AICI ÎNCEPE APLICAȚIA TA NORMALĂ ---

st.title("📈 Portofoliu Investiții")

# 1. Încărcare Date
df_trans = utils.load_transactions()
df_portfolio = utils.process_portfolio(df_trans)

# 2. Date de Piață Live
if not df_portfolio.empty:
    tickers = df_portfolio['Ticker'].tolist()
    current_prices, history_data = utils.fetch_market_data(tickers)
    
    # Calcul Valoare Curentă
    df_portfolio['Preț Curent ($)'] = df_portfolio['Ticker'].map(current_prices)
    df_portfolio['Valoare Curentă ($)'] = df_portfolio['Acțiuni'] * df_portfolio['Preț Curent ($)']
    
    # Calcul Profit/Pierdere
    df_portfolio['Profit ($)'] = df_portfolio['Valoare Curentă ($)'] - df_portfolio['Total Investit ($)']
    df_portfolio['ROI (%)'] = (df_portfolio['Profit ($)'] / df_portfolio['Total Investit ($)']) * 100
    
    # Adăugare Sector
    sector_map = utils.get_sector_map(tickers)
    df_portfolio['Sector'] = df_portfolio['Ticker'].map(sector_map)

# 3. Interfața cu Tab-uri
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "➕ Adaugă Tranzacție", "📜 Istoric"])

with tab1:
    if df_portfolio.empty:
        st.info("Nu ai nicio investiție activă. Adaugă o tranzacție în tab-ul următor!")
    else:
        # Metrici Principale
        total_invested = df_portfolio['Total Investit ($)'].sum()
        current_value = df_portfolio['Valoare Curentă ($)'].sum()
        total_profit = current_value - total_invested
        total_roi = (total_profit / total_invested * 100) if total_invested > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Valoare Portofoliu", f"${current_value:,.2f}")
        col2.metric("Total Investit", f"${total_invested:,.2f}")
        col3.metric("Profit Total", f"${total_profit:,.2f}", f"{total_roi:.2f}%")
        
        st.markdown("---")
        
        # Grafice
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Structura Portofoliului")
            fig = px.pie(df_portfolio, values='Valoare Curentă ($)', names='Ticker', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("Top Sectoare")
            sector_counts = df_portfolio.groupby("Sector")['Valoare Curentă ($)'].sum().reset_index()
            fig_sec = px.bar(sector_counts, x='Sector', y='Valoare Curentă ($)')
            st.plotly_chart(fig_sec, use_container_width=True)
            
        # Tabel Detaliat
        st.subheader("Detaliu Dețineri")
        
        # Pregătim tabelul pentru afișare (formatare frumoasă)
        df_view = df_portfolio[['Ticker', 'Sector', 'Acțiuni', 'Preț Curent ($)', 'Total Investit ($)', 'Valoare Curentă ($)', 'Profit ($)', 'ROI (%)']].copy()
        
        # Aici era eroarea inainte - acum va merge daca ai pus matplotlib in requirements.txt
        st.dataframe(
            df_view.set_index("Ticker").style.format({
                "Acțiuni": "{:.4f}",
                "Preț Curent ($)": "${:.2f}",
                "Total Investit ($)": "${:.2f}",
                "Valoare Curentă ($)": "${:.2f}",
                "Profit ($)": "${:.2f}",
                "ROI (%)": "{:.2f}%"
            }).background_gradient(subset=["ROI (%)"], cmap="RdYlGn"),
            use_container_width=True
        )

with tab2:
    st.header("Adaugă o nouă tranzacție")
    
    with st.form("add_transaction"):
        c1, c2 = st.columns(2)
        date = c1.date_input("Data Tranzacției", datetime.today())
        ticker = c2.text_input("Simbol (ex: AAPL, TSLA)").upper()
        
        c3, c4 = st.columns(2)
        t_type = c3.selectbox("Tip", ["BUY", "SELL"])
        shares = c4.number_input("Număr Acțiuni", min_value=0.0001, format="%.4f")
        
        c5, c6 = st.columns(2)
        price = c5.number_input("Preț per Acțiune ($)", min_value=0.01, format="%.2f")
        comm = c6.number_input("Comision ($)", min_value=0.0, format="%.2f")
        
        submitted = st.form_submit_button("Salvează Tranzacția")
        
        if submitted:
            if ticker and shares > 0 and price > 0:
                utils.save_transaction(date, ticker, t_type, shares, price, comm)
                st.success(f"Tranzacție salvată pentru {ticker}!")
                st.rerun()
            else:
                st.error("Te rog completează toate câmpurile corect.")

with tab3:
    st.header("Istoric Tranzacții")
    if not df_trans.empty:
        # Afisam tabelul sortat dupa data (cele mai noi sus)
        df_display = df_trans.sort_values(by="date", ascending=False).reset_index(drop=True)
        st.dataframe(df_display, use_container_width=True)
        
        st.warning("⚠️ Zona Periculoasă: Ștergere Tranzacții")
        indices = st.multiselect("Selectează tranzacțiile de șters (după indexul din tabel):", df_display.index)
        
        if st.button("Șterge Tranzacțiile Selectate"):
            if indices:
                utils.delete_transactions(indices)
                st.success("Tranzacții șterse!")
                st.rerun()
    else:
        st.info("Nu există tranzacții în istoric.")
