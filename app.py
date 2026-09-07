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

# --- 2-File Limit ---
MAX_FILES = 2

if uploaded_files:
    if len(uploaded_files) > MAX_FILES:
        st.error(f"⚠️ You can only process up to {MAX_FILES} files at a time. Please select {MAX_FILES} or fewer files.")
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
                # ... rest of your code
            
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
            'Deduction Description', 'Deduction Amount', 'Net', 'Total Refunds'   # <--- ADD 'Total Refunds' HERE
        ]
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
        universal_csv = output.getvalue()
        
        # Generate QuickBooks CSV (now returns string)
        qb_csv = export_to_quickbooks(all_rows)
        
        # Convert to bytes for download (safe practice)
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