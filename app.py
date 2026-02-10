import streamlit as st
import pandas as pd
import plotly.express as px
from utils import *

# Configurare Pagina
st.set_page_config(
    page_title="Portofoliu Investiții", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- FUNCTII AUXILIARE UI ---
def make_chart_transparent(fig):
    """Face graficele să arate bine și pe Dark Mode și pe Light Mode."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, l=10, r=10, b=10),
        font=dict(size=14)
    )
    return fig

def calculate_height(df, min_rows=3, max_height=500):
    """Calculează înălțimea tabelului ca să nu lase spațiu gol."""
    rows = len(df)
    if rows < min_rows:
        rows = min_rows
    calc_height = (rows + 1) * 35 + 3 # 35px per rând + header
    return min(calc_height, max_height)

# --- SIDEBAR: ADAUGĂ TRANZACȚIE ---
with st.sidebar:
    st.header("➕ Adaugă Operațiune")
    with st.container(border=True):
        with st.form("add_tx_form", clear_on_submit=True):
            date = st.date_input("📅 Data")
            ticker = st.text_input("🔤 Simbol (ex: AAPL, TSLA)").upper()
            
            c1, c2 = st.columns(2)
            with c1:
                ttype = st.selectbox("Tip", ["BUY", "SELL"])
            with c2:
                shares = st.number_input("Cantitate", min_value=0.01, step=1.0)
                
            price = st.number_input("💵 Preț execuție ($)", min_value=0.01, step=0.1)
            comm = st.number_input("💸 Comision ($)", min_value=0.0, step=0.1, value=0.0, help="Dacă ai cont în lei, pune 0.5% aici.")
            
            submitted = st.form_submit_button("💾 Salvează Tranzacția", use_container_width=True)
            
            if submitted and ticker and shares > 0 and price > 0:
                save_transaction(date, ticker, ttype, shares, price, comm)
                st.toast(f"✅ {ticker} salvat cu succes!", icon="🎉")
                st.cache_data.clear()
                st.rerun()
            
    st.info("Pentru a șterge tranzacții greșite, mergi la tab-ul '📝 Istoric'.")

# --- TITLU PRINCIPAL ---
st.title("📈 Manager Portofoliu")
st.markdown("---")

# 1. Încărcare Date Backend
df_tx = load_transactions()
df_portfolio = process_portfolio(df_tx)

# Fetch date live doar dacă avem portofoliu
tickers = []
current_prices = {}
history_data = pd.DataFrame()

if not df_portfolio.empty:
    tickers = df_portfolio["Ticker"].tolist()
    current_prices, history_data = fetch_market_data(tickers)

# 2. Structura Tab-urilor
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Portofoliu", 
    "🍰 Alocare",
    "🏭 Sectoare", 
    "📈 Analiză Companie", 
    "📝 Istoric", 
    "💰 Dividende"
])

# -----------------------------------------------------------
# TAB 1: PORTOFOLIU GENERAL (MODIFICAT CU EXPLICAȚII)
# -----------------------------------------------------------
with tab1:
    if df_portfolio.empty:
        st.info("👋 Nu ai nicio poziție deschisă. Folosește meniul din stânga pentru a adăuga prima tranzacție.")
    else:
        # Pregătire Date
        df_view = df_portfolio.copy()
        df_view["Preț Curent ($)"] = df_view["Ticker"].map(current_prices)
        df_view["Valoare Curentă ($)"] = df_view["Acțiuni"] * df_view["Preț Curent ($)"]
        df_view["Profit/Pierdere ($)"] = df_view["Valoare Curentă ($)"] - df_view["Total Investit ($)"]
        
        # Evităm împărțirea la zero
        df_view["Randament (%)"] = df_view.apply(
            lambda x: (x["Profit/Pierdere ($)"] / x["Total Investit ($)"] * 100) if x["Total Investit ($)"] > 0 else 0, axis=1
        )
        
        # Totals
        total_investit = df_view["Total Investit ($)"].sum()
        total_valoare = df_view["Valoare Curentă ($)"].sum()
        total_profit = total_valoare - total_investit
        total_randament = (total_profit / total_investit * 100) if total_investit > 0 else 0

        # --- CARDS PENTRU METRICI ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Total Investit", f"${total_investit:,.2f}", help="Suma totală de bani scoasă din buzunar (Preț + Comisioane).")
        with col2:
            st.metric("💎 Valoare Curentă", f"${total_valoare:,.2f}", help="Câți bani ai încasa dacă ai vinde totul acum.")
        with col3:
            st.metric("🚀 Profit/Pierdere", f"${total_profit:,.2f}", delta=f"{total_randament:.2f}%", help="Diferența dintre valoarea curentă și banii investiți.")
        
        st.write("") 

        # --- TABEL PRINCIPAL CU TOOLTIPS ---
        st.dataframe(
            df_view.set_index("Ticker").style.format({
                "Acțiuni": "{:.2f}",
                "Total Investit ($)": "${:,.2f}",
                "Preț Curent ($)": "${:.2f}",
                "Valoare Curentă ($)": "${:,.2f}",
                "Profit/Pierdere ($)": "${:+,.2f}",
                "Randament (%)": "{:+.2f}%"
            }).background_gradient(cmap="RdYlGn", subset=["Randament (%)"], vmin=-20, vmax=20),
            column_config={
                "Ticker": st.column_config.Column(
                    "Ticker",
                    help="Simbolul unic al companiei la bursă (ex: TSLA)."
                ),
                "Acțiuni": st.column_config.NumberColumn(
                    "Acțiuni",
                    help="Numărul de bucăți pe care le deții acum."
                ),
                "Total Investit ($)": st.column_config.NumberColumn(
                    "Total Investit ($)",
                    help="Costul total de achiziție (Preț acțiune + Comisioane)."
                ),
                "Preț Curent ($)": st.column_config.NumberColumn(
                    "Preț Curent ($)",
                    help="Prețul unei singure acțiuni pe piață în timp real."
                ),
                "Valoare Curentă ($)": st.column_config.NumberColumn(
                    "Valoare Curentă ($)",
                    help="Cât valorează deținerea ta acum (Acțiuni x Preț Curent)."
                ),
                "Profit/Pierdere ($)": st.column_config.NumberColumn(
                    "Profit/Pierdere ($)",
                    help="Câți dolari ai câștigat (+) sau pierdut (-) față de investiția inițială."
                ),
                "Randament (%)": st.column_config.NumberColumn(
                    "Randament (%)",
                    help="Eficiența investiției. Cât la sută ai câștigat peste suma investită."
                )
            },
            use_container_width=True,
            height=calculate_height(df_view)
        )

# -----------------------------------------------------------
# TAB 2: ALOCARE
# -----------------------------------------------------------
with tab2:
    if df_portfolio.empty:
        st.write("Adaugă tranzacții pentru a vedea graficele.")
    else:
        st.subheader("🍰 Distribuția Activelor")
        
        col_g1, col_g2 = st.columns([1.5, 1])
        
        with col_g1:
            with st.container(border=True):
                st.write("**Hartă Vizuală (Mărime = Valoare)**")
                fig_tree = px.treemap(
                    df_view, 
                    path=['Ticker'], 
                    values='Valoare Curentă ($)',
                    color='Randament (%)',
                    color_continuous_scale='RdYlGn',
                    color_continuous_midpoint=0
                )
                st.plotly_chart(make_chart_transparent(fig_tree), use_container_width=True)

        with col_g2:
            with st.container(border=True):
                st.write("**Procentual**")
                fig_pie = px.pie(
                    df_view, 
                    values='Valoare Curentă ($)', 
                    names='Ticker', 
                    hole=0.4
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(make_chart_transparent(fig_pie), use_container_width=True)

        st.markdown("### 💡 Interpretare Portofoliu")
        max_pos = df_view.loc[df_view['Valoare Curentă ($)'].idxmax()]
        pct_max = (max_pos['Valoare Curentă ($)'] / total_valoare) * 100
        
        st.info(f"""
        * **Cea mai mare deținere:** Ai **{pct_max:.1f}%** din bani investiți în **{max_pos['Ticker']}**.
        * **Diversificare:** Ai un total de **{len(df_view)}** companii în portofoliu.
        """)

# -----------------------------------------------------------
# TAB 3: SECTOARE
# -----------------------------------------------------------
with tab3:
    if df_portfolio.empty:
        st.write("Lipsă date.")
    else:
        st.subheader("🏭 Expunere pe Industrii")
        
        sector_map = get_sector_map(tickers)
        df_sector_view = df_view.copy()
        df_sector_view["Sector"] = df_sector_view["Ticker"].map(sector_map)
        
        # 1. Agregăm datele pe Sector
        sector_group = df_sector_view.groupby("Sector")[["Total Investit ($)", "Valoare Curentă ($)"]].sum().reset_index()
        
        # 2. Calculăm Profitul pe Sector
        sector_group["Profit/Pierdere ($)"] = sector_group["Valoare Curentă ($)"] - sector_group["Total Investit ($)"]
        
        c_sec1, c_sec2 = st.columns([1, 1])
        
        with c_sec1:
            with st.container(border=True):
                st.write("**Grafic Sectoare**")
                fig_sec = px.pie(sector_group, values='Valoare Curentă ($)', names='Sector')
                st.plotly_chart(make_chart_transparent(fig_sec), use_container_width=True)
            
        with c_sec2:
            with st.container(border=True):
                st.write("**Detaliu Valoric**")
                
                # 3. Creăm rândul de TOTAL
                totals = sector_group[["Total Investit ($)", "Valoare Curentă ($)", "Profit/Pierdere ($)"]].sum()
                total_row = pd.DataFrame([{
                    "Sector": "TOTAL",
                    "Total Investit ($)": totals["Total Investit ($)"],
                    "Valoare Curentă ($)": totals["Valoare Curentă ($)"],
                    "Profit/Pierdere ($)": totals["Profit/Pierdere ($)"]
                }])
                
                # 4. Lipim rândul de Total
                sector_display = pd.concat([sector_group, total_row], ignore_index=True)
                
                st.dataframe(
                    sector_display.set_index("Sector").style.format({
                        "Total Investit ($)": "${:,.2f}",
                        "Valoare Curentă ($)": "${:,.2f}",
                        "Profit/Pierdere ($)": "${:+,.2f}"
                    }).applymap(
                        lambda x: 'color: #ff4b4b' if x < 0 else 'color: #3dd56d', 
                        subset=['Profit/Pierdere ($)']
                    ).apply(
                        lambda x: ['font-weight: bold' if x.name == 'TOTAL' else '' for i in x], axis=1
                    ),
                    use_container_width=True,
                    height=calculate_height(sector_display)
                )

# -----------------------------------------------------------
# TAB 4: ANALIZĂ COMPANIE
# -----------------------------------------------------------
with tab4:
    if df_portfolio.empty:
        st.write("Adaugă companii în portofoliu.")
    else:
        col_sel, col_rest = st.columns([1, 3])
        with col_sel:
            selected_ticker = st.selectbox("🔍 Alege compania:", tickers)
        
        if selected_ticker and selected_ticker in history_data:
            price_series = history_data[selected_ticker]
            metrics = calculate_metrics(selected_ticker, price_series)
            sector = get_sector_map([selected_ticker]).get(selected_ticker, "-")
            curr_price = current_prices.get(selected_ticker, 0)
            
            with st.container(border=True):
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Preț Acum", f"${curr_price:.2f}")
                k2.metric("Sector", sector)
                if metrics:
                    k3.metric("Risc", metrics["Verdict"])
                    k4.metric("Volatilitate (1Y)", f"{metrics['Volatility']*100:.2f}%")
            
            st.write("")
            st.subheader(f"Evoluție {selected_ticker} (1 An)")
            st.line_chart(price_series, use_container_width=True, height=300)

# -----------------------------------------------------------
# TAB 5: ISTORIC & EDITARE
# -----------------------------------------------------------
with tab5:
    st.subheader("📝 Registru Tranzacții")
    
    if df_tx.empty:
        st.write("Nicio tranzacție.")
    else:
        st.markdown("Selectează căsuța din stânga pentru a șterge o înregistrare greșită.")
        
        df_to_edit = df_tx.copy()
        df_to_edit.insert(0, "Selectează", False)
        
        edited_df = st.data_editor(
            df_to_edit,
            column_config={
                "Selectează": st.column_config.CheckboxColumn("🗑️", width="small"),
                "date": st.column_config.DateColumn("Data", format="YYYY-MM-DD"),
                "price": st.column_config.NumberColumn("Preț", format="$%.2f"),
                "commission": st.column_config.NumberColumn("Comision", format="$%.2f"),
                "shares": st.column_config.NumberColumn("Cantitate"),
            },
            disabled=["ticker", "type", "shares", "price", "commission", "currency", "date"],
            hide_index=True,
            use_container_width=True,
            height=calculate_height(df_to_edit, min_rows=5, max_height=600)
        )
        
        rows_to_delete = edited_df[edited_df["Selectează"] == True]
        
        if not rows_to_delete.empty:
            st.error(f"⚠️ Ești pe cale să ștergi {len(rows_to_delete)} tranzacții.")
            if st.button("🔴 CONFIRMĂ ȘTERGEREA", use_container_width=True):
                indices = rows_to_delete.index.tolist()
                delete_transactions(indices)
                st.toast("Tranzacții șterse!", icon="🗑️")
                st.cache_data.clear()
                st.rerun()

# -----------------------------------------------------------
# TAB 6: DIVIDENDE
# -----------------------------------------------------------
with tab6:
    st.subheader("💰 Calculator Dividende")
    
    if df_portfolio.empty:
        st.write("Adaugă acțiuni în portofoliu.")
    else:
        saved_yields = load_dividend_settings()
        new_settings = saved_yields.copy()
        
        c_div1, c_div2 = st.columns([1, 2])
        
        with c_div1:
            with st.container(border=True):
                st.markdown("**% Dividend (Manual)**")
                has_changes = False
                for t in tickers:
                    default_val = saved_yields.get(t, 0.0)
                    user_val = st.number_input(f"{t} (%)", 0.0, 100.0, step=0.1, value=float(default_val), key=f"div_{t}")
                    if user_val != default_val:
                        new_settings[t] = user_val
                        has_changes = True
                
                if has_changes:
                    save_dividend_settings(new_settings)
                    st.toast("Recalculez...", icon="💾")
                    st.rerun()

        with c_div2:
            div_results = []
            total_anual = 0
            
            for index, row in df_view.iterrows():
                t = row["Ticker"]
                valoare_acum = row["Valoare Curentă ($)"]
                investit = row["Total Investit ($)"]
                yield_pct = new_settings.get(t, 0.0)
                
                bani_anual = valoare_acum * (yield_pct / 100)
                yield_on_cost = (bani_anual / investit * 100) if investit > 0 else 0
                total_anual += bani_anual
                
                div_results.append({
                    "Ticker": t,
                    "Yield (%)": f"{yield_pct}%",
                    "Estimat Anual ($)": bani_anual,
                    "Yield on Cost (%)": yield_on_cost
                })
            
            with st.container(border=True):
                st.metric("💵 Venit Pasiv Estimat (Anual)", f"${total_anual:,.2f}")
                st.dataframe(
                    pd.DataFrame(div_results).set_index("Ticker").style.format({
                        "Estimat Anual ($)": "${:,.2f}", 
                        "Yield on Cost (%)": "{:.2f}%"
                    }), 
                    use_container_width=True,
                    height=calculate_height(pd.DataFrame(div_results))
                )