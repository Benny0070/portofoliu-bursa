import streamlit as st
import pandas as pd
import yfinance as yf
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# --- CONFIGURARE GOOGLE SHEETS ---
def connect_to_gsheet():
    """Conectează aplicația la Google Sheets folosind secrets.toml"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Incarcam credetialele din secrets.toml
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # Gspread are nevoie de cheia privata cu \n reale
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Deschidem foaia de calcul 'bursa_db'
    sheet = client.open("bursa_db").sheet1 
    return sheet

# 1. SALVARE TRANZACTIE (Direct in Cloud)
def save_transaction(date, ticker, ttype, shares, price, comm):
    sheet = connect_to_gsheet()
    
    # Pregatim randul pentru Google Sheets
    row = [
        str(date), 
        ticker, 
        ttype, 
        shares, 
        price, 
        comm
    ]
    
    sheet.append_row(row)

# 2. INCARCARE TRANZACTII (Din Cloud - Varianta Robustă)
def load_transactions():
    try:
        sheet = connect_to_gsheet()
        
        # Folosim get_all_values() care aduce totul ca o lista simpla (mai sigur decat get_all_records)
        all_values = sheet.get_all_values()
        
        # Daca e gol sau are doar header-ul
        if len(all_values) <= 1:
            return pd.DataFrame(columns=["date", "ticker", "type", "shares", "price", "commission"])
            
        # Primul rand e header-ul, restul sunt datele
        headers = all_values[0]
        data = all_values[1:]
        
        df = pd.DataFrame(data, columns=headers)
        
        # CURATENIE: Stergem spatiile goale din numele coloanelor (ex: "commission " devine "commission")
        df.columns = df.columns.str.strip()
        
        # Verificam daca avem coloana critica
        if "commission" not in df.columns:
            # Incercam sa fim destepti: daca nu gasim 'commission', poate e coloana 6
            if len(df.columns) >= 6:
                df.columns = ["date", "ticker", "type", "shares", "price", "commission"]
            else:
                st.error(f"Eroare coloane Google Sheet. Coloanele gasite sunt: {list(df.columns)}")
                return pd.DataFrame(columns=["date", "ticker", "type", "shares", "price", "commission"])

        # Conversii obligatorii (reparam virgule si transformam in numere)
        # Inlocuim virgula cu punctul daca ai scris "0,5" in loc de "0.5" in Sheet
        df["shares"] = pd.to_numeric(df["shares"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        df["price"] = pd.to_numeric(df["price"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        df["commission"] = pd.to_numeric(df["commission"].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
        
        # Data
        df["date"] = pd.to_datetime(df["date"], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Eroare la conectare Google Sheets: {e}")
        return pd.DataFrame(columns=["date", "ticker", "type", "shares", "price", "commission"])

# 3. STERGERE TRANZACTII (Din Cloud)
def delete_transactions(indices_to_delete):
    sheet = connect_to_gsheet()
    
    # Sortam descrescator ca sa nu stricam ordinea cand stergem
    # Atentie: Google Sheets incepe de la randul 1 (header), deci datele incep de la 2
    # DataFrame index 0 = Sheet Row 2
    rows_to_delete_gsheet = [i + 2 for i in indices_to_delete]
    rows_to_delete_gsheet.sort(reverse=True)
    
    for r in rows_to_delete_gsheet:
        sheet.delete_rows(r)

# --- PROCESARE PORTOFOLIU ---
def process_portfolio(df):
    """Transformă lista de tranzacții în portofoliu consolidat."""
    if df.empty:
        return pd.DataFrame()

    portfolio = {}

    for _, row in df.iterrows():
        ticker = row['ticker']
        shares = row['shares']
        price = row['price']
        comm = row['commission']
        
        # Daca nu am mai intalnit compania, o initializam
        if ticker not in portfolio:
            portfolio[ticker] = {'shares': 0.0, 'invested': 0.0}
        
        if row['type'] == 'BUY':
            portfolio[ticker]['shares'] += shares
            portfolio[ticker]['invested'] += (shares * price) + comm
        elif row['type'] == 'SELL':
            # La vanzare scadem proportional din costul mediu
            avg_price = portfolio[ticker]['invested'] / portfolio[ticker]['shares'] if portfolio[ticker]['shares'] > 0 else 0
            portfolio[ticker]['shares'] -= shares
            portfolio[ticker]['invested'] -= (shares * avg_price)

    # Creare DataFrame final
    data = []
    for ticker, values in portfolio.items():
        if values['shares'] > 0.001: # Filtram pozitiile inchise (aprox 0)
            data.append({
                "Ticker": ticker,
                "Acțiuni": values['shares'],
                "Total Investit ($)": values['invested']
            })
            
    return pd.DataFrame(data)

# --- DATE DE PIATA ---
@st.cache_data(ttl=600) # Cache 10 minute
def fetch_market_data(tickers):
    if not tickers:
        return {}, pd.DataFrame()
    
    # Descarcam date pentru toti odata
    data = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    
    current_prices = {}
    history = pd.DataFrame()
    
    # Daca e un singur ticker, structura e diferita
    if len(tickers) == 1:
        t = tickers[0]
        try:
            current_prices[t] = data['Close'].iloc[-1].item()
            history[t] = data['Close']
        except:
             current_prices[t] = 0.0
    else:
        for t in tickers:
            try:
                # Accesam coloana Close pentru fiecare ticker
                price = data[t]['Close'].iloc[-1]
                current_prices[t] = float(price)
                history[t] = data[t]['Close']
            except:
                current_prices[t] = 0.0
                
    return current_prices, history

def get_sector_map(tickers):
    """Aflam sectorul pentru fiecare companie folosind yfinance Ticker info."""
    sector_map = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            sector_map[t] = info.get("sector", "Necunoscut")
        except:
            sector_map[t] = "Necunoscut"
    return sector_map

def calculate_metrics(ticker, price_series):
    """Calculeaza volatilitatea si un verdict simplu."""
    if price_series.empty:
        return None
        
    # Calculam modificarea zilnica procentuala
    daily_returns = price_series.pct_change().dropna()
    
    # Volatilitate anuala (deviatia standard * radacina din 252 zile lucratoare)
    volatility = daily_returns.std() * (252 ** 0.5)
    
    verdict = "Moderată"
    if volatility < 0.2:
        verdict = "Scăzută (Sigur)"
    elif volatility > 0.4:
        verdict = "Ridicată (Riscant)"
        
    return {"Volatility": volatility, "Verdict": verdict}

# --- DIVIDENDE LOCALE ---
DIV_FILE = "dividend_settings.json"

def load_dividend_settings():
    if os.path.exists(DIV_FILE):
        with open(DIV_FILE, "r") as f:
            return json.load(f)
    return {}

def save_dividend_settings(settings):
    with open(DIV_FILE, "w") as f:
        json.dump(settings, f)