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

@st.cache_data(ttl=604800) # Cache Market Caps for 7 Days
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
    st.toast("Fetching live market data... This takes ~60 seconds.", icon="⏳")
    
    # We add specific benchmark indices needed for the Table and the Decline chart
    benchmarks = ['^GSPC', '^VIX', 'SPY', 'QQQ', 'DIA', 'IWM']
    all_tickers = list(set(tickers + benchmarks))
    
    # Extended to 4 years to satisfy the drawdown chart requirement
    prices = yf.download(all_tickers, period="4y", auto_adjust=True, progress=False)['Close'].ffill()
    
    matrices = {
        'Price': prices,
        'SMA_50': prices.rolling(window=50).mean(),
        'SMA_150': prices.rolling(window=150).mean(),
        'SMA_200': prices.rolling(window=200).mean(),
        'EMA_200': prices.ewm(span=200, adjust=False).mean(), # Added for R1C4
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
    ema_30w = matrices['EMA_30W'][active_tickers]
    ema_30w_ago = matrices['EMA_30W_1M_Ago'][active_tickers]
    
    breadth = pd.DataFrame(index=p.index)
    
    # Standard SMAs
    breadth['pct_above_50'] = (p > matrices['SMA_50'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_150'] = (p > matrices['SMA_150'][active_tickers]).mean(axis=1) * 100
    breadth['pct_above_200'] = (p > matrices['SMA_200'][active_tickers]).mean(axis=1) * 100
    
    # 200 EMA (Above and Below)
    breadth['pct_above_200_ema'] = (p > matrices['EMA_200'][active_tickers]).mean(axis=1) * 100
    breadth['pct_below_200_ema'] = 100 - breadth['pct_above_200_ema']
    
    # Stage Analysis
    breadth['stage_2'] = ((p > ema_30w) & (ema_30w > ema_30w_ago)).mean(axis=1) * 100
    breadth['stage_4'] = ((p < ema_30w) & (ema_30w < ema_30w_ago)).mean(axis=1) * 100
    
    # Market Cap Based 30W EMA Breadth
    is_above_30w = p > ema_30w
    for cap_tier in ['Mega', 'Large', 'Mid', 'Small', 'Micro']:
        tier_tickers = [t for t in active_tickers if cap_categories.get(t) == cap_tier]
        if tier_tickers:
            breadth[f'30w_{cap_tier}'] = is_above_30w[tier_tickers].mean(axis=1) * 100
        else:
            breadth[f'30w_{cap_tier}'] = 0 
            
    latest = pd.DataFrame({
        'Price': p.iloc[-1],
        '52W_High': matrices['High_52W'][active_tickers].iloc[-1],
        '30W_EMA': ema_30w.iloc[-1]
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
    date_range = st.sidebar.slider("Date Range", min_value=min_date, max_value=max_date, value=(max_date - datetime.timedelta(days=365*4), max_date))

    # --- APPLY FILTERS ---
    if selected_sector == "All S&P 500":
        active_universe = sp500_tickers
        st.title("🦅 S&P 500 Market Breadth")
    else:
        active_universe = [ticker for ticker, sec in sp500_sectors.items() if sec == selected_sector]
        st.title(f"🦅 {selected_sector} Breadth")

    breadth_ts, latest_cross_section = calculate_dynamic_breadth(core_matrices, active_universe, market_cap_categories)
    
    # Filter time-series by selected date range
    mask = (breadth_ts.index >= date_range[0]) & (breadth_ts.index <= date_range[1])
    breadth_ts = breadth_ts.loc[mask]

    # ==========================================
    # 5. DASHBOARD LAYOUT & CHARTS
    # ==========================================
    def plot_line_chart(title, traces_dict, df_timeseries, y_range=[0, 100], hline=None):
        fig = go.Figure()
        for name, col_name, color in traces_dict:
            if df_timeseries[col_name].sum() > 0:
                fig.add_trace(go.Scatter(x=df_timeseries.index, y=df_timeseries[col_name], mode='lines', name=name, line=dict(width=1.5, color=color)))
        if hline:
            fig.add_hline(y=hline, line_dash="solid", line_color="red", line_width=1, opacity=0.5)
        fig.update_layout(
            title=title, height=300, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="white", yaxis=dict(range=y_range, gridcolor='#eeeeee', dtick=10),
            xaxis=dict(gridcolor='#eeeeee'), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
        )
        return fig

    # --- ROW 1 ---
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

    with r1_col1:
        traces = [
            ("Mega-Cap", '30w_Mega', "#5D9CEc"), ("Large-Cap", '30w_Large', "#A0D468"),
            ("Mid-Cap", '30w_Mid', "#ED5565"), ("Small-Cap", '30w_Small', "#FFCE54")
        ]
        st.plotly_chart(plot_line_chart("% Stocks > 30W EMA by Cap", traces, breadth_ts), use_container_width=True)

    with r1_col2:
        traces = [("stage 2", 'stage_2', "#48CFAD"), ("stage 4", 'stage_4', "#FC6E51")]
        st.plotly_chart(plot_line_chart("Stage analysis", traces, breadth_ts), use_container_width=True)

    with r1_col3:
        latest_cross_section['Near_High'] = latest_cross_section['Price'] >= (latest_cross_section['52W_High'] * 0.97)
        sector_highs = latest_cross_section.groupby(latest_cross_section.index.map(sp500_sectors))['Near_High'].mean() * 100
        sector_highs = sector_highs.sort_values(ascending=True)
        
        fig = px.bar(x=sector_highs.values, y=sector_highs.index, orientation='h', text=sector_highs.values,
                     color=sector_highs.index, color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(title="% Sector wise close to 52 Wk Highs", height=300, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False, xaxis=dict(range=[0, 100]))
        fig.update_traces(textposition='outside', texttemplate='%{text:.1f}%')
        st.plotly_chart(fig, use_container_width=True)

    with r1_col4:
        # UPDATED: % Above and Below 200 EMA with 50% median line
        traces = [
            ("% above 200 ema", 'pct_above_200_ema', "#A0D468"),
            ("% below 200 ema", 'pct_below_200_ema', "#ED5565")
        ]
        st.plotly_chart(plot_line_chart("% Stocks above & below 200 EMA", traces, breadth_ts, hline=50), use_container_width=True)

    # --- ROW 2 ---
    r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

    with r2_col1:
        # UPDATED: % Stocks above 200 DMA with 50% median line
        traces = [("% above 200dma", 'pct_above_200', "#48CFAD")]
        st.plotly_chart(plot_line_chart("% Stocks above 200 DMA", traces, breadth_ts, y_range=[0, 100], hline=50), use_container_width=True)

    with r2_col2:
        # UPDATED: % above 200 DMA, 50 DMA, 150 DMA
        traces = [
            ("above 200dma", 'pct_above_200', "#AAB2BD"),
            ("above 50dma", 'pct_above_50', "#ED5565"),
            ("above 150dma", 'pct_above_150', "#48CFAD")
        ]
        st.plotly_chart(plot_line_chart("% abv 50 150 200 SMA", traces, breadth_ts, y_range=[0, 100]), use_container_width=True)

    with r2_col3:
        # UPDATED: Key Indices % away from 30W EMA
        st.markdown("**Indices : %Age Away from 30 WMA**")
        indices_list = ['^VIX', 'SPY', 'QQQ', 'DIA', 'IWM']
        idx_data = []
        for idx in indices_list:
            if idx in core_matrices['Price'].columns:
                p = core_matrices['Price'][idx].iloc[-1]
                ema30 = core_matrices['EMA_30W'][idx].iloc[-1]
                dist = ((p - ema30) / ema30) * 100
                display_name = idx.replace('^', 'INDIAVIX' if idx=='^VIX' else idx) # Formatted cleanly
                idx_data.append({"Symbol": display_name, "% from 30w ema": dist})
                
        df_table = pd.DataFrame(idx_data).sort_values(by="% from 30w ema", ascending=False)
        st.dataframe(df_table.style.background_gradient(subset=['% from 30w ema'], cmap='YlOrRd').format({'% from 30w ema': "{:.2f}"}), 
                     hide_index=True, use_container_width=True, height=250)

    with r2_col4:
        # UPDATED: Decline (Drawdowns) in S&P 500 on daily basis over 4 years
        sp500_price = core_matrices['Price']['^GSPC']
        rolling_max = sp500_price.cummax()
        # Calculate daily drawdown percentage from peak
        drawdown_pct = ((sp500_price - rolling_max) / rolling_max) * 100 
        
        # We plot the absolute value of the drop to create the red spikes seen in the image
        drawdown_abs = drawdown_pct.abs()
        
        # Apply the date filter to the drawdown index
        drawdown_mask = (drawdown_abs.index >= date_range[0]) & (drawdown_abs.index <= date_range[1])
        drawdown_filtered = drawdown_abs.loc[drawdown_mask]
        
        fig = go.Figure(data=[go.Bar(x=drawdown_filtered.index, y=drawdown_filtered, marker_color="#ED5565")])
        fig.update_layout(
            title="Drawdowns Peaks (S&P 500)", height=300, margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor="white", yaxis=dict(gridcolor='#eeeeee', title="% Decline")
        )
        st.plotly_chart(fig, use_container_width=True)
