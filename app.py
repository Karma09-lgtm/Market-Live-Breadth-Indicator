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
    page_title="Global Market Breadth Terminal",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. DATA PIPELINE (The "Decoupled" Cache Engine)
# ==========================================
@st.cache_data(ttl=86400) # Cache for 24h
def get_universes():
    """Fetches S&P 500 and Nifty 50 tickers."""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # S&P 500
    try:
        url_sp = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table_sp = pd.read_html(requests.get(url_sp, headers=headers).text)[0]
        table_sp['Symbol'] = table_sp['Symbol'].str.replace('.', '-', regex=False)
        sp500_tickers = table_sp['Symbol'].tolist()
        sp500_sectors = dict(zip(table_sp['Symbol'], table_sp['GICS Sector']))
    except:
        sp500_tickers, sp500_sectors = ['AAPL', 'MSFT', 'NVDA'], {'AAPL': 'Tech', 'MSFT': 'Tech', 'NVDA': 'Tech'}

    # Nifty 50 (Using top Indian stocks to prevent yfinance rate-limit bans)
    try:
        url_nifty = 'https://en.wikipedia.org/wiki/NIFTY_50'
        tables = pd.read_html(requests.get(url_nifty, headers=headers).text)
        # Find the table with the symbols
        for t in tables:
            if 'Symbol' in t.columns:
                table_nifty = t
                break
        table_nifty['Symbol'] = table_nifty['Symbol'] + '.NS' # Yahoo Finance suffix for NSE
        nifty_tickers = table_nifty['Symbol'].tolist()
        nifty_sectors = dict(zip(table_nifty['Symbol'], table_nifty['Sector']))
    except:
        nifty_tickers, nifty_sectors = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS'], {'RELIANCE.NS': 'Energy', 'TCS.NS': 'IT', 'HDFCBANK.NS': 'Finance'}

    return sp500_tickers, sp500_sectors, nifty_tickers, nifty_sectors

@st.cache_data(ttl=3600, show_spinner=False) # Fetch market data once per hour
def get_market_data(tickers):
    # Download 2 years of daily close prices
    data = yf.download(tickers, period="2y", auto_adjust=True, progress=False)['Close']
    data = data.ffill() # Forward fill missing data
    
    # Vectorized Moving Averages
    sma_20 = data.rolling(window=20).mean()
    sma_50 = data.rolling(window=50).mean()
    sma_150 = data.rolling(window=150).mean()
    sma_200 = data.rolling(window=200).mean()
    ema_30w = data.ewm(span=150, adjust=False).mean()
    ema_30w_1m_ago = ema_30w.shift(20)
    high_52w = data.rolling(window=252).max()
    
    # Historical Breadth DataFrame
    breadth = pd.DataFrame(index=data.index)
    breadth['pct_above_20'] = (data > sma_20).mean(axis=1) * 100
    breadth['pct_above_50'] = (data > sma_50).mean(axis=1) * 100
    breadth['pct_above_150'] = (data > sma_150).mean(axis=1) * 100
    breadth['pct_above_200'] = (data > sma_200).mean(axis=1) * 100
    breadth['stage_2'] = ((data > ema_30w) & (ema_30w > ema_30w_1m_ago)).mean(axis=1) * 100
    breadth['stage_4'] = ((data < ema_30w) & (ema_30w < ema_30w_1m_ago)).mean(axis=1) * 100
    
    # Latest Cross Section for Sector Analysis
    latest_data = pd.DataFrame({
        'Price': data.iloc[-1],
        '50_SMA': sma_50.iloc[-1],
        '200_SMA': sma_200.iloc[-1],
        '30W_EMA': ema_30w.iloc[-1],
        '52W_High': high_52w.iloc[-1]
    })
    
    return breadth.dropna(), latest_data

# Initialize Data
with st.spinner("Synchronizing Global Market Data (This takes ~45 seconds on first load)..."):
    sp_tickers, sp_sectors, in_tickers, in_sectors = get_universes()
    sp_breadth, sp_latest = get_market_data(sp_tickers)
    in_breadth, in_latest = get_market_data(in_tickers)
    
    sp_latest['Sector'] = sp_latest.index.map(sp_sectors)
    in_latest['Sector'] = in_latest.index.map(in_sectors)

# ==========================================
# 3. SIDEBAR (Interactivity & Filtering)
# ==========================================
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Stock_market_crash_%282020%29.svg/512px-Stock_market_crash_%282020%29.svg.png", width=50)
st.sidebar.title("Terminal Controls")

# Ticker Lookup Feature
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Stock Lookup")
lookup_ticker = st.sidebar.text_input("Enter Ticker (e.g., AAPL or TCS.NS)").upper()
if lookup_ticker:
    try:
        if lookup_ticker in sp_latest.index:
            stock_info = sp_latest.loc[lookup_ticker]
        elif lookup_ticker in in_latest.index:
            stock_info = in_latest.loc[lookup_ticker]
        else:
            # Quick fetch if not in our top lists
            quick_data = yf.Ticker(lookup_ticker).history(period="1y")
            stock_info = {'Price': quick_data['Close'].iloc[-1], '200_SMA': quick_data['Close'].rolling(200).mean().iloc[-1]}
            
        st.sidebar.success(f"**{lookup_ticker}**")
        st.sidebar.write(f"**Price:** ${stock_info['Price']:.2f}")
        trend = "🟢 Uptrend" if stock_info['Price'] > stock_info.get('200_SMA', 0) else "🔴 Downtrend"
        st.sidebar.write(f"**Status:** {trend} (vs 200 SMA)")
    except:
        st.sidebar.error("Ticker not found.")

# Date Slider for Charts
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Chart Timeframe")
min_date = sp_breadth.index.min().to_pydatetime()
max_date = sp_breadth.index.max().to_pydatetime()
start_date, end_date = st.sidebar.slider(
    "Select Range",
    min_value=min_date, max_value=max_date,
    value=(max_date - datetime.timedelta(days=252), max_date), # Default to 1 year
    format="MMM YY"
)

# Sector Filter
st.sidebar.markdown("---")
st.sidebar.subheader("🏢 Sector Filter (US)")
all_sectors = ["All"] + sorted([str(s) for s in set(sp_sectors.values()) if str(s) != 'nan'])
selected_sector = st.sidebar.selectbox("Analyze Specific Sector", all_sectors)

st.sidebar.caption(f"Data Cached: {sp_breadth.index[-1].strftime('%d %b %Y')}")

# ==========================================
# 4. UI CHART GENERATORS
# ==========================================
def plot_line_chart(title, traces_dict, df_timeseries, y_range=[0, 100], hline=None):
    fig = go.Figure()
    # Apply the Date Filter from the Sidebar
    df_plot = df_timeseries.loc[start_date:end_date]
    
    for name, col_name, color in traces_dict:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot[col_name], mode='lines', name=name, line=dict(width=1.5, color=color)))
    
    if hline:
        fig.add_hline(y=hline, line_dash="solid", line_color="red", line_width=1)
        
    fig.update_layout(
        title=title, height=300, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white", yaxis=dict(range=y_range, gridcolor='#eeeeee', dtick=10),
        xaxis=dict(gridcolor='#eeeeee'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    return fig

# ==========================================
# 5. MAIN DASHBOARD (Tabs)
# ==========================================
st.title("🌍 Global Market Breadth")

# Create the Tabs for US and Indian Markets
tab1, tab2 = st.tabs(["🦅 US Market (S&P 500)", "🐅 Indian Market (Nifty 50)"])

# --- TAB 1: US MARKET ---
with tab1:
    # Apply Sector Filter to Cross-Sectional Data
    if selected_sector != "All":
        us_latest_filtered = sp_latest[sp_latest['Sector'] == selected_sector]
        st.subheader(f"Filtered View: {selected_sector}")
    else:
        us_latest_filtered = sp_latest
        
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

    with r1_col1:
        traces = [("% > 200 SMA", 'pct_above_200', "#A0D468"), ("% > 50 SMA", 'pct_above_50', "#ED5565")]
        st.plotly_chart(plot_line_chart("S&P Broad Breadth", traces, sp_breadth), use_container_width=True)

    with r1_col2:
        traces = [("Stage 2 (Uptrend)", 'stage_2', "#48CFAD"), ("Stage 4 (Downtrend)", 'stage_4', "#FC6E51")]
        st.plotly_chart(plot_line_chart("S&P Stage Analysis", traces, sp_breadth), use_container_width=True)

    with r1_col3:
        # Sector 52-Week Highs
        us_latest_filtered['Near_High'] = us_latest_filtered['Price'] >= (us_latest_filtered['52W_High'] * 0.97)
        if not us_latest_filtered.empty:
            sector_highs = us_latest_filtered.groupby('Sector')['Near_High'].mean() * 100
            sector_highs = sector_highs.sort_values(ascending=True)
            
            fig = px.bar(x=sector_highs.values, y=sector_highs.index, orientation='h', text=sector_highs.values,
                         color=sector_highs.index, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(title="% Near 52-Week High by Sector", height=300, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False, xaxis=dict(range=[0, 100]))
            fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%')
            st.plotly_chart(fig, use_container_width=True)

    with r1_col4:
        us_latest_filtered['Pct_From_30W'] = ((us_latest_filtered['Price'] - us_latest_filtered['30W_EMA']) / us_latest_filtered['30W_EMA']) * 100
        st.markdown("**Top Extensions (Above 30W EMA)**")
        top_extended = us_latest_filtered[['Pct_From_30W']].sort_values(by='Pct_From_30W', ascending=False).head(8).reset_index()
        top_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% Extension'}, inplace=True)
        st.dataframe(top_extended.style.background_gradient(cmap='coolwarm').format({'% Extension': "{:.2f}%"}), hide_index=True, use_container_width=True)


# --- TAB 2: INDIAN MARKET ---
with tab2:
    st.info("Displaying Nifty 50 constituents to optimize real-time processing speed.")
    r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

    with r2_col1:
        traces = [("% > 200 SMA", 'pct_above_200', "#A0D468"), ("% > 50 SMA", 'pct_above_50', "#ED5565")]
        st.plotly_chart(plot_line_chart("Nifty Broad Breadth", traces, in_breadth), use_container_width=True)

    with r2_col2:
        traces = [("Stage 2 (Uptrend)", 'stage_2', "#48CFAD"), ("Stage 4 (Downtrend)", 'stage_4', "#FC6E51")]
        st.plotly_chart(plot_line_chart("Nifty Stage Analysis", traces, in_breadth), use_container_width=True)

    with r2_col3:
        # Sector 52-Week Highs
        in_latest['Near_High'] = in_latest['Price'] >= (in_latest['52W_High'] * 0.97)
        if not in_latest.empty:
            in_sector_highs = in_latest.groupby('Sector')['Near_High'].mean() * 100
            in_sector_highs = in_sector_highs.sort_values(ascending=True)
            
            fig = px.bar(x=in_sector_highs.values, y=in_sector_highs.index, orientation='h', text=in_sector_highs.values,
                         color=in_sector_highs.index, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(title="Nifty: % Near 52-Week High", height=300, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False, xaxis=dict(range=[0, 100]))
            fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%')
            st.plotly_chart(fig, use_container_width=True)

    with r2_col4:
        in_latest['Pct_From_30W'] = ((in_latest['Price'] - in_latest['30W_EMA']) / in_latest['30W_EMA']) * 100
        st.markdown("**Nifty Extensions (Above 30W EMA)**")
        in_top_extended = in_latest[['Pct_From_30W']].sort_values(by='Pct_From_30W', ascending=False).head(8).reset_index()
        in_top_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% Extension'}, inplace=True)
        st.dataframe(in_top_extended.style.background_gradient(cmap='coolwarm').format({'% Extension': "{:.2f}%"}), hide_index=True, use_container_width=True)
