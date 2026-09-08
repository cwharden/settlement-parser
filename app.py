import streamlit as st
import tempfile
import os
import csv
from io import StringIO

# Import all the parser functions from your existing script
from settlement_parser_final import (
    extract_text_from_pdf,
    detect_company,
    parse_bennett,
    parse_landstar,
    export_to_quickbooks
)

# ---------- IFTA Module ----------
def run_ifta():
    """IFTA Fuel Tax Module with Miles by State and Deadhead Tracking"""
    
    st.subheader("📊 IFTA Fuel Tax Tracker")
    st.markdown("Track your miles and fuel purchases by state for quarterly IFTA reporting.")
    
    # Initialize session state for IFTA data
    if 'ifta_trips' not in st.session_state:
        st.session_state.ifta_trips = []
    if 'ifta_fuel' not in st.session_state:
        st.session_state.ifta_fuel = []
    
    # --- Tab Layout for IFTA ---
    ifta_tab1, ifta_tab2, ifta_tab3 = st.tabs(["📝 Trip Log", "⛽ Fuel Log", "📊 Quarterly Report"])
    
    # ---------- IFTA TAB 1: Trip Log ----------
    with ifta_tab1:
        st.subheader("📝 Log a Trip")
        
        with st.form("trip_form"):
            col1, col2 = st.columns(2)
            with col1:
                trip_date = st.date_input("Date")
                origin = st.text_input("Origin (City, ST)")
                destination = st.text_input("Destination (City, ST)")
            with col2:
                trip_notes = st.text_area("Notes (optional)", height=68)
            
            st.markdown("**Miles by State (add each state you drove through)**")
            
            st.markdown("""
            Enter each state on a new line with format: **State, Total Miles, Deadhead Miles**
            Example: