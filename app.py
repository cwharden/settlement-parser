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

st.set_page_config(page_title="Settlement Parser", page_icon="🚛", layout="wide")

st.title("📂 Settlement PDF Parser")
st.markdown("Upload **Bennett** or **Landstar** settlement PDFs and download the extracted data as CSV.")

st.info("ℹ️ **Free Trial:** You can process up to 2 PDF files per session.")

uploaded_files = st.file_uploader(
    "Choose PDF files",
    type="pdf",
    accept_multiple_files=True
)

# --- 2-File Limit (Session-Based) ---
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0

MAX_FILES = 2

if uploaded_files:
    # Check if user has already processed the max
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
    
    # --- Increment the processed count ---
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
        
        # Show preview
        st.subheader("📊 Data Preview")
        st.dataframe(all_rows[:10])
        
        # Generate Universal CSV
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
        
        # Generate QuickBooks CSV
        qb_csv = export_to_quickbooks(all_rows)
        
        # Convert to bytes for download
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

# --- Feedback & Carrier Requests ---
st.markdown("---")
st.subheader("📝 Feedback & Carrier Requests")

# Row 1: General Feedback
st.markdown("""
**Found a bug? Have a suggestion?** I'm constantly improving this tool, and your feedback helps me make it better for everyone.
""")

feedback_url = "mailto:settlementparsermail@gmail.com?subject=Settlement%20Parser%20Feedback"
st.link_button("📩 Send Feedback", feedback_url, type="secondary")

# Row 2: New Carrier Request (with divider)
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