import streamlit as st
import tempfile
import os
import csv
from io import StringIO

# Import the parser functions (make sure settlement_parser_final.py is in the same folder)
from settlement_parser_final import (
    extract_text_from_pdf,
    detect_company,
    parse_bennett,
    parse_landstar,
    export_to_quickbooks
)

# ---------- IFTA Module ----------
# ---------- Helper: Load Tax Rates from CSV ----------
def load_tax_rates():
    """Load state tax rates from local CSV file. Fallback to hardcoded dict."""
    try:
        with open("state_tax_rates.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rates = {}
            for row in reader:
                state = row['state'].strip().upper()
                tax = float(row['tax_rate'].strip())
                rates[state] = tax
                return rates
    except FileNotFoundError:
        # Fallback – using correct Q3 2026 rates
        st.warning("⚠️ **Debug:** CSV not found – using hardcoded fallback rates")
        return {
            'AL': 0.31, 'AZ': 0.26, 'AR': 0.285, 'CA': 0.979, 'CO': 0.335,
            'CT': 0.499, 'DE': 0.22, 'FL': 0.4097, 'GA': 0.373, 'ID': 0.32,
            'IL': 0.738, 'IN': 0.63, 'IA': 0.325, 'KS': 0.26, 'KY': 0.325,
            'LA': 0.20, 'ME': 0.312, 'MD': 0.4745, 'MA': 0.24, 'MI': 0.524,
            'MN': 0.326, 'MS': 0.24, 'MO': 0.295, 'MT': 0.2975, 'NE': 0.318,
            'NV': 0.27, 'NH': 0.222, 'NJ': 0.561, 'NM': 0.21, 'NY': 0.3805,
            'NC': 0.41, 'ND': 0.23, 'OH': 0.47, 'OK': 0.19, 'OR': 0.00,
            'PA': 0.741, 'RI': 0.40, 'SC': 0.28, 'SD': 0.28, 'TN': 0.27,
            'TX': 0.20, 'UT': 0.379, 'VT': 0.31, 'VA': 0.479, 'WA': 0.595,
            'WV': 0.357, 'WI': 0.329, 'WY': 0.24
        }
# ---------- IFTA Module ----------
def run_ifta():
    """IFTA Fuel Tax Module with Trip Log, Fuel Log, Quarterly Report, and Load Estimator"""
    
    st.subheader("📊 IFTA Fuel Tax Tracker")
    st.markdown("Track your miles and fuel purchases by state for quarterly IFTA reporting, plus estimate load profits.")
    
    # Load tax rates from CSV (once per session)
    if 'tax_rates' not in st.session_state:
        st.session_state.tax_rates = load_tax_rates()
    
    state_tax_rates = st.session_state.tax_rates
    us_states = sorted(state_tax_rates.keys())
    
    # ✅ Show current rates status (moved here)
    st.success(f"📋 **Tax Rates:** Loaded from CSV – {len(state_tax_rates)} states available (Q3 2026)")
    
    # Initialize session state for data
    if 'ifta_trips' not in st.session_state:
        st.session_state.ifta_trips = []
    if 'ifta_fuel' not in st.session_state:
        st.session_state.ifta_fuel = []
    if 'ifta_estimates' not in st.session_state:
        st.session_state.ifta_estimates = []
    
    # --- Tab Layout ---
    ifta_tab1, ifta_tab2, ifta_tab3, ifta_tab4 = st.tabs([
        "📝 Trip Log", 
        "⛽ Fuel Log", 
        "📊 Quarterly Report",
        "💰 Load Estimator"
    ])
    
    # ---------- TAB 1: Trip Log ----------
    with ifta_tab1:
        st.subheader("📝 Log a Trip")
        
        with st.form("point_to_point_form"):
            st.markdown("**📍 Point‑to‑Point Trip (Origin → Destination)**")
            
            col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
            with col_h1:
                st.write("**Location (City, ST)**")
            with col_h2:
                st.write("**Total Miles**")
            with col_h3:
                st.write("**Deadhead**")
            st.divider()
            
            col_o1, col_o2, col_o3 = st.columns([2, 1, 1])
            with col_o1:
                orig_city = st.text_input("Origin City", placeholder="e.g. Lancaster", key="orig_city")
                orig_state = st.selectbox("Origin State", us_states, key="orig_state", index=us_states.index("SC") if "SC" in us_states else 0)
            with col_o2:
                orig_miles = st.number_input(" ", min_value=0.0, step=0.01, value=0.0, key="orig_miles", label_visibility="collapsed")
            with col_o3:
                orig_dead = st.number_input("  ", min_value=0.0, step=0.01, value=0.0, key="orig_dead", label_visibility="collapsed")
            
            col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
            with col_d1:
                dest_city = st.text_input("Destination City", placeholder="e.g. Hirman", key="dest_city")
                dest_state = st.selectbox("Destination State", us_states, key="dest_state", index=us_states.index("GA") if "GA" in us_states else 0)
            with col_d2:
                dest_miles = st.number_input("   ", min_value=0.0, step=0.01, value=0.0, key="dest_miles", label_visibility="collapsed")
            with col_d3:
                dest_dead = st.number_input("    ", min_value=0.0, step=0.01, value=0.0, key="dest_dead", label_visibility="collapsed")
            
            st.divider()
            col_date, col_notes = st.columns(2)
            with col_date:
                trip_date = st.date_input("Trip Date")
            with col_notes:
                trip_notes = st.text_area("Notes (optional)", height=68)
            
            submitted_ptp = st.form_submit_button("✅ Save Trip")
            
            if submitted_ptp:
                states_list = []
                total_miles = 0
                total_deadhead = 0
                valid = True
                
                if orig_miles > 0:
                    if orig_miles >= orig_dead:
                        states_list.append({'state': orig_state, 'total_miles': orig_miles, 'deadhead_miles': orig_dead, 'loaded_miles': orig_miles - orig_dead})
                        total_miles += orig_miles
                        total_deadhead += orig_dead
                    else:
                        st.warning(f"Origin deadhead ({orig_dead}) cannot exceed total miles ({orig_miles}).")
                        valid = False
                else:
                    st.warning("Origin total miles must be greater than 0.")
                    valid = False
                
                if dest_miles > 0:
                    if dest_miles >= dest_dead:
                        states_list.append({'state': dest_state, 'total_miles': dest_miles, 'deadhead_miles': dest_dead, 'loaded_miles': dest_miles - dest_dead})
                        total_miles += dest_miles
                        total_deadhead += dest_dead
                    else:
                        st.warning(f"Destination deadhead ({dest_dead}) cannot exceed total miles ({dest_miles}).")
                        valid = False
                else:
                    st.warning("Destination total miles must be greater than 0.")
                    valid = False
                
                if valid and states_list:
                    origin_display = f"{orig_city}, {orig_state}" if orig_city else orig_state
                    dest_display = f"{dest_city}, {dest_state}" if dest_city else dest_state
                    st.session_state.ifta_trips.append({
                        'date': trip_date.strftime("%m/%d/%Y"),
                        'origin': origin_display,
                        'destination': dest_display,
                        'notes': trip_notes,
                        'states': states_list,
                        'total_miles': total_miles,
                        'total_deadhead': total_deadhead,
                        'total_loaded': total_miles - total_deadhead
                    })
                    st.success(f"✅ Trip saved! {total_miles} total miles, {total_deadhead} deadhead miles.")
                elif not valid:
                    st.error("Please correct the errors above.")
        
        st.markdown("---")
        st.info("🔄 **For trips with 3+ states** (e.g., GA → SC → NC), use the multi‑state text area below.")
        
        with st.form("multi_state_form"):
            col1, col2 = st.columns(2)
            with col1:
                multi_date = st.date_input("Date", key="multi_date")
                multi_origin = st.text_input("Origin (City, ST)", key="multi_origin")
            with col2:
                multi_dest = st.text_input("Destination (City, ST)", key="multi_dest")
                multi_notes = st.text_area("Notes (optional)", height=68, key="multi_notes")
            st.markdown("**Miles by State (one per line)**")
            st.markdown("Format: **State, Total Miles, Deadhead Miles** (e.g. `GA, 169.72, 50.00`)")
            state_miles_input = st.text_area("State miles", height=100, key="multi_miles")
            submitted_multi = st.form_submit_button("✅ Save Multi-State Trip")
            
            if submitted_multi:
                if not state_miles_input.strip():
                    st.warning("Please enter at least one state with miles.")
                else:
                    lines = state_miles_input.strip().split('\n')
                    states = []
                    total_miles = 0
                    total_deadhead = 0
                    valid = True
                    for line in lines:
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) == 3:
                            state = parts[0].upper()
                            try:
                                total = float(parts[1])
                                deadhead = float(parts[2])
                                if total >= deadhead:
                                    states.append({'state': state, 'total_miles': total, 'deadhead_miles': deadhead, 'loaded_miles': total - deadhead})
                                    total_miles += total
                                    total_deadhead += deadhead
                                else:
                                    st.warning(f"Deadhead ({deadhead}) exceeds total ({total}) for {state}. Skipping.")
                                    valid = False
                            except ValueError:
                                st.warning(f"Invalid numbers in line: {line}. Skipping.")
                                valid = False
                        else:
                            st.warning(f"Invalid format: {line}. Expected: State, Total Miles, Deadhead Miles")
                            valid = False
                    if valid and states:
                        st.session_state.ifta_trips.append({
                            'date': multi_date.strftime("%m/%d/%Y"),
                            'origin': multi_origin,
                            'destination': multi_dest,
                            'notes': multi_notes,
                            'states': states,
                            'total_miles': total_miles,
                            'total_deadhead': total_deadhead,
                            'total_loaded': total_miles - total_deadhead
                        })
                        st.success(f"✅ Trip saved! {total_miles} total miles, {total_deadhead} deadhead miles.")
                    elif not valid:
                        st.error("Please correct the errors and try again.")
        
        # --- Trip History + CSV Download ---
        if st.session_state.ifta_trips:
            st.subheader("📋 Trip History")
            for idx, trip in enumerate(st.session_state.ifta_trips):
                with st.expander(f"Trip {idx+1}: {trip['date']} - {trip['origin']} → {trip['destination']} ({trip['total_miles']} mi)"):
                    st.write(f"**Date:** {trip['date']}")
                    st.write(f"**Origin:** {trip['origin']}")
                    st.write(f"**Destination:** {trip['destination']}")
                    st.write(f"**Notes:** {trip['notes']}")
                    st.write(f"**Total Miles:** {trip['total_miles']}")
                    st.write(f"**Deadhead Miles:** {trip['total_deadhead']}")
                    st.write(f"**Loaded Miles:** {trip['total_loaded']}")
                    st.write("**Miles by State:**")
                    state_data = []
                    for s in trip['states']:
                        state_data.append({
                            'State': s['state'],
                            'Total Miles': f"{s['total_miles']:.2f}",
                            'Deadhead': f"{s['deadhead_miles']:.2f}",
                            'Loaded': f"{s['loaded_miles']:.2f}"
                        })
                    st.dataframe(state_data)
                    if st.button(f"🗑️ Delete Trip {idx+1}", key=f"del_trip_{idx}"):
                        st.session_state.ifta_trips.pop(idx)
                        st.rerun()
            
            # CSV Download for Trip Log
            if st.button("📥 Download Trip Log (CSV)", key="dl_trips"):
                trip_flat = []
                for t in st.session_state.ifta_trips:
                    for s in t['states']:
                        trip_flat.append({
                            'Date': t['date'],
                            'Origin': t['origin'],
                            'Destination': t['destination'],
                            'Notes': t['notes'],
                            'State': s['state'],
                            'Total Miles': s['total_miles'],
                            'Deadhead': s['deadhead_miles'],
                            'Loaded': s['loaded_miles']
                        })
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=['Date', 'Origin', 'Destination', 'Notes', 'State', 'Total Miles', 'Deadhead', 'Loaded'])
                writer.writeheader()
                writer.writerows(trip_flat)
                st.download_button(
                    label="📥 Click to Download Trip Log CSV",
                    data=output.getvalue().encode('utf-8'),
                    file_name="IFTA_Trip_Log.csv",
                    mime="text/csv"
                )
    
    # ---------- TAB 2: Fuel Log ----------
    with ifta_tab2:
        st.subheader("⛽ Log Fuel Purchase")
        
        with st.form("fuel_form"):
            col1, col2 = st.columns(2)
            with col1:
                fuel_date = st.date_input("Date")
                state = st.selectbox("State/Province", us_states)
                gallons = st.number_input("Gallons Purchased", min_value=0.0, step=0.1)
            with col2:
                price_per_gallon = st.number_input("Price per Gallon ($)", min_value=0.0, step=0.01)
                tax_rate = state_tax_rates.get(state, 0.30)
                tax_paid = gallons * tax_rate
                st.info(f"**Tax Paid:** ${tax_paid:.2f} (at ${tax_rate:.2f}/gallon)")
            submitted = st.form_submit_button("Save Fuel Purchase")
            if submitted and gallons > 0:
                st.session_state.ifta_fuel.append({
                    'date': fuel_date.strftime("%m/%d/%Y"),
                    'state': state,
                    'gallons': gallons,
                    'price_per_gallon': price_per_gallon,
                    'tax_rate': tax_rate,
                    'tax_paid': tax_paid
                })
                st.success(f"✅ Fuel purchase saved! ({gallons} gallons in {state})")
            elif submitted:
                st.warning("Please enter gallons purchased.")
        
        if st.session_state.ifta_fuel:
            st.subheader("📋 Fuel Purchase History")
            st.dataframe(st.session_state.ifta_fuel)
            
            col_del, col_dl = st.columns(2)
            with col_del:
                if st.button("🗑️ Clear All Fuel Purchases"):
                    st.session_state.ifta_fuel = []
                    st.rerun()
            with col_dl:
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=['date', 'state', 'gallons', 'price_per_gallon', 'tax_rate', 'tax_paid'])
                writer.writeheader()
                writer.writerows(st.session_state.ifta_fuel)
                st.download_button(
                    label="📥 Download Fuel Log CSV",
                    data=output.getvalue().encode('utf-8'),
                    file_name="IFTA_Fuel_Log.csv",
                    mime="text/csv"
                )
    
    # ---------- TAB 3: Quarterly Report ----------
    with ifta_tab3:
        st.subheader("📊 Quarterly IFTA Report")
        
        if not st.session_state.ifta_trips:
            st.info("No trip data yet. Start by logging trips.")
        else:
            total_miles_by_state = {}
            total_deadhead_by_state = {}
            total_loaded_by_state = {}
            total_miles_all = 0
            total_deadhead_all = 0
            
            for trip in st.session_state.ifta_trips:
                for s in trip['states']:
                    state = s['state']
                    total_miles_by_state[state] = total_miles_by_state.get(state, 0) + s['total_miles']
                    total_deadhead_by_state[state] = total_deadhead_by_state.get(state, 0) + s['deadhead_miles']
                    total_loaded_by_state[state] = total_loaded_by_state.get(state, 0) + s['loaded_miles']
                    total_miles_all += s['total_miles']
                    total_deadhead_all += s['deadhead_miles']
            
            total_fuel_by_state = {}
            total_gallons_all = 0
            for fuel in st.session_state.ifta_fuel:
                state = fuel['state']
                total_fuel_by_state[state] = total_fuel_by_state.get(state, 0) + fuel['gallons']
                total_gallons_all += fuel['gallons']
            
            mpg = total_miles_all / total_gallons_all if total_gallons_all > 0 else 0
            
            st.subheader("📋 Quarterly Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Miles", f"{total_miles_all:,.0f}")
            with col2:
                st.metric("Deadhead Miles", f"{total_deadhead_all:,.0f}")
            with col3:
                st.metric("Deadhead %", f"{(total_deadhead_all/total_miles_all*100):.1f}%" if total_miles_all > 0 else "0%")
            with col4:
                st.metric("Fleet MPG", f"{mpg:.1f}")
            
            report_data = []
            total_tax_owed = 0
            total_tax_paid = 0
            
            for state, miles in total_miles_by_state.items():
                if miles > 0:
                    taxable_gallons = miles / mpg if mpg > 0 else 0
                    tax_rate = state_tax_rates.get(state, 0.30)
                    tax_owed = taxable_gallons * tax_rate
                    tax_paid = total_fuel_by_state.get(state, 0) * tax_rate
                    total_tax_owed += tax_owed
                    total_tax_paid += tax_paid
                    report_data.append({
                        'State': state,
                        'Miles': f"{miles:,.0f}",
                        'Deadhead': f"{total_deadhead_by_state.get(state, 0):,.0f}",
                        'Loaded': f"{total_loaded_by_state.get(state, 0):,.0f}",
                        'Taxable Gal': f"{taxable_gallons:,.1f}",
                        'Tax Rate': f"${tax_rate:.2f}",
                        'Tax Owed': f"${tax_owed:.2f}",
                        'Tax Paid': f"${tax_paid:.2f}",
                        'Net': f"${tax_paid - tax_owed:,.2f}"
                    })
            
            if report_data:
                st.dataframe(report_data)
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Tax Owed", f"${total_tax_owed:,.2f}")
                with col2:
                    st.metric("Total Tax Paid", f"${total_tax_paid:,.2f}")
                with col3:
                    net_credit = total_tax_paid - total_tax_owed
                    st.metric("Net (Paid - Owed)", f"${net_credit:,.2f}", 
                              delta=f"${net_credit:,.2f}" if net_credit >= 0 else f"-${abs(net_credit):,.2f}",
                              delta_color="normal" if net_credit >= 0 else "inverse")
                if net_credit > 0:
                    st.success(f"✅ You have a credit of ${net_credit:,.2f} for this quarter!")
                elif net_credit < 0:
                    st.warning(f"⚠️ You owe ${abs(net_credit):,.2f} for this quarter.")
                else:
                    st.info("You've broken even this quarter.")
                
                # CSV Download for Quarterly Report
                st.subheader("📥 Download Report")
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=['State', 'Miles', 'Deadhead', 'Loaded', 'Taxable Gal', 'Tax Rate', 'Tax Owed', 'Tax Paid', 'Net'])
                writer.writeheader()
                writer.writerows(report_data)
                summary_row = {
                    'State': 'TOTAL',
                    'Miles': f"{total_miles_all:,.0f}",
                    'Deadhead': f"{total_deadhead_all:,.0f}",
                    'Loaded': f"{total_miles_all - total_deadhead_all:,.0f}",
                    'Taxable Gal': '',
                    'Tax Rate': '',
                    'Tax Owed': f"${total_tax_owed:,.2f}",
                    'Tax Paid': f"${total_tax_paid:,.2f}",
                    'Net': f"${total_tax_paid - total_tax_owed:,.2f}"
                }
                rows_with_summary = report_data.copy()
                rows_with_summary.append(summary_row)
                output2 = StringIO()
                writer2 = csv.DictWriter(output2, fieldnames=['State', 'Miles', 'Deadhead', 'Loaded', 'Taxable Gal', 'Tax Rate', 'Tax Owed', 'Tax Paid', 'Net'])
                writer2.writeheader()
                writer2.writerows(rows_with_summary)
                st.download_button(
                    label="📥 Download Quarterly Report CSV",
                    data=output2.getvalue().encode('utf-8'),
                    file_name="IFTA_Quarterly_Report.csv",
                    mime="text/csv"
                )
    
    # ---------- TAB 4: Load Estimator ----------
    with ifta_tab4:
        st.subheader("💰 Load Estimator")
        st.markdown("Estimate gross revenue, fuel cost, IFTA tax, and net profit for a potential load.")
        
        with st.form("estimate_form"):
            st.markdown("**📍 Trip Details**")
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                est_origin = st.text_input("Origin (City, ST)", placeholder="e.g. Atlanta, GA")
                est_dest = st.text_input("Destination (City, ST)", placeholder="e.g. Charlotte, NC")
            with col_e2:
                est_date = st.date_input("Estimate Date")
                est_notes = st.text_area("Notes (optional)", height=68)
            
            st.markdown("**📍 Miles by State (Origin & Destination)**")
            col_o1, col_o2, col_o3 = st.columns([2, 1, 1])
            with col_o1:
                st.write("**Location**")
            with col_o2:
                st.write("**Miles**")
            with col_o3:
                st.write("**Deadhead**")
            st.divider()
            
            col_est_o1, col_est_o2, col_est_o3 = st.columns([2, 1, 1])
            with col_est_o1:
                est_orig_state = st.selectbox("Origin State", us_states, key="est_orig_state", index=us_states.index("GA") if "GA" in us_states else 0)
            with col_est_o2:
                est_orig_miles = st.number_input("  ", min_value=0.0, step=0.01, value=0.0, key="est_orig_miles", label_visibility="collapsed")
            with col_est_o3:
                est_orig_dead = st.number_input("   ", min_value=0.0, step=0.01, value=0.0, key="est_orig_dead", label_visibility="collapsed")
            
            col_est_d1, col_est_d2, col_est_d3 = st.columns([2, 1, 1])
            with col_est_d1:
                est_dest_state = st.selectbox("Destination State", us_states, key="est_dest_state", index=us_states.index("SC") if "SC" in us_states else 0)
            with col_est_d2:
                est_dest_miles = st.number_input("    ", min_value=0.0, step=0.01, value=0.0, key="est_dest_miles", label_visibility="collapsed")
            with col_est_d3:
                est_dest_dead = st.number_input("     ", min_value=0.0, step=0.01, value=0.0, key="est_dest_dead", label_visibility="collapsed")
            
            st.divider()
            st.markdown("**💰 Financial Estimates**")
            col_rate, col_mpg, col_fuel = st.columns(3)
            with col_rate:
                rate_per_mile = st.number_input("Rate per Mile ($)", min_value=0.0, step=0.01, value=2.50)
            with col_mpg:
                est_mpg = st.number_input("Estimated MPG", min_value=0.0, step=0.1, value=6.5)
            with col_fuel:
                est_fuel_price = st.number_input("Avg Fuel Price ($/gal)", min_value=0.0, step=0.01, value=3.40)
            
            submitted_est = st.form_submit_button("💰 Calculate & Save Estimate")
            
            if submitted_est:
                states_list = []
                total_miles = 0
                total_deadhead = 0
                valid = True
                
                if est_orig_miles > 0:
                    if est_orig_miles >= est_orig_dead:
                        states_list.append({'state': est_orig_state, 'total_miles': est_orig_miles, 'deadhead_miles': est_orig_dead})
                        total_miles += est_orig_miles
                        total_deadhead += est_orig_dead
                    else:
                        st.warning(f"Origin deadhead ({est_orig_dead}) cannot exceed total miles ({est_orig_miles}).")
                        valid = False
                else:
                    st.warning("Origin miles must be greater than 0.")
                    valid = False
                
                if est_dest_miles > 0:
                    if est_dest_miles >= est_dest_dead:
                        states_list.append({'state': est_dest_state, 'total_miles': est_dest_miles, 'deadhead_miles': est_dest_dead})
                        total_miles += est_dest_miles
                        total_deadhead += est_dest_dead
                    else:
                        st.warning(f"Destination deadhead ({est_dest_dead}) cannot exceed total miles ({est_dest_miles}).")
                        valid = False
                else:
                    st.warning("Destination miles must be greater than 0.")
                    valid = False
                
                if valid and states_list:
                    gross_revenue = total_miles * rate_per_mile
                    fuel_gallons_needed = total_miles / est_mpg if est_mpg > 0 else 0
                    fuel_cost = fuel_gallons_needed * est_fuel_price
                    
                    total_tax_owed_est = 0
                    state_breakdown = []
                    for s in states_list:
                        state = s['state']
                        taxable_gal = s['total_miles'] / est_mpg if est_mpg > 0 else 0
                        tax_rate = state_tax_rates.get(state, 0.30)
                        tax_owed = taxable_gal * tax_rate
                        total_tax_owed_est += tax_owed
                        state_breakdown.append(f"{state}: {tax_owed:.2f}")
                    
                    net_profit = gross_revenue - fuel_cost - total_tax_owed_est
                    
                    st.session_state.ifta_estimates.append({
                        'date': est_date.strftime("%m/%d/%Y"),
                        'origin': est_origin,
                        'destination': est_dest,
                        'notes': est_notes,
                        'total_miles': total_miles,
                        'total_deadhead': total_deadhead,
                        'rate_per_mile': rate_per_mile,
                        'gross_revenue': gross_revenue,
                        'mpg': est_mpg,
                        'fuel_gallons': fuel_gallons_needed,
                        'fuel_cost': fuel_cost,
                        'ifta_tax_owed': total_tax_owed_est,
                        'net_profit': net_profit,
                        'state_breakdown': "; ".join(state_breakdown)
                    })
                    
                    st.success(f"✅ Estimate saved! Net Profit: **${net_profit:,.2f}**")
                    st.metric("Gross Revenue", f"${gross_revenue:,.2f}")
                    st.metric("Fuel Cost", f"${fuel_cost:,.2f}")
                    st.metric("IFTA Tax", f"${total_tax_owed_est:,.2f}")
                    st.metric("Net Profit", f"${net_profit:,.2f}", delta=f"${net_profit:,.2f}")
                elif not valid:
                    st.error("Please correct the errors above.")
        
        # --- Estimator History ---
        if st.session_state.ifta_estimates:
            st.subheader("📋 Estimate History")
            est_display = []
            for idx, e in enumerate(st.session_state.ifta_estimates):
                est_display.append({
                    'Date': e['date'],
                    'Origin': e['origin'],
                    'Destination': e['destination'],
                    'Total Miles': e['total_miles'],
                    'Rate': f"${e['rate_per_mile']:.2f}",
                    'Gross': f"${e['gross_revenue']:.2f}",
                    'Fuel Cost': f"${e['fuel_cost']:.2f}",
                    'IFTA Tax': f"${e['ifta_tax_owed']:.2f}",
                    'Net Profit': f"${e['net_profit']:.2f}"
                })
            st.dataframe(est_display)
            
            for idx, e in enumerate(st.session_state.ifta_estimates):
                with st.expander(f"Estimate {idx+1}: {e['date']} - {e['origin']} → {e['destination']} (Net: ${e['net_profit']:.2f})"):
                    st.write(f"**Total Miles:** {e['total_miles']}")
                    st.write(f"**Rate per Mile:** ${e['rate_per_mile']:.2f}")
                    st.write(f"**Gross Revenue:** ${e['gross_revenue']:.2f}")
                    st.write(f"**MPG:** {e['mpg']}")
                    st.write(f"**Fuel Gallons:** {e['fuel_gallons']:.1f}")
                    st.write(f"**Fuel Cost:** ${e['fuel_cost']:.2f}")
                    st.write(f"**IFTA Tax Owed:** ${e['ifta_tax_owed']:.2f}")
                    st.write(f"**Net Profit:** ${e['net_profit']:.2f}")
                    st.write(f"**State Tax Breakdown:** {e['state_breakdown']}")
                    if st.button(f"🗑️ Delete Estimate {idx+1}", key=f"del_est_{idx}"):
                        st.session_state.ifta_estimates.pop(idx)
                        st.rerun()
            
            st.subheader("📥 Download Estimates")
            est_flat = []
            for e in st.session_state.ifta_estimates:
                est_flat.append({
                    'Date': e['date'],
                    'Origin': e['origin'],
                    'Destination': e['destination'],
                    'Notes': e['notes'],
                    'Total Miles': e['total_miles'],
                    'Deadhead': e['total_deadhead'],
                    'Rate per Mile': e['rate_per_mile'],
                    'Gross Revenue': e['gross_revenue'],
                    'MPG': e['mpg'],
                    'Fuel Gallons': e['fuel_gallons'],
                    'Fuel Cost': e['fuel_cost'],
                    'IFTA Tax Owed': e['ifta_tax_owed'],
                    'Net Profit': e['net_profit'],
                    'State Breakdown': e['state_breakdown']
                })
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=['Date', 'Origin', 'Destination', 'Notes', 'Total Miles', 'Deadhead', 'Rate per Mile', 'Gross Revenue', 'MPG', 'Fuel Gallons', 'Fuel Cost', 'IFTA Tax Owed', 'Net Profit', 'State Breakdown'])
            writer.writeheader()
            writer.writerows(est_flat)
            st.download_button(
                label="📥 Download Load Estimates CSV",
                data=output.getvalue().encode('utf-8'),
                file_name="IFTA_Load_Estimates.csv",
                mime="text/csv"
            )
# ---------- MAIN APP ----------
st.set_page_config(page_title="Settlement Parser", page_icon="🚛", layout="wide")

st.title("📂 Settlement Parser")
st.markdown("Upload settlements, track IFTA fuel tax, and manage your books all in one place.")

# --- Create Tabs ---
tab1, tab2, tab3 = st.tabs(["📄 Settlement Parser", "📊 IFTA Fuel Tax", "📝 Feedback"])

# ---------- TAB 1: Settlement Parser ----------
with tab1:
    st.markdown("Upload **Bennett** or **Landstar** settlement PDFs and download the extracted data as CSV.")
    st.info("ℹ️ **Free Trial:** You can process up to 2 PDF files per session.")
    
    uploaded_files = st.file_uploader(
        "Choose PDF files",
        type="pdf",
        accept_multiple_files=True
    )
    
    if 'processed_count' not in st.session_state:
        st.session_state.processed_count = 0
    
    MAX_FILES = 2
    
    if uploaded_files:
        if st.session_state.processed_count >= MAX_FILES:
            st.error(f"⚠️ You have already processed {MAX_FILES} files. Please refresh the page to start a new session.")
            st.stop()
        
        if uploaded_files:
            all_rows = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {uploaded_file.name}...")
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    text = extract_text_from_pdf(tmp_path)
                    if not text:
                        st.warning(f"No text extracted from {uploaded_file.name}. Skipping.")
                        os.unlink(tmp_path)
                        continue
                    
                    lines = text.split('\n')
                    company = detect_company(text)
                    
                    if company == 'BENNETT':
                        payment_rows, deduction_rows = parse_bennett(text, lines)
                    elif company == 'LANDSTAR':
                        payment_rows, deduction_rows = parse_landstar(text, lines)
                    else:
                        payment_rows, deduction_rows = parse_bennett(text, lines)
                    
                    rows = payment_rows + deduction_rows
                    all_rows.extend(rows)
                    os.unlink(tmp_path)
                except Exception as e:
                    st.error(f"Error processing {uploaded_file.name}: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            st.session_state.processed_count += len(uploaded_files)
            status_text.text("Processing complete!")
            
            if all_rows:
                st.success(f"✅ Extracted **{len(all_rows)}** rows from **{len(uploaded_files)}** files!")
                
                # Add Net column
                for row in all_rows:
                    entered_amt = row.get('Entered Amount', '')
                    deduction_amt = row.get('Deduction Amount', '')
                    net = ''
                    if entered_amt:
                        try:
                            net = float(entered_amt)
                        except:
                            pass
                    if deduction_amt:
                        try:
                            ded = float(deduction_amt)
                            net = net + ded if net else ded
                        except:
                            pass
                    row['Net'] = f"{net:.2f}" if net != '' else ''
                
                st.subheader("📊 Data Preview")
                st.dataframe(all_rows[:10])
                
                fieldnames = [
                    'Company', 'Control #', 'Terminal', 'EFS #', 'Driver', 'Date',
                    'Truck #', 'Billed Miles', 'Trailer #', 'Check Amount',
                    'Process #', 'Orig', 'Dest', 'Miles', 'Truck Repair Fund',
                    'Escrow Balance', 'T_Truck #', 'Total_1099_Revenue',
                    'Rate Base', 'Line_1099_Revenue', 'Original Balance',
                    'Remaining Balance', 'Gross_Revenue', 'Last_Statement_Balance',
                    'Direct_Deposit_Check#', 'Direct_Deposit_Amount',
                    'Entered Date', 'Entered Processed Date', 'Entered Description',
                    'Entered Amount', 'Total Deductions', 'Balance to be Paid',
                    'Deduction Entered Date', 'Deduction Processed Date',
                    'Deduction Description', 'Deduction Amount', 'Net', 'Total Refunds'
                ]
                
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
                universal_csv = output.getvalue()
                
                qb_csv = export_to_quickbooks(all_rows)
                
                universal_bytes = universal_csv.encode('utf-8')
                qb_bytes = qb_csv.encode('utf-8')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📥 Download Universal CSV",
                        data=universal_bytes,
                        file_name="UNIVERSAL_SETTLEMENTS_FINAL.csv",
                        mime="text/csv"
                    )
                with col2:
                    st.download_button(
                        label="📥 Download QuickBooks CSV",
                        data=qb_bytes,
                        file_name="QUICKBOOKS_IMPORT.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("No data extracted from the uploaded files.")

# ---------- TAB 2: IFTA ----------
with tab2:
    run_ifta()

# ---------- TAB 3: Feedback ----------
with tab3:
    st.markdown("---")
    st.subheader("📝 Feedback & Carrier Requests")
    st.markdown("""
    **Found a bug? Have a suggestion?** I'm constantly improving this tool, and your feedback helps me make it better for everyone.
    """)
    feedback_url = "mailto:settlementparsermail@gmail.com?subject=Settlement%20Parser%20Feedback"
    st.link_button("📩 Send Feedback", feedback_url, type="secondary")
    
    st.markdown("---")
    st.subheader("🚛 Don't see your carrier?")
    st.markdown("""
    Currently supporting **Bennett** and **Landstar**. If you use a different carrier, I can add support for it!
    
    **What I need from you:**
    - 3-5 sample settlement PDFs (different dates if possible)
    - Your carrier name
    - Any specific data you need captured
    
    **Pricing:**
    - **$150 one-time fee** (standard carriers)
    - **$250 one-time fee** (complex carriers with images/OCR)
    - **Free with annual subscription** ($99/year)
    
    **Turnaround:** 2-3 weeks (I work on this in my free time)
    """)
    carrier_request_url = "mailto:settlementparsermail@gmail.com?subject=New%20Carrier%20Request%20-%20[Carrier%20Name]"
    st.link_button("🚛 Request a New Carrier", carrier_request_url, type="primary")