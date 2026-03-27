import streamlit as st

# Configure the page
st.set_page_config(
    page_title="Market Breadth Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Live Market Breadth Indicators")
st.write("Deployment successful! The UI components are currently being built.")

# A simple layout test
col1, col2 = st.columns(2)
with col1:
    st.info("US Market Data will appear here.")
with col2:
    st.info("Indian Market Data will appear here.")