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
    page_title="Market Breadth Indicators",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("Market Breadth Indicators")
st.caption(f"Last Updated: {datetime.datetime.now().strftime('%d %b, %I:%M %p')}")

# ==========================================
# 2. MOCK DATA GENERATORS (For UI Testing)
# ==========================================
# In the final version, these functions will read from your Redis/CSV cache

def get_timeseries_data():
    dates = pd.date_range(start="2022-01-01", end="2026-03-20", freq="W")
    return dates

def plot_line_chart(title, traces, y_range=[0, 100], hline=None):
    fig = go.Figure()
    for name, data, color in traces:
        fig.add_trace(go.Scatter(x=get_timeseries_data(), y=data, mode='lines', name=name, line=dict(width=1.5, color=color)))
    
    if hline:
        fig.add_hline(y=hline, line_dash="solid", line_color="red", line_width=1)
        
    fig.update_layout(
        title=title,
        height=300,
        margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white",
        yaxis=dict(range=y_range, gridcolor='#eeeeee', dtick=10),
        xaxis=dict(gridcolor='#eeeeee'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )
    return fig

# ==========================================
# 3. DASHBOARD LAYOUT (4 Columns x 2 Rows)
# ==========================================

# --- ROW 1 ---
r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)

with r1_col1:
    # Chart 1: % Stocks above 30W EMA by Market Cap
    dates = len(get_timeseries_data())
    traces = [
        ("Largecap", np.random.uniform(20, 90, dates), "#5D9CEc"),
        ("Midcap", np.random.uniform(15, 85, dates), "#ED5565"),
        ("Smallcap", np.random.uniform(10, 80, dates), "#A0D468")
    ]
    st.plotly_chart(plot_line_chart("Percentage of Stocks Trading above 30W EMA", traces), use_container_width=True)

with r1_col2:
    # Chart 2: Stage Analysis
    traces = [
        ("stage 2", np.random.uniform(20, 60, dates), "#48CFAD"),
        ("stage 4", np.random.uniform(30, 80, dates), "#FC6E51")
    ]
    st.plotly_chart(plot_line_chart("Stage analysis", traces), use_container_width=True)

with r1_col3:
    # Chart 3: Sector-wise 52 Week Highs (Horizontal Bar)
    sectors = ["Metals & mining", "Power & utilities", "Telecom", "Plastic products", 
               "Healthcare", "Energy", "Textiles", "Industrials", "Aerospace & defence"]
    values = [40, 35.71, 33.33, 33.33, 28.85, 26.67, 25, 20, 18.18]
    
    fig = px.bar(x=values, y=sectors, orientation='h', text=values,
                 color=sectors, color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_layout(
        title="% Sector wise Nifty 500 stocks close to 52 Week Highs",
        height=300, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white", showlegend=False,
        yaxis=dict(categoryorder='total ascending')
    )
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, use_container_width=True)

with r1_col4:
    # Chart 4: Nifty 500 % Above & Below 200 EMA
    traces = [
        ("% above 200 ema", np.random.uniform(20, 90, dates), "#A0D468"),
        ("% below 200 ema", np.random.uniform(10, 80, dates), "#ED5565")
    ]
    st.plotly_chart(plot_line_chart("Nifty 500 % Stocks above & below 200 EMA", traces, hline=60), use_container_width=True)


# --- ROW 2 ---
r2_col1, r2_col2, r2_col3, r2_col4 = st.columns(4)

with r2_col1:
    # Chart 5: % Stocks above 200 DMA
    traces = [("% above 200dma", np.random.uniform(10, 60, dates), "#48CFAD")]
    st.plotly_chart(plot_line_chart("% Stocks above 200 DMA", traces, y_range=[0, 70], hline=40), use_container_width=True)

with r2_col2:
    # Chart 6: % abv 20, 50, 200 SMA
    traces = [
        ("above 200dma", np.random.uniform(20, 60, dates), "#AAB2BD"),
        ("above 50dma", np.random.uniform(15, 65, dates), "#ED5565"),
        ("above 150dma", np.random.uniform(25, 55, dates), "#48CFAD")
    ]
    st.plotly_chart(plot_line_chart("% abv 20 50 200 SMA", traces, y_range=[0, 70]), use_container_width=True)

with r2_col3:
    # Chart 7: Indices Table
    st.markdown("**Indices : %Age Away from 30 WMA**")
    df_table = pd.DataFrame({
        "Symbol": ["INDIAVIX", "NIFTYMETAL", "NIFTYPSUBANK", "CNXENERGY", "CNXPHARMA", "NIFTYCOMMODITIES", "NIFTYHEALTHCARE"],
        "% from 30w ema": [63.2, 4.58, 2.35, 1.07, 0.74, 0.38, -0.85]
    })
    # Apply styling to mimic the image
    st.dataframe(df_table.style.background_gradient(subset=['% from 30w ema'], cmap='YlOrRd', vmin=0, vmax=65), 
                 hide_index=True, use_container_width=True, height=250)

with r2_col4:
    # Chart 8: Drawdowns Peaks (Bar Spikes)
    fig = go.Figure(data=[go.Bar(x=get_timeseries_data(), y=np.random.exponential(scale=200, size=dates), marker_color="#ED5565")])
    fig.update_layout(
        title="Drawdowns Peaks", height=300, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white", yaxis=dict(gridcolor='#eeeeee')
    )
    st.plotly_chart(fig, use_container_width=True)
