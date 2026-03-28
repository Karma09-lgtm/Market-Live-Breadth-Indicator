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
    initial_sidebar_state="collapsed"
)

st.title("🦅 S&P 500 Market Breadth Indicators")

# ==========================================
# 2. DATA PIPELINE (Cached for Speed)
# ==========================================
@st.cache_data(ttl=86400) # Cache universe for 24h
def get_sp500_universe():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text)[0]
    table['Symbol'] = table['Symbol'].str.replace('.', '-', regex=False)
    
    tickers = table['Symbol'].tolist()
    sector_mapping = dict(zip(table['Symbol'], table['GICS Sector']))
    return tickers, sector_mapping

@st.cache_data(ttl=3600) # Fetch market data once per hour
def get_market_data(tickers):
    st.toast("Fetching live market data... This takes ~60 seconds.", icon="⏳")
    # Download 3 years of daily close prices to build historical charts
    data = yf.download(tickers, period="3y", auto_adjust=True, progress=False)['Close']
    
    # Forward fill missing data (e.g., if a stock was halted or newly listed)
    data = data.ffill()
    
    # Calculate Moving Averages (Vectorized across all 500 stocks instantly)
    sma_20 = data.rolling(window=20).mean()
    sma_50 = data.rolling(window=50).mean()
    sma_150 = data.rolling(window=150).mean()
    sma_200 = data.rolling(window=200).mean()
    ema_30w = data.ewm(span=150, adjust=False).mean() # ~150 days = 30 weeks
    ema_30w_1m_ago = ema_30w.shift(20)
    high_52w = data.rolling(window=252).max()
    
    # Calculate Historical Breadth (% of stocks meeting criteria per day)
    breadth = pd.DataFrame(index=data.index)
    breadth['pct_above_20'] = (data > sma_20).mean(axis=1) * 100
    breadth['pct_above_50'] = (data > sma_50).mean(axis=1) * 100
    breadth['pct_above_150'] = (data > sma_150).mean(axis=1) * 100
    breadth['pct_above_200'] = (data > sma_200).mean(axis=1) * 100
    
    # Stage Analysis
    breadth['stage_2'] = ((data > ema_30w) & (ema_30w > ema_30w_1m_ago)).mean(axis=1) * 100
    breadth['stage_4'] = ((data < ema_30w) & (ema_30w < ema_30w_1m_ago)).mean(axis=1) * 100
    
    # Get the absolute latest data row for cross-sectional/sector analysis
    latest_data = pd.DataFrame({
        'Price': data.iloc[-1],
        '52W_High': high_52w.iloc[-1],
        '30W_EMA': ema_30w.iloc[-1]
    })
    
    return breadth.dropna(), latest_data

# Load Data
try:
    sp500_tickers, sp500_sectors = get_sp500_universe()
    # To prevent yfinance from timing out on free servers, we'll process the top 400 for stability if needed, 
    # but let's try all 500 first.
    breadth_ts, latest_cross_section = get_market_data(sp500_tickers)
    
    # Add sectors to our latest data
    latest_cross_section['Sector'] = latest_cross_section.index.map(sp500_sectors)
    
    data_loaded = True
    st.caption(f"Market Data Last Synced: {breadth_ts.index[-1].strftime('%d %b %Y')}")
except Exception as e:
    st.error(f"Data feed currently initializing or rate-limited. Please try again in a few minutes. Error: {e}")
    data_loaded = False


# ==========================================
# 3. UI CHART GENERATORS
# ==========================================
def plot_line_chart(title, traces_dict, df_timeseries, y_range=[0, 100], hline=None):
    fig = go.Figure()
    # Slicing to the last 252 trading days (1 year) for a clean chart
    df_plot = df_timeseries.tail(252) 
    
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
# 4. DASHBOARD LAYOUT
# ==========================================
if data_loaded:
    # --- ROW 1 ---
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

    with r1_col1:
        # We don't have Market Cap data easily free, so we show 50/150/200 SMA Broad Breadth here instead
        traces = [
            ("% > 200 SMA", 'pct_above_200', "#A0D468"),
            ("% > 150 SMA", 'pct_above_150', "#5D9CEc"),
            ("% > 50 SMA", 'pct_above_50', "#ED5565")
        ]
        st.plotly_chart(plot_line_chart("S&P 500: % Above Key SMAs", traces, breadth_ts), use_container_width=True)

    with r1_col2:
        traces = [
            ("Stage 2 (Uptrend)", 'stage_2', "#48CFAD"),
            ("Stage 4 (Downtrend)", 'stage_4', "#FC6E51")
        ]
        st.plotly_chart(plot_line_chart("S&P 500: Stage Analysis", traces, breadth_ts), use_container_width=True)

    with r1_col3:
        # Calculate % of stocks within 3% of 52-Week High by Sector
        latest_cross_section['Near_High'] = latest_cross_section['Price'] >= (latest_cross_section['52W_High'] * 0.97)
        sector_highs = latest_cross_section.groupby('Sector')['Near_High'].mean() * 100
        sector_highs = sector_highs.sort_values(ascending=True) # Ascending for Plotly horizontal bar
        
        fig = px.bar(x=sector_highs.values, y=sector_highs.index, orientation='h', text=sector_highs.values,
                     color=sector_highs.index, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(
            title="S&P 500: % Near 52-Week High by Sector", height=300, 
            margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False,
            xaxis=dict(range=[0, 100])
        )
        fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%')
        st.plotly_chart(fig, use_container_width=True)

    with r1_col4:
        traces = [
            ("% Above 200 SMA", 'pct_above_200', "#A0D468"),
        ]
        st.plotly_chart(plot_line_chart("S&P 500: 200-Day Breadth Base", traces, breadth_ts, hline=50), use_container_width=True)

    # --- ROW 2 ---
    r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

    with r2_col1:
        # Zoomed in short-term breadth
        traces = [("% Above 20 DMA", 'pct_above_20', "#48CFAD")]
        st.plotly_chart(plot_line_chart("S&P 500: Short-Term Momentum", traces, breadth_ts, y_range=[0, 100], hline=40), use_container_width=True)

    with r2_col2:
        # Distance from 30W EMA distribution
        latest_cross_section['Pct_From_30W'] = ((latest_cross_section['Price'] - latest_cross_section['30W_EMA']) / latest_cross_section['30W_EMA']) * 100
        fig = px.histogram(latest_cross_section, x='Pct_From_30W', nbins=50, color_discrete_sequence=['#AAB2BD'])
        fig.update_layout(title="Distribution: % Distance from 30W EMA", height=300, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)

    with r2_col3:
        st.markdown("**Top 10 Stocks : Farthest Above 30W EMA**")
        top_extended = latest_cross_section[['Pct_From_30W', 'Sector']].sort_values(by='Pct_From_30W', ascending=False).head(10)
        top_extended.reset_index(inplace=True)
        top_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% from 30W EMA'}, inplace=True)
        
        st.dataframe(top_extended.style.background_gradient(subset=['% from 30W EMA'], cmap='coolwarm').format({'% from 30W EMA': "{:.2f}%"}), 
                     hide_index=True, use_container_width=True, height=250)

    with r2_col4:
        st.markdown("**Bottom 10 Stocks : Farthest Below 30W EMA**")
        bottom_extended = latest_cross_section[['Pct_From_30W', 'Sector']].sort_values(by='Pct_From_30W', ascending=True).head(10)
        bottom_extended.reset_index(inplace=True)
        bottom_extended.rename(columns={'index': 'Symbol', 'Pct_From_30W': '% from 30W EMA'}, inplace=True)
        
        st.dataframe(bottom_extended.style.background_gradient(subset=['% from 30W EMA'], cmap='coolwarm_r').format({'% from 30W EMA': "{:.2f}%"}), 
                     hide_index=True, use_container_width=True, height=250)
