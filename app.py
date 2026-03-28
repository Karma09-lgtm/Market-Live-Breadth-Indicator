import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import datetime

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
st.caption(f"Last Updated: {datetime.datetime.now().strftime('%d %b, %I:%M %p')} ET")

# ==========================================
# 2. THE S&P 500 UNIVERSE BUILDER
# ==========================================
@st.cache_data(ttl=86400) # Cache this list for 24 hours so we don't spam Wikipedia
def get_sp500_universe():
    """Dynamically fetches the current S&P 500 companies and their sectors."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    table = pd.read_html(url)[0]
    
    # yfinance uses '-' instead of '.' for tickers like BRK.B
    table['Symbol'] = table['Symbol'].str.replace('.', '-')
    
    tickers = table['Symbol'].tolist()
    sector_mapping = dict(zip(table['Symbol'], table['GICS Sector']))
    
    return tickers, sector_mapping

# Fetch the universe in the background
sp500_tickers, sp500_sectors = get_sp500_universe()

# ==========================================
# 3. UI CHART GENERATORS (Currently Mocked for UI Build)
# ==========================================
def get_timeseries_data():
    dates = pd.date_range(start="2022-01-01", end=datetime.datetime.today(), freq="W")
    return dates

def plot_line_chart(title, traces, y_range=[0, 100], hline=None):
    fig = go.Figure()
    for name, data, color in traces:
        fig.add_trace(go.Scatter(x=get_timeseries_data(), y=data, mode='lines', name=name, line=dict(width=1.5, color=color)))
    
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

# --- ROW 1 ---
r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
dates = len(get_timeseries_data())

with r1_col1:
    traces = [
        ("Mega-Cap", np.random.uniform(30, 95, dates), "#5D9CEc"),
        ("Mid-Cap", np.random.uniform(20, 85, dates), "#ED5565"),
        ("Small-Cap", np.random.uniform(10, 80, dates), "#A0D468")
    ]
    st.plotly_chart(plot_line_chart("S&P 500: % Above 30W EMA by Size", traces), use_container_width=True)

with r1_col2:
    traces = [
        ("Stage 2 (Uptrend)", np.random.uniform(25, 70, dates), "#48CFAD"),
        ("Stage 4 (Downtrend)", np.random.uniform(20, 75, dates), "#FC6E51")
    ]
    st.plotly_chart(plot_line_chart("S&P 500: Stage Analysis", traces), use_container_width=True)

with r1_col3:
    # Actual S&P 500 GICS Sectors
    sectors = ["Information Technology", "Health Care", "Financials", "Consumer Discretionary", 
               "Communication Services", "Industrials", "Consumer Staples", "Energy", "Utilities", "Real Estate", "Materials"]
    values = sorted([np.random.randint(10, 80) for _ in range(11)], reverse=True) # Mock percentages
    
    fig = px.bar(x=values[::-1], y=sectors[::-1], orientation='h', text=values[::-1],
                 color=sectors[::-1], color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(
        title="S&P 500: % of Stocks Near 52-Week High by Sector", height=300, 
        margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", showlegend=False,
        xaxis=dict(range=[0, 100])
    )
    fig.update_traces(textposition='outside', texttemplate='%{text}%')
    st.plotly_chart(fig, use_container_width=True)

with r1_col4:
    traces = [
        ("% Above 200 SMA", np.random.uniform(30, 85, dates), "#A0D468"),
        ("% Below 200 SMA", np.random.uniform(15, 70, dates), "#ED5565")
    ]
    st.plotly_chart(plot_line_chart("S&P 500: % Above/Below 200-Day SMA", traces, hline=50), use_container_width=True)

# --- ROW 2 ---
r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

with r2_col1:
    traces = [("% Above 200 DMA", np.random.uniform(20, 80, dates), "#48CFAD")]
    st.plotly_chart(plot_line_chart("S&P 500 Broad Breadth", traces, y_range=[0, 100], hline=40), use_container_width=True)

with r2_col2:
    traces = [
        ("> 200 DMA", np.random.uniform(30, 80, dates), "#AAB2BD"),
        ("> 50 DMA", np.random.uniform(25, 75, dates), "#ED5565"),
        ("> 20 DMA", np.random.uniform(20, 85, dates), "#48CFAD")
    ]
    st.plotly_chart(plot_line_chart("S&P 500: Short vs Long Term Breadth", traces, y_range=[0, 100]), use_container_width=True)

with r2_col3:
    st.markdown("**Key Indices : % Away from 30W EMA**")
    df_table = pd.DataFrame({
        "Symbol": ["^VIX (Volatility)", "SPY (S&P 500)", "QQQ (Nasdaq 100)", "IWM (Russell 2000)", "XLF (Financials)", "XLK (Tech)", "XLE (Energy)"],
        "% from 30w ema": [np.random.uniform(-10, 50) for _ in range(7)]
    }).sort_values(by="% from 30w ema", ascending=False)
    
    st.dataframe(df_table.style.background_gradient(subset=['% from 30w ema'], cmap='coolwarm', vmin=-15, vmax=30).format({'% from 30w ema': "{:.2f}%"}), 
                 hide_index=True, use_container_width=True, height=250)

with r2_col4:
    # Simulating a "New Highs minus New Lows" or Drawdown chart
    fig = go.Figure(data=[go.Bar(x=get_timeseries_data(), y=np.random.normal(0, 50, dates), 
                                 marker_color=np.where(np.random.normal(0, 50, dates) > 0, '#48CFAD', '#ED5565'))])
    fig.update_layout(
        title="Net New 52-Week Highs (Highs minus Lows)", height=300, 
        margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", yaxis=dict(gridcolor='#eeeeee')
    )
    st.plotly_chart(fig, use_container_width=True)
