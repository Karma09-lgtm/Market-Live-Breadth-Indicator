import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import datetime
import requests
import yfinance as yf

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM CSS
# ==========================================
st.set_page_config(
    page_title="S&P 500 Market Breadth",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injecting Custom CSS for a sleek "Dark Terminal" look
st.markdown("""
    <style>
        /* Force Dark Theme elements */
        .stApp { background-color: #0E1117; color: #FFFFFF; }
        
        /* Style the top header */
        h1 { color: #00E396; font-weight: 600; font-family: 'Inter', sans-serif; }
        
        /* Clean up the dataframe tables */
        .stDataFrame { background-color: #161A25; border-radius: 8px; }
        
        /* Adjust padding for a tighter, dashboard feel */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATA ARCHITECTURE (Cached)
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

@st.cache_data(ttl=604800)
def get_market_caps(tickers):
    caps, cap_categories = {}, {}
    for ticker in tickers:
        try:
            cap = yf.Ticker(ticker).fast_info['marketCap']
            caps[ticker] = cap
            if cap >= 200_000_000_000: cap_categories[ticker] = 'Mega'
            elif cap >= 10_000_000_000: cap_categories[ticker] = 'Large'
            elif cap >= 2_000_000_000: cap_categories[ticker] = 'Mid'
            elif cap >= 250_000_000: cap_categories[ticker] = 'Small'
            else: cap_categories[ticker] = 'Micro'
        except:
            cap_categories[ticker] = 'Unknown'
    return cap_categories

@st.cache_data(ttl=3600)
def fetch_core_market_matrix(tickers):
    st.toast("Syncing live market data...", icon="🔄")
    benchmarks = ['^GSPC', '^VIX', 'SPY', 'QQQ', 'DIA', 'IWM']
    all_tickers = list(set(tickers + benchmarks))
    prices = yf.download(all_tickers, period="4y", auto_adjust=True, progress=False)['Close'].ffill()
    
    matrices = {
        'Price': prices,
        'SMA_50': prices.rolling(window=50).mean(),
        'SMA_150': prices.rolling(window=150).mean(),
        'SMA_200': prices.rolling(window=200).mean(),
        'EMA_200': prices.ewm(span=200, adjust=False).mean(),
        'EMA_30W': prices.ewm(span=150, adjust=False).mean(),
        'High_52W': prices.rolling(window=252).max()
    }
    matrices['EMA_30W_1M_Ago'] = matrices['EMA_30W'].shift(20)
    return matrices

def calculate_dynamic_breadth(matrices, active_tickers, cap_categories):
    p = matrices['Price'][active_tickers]
    ema_30w = matrices['EMA_30W'][active_tickers]
    ema_30w_ago = matrices['EMA_30W_1M_Ago'][active_tickers]
    
    breadth = pd.DataFrame(index=p.index)
    
    breadth['pct_above_50'] = (p > matrices['SMA_50'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_150'] = (p > matrices['SMA_150'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_200'] = (p > matrices['SMA_200'][active_tickers]).mean(axis=1) * 100
    
    breadth['pct_above_200_ema'] = (p > matrices['EMA_200'][active_tickers]).mean(axis=1) * 100
    breadth['pct_below_200_ema'] = 100 - breadth['pct_above_200_ema']
    
    breadth['stage_2'] = ((p > ema_30w) & (ema_30w > ema_30w_ago)).mean(axis=1) * 100
    breadth['stage_4'] = ((p < ema_30w) & (ema_30w < ema_30w_ago)).mean(axis=1) * 100
    
    is_above_30w = p > ema_30w
    for cap_tier in ['Mega', 'Large', 'Mid', 'Small', 'Micro']:
        tier_tickers = [t for t in active_tickers if cap_categories.get(t) == cap_tier]
        breadth[f'30w_{cap_tier}'] = is_above_30w[tier_tickers].mean(axis=1) * 100 if tier_tickers else 0 
            
    latest = pd.DataFrame({
        'Price': p.iloc[-1], '52W_High': matrices['High_52W'][active_tickers].iloc[-1], '30W_EMA': ema_30w.iloc[-1]
    })
    return breadth.dropna(), latest

# --- INITIALIZE DATA ---
try:
    sp500_tickers, sp500_sectors = get_sp500_universe()
    market_cap_categories = get_market_caps(sp500_tickers)
    core_matrices = fetch_core_market_matrix(sp500_tickers)
    data_loaded = True
except Exception as e:
    st.error(f"Data feed initializing. Error: {e}")
    data_loaded = False

# ==========================================
# 3. INTERACTIVE SIDEBAR & FILTERS
# ==========================================
if data_loaded:
    st.sidebar.markdown("### ⚙️ Control Panel")
    
    unique_sectors = sorted(list(set(sp500_sectors.values())))
    selected_sector = st.sidebar.selectbox("Filter by Sector", ["All S&P 500"] + unique_sectors)
    
    min_date = core_matrices['Price'].index[200].to_pydatetime() 
    max_date = core_matrices['Price'].index[-1].to_pydatetime()
    date_range = st.sidebar.slider("Timeline Range", min_value=min_date, max_value=max_date, value=(max_date - datetime.timedelta(days=365*3), max_date))

    if selected_sector == "All S&P 500":
        active_universe = sp500_tickers
        st.title("📈 S&P 500 Market Breadth")
    else:
        active_universe = [ticker for ticker, sec in sp500_sectors.items() if sec == selected_sector]
        st.title(f"📈 {selected_sector} Breadth")

    breadth_ts, latest_cross_section = calculate_dynamic_breadth(core_matrices, active_universe, market_cap_categories)
    
    mask = (breadth_ts.index >= date_range[0]) & (breadth_ts.index <= date_range[1])
    breadth_ts = breadth_ts.loc[mask]

    # ==========================================
    # 4. DASHBOARD LAYOUT & PRO CHARTS
    # ==========================================
    # The upgraded plotting engine for a dark terminal look
    def plot_line_chart(title, traces_dict, df_timeseries, y_range=[0, 100], hline=None):
        fig = go.Figure()
        for name, col_name, color in traces_dict:
            if df_timeseries[col_name].sum() > 0:
                fig.add_trace(go.Scatter(
                    x=df_timeseries.index, y=df_timeseries[col_name], 
                    mode='lines', name=name, line=dict(width=1.5, color=color)
                ))
        if hline:
            fig.add_hline(y=hline, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1.5)
            
        fig.update_layout(
            title=dict(text=title, font=dict(size=14, color="#E0E0E0")),
            template="plotly_dark", # Forces dark mode styling
            plot_bgcolor="rgba(0,0,0,0)", # Transparent to blend with Streamlit
            paper_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(range=y_range, gridcolor='#222631', zerolinecolor='#222631'),
            xaxis=dict(gridcolor='#222631', zerolinecolor='#222631', showgrid=False),
            hovermode="x unified", # Pro terminal crosshairs
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
        )
        return fig

    # --- ROW 1 ---
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

    with r1_col1:
        # High contrast colors: Cyan, Lime, Magenta, Orange
        traces = [
            ("Mega", '30w_Mega', "#00E396"), ("Large", '30w_Large', "#008FFB"),
            ("Mid", '30w_Mid', "#FEB019"), ("Small", '30w_Small', "#FF4560")
        ]
        st.plotly_chart(plot_line_chart("% > 30W EMA by Cap", traces, breadth_ts), use_container_width=True)

    with r1_col2:
        traces = [("Stage 2 (Bull)", 'stage_2', "#00E396"), ("Stage 4 (Bear)", 'stage_4', "#FF4560")]
        st.plotly_chart(plot_line_chart("Weinstein Stage Analysis", traces, breadth_ts), use_container_width=True)

    with r1_col3:
        latest_cross_section['Near_High'] = latest_cross_section['Price'] >= (latest_cross_section['52W_High'] * 0.97)
        sector_highs = latest_cross_section.groupby(latest_cross_section.index.map(sp500_sectors))['Near_High'].mean() * 100
        sector_highs = sector_highs.sort_values(ascending=True)
        
        fig = px.bar(x=sector_highs.values, y=sector_highs.index, orientation='h', text=sector_highs.values,
                     color_discrete_sequence=["#008FFB"]) # Clean uniform blue for sectors
        fig.update_layout(
            title=dict(text="% Sector Near 52-Wk Highs", font=dict(size=14, color="#E0E0E0")),
            template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(l=10, r=10, t=40, b=10), xaxis=dict(range=[0, 100], gridcolor='#222631')
        )
        fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%', textfont_color="#FFFFFF")
        st.plotly_chart(fig, use_container_width=True)

    with r1_col4:
        traces = [("% Above", 'pct_above_200_ema', "#00E396"), ("% Below", 'pct_below_200_ema', "#FF4560")]
        st.plotly_chart(plot_line_chart("% Stocks > / < 200 EMA", traces, breadth_ts, hline=50), use_container_width=True)

    # --- ROW 2 ---
    r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

    with r2_col1:
        traces = [("% > 200 DMA", 'pct_above_200', "#008FFB")]
        st.plotly_chart(plot_line_chart("% Stocks > 200 DMA", traces, breadth_ts, y_range=[0, 100], hline=50), use_container_width=True)

    with r2_col2:
        traces = [("> 200 DMA", 'pct_above_200', "#775DD0"), ("> 150 DMA", 'pct_above_150', "#008FFB"), ("> 50 DMA", 'pct_above_50', "#00E396")]
        st.plotly_chart(plot_line_chart("% > 50 / 150 / 200 SMA", traces, breadth_ts, y_range=[0, 100]), use_container_width=True)

    with r2_col3:
        st.markdown("<p style='font-size: 14px; color: #E0E0E0; font-weight: bold; margin-bottom: 0px;'>Indices : Distance from 30 WMA</p>", unsafe_allow_html=True)
        indices_list = ['^VIX', 'SPY', 'QQQ', 'DIA', 'IWM']
        idx_data = []
        for idx in indices_list:
            if idx in core_matrices['Price'].columns:
                p = core_matrices['Price'][idx].iloc[-1]
                ema30 = core_matrices['EMA_30W'][idx].iloc[-1]
                dist = ((p - ema30) / ema30) * 100
                display_name = idx.replace('^', 'VIX' if idx=='^VIX' else idx)
                idx_data.append({"Symbol": display_name, "% Dist": dist})
                
        df_table = pd.DataFrame(idx_data).sort_values(by="% Dist", ascending=False)
        # Using a dark-mode friendly colormap (RdYlGn reversed so high dist = hot/red, low = green)
        st.dataframe(df_table.style.background_gradient(subset=['% Dist'], cmap='RdYlGn_r').format({'% Dist': "{:.2f}%"}), 
                     hide_index=True, use_container_width=True, height=250)

    with r2_col4:
        sp500_price = core_matrices['Price']['^GSPC']
        rolling_max = sp500_price.cummax()
        drawdown_pct = ((sp500_price - rolling_max) / rolling_max) * 100 
        drawdown_abs = drawdown_pct.abs()
        
        drawdown_mask = (drawdown_abs.index >= date_range[0]) & (drawdown_abs.index <= date_range[1])
        drawdown_filtered = drawdown_abs.loc[drawdown_mask]
        
        fig = go.Figure(data=[go.Bar(x=drawdown_filtered.index, y=drawdown_filtered, marker_color="#FF4560")])
        fig.update_layout(
            title=dict(text="S&P 500 Peak Drawdowns", font=dict(size=14, color="#E0E0E0")),
            template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            height=300, margin=dict(l=10, r=10, t=40, b=10),
            yaxis=dict(gridcolor='#222631', title=dict(text="% Decline", font=dict(size=10))),
            xaxis=dict(showgrid=False), hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
