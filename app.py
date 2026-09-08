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
            
            # Use a raw string to avoid escape issues, and keep triple quotes on their own lines
            st.markdown("""
            Enter each state on a new line with format: **State, Total Miles, Deadhead Miles**
            Example:
            GA, 169.72, 50.00
            SC, 87.42, 10.00
            """)
            
            state_miles_input = st.text_area("State miles (one per line)", height=100)
            
            submitted = st.form_submit_button("Save Trip")
            
            if submitted:
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
                                    states.append({
                                        'state': state,
                                        'total_miles': total,
                                        'deadhead_miles': deadhead,
                                        'loaded_miles': total - deadhead
                                    })
                                    total_miles += total
                                    total_deadhead += deadhead
                                else:
                                    st.warning(f"Deadhead miles ({deadhead}) cannot exceed total miles ({total}) for {state}. Skipping this line.")
                                    valid = False
                            except ValueError:
                                st.warning(f"Invalid numbers in line: {line}. Skipping.")
                                valid = False
                        else:
                            st.warning(f"Invalid format in line: {line}. Expected: State, Total Miles, Deadhead Miles")
                            valid = False
                    
                    if valid and states:
                        st.session_state.ifta_trips.append({
                            'date': trip_date.strftime("%m/%d/%Y"),
                            'origin': origin,
                            'destination': destination,
                            'notes': trip_notes,
                            'states': states,
                            'total_miles': total_miles,
                            'total_deadhead': total_deadhead,
                            'total_loaded': total_miles - total_deadhead
                        })
                        st.success(f"✅ Trip saved! {total_miles} total miles, {total_deadhead} deadhead miles.")
                    elif not valid:
                        st.error("Please correct the errors and try again.")
        
        # Show existing trips (indented correctly under with ifta_tab1)
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
    
    # ---------- IFTA TAB 2: Fuel Log ----------
    with ifta_tab2:
        st.subheader("⛽ Log Fuel Purchase")
        
        state_tax_rates = {
            'AL': 0.28, 'AZ': 0.26, 'AR': 0.28, 'CA': 0.53, 'CO': 0.22,
            'CT': 0.44, 'DE': 0.23, 'FL': 0.34, 'GA': 0.32, 'ID': 0.33,
            'IL': 0.46, 'IN': 0.36, 'IA': 0.34, 'KS': 0.26, 'KY': 0.28,
            'LA': 0.27, 'ME': 0.36, 'MD': 0.37, 'MA': 0.27, 'MI': 0.30,
            'MN': 0.29, 'MS': 0.29, 'MO': 0.30, 'MT': 0.30, 'NE': 0.29,
            'NV': 0.30, 'NH': 0.23, 'NJ': 0.37, 'NM': 0.27, 'NY': 0.45,
            'NC': 0.36, 'ND': 0.23, 'OH': 0.28, 'OK': 0.26, 'OR': 0.33,
            'PA': 0.39, 'RI': 0.35, 'SC': 0.28, 'SD': 0.30, 'TN': 0.28,
            'TX': 0.20, 'UT': 0.31, 'VT': 0.33, 'VA': 0.30, 'WA': 0.49,
            'WV': 0.36, 'WI': 0.30, 'WY': 0.24
        }
        
        with st.form("fuel_form"):
            col1, col2 = st.columns(2)
            with col1:
                fuel_date = st.date_input("Date")
                state = st.selectbox("State/Province", list(state_tax_rates.keys()))
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
            if st.button("🗑️ Clear All Fuel Purchases"):
                st.session_state.ifta_fuel = []
                st.rerun()
    
    # ---------- IFTA TAB 3: Quarterly Report ----------
    with ifta_tab3:
        st.subheader("📊 Quarterly IFTA Report")
        
        if not st.session_state.ifta_trips:
            st.info("No trip data yet. Start by logging trips.")
            return
        
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