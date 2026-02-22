# heatseeker_web.py - Polished, auto-refreshing, dark-mode ready dashboard

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import plotly.express as px
import datetime
import numpy as np
from scipy.stats import norm

from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, OptionContractsRequest

# ────────────────────────────────────────────────
# Your keys
API_KEY = 'CKEAW2L73NRACB57V55I5VNQL7'
SECRET_KEY = '5ekewPLbYhQ3ksFQd3Ff5Y7GQdGzk9qNVPQh4PbVQMky'

client = OptionHistoricalDataClient(API_KEY, SECRET_KEY)

# Paste your functions here (calculate_vanna, get_next_expiration, compute_heatseeker)
# Copy them from your working console version - they stay the same

# ────────────────────────────────────────────────
st.set_page_config(page_title="Heatseeker Live", layout="wide")

# Dark mode toggle
dark_mode = st.sidebar.checkbox("Dark Mode", value=True)
if dark_mode:
    st.markdown("""
        <style>
        section[data-testid="stSidebar"] {background-color: #111;}
        .stApp {background-color: #0e1117; color: white;}
        .stButton>button {background-color: #1f77b4; color: white;}
        </style>
    """, unsafe_allow_html=True)

st.title("Heatseeker - Live Dealer Positioning")

# Sidebar
with st.sidebar:
    st.header("Settings")
    ticker = st.selectbox("Ticker", ["SPY", "QQQ", "SPX", "GLD", "CVNA", "TSM", "TSLA"], index=0)
    mode = st.radio("Mode", ["0DTE (Today)", "SWING (Next Expiration)"])
    refresh_sec = st.slider("Auto-refresh every", 30, 300, 60, step=10)
    st.info(f"Auto-refresh active every {refresh_sec} seconds (best during market hours).")

# Auto-refresh
st_autorefresh(interval=refresh_sec * 1000, key="live_refresh")

# Market hours check (EST)
now_est = datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=-5)))
is_market_open = (now_est.weekday() < 5) and (9 <= now_est.hour < 16 or (now_est.hour == 9 and now_est.minute >= 30))

if not is_market_open:
    st.warning("Markets are closed (weekend/after-hours). Data may be stale or unavailable. Try Monday 9:30 AM EST.")

if st.button("Analyze / Refresh Now"):
    with st.spinner(f"Fetching live data for {ticker}..."):
        if mode == "0DTE (Today)":
            expiration = datetime.date.today().isoformat()
        else:
            expiration = get_next_expiration(ticker)
            if not expiration:
                st.error("No future expiration found.")
                st.stop()

        res_df = compute_heatseeker(ticker, expiration)

    if res_df is not None:
        st.success(f"Updated at {datetime.datetime.now().strftime('%H:%M:%S EST')}")

        # Key metrics cards
        col1, col2, col3, col4 = st.columns(4)
        king = res_df.loc[res_df['abs_gex'].idxmax()]['strike']
        col1.metric("King Node", king, delta=None, delta_color="normal")
        # Add gatekeepers/floors/ceilings as needed (e.g. col2.metric("Strongest Gatekeeper", ...))

        # Top strikes table
        st.subheader("Top Strikes by Strength")
        st.dataframe(
            res_df.sort_values('abs_gex', ascending=False).head(15)[['strike', 'net_gex', 'net_vex', 'oi_total']],
            use_container_width=True,
            height=500
        )

        # Interactive Plotly charts
        st.subheader("GEX & VEX Visuals")
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            fig_gex = px.bar(res_df, x='strike', y='net_gex',
                             title="GEX Heatmap",
                             color='net_gex',
                             color_continuous_scale=['green', 'red'])
            fig_gex.update_layout(xaxis_title="Strike", yaxis_title="Net GEX")
            st.plotly_chart(fig_gex, use_container_width=True)

        with col_chart2:
            fig_vex = px.bar(res_df, x='strike', y='net_vex',
                             title="VEX Heatmap",
                             color='net_vex',
                             color_continuous_scale=['green', 'red'])
            fig_vex.update_layout(xaxis_title="Strike", yaxis_title="Net VEX")
            st.plotly_chart(fig_vex, use_container_width=True)

        # Download
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Full Results (CSV)", csv, f"{ticker}_{expiration}_heatseeker.csv", "text/csv")

    else:
        st.warning("No data returned. Markets may be closed, or check ticker/expiration.")

# Footer
st.markdown("---")
st.caption(f"Powered by Alpaca • Auto-refresh: {refresh_sec}s • Best during 9:30 AM – 4 PM EST")
