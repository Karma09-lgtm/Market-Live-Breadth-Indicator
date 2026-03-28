import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import datetime
import requests
import yfinance as yf

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="S&P 500 Market Breadth",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. DECOUPLED DATA ARCHITECTURE
# ==========================================
@st.cache_data(ttl=86400)
def get_sp500_universe():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text)[0]
    table['Symbol'] = table['Symbol'].str.replace('.', '-', regex=False)
    
    tickers = table['Symbol'].tolist()
    sector_mapping = dict(zip(table['Symbol'], table['GICS Sector']))
    return tickers, sector_mapping

@st.cache_data(ttl=604800) # Cache Market Caps for 7 Days (Heavy operation)
def get_market_caps(tickers):
    caps = {}
    cap_categories = {}
    
    # Using fast_info to bypass massive dictionary downloads
    for ticker in tickers:
        try:
            cap = yf.Ticker(ticker).fast_info['marketCap']
            caps[ticker] = cap
            
            # User-defined criteria
            if cap >= 200_000_000_000:
                cap_categories[ticker] = 'Mega'
            elif cap >= 10_000_000_000:
                cap_categories[ticker] = 'Large'
            elif cap >= 2_000_000_000:
                cap_categories[ticker] = 'Mid'
            elif cap >= 250_000_000:
                cap_categories[ticker] = 'Small'
            else:
                cap_categories[ticker] = 'Micro'
        except:
            cap_categories[ticker] = 'Unknown'
            
    return cap_categories

@st.cache_data(ttl=3600)
def fetch_core_market_matrix(tickers):
    st.toast("Fetching live market data... This takes ~60 seconds.", icon="⏳")
    prices = yf.download(tickers, period="3y", auto_adjust=True, progress=False)['Close'].ffill()
    
    matrices = {
        'Price': prices,
        'SMA_20': prices.rolling(window=20).mean(),
        'SMA_50': prices.rolling(window=50).mean(),
        'SMA_150': prices.rolling(window=150).mean(),
        'SMA_200': prices.rolling(window=200).mean(),
        'EMA_30W': prices.ewm(span=150, adjust=False).mean(),
        'High_52W': prices.rolling(window=252).max()
    }
    matrices['EMA_30W_1M_Ago'] = matrices['EMA_30W'].shift(20)
    return matrices

# ==========================================
# 3. DYNAMIC BREADTH ENGINE 
# ==========================================
def calculate_dynamic_breadth(matrices, active_tickers, cap_categories):
    p = matrices['Price'][active_tickers]
    ema = matrices['EMA_30W'][active_tickers]
    ema_ago = matrices['EMA_30W_1M_Ago'][active_tickers]
    
    breadth = pd.DataFrame(index=p.index)
    
    # 1. Standard Moving Averages
    breadth['pct_above_20'] = (p > matrices['SMA_20'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_50'] = (p > matrices['SMA_50'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_150'] = (p > matrices['SMA_150'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_200'] = (p > matrices['SMA_200'][active_tickers]).mean(axis=1) * 100
    
    # 2. Stage Analysis
    breadth['stage_2'] = ((p > ema) & (ema > ema_ago)).mean(axis=1) * 100
    breadth['stage_4'] = ((p < ema) & (ema < ema_ago)).mean(axis=1) * 100
    
    # 3. Market Cap Based 30W EMA Breadth (Historical calculation)
    is_above_30w = p > ema
    for cap_tier in ['Mega', 'Large', 'Mid', 'Small', 'Micro']:
        tier_tickers = [t for t in active_tickers if cap_categories.get(t) == cap_tier]
        if tier_tickers:
            breadth[f'30w_{cap_tier}'] = is_above_30w[tier_tickers].mean(axis=1) * 100
        else:
            breadth[f'30w_{cap_tier}'] = 0 # Handle empty buckets safely
            
    # Cross section for the absolute latest day
    latest = pd.DataFrame({
        'Price': p.iloc[-1],
        '52W_High': matrices['High_52W'][active_tickers].iloc[-1],
        '30W_EMA': ema.iloc[-1]
    })
    return breadth.dropna(), latest


# --- INITIALIZE DATA ---
try:
    sp500_tickers, sp500_sectors = get_sp500_universe()
    market_cap_categories = get_market_caps(sp500_tickers)
    core_matrices = fetch_core_market_matrix(sp500_tickers)
    data_loaded = True
except Exception as e:
    st.error(f"Data feed initializing. Please wait. Error: {e}")
    data_loaded = False

# ==========================================
# 4. INTERACTIVE SIDEBAR & FILTERS
# ==========================================
if data_loaded:
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/S%26P_500_logo.svg/512px-S%26P_500_logo.svg.png", width=150)
    st.sidebar.header("Control Panel")
    
    unique_sectors = sorted(list(set(sp500_sectors.values())))
    selected_sector = st.sidebar.selectbox("Filter by Sector", ["All S&P 500"] + unique_sectors)
    
    min_date = core_matrices['Price'].index[200].to_pydatetime() 
    max_date = core_matrices['Price'].index[-1].to_pydatetime()
    date_range = st.sidebar.slider("Date Range", min_value=min_date, max_value=max_date, value=(max_date - datetime.timedelta(days=365), max_date))
    
    st.sidebar.divider()
    st.sidebar.subheader("Stock Lookup")
    search_ticker = st.sidebar.text_input("Enter Ticker (e.g., AAPL, NVDA)").upper()

    # --- APPLY FILTERS ---
    if selected_sector == "All S&P 500":
        active_universe = sp500_tickers
        st.title("🦅 S&P 500 Market Breadth")
    else:
        active_universe = [ticker for ticker, sec in sp500_sectors.items() if sec == selected_sector]
        st.title(f"🦅 {selected_sector} Breadth")
        
    st.caption(f"Analyzing {len(active_universe)} stocks | Last Sync: {max_date.strftime('%d %b %Y')}")

    breadth_ts, latest_cross_section = calculate_dynamic_breadth(core_matrices, active_universe, market_cap_categories)
    latest_cross_section['Sector'] = latest_cross_section.index.map(sp500_sectors)
    
    mask = (breadth_ts.index >= date_range[0]) & (breadth_ts.index <= date_range[1])
    breadth_ts = breadth_ts.loc[mask]

    # ==========================================
    # 5. INDIVIDUAL TICKER LOOKUP CARD
    # ==========================================
    if search_ticker and search_ticker in sp500_tickers:
        st.markdown(f"### 🔎 Deep Dive: {search_ticker}")
        t_data = latest_cross_section.loc[search_ticker]
        t_price = t_data['Price']
        t_ema = t_data['30W_EMA']
        pct_from_ema = ((t_price - t_ema) / t_ema) * 100
        
        ema_now = core_matrices['EMA_30W'][search_ticker].iloc[-1]
        ema_ago = core_matrices['EMA_30W_1M_Ago'][search_ticker].iloc[-1]
        
        if t_price > ema_now and ema_now > ema_ago:
            stage = "🟢 Stage 2 (Uptrend)"
        elif t_price < ema_now and ema_now < ema_ago:
            stage = "🔴 Stage 4 (Downtrend)"
        else:
            stage = "🟡 Transitioning"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Price", f"${t_price:.2f}")
        c2.metric("Distance from 30W EMA", f"{pct_from_ema:.2f}%")
        c3.metric("Size Tier", market_cap_categories.get(search_ticker, "Unknown"))
        c4.info(f"**Trend:** {stage}")
        st.divider()

    # ==========================================
    # 6. DASHBOARD LAYOUT
    # ==========================================
    def plot_line_chart(title, traces_dict, df_timeseries, y_range=[0, 100], hline=None):
        fig = go.Figure()
        for name, col_name, color in traces_dict:
            # Only plot lines where the data isn't universally zero (removes empty Small/Micro cap lines)
            if df_timeseries[col_name].sum() > 0:
                fig.add_trace(go.Scatter(x=df_timeseries.index, y=df_timeseries[col_name], mode='lines', name=name, line=dict(width=1.5, color=color)))
        if hline:
            fig.add_hline(y=hline, line_dash="solid", line_color="red", line_width=1)
        fig.update_layout(
            title=title, height=300, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="white", yaxis=dict(range=y_range, gridcolor='#eeeeee', dtick=10),
            xaxis=dict(gridcolor='#eeeeee'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        )
        return fig

    # --- ROW 1 ---
    r1_col1, r1_col2, r1_col3 = st.columns([1, 1, 1])

    with r1_col1:
        # NEW CHART: % Above 30W EMA categorized by Market Cap
        traces = [
            ("Mega-Cap (> $200B)", '30w_Mega', "#5D9CEc"), 
            ("Large-Cap ($10B - $200B)", '30w_Large', "#A0D468"),
            ("Mid-Cap ($2B - $10B)", '30w_Mid', "#ED5565"),
            ("Small-Cap ($250M - $2B)", '30w_Small', "#FFCE54"),
            ("Micro-Cap (< $250M)", '30w_Micro', "#AC92EC")
        ]
        st.plotly_chart(plot_line_chart("% Above 30W EMA by Market Cap", traces, breadth_ts), use_container_width=True)

    with r1_col2:
        traces = [("Stage 2 (Uptrend)", 'stage_2', "#48CFAD"), ("Stage 4 (Downtrend)", 'stage_4', "#FC6E51")]
        st.plotly_chart(plot_line_chart("Weinstein Stage Analysis", traces, breadth_ts), use_container_width=True)

    with r1_col3:
        latest_cross_section['Near_High'] = latest_cross_section['Price'] >= (latest_cross_section['52W_High'] * 0.97)
        sector_highs = latest_cross_section.groupby('Sector')['Near_High'].mean() * 100
        sector_highs = sector_highs.sort_values(ascending=True)
        
        fig = px.bar(x=sector_highs.values, y=sector_highs.index, orientation='h', text=sector_highs.values,
                     color=sector_highs.index, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(title="% Near 52-Week High by Sector", height=300, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False, xaxis=dict(range=[0, 100]))
        fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%')
        st.plotly_chart(fig, use_container_width=True)

    # --- ROW 2 ---
    r2_col1, r2_col2 = st.columns(2)

    with r2_col1:
        st.markdown(f"**Top Extended Stocks in {selected_sector} (+ from 30W EMA)**")
        latest_cross_section['Pct_From_30W'] = ((latest_cross_section['Price'] - latest_cross_section['30W_EMA']) / latest_cross_section['30W_EMA']) * 100
        top_extended = latest_cross_section[['Pct_From_30W']].sort_values(by='Pct_From_30W', ascending=False).head(10)
        top_extended.reset_index(inplace=True)
        top_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% from 30W EMA'}, inplace=True)
        st.dataframe(top_extended.style.background_gradient(subset=['% from 30W EMA'], cmap='coolwarm').format({'% from 30W EMA': "{:.2f}%"}), hide_index=True, use_container_width=True)

    with r2_col2:
        st.markdown(f"**Bottom Extended Stocks in {selected_sector} (- from 30W EMA)**")
        bottom_extended = latest_cross_section[['Pct_From_30W']].sort_values(by='Pct_From_30W', ascending=True).head(10)
        bottom_extended.reset_index(inplace=True)
        bottom_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% from 30W EMA'}, inplace=True)
        st.dataframe(bottom_extended.style.background_gradient(subset=['% from 30W EMA'], cmap='coolwarm_r').format({'% from 30W EMA': "{:.2f}%"}), hide_index=True, use_container_width=True)
        
