import pdfplumber
import csv
import re
import tkinter as tk
from tkinter import filedialog
import os
import sys
import pytesseract
from pdf2image import convert_from_path
from io import StringIO

# Set Tesseract path (adjust if yours is different)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("=" * 60)
print("🚀 LANDSTAR SETTLEMENT PARSER STARTING...")
print("=" * 60)

# ---------- QuickBooks Export ----------
def format_date_for_quickbooks(date_str):
    """Convert various date formats to MM/DD/YYYY"""
    if not date_str:
        return ''
    
    # If it's already MM/DD/YYYY
    if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
        return date_str
    
    # If it's DD-MMM format (11-Apr)
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    match = re.match(r'(\d{1,2})-([A-Za-z]{3})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month = month_map.get(match.group(2), '01')
        # Use the year from the invoice date or default to 2022
        return f"{month}/{day}/2022"
    
    # If it's MM-DD (4-11), convert to MM/DD/2022
    match = re.match(r'(\d{1,2})-(\d{1,2})', date_str)
    if match:
        month = match.group(1).zfill(2)
        day = match.group(2).zfill(2)
        return f"{month}/{day}/2022"
    
    return date_str


def export_to_quickbooks(all_rows, output_file="QUICKBOOKS_IMPORT.csv"):
    """Convert extracted data to QuickBooks import format and return CSV content"""
    qb_rows = []
    for row in all_rows:
        invoice_no = row.get('Control #', '')
        if not invoice_no:
            invoice_no = row.get('control_number', '')
        if not invoice_no:
            invoice_no = '4920'
        company_name = row.get('Company', 'Landstar')
        invoice_date = format_date_for_quickbooks(row.get('Date', ''))
        entered_date = format_date_for_quickbooks(row.get('Entered Date', '') or row.get('Date', ''))
        processed_date = format_date_for_quickbooks(row.get('Entered Processed Date', '') or row.get('Date', ''))
        deduction_date = format_date_for_quickbooks(row.get('Deduction Entered Date', '') or row.get('Date', ''))
        
        if row.get('Entered Description'):
            qb_row = {
                'InvoiceNo': invoice_no,
                'Customer': company_name,
                'InvoiceDate': invoice_date,
                'DueDate': processed_date,
                'Terms': '',
                'Location': f"{row.get('Orig', '')} - {row.get('Dest', '')}" if row.get('Orig') and row.get('Dest') else '',
                'Memo': '',
                'Item(Product/Service)': '',
                'ItemDescription': row.get('Entered Description', ''),
                'ItemQuantity': '',
                'ItemRate': '',
                'ItemAmount': row.get('Entered Amount', ''),
                'Service Date': entered_date
            }
            qb_rows.append(qb_row)
        
        if row.get('Deduction Description'):
            amount = row.get('Deduction Amount', '')
            if amount and amount != '0.00':
                try:
                    amount_clean = amount.replace('--', '-').replace(',', '').strip()
                    if not amount_clean.startswith('-'):
                        amount_clean = f"-{amount_clean}"
                    amount = amount_clean
                except:
                    pass
            qb_row = {
                'InvoiceNo': invoice_no,
                'Customer': company_name,
                'InvoiceDate': invoice_date,
                'DueDate': deduction_date,
                'Terms': '',
                'Location': f"{row.get('Orig', '')} - {row.get('Dest', '')}" if row.get('Orig') and row.get('Dest') else '',
                'Memo': '',
                'Item(Product/Service)': '',
                'ItemDescription': row.get('Deduction Description', ''),
                'ItemQuantity': '',
                'ItemRate': '',
                'ItemAmount': amount,
                'Service Date': deduction_date
            }
            qb_rows.append(qb_row)
    
    fieldnames = ['InvoiceNo', 'Customer', 'InvoiceDate', 'DueDate', 'Terms',
                  'Location', 'Memo', 'Item(Product/Service)', 'ItemDescription',
                  'ItemQuantity', 'ItemRate', 'ItemAmount', 'Service Date']
    
    # Write to StringIO instead of file
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(qb_rows)
    return output.getvalue()  # Return CSV content as string

# ---------- Date Helpers ----------
def parse_date(date_str):
    """Convert MM/DD/YY or MM-DD to MM/DD/YYYY (or keep MM-DD for Landstar)"""
    if not date_str:
        return ''
    date_str = date_str.replace('-', '/')
    parts = date_str.split('/')
    if len(parts) == 2:
        # For Landstar, keep as MM/DD (year not always provided)
        return date_str
    if len(parts) == 3:
        month = parts[0].zfill(2)
        day = parts[1].zfill(2)
        year = parts[2]
        if len(year) == 2:
            year = f"20{year}"
        return f"{month}/{day}/{year}"
    return date_str

def clean_field(value):
    if not value or value == 'CHECK' or value == 'CHECK AMOUNT:' or 'CHECK' in str(value):
        return ''
    return value

# ---------- PDF Text Extraction (with OCR fallback) ----------
def extract_text_from_pdf(pdf_file):
    """Extract text from PDF, using OCR if needed"""
    print(f"  🔍 Extracting text from PDF...")
    with pdfplumber.open(pdf_file) as pdf:
        all_text = ''
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                all_text += f"\n--- PAGE {i+1} ---\n" + page_text + '\n'
        if all_text and len(all_text.strip()) > 100:
            print(f"  ✓ Text extracted successfully (length: {len(all_text)})")
            return all_text
    print(f"  🔍 No text found with pdfplumber, using OCR...")
    try:
        images = convert_from_path(pdf_file)
        all_text = ''
        for i, image in enumerate(images):
            print(f"  🔍 OCR Page {i+1} of {len(images)}...")
            page_text = pytesseract.image_to_string(image)
            all_text += f"\n--- PAGE {i+1} ---\n" + page_text + '\n'
        if all_text and len(all_text.strip()) > 50:
            print(f"  ✓ OCR complete (length: {len(all_text)})")
            return all_text
        else:
            print(f"  ⚠️ OCR found very little text")
            return ''
    except Exception as e:
        print(f"  ❌ OCR failed: {e}")
        return ''

def extract_statement_totals_from_text(text):
    """
    Extract the Statement Totals from the last page of a Landstar PDF.
    Looks for the LAST Totals line with three numbers: Revenue, Deductions, Net.
    """
    totals = {
        'statement_revenue': '',
        'statement_deductions': '',
        'statement_net': '',
        'direct_deposit_check': '',
        'direct_deposit_amount': ''
    }
    
    lines = text.split('\n')
    
    # Find ALL lines containing "Totals" and take the LAST one
    totals_lines = []
    for line in lines:
        if re.search(r'\bTotals?\b', line, re.IGNORECASE):
            totals_lines.append(line)
    
    if totals_lines:
        line = totals_lines[-1]
        numbers = re.findall(r'([\d,]+\.?\d*)', line)
        
	# Removed Debug Prints
	# print(f"DEBUG - Totals line: '{line}'")
        # print(f"DEBUG - Numbers found: {numbers}")
        
        if len(numbers) >= 4:
            # 1st = Revenue, 2nd = Refunds, 3rd = Deductions, 4th = Net
            totals['statement_revenue'] = numbers[0].replace(',', '')
            totals['statement_refunds'] = numbers[1].replace(',', '')
            totals['statement_deductions'] = numbers[2].replace(',', '')
            totals['statement_net'] = numbers[3].replace(',', '')
        elif len(numbers) >= 3:
            totals['statement_revenue'] = numbers[0].replace(',', '')
            totals['statement_deductions'] = numbers[1].replace(',', '')
            if len(numbers) >= 3:
                totals['statement_net'] = numbers[2].replace(',', '')
    
    # If no Totals line found, fallback to Subtotal
    if not totals['statement_revenue']:
        for line in lines:
            if 'Subtotal' in line:
                numbers = re.findall(r'([\d,]+\.?\d*)', line)
                if numbers:
                    totals['statement_revenue'] = numbers[0].replace(',', '')
                    if len(numbers) > 1:
                        totals['statement_deductions'] = numbers[1].replace(',', '')
                    if len(numbers) > 2:
                        totals['statement_net'] = numbers[2].replace(',', '')
                    break
    
    # Direct Deposit Check Number and Check Amount
    for line in lines:
        if 'Direct Deposit Check' in line:
            # Check number
            check_match = re.search(r'Direct\s*Deposit\s*Check\s*Number:?\s*(\d+)', line, re.IGNORECASE)
            if check_match:
                totals['direct_deposit_check'] = check_match.group(1)
            # Check amount (the number after the check number)
            amount_match = re.search(r'Direct\s*Deposit\s*Check\s*Number:?\s*\d+\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if amount_match:
                totals['direct_deposit_amount'] = amount_match.group(1).replace(',', '')
            # Fallback: if no amount found, look for any number after the check number
            if not amount_match:
                numbers = re.findall(r'([\d,]+\.?\d*)', line)
                if len(numbers) >= 2:
                    totals['direct_deposit_amount'] = numbers[1].replace(',', '')
    
    return totals

# ---------- Bennett Parser ----------
def parse_bennett(text, lines):
    """Parse Bennett settlement PDFs"""
    header = extract_header_info_bennett(text)
    header['Truck Repair Fund'] = extract_truck_repair_fund(text)
    
    payment_rows = []
    deduction_rows = []
    in_deduction_section = False
    passed_total_pay = False
    
    has_deduction_header = False
    deduction_line_count = 0
    
    for line in lines:
        if line.strip() == "Deduction":
            has_deduction_header = True
            continue
        if has_deduction_header:
            if re.match(r'\d{1,2}/\d{1,2}/\d{4}', line.strip()):
                deduction_line_count += 1
    
    is_single_item_deduction = (has_deduction_header and deduction_line_count == 1)
    
    for line in lines:
        if "ENTERED PROCESSED:" in line:
            in_deduction_section = False
            continue
        elif "Deduction" in line and "TOTAL DEDUCTIONS" not in line:
            in_deduction_section = True
            continue
        elif "TOTAL PAY BEFORE DEDUCTIONS:" in line:
            passed_total_pay = True
            continue
        
        if any(x in line for x in ['COMPANY:', 'TERMINAL:', 'NAME:', 'TRUCK:', 
                                  'BALANCE', 'Y.T.D', 'DESCRIPTION',
                                  'Earnings', 'TRUCK REPAIR']):
            continue
        
        dollar_pos = -1
        is_negative = False
        
        if '$-' in line:
            dollar_pos = line.find('$-')
            is_negative = True
        elif '$' in line:
            dollar_pos = line.find('$')
        
        if dollar_pos == -1:
            continue
        
        description = line[:dollar_pos].strip()
        amount_part = line[dollar_pos:].strip()
        
        if is_negative:
            amount_match = re.match(r'\$-?([\d,]+\.?\d*)', amount_part)
        else:
            amount_match = re.match(r'\$([\d,]+\.?\d*)', amount_part)
            
        if amount_match:
            amount_with_symbol = amount_match.group(0)
            amount_clean = amount_with_symbol.replace('$', '').replace(',', '')
            if is_negative:
                amount_clean = f"-{amount_clean}"
        else:
            continue
        
        dates = re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
        if len(dates) >= 2:
            date1 = parse_date(dates[0])
            date2 = parse_date(dates[1])
        else:
            continue
        
        for d in dates:
            description = description.replace(d, '')
        description = re.sub(r'\s+', ' ', description).strip()
        
        if len(description) < 2:
            continue
        
        if is_single_item_deduction and in_deduction_section:
            is_deduction = False
        elif 'RECEIVED CK#' in description or 'RECEIVED EFS CK#' in description:
            is_deduction = False
        elif 'TARPING' in description:
            is_deduction = passed_total_pay
        else:
            is_deduction = in_deduction_section or is_negative or any(k in description for k in 
                          ['ESCROW', 'FEE', 'DMG', 'TAX', 'ATBS', 'KINGPIN', 'BOBTAIL',
                           'OCC/ACC', 'TABLET'])
        
        row = header.copy()
        
        if is_deduction:
            row['Deduction Entered Date'] = date1
            row['Deduction Processed Date'] = date2
            row['Deduction Description'] = description
            row['Deduction Amount'] = amount_clean
            row['Entered Date'] = ''
            row['Entered Processed Date'] = ''
            row['Entered Description'] = ''
            row['Entered Amount'] = ''
            deduction_rows.append(row)
        else:
            row['Entered Date'] = date1
            row['Entered Processed Date'] = date2
            row['Entered Description'] = description
            row['Entered Amount'] = amount_clean
            row['Deduction Entered Date'] = ''
            row['Deduction Processed Date'] = ''
            row['Deduction Description'] = ''
            row['Deduction Amount'] = ''
            payment_rows.append(row)
    
    return payment_rows, deduction_rows

# ---------- Truck Repair Fund (Bennett) ----------
def extract_truck_repair_fund(text):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if "TRUCK REPAIR FUND" in line:
            for j in range(i, min(i+5, len(lines))):
                if "Balance Available:" in lines[j]:
                    match = re.search(r'\$([\d,]+\.?\d*)', lines[j])
                    if match:
                        return match.group(1).replace(',', '')
                    break
    return "0.00"



# ---------- Bennett Header ----------
def extract_header_info_bennett(text):
    header = {
        'Company': '', 'Control #': '', 'Terminal': '', 'EFS #': '',
        'Driver': '', 'Date': '', 'Truck #': '', 'Billed Miles': '',
        'Trailer #': '', 'Check Amount': '', 'Process #': '', 
        'Orig': '', 'Dest': '', 'Miles': '',
        'Total Deductions': '', 'Balance to be Paid': '',
        'Escrow Balance': '', 'T_Truck #': '', 'Total_1099_Revenue': '',
        'Rate Base': '', 'Line_1099_Revenue': '', 'Original Balance': '',
        'Remaining Balance': '', 'Gross_Revenue': '', 'Last_Statement_Balance': '',
        'Direct_Deposit_Check#': ''
    }
    lines = text.split('\n')
    for line in lines:
        if 'COMPANY:' in line and 'CONTROL #:' in line:
            company_match = re.search(r'COMPANY:\s*(\d+)', line)
            if company_match:
                header['Company'] = company_match.group(1)
            control_match = re.search(r'CONTROL #:\s*(\d+)', line)
            if control_match:
                header['Control #'] = control_match.group(1)
        elif 'TERMINAL:' in line and 'EFS #:' in line:
            terminal_match = re.search(r'TERMINAL:\s*([A-Z0-9]+)', line)
            if terminal_match:
                header['Terminal'] = terminal_match.group(1)
            efs_match = re.search(r'EFS #:\s*(\d+)', line)
            if efs_match:
                header['EFS #'] = efs_match.group(1)
        elif 'NAME:' in line or 'DRIVER:' in line:
            name_match = re.search(r'(?:NAME|DRIVER):(.*?)(?:DATE:|$)', line)
            if name_match:
                header['Driver'] = name_match.group(1).strip()
            date_match = re.search(r'DATE:\s*(\d{1,2}/\d{1,2}/\d{2,4})', line)
            if date_match:
                header['Date'] = parse_date(date_match.group(1))
        elif 'TRUCK #:' in line and 'BILLED MILES:' in line:
            truck_match = re.search(r'TRUCK #:\s*(\d+)', line)
            if truck_match:
                header['Truck #'] = truck_match.group(1)
            miles_match = re.search(r'BILLED MILES:\s*(\d+)', line)
            if miles_match:
                header['Billed Miles'] = miles_match.group(1)
        elif 'TRAILER #:' in line and 'CHECK AMOUNT:' in line:
            trailer_match = re.search(r'TRAILER #:\s*([A-Z0-9]+)', line)
            if trailer_match:
                trailer_value = trailer_match.group(1)
                if trailer_value and not 'CHECK' in trailer_value and len(trailer_value) > 1:
                    header['Trailer #'] = trailer_value
            check_match = re.search(r'CHECK AMOUNT:\s*\$?([\d,]+\.?\d*)', line)
            if check_match:
                header['Check Amount'] = check_match.group(1).replace(',', '')
        elif 'ORIG:' in line and 'DEST:' in line:
            process_match = re.search(r'^(\d+)\s+ORIG:', line)
            if process_match:
                header['Process #'] = process_match.group(1)
            orig_match = re.search(r'ORIG:\s*([A-Z,\s]+?)(?=\s+DEST:|$)', line)
            if orig_match:
                header['Orig'] = orig_match.group(1).strip()
            dest_match = re.search(r'DEST:\s*([A-Z,\s]+?)(?=\s+MILES:|$)', line)
            if dest_match:
                header['Dest'] = dest_match.group(1).strip()
            miles_match = re.search(r'MILES:\s*(\d+)', line)
            if miles_match:
                header['Miles'] = miles_match.group(1)
        elif 'TOTAL DEDUCTIONS:' in line:
            ded_match = re.search(r'TOTAL DEDUCTIONS:\s*\$?(-?[\d,]+\.?\d*)', line)
            if ded_match:
                header['Total Deductions'] = ded_match.group(1).replace(',', '').replace('-', '')
        elif 'BALANCE TO BE PAID:' in line:
            balance_match = re.search(r'BALANCE TO BE PAID:\s*\$?([\d,]+\.?\d*)', line)
            if balance_match:
                header['Balance to be Paid'] = balance_match.group(1).replace(',', '')
    header['Truck #'] = clean_field(header['Truck #'])
    header['Trailer #'] = clean_field(header['Trailer #'])
    return header

# ---------- Landstar Header ----------

def extract_header_info_landstar(text):
    """Extract header fields from Landstar PDF"""
    header = {
        'Company': 'Landstar',
        'Control #': '',
        'Terminal': '',
        'EFS #': '',
        'Driver': '',
        'Date': '',
        'Truck #': '',
        'Billed Miles': '',
        'Trailer #': '',
        'Check Amount': '',
        'Process #': '',
        'Orig': '',
        'Dest': '',
        'Miles': '',
        'Total Deductions': '',
        'Balance to be Paid': '',
        'Escrow Balance': '',
        'T_Truck #': '',
        'Total_1099_Revenue': '',
        'Rate Base': '',
        'Line_1099_Revenue': '',
        'Original Balance': '',
        'Remaining Balance': '',
        'Gross_Revenue': '',
        'Last_Statement_Balance': '',
        'Direct_Deposit_Check#': '',
        'Direct_Deposit_Amount': ''
    }
    
    lines = text.split('\n')
    for line in lines:
        # Extract Truck # (letter + 6 digits)
        if 'Unit' in line:
            match = re.search(r'Unit\s*#?\s*([A-Z]\d{6})', line, re.IGNORECASE)
            if match:
                header['Truck #'] = match.group(1)
                continue
            match = re.search(r'Unit\s*#?\s*([A-Z0-9]+)', line, re.IGNORECASE)
            if match:
                truck_num = match.group(1)
                if truck_num not in ['FID', 'PID', 'EFS', 'Truck', 'Trip', 'Unit', 'Earnings', 'Year']:
                    header['Truck #'] = truck_num
        
        # Extract Escrow Balance
        if 'Escrow Balance' in line:
            match = re.search(r'Escrow Balance\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if match:
                header['Escrow Balance'] = match.group(1).replace(',', '')
        
        # Extract Period Ending (Date)
        if 'Period Ending' in line:
            match = re.search(r'Period Ending\s*(\d{1,2}/\d{1,2}/\d{2,4})', line, re.IGNORECASE)
            if match:
                header['Date'] = parse_date(match.group(1))
        
        # Extract Year-to-Date 1099 Revenue
        if 'Year-to-Date' in line or 'YTD' in line:
            match = re.search(r'([\d,]+\.?\d*)\s+Year-?To-?Date', line, re.IGNORECASE)
            if match:
                header['Total_1099_Revenue'] = match.group(1).replace(',', '')
        
        # Extract FID/PID (Control #)
        if 'FID' in line or 'PID' in line:
            match = re.search(r'[FP]ID\s*\*+(\d+)', line, re.IGNORECASE)
            if match:
                header['Control #'] = match.group(1)
            elif 'PID' in line:
                match = re.search(r'PID\s*(\d+)', line, re.IGNORECASE)
                if match:
                    header['Control #'] = match.group(1)
        
        # --- NEW: Extract Check Amount ---
        if 'Check Amount' in line or 'CHECK AMOUNT' in line:
            match = re.search(r'Check\s+Amount\s*:?\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if match:
                header['Check Amount'] = match.group(1).replace(',', '')
        
        # --- NEW: Extract Direct Deposit ---
        if 'Direct Deposit' in line:
            # Check number
            check_match = re.search(r'Direct\s+Deposit\s+Check\s+#?\s*(\d+)', line, re.IGNORECASE)
            if check_match:
                header['Direct_Deposit_Check#'] = check_match.group(1)
            # Amount
            amount_match = re.search(r'Direct\s+Deposit\s+Check\s+#?\s*\d+\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if amount_match:
                header['Direct_Deposit_Amount'] = amount_match.group(1).replace(',', '')
    
    return header

def extract_header_info_landstar_from_line(line):
    """Extract header values from a single line"""
    info = {}
    
    # Extract Unit # / Truck #
    if 'Unit' in line:
        match = re.search(r'Unit\s*#?\s*([A-Z0-9]+)', line, re.IGNORECASE)
        if match:
            truck_num = match.group(1)
            if truck_num not in ['FID', 'PID', 'EFS', 'Truck', 'Trip', 'Unit']:
                info['Truck #'] = truck_num
    
    # Extract PID / Control #
    if 'PID' in line or 'FID' in line:
        match = re.search(r'[FP]ID\s*(\d+)', line, re.IGNORECASE)
        if match:
            info['Control #'] = match.group(1)
    
    # Extract Escrow Balance
    if 'Escrow' in line:
        match = re.search(r'Escrow Balance\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
        if match:
            info['Escrow Balance'] = match.group(1).replace(',', '')
    
    # Extract Date
    if 'Period Ending' in line:
        match = re.search(r'Period Ending\s*(\d{1,2}/\d{1,2}/\d{2,4})', line, re.IGNORECASE)
        if match:
            info['Date'] = parse_date(match.group(1))
    
    # Extract Year-to-Date Revenue
    if 'Year-to-Date' in line:
        match = re.search(r'([\d,]+\.?\d*)\s+Year-?To-?Date', line, re.IGNORECASE)
        if match:
            info['Total_1099_Revenue'] = match.group(1).replace(',', '')
    
    return info
def extract_landstar_deduction_row(text):
    """Extract scheduled deduction rows like: '4-14-22 LCN FEES - CONT.'"""
    text = text.strip()
    if not text:
        return None
    
    if text.startswith('|'):
        text = text[1:].lstrip()
    
    parts = text.split('|')
    main_part = parts[0].strip() if len(parts) > 0 else ''
    
    date_match = re.match(r'^(\d{1,2}-\d{1,2}-\d{2})\s+', main_part)
    if not date_match:
        return None
    
    date_val = date_match.group(1)
    desc = main_part[date_match.end():].strip()
    
    # Look for amount in remaining parts
    amount = ''
    for part in parts[1:]:
        if part.strip():
            num_match = re.search(r'([\d,]+\.?\d*)', part)
            if num_match:
                amount = num_match.group(1).replace(',', '')
                break
    
    return {
        'date': date_val,
        'trip_number': '',
        'description': desc,
        'origin': '',
        'destination': '',
        'line_haul': '',
        'rate_base': '',
        'line_1099': '',
        'refunds': '',
        'deductions': amount,
        'net': '',
        'is_deduction': True,
        'truck_number': '',
        'control_number': ''
    }

# ---------- LANDSTAR PARSER ----------
def parse_landstar(text, lines):
    """
    Parse Landstar settlement PDFs - RETURNS ALL ROWS, NO CLASSIFICATION.
    Every row from every page is extracted, header data is repeated.
    """
    # Initialize header with defaults
    current_header = {
        'Company': 'Landstar',
        'Control #': '',
        'Truck #': '',
        'Date': '',
        'Escrow Balance': '',
        'Total_1099_Revenue': '',
        'Direct_Deposit_Check#': '',
        'Direct_Deposit_Amount': ''
    }

    # Extract Statement Totals
    totals = extract_statement_totals_from_text(text)
    current_header['Total_1099_Revenue'] = totals.get('statement_revenue', '')
    current_header['Total Deductions'] = totals.get('statement_deductions', '')
    current_header['Total Refunds'] = totals.get('statement_refunds', '')

    if totals.get('direct_deposit_check'):
        current_header['Direct_Deposit_Check#'] = totals.get('direct_deposit_check')
    if totals.get('direct_deposit_amount'):
        current_header['Direct_Deposit_Amount'] = totals.get('direct_deposit_amount')
        current_header['Check Amount'] = totals.get('direct_deposit_amount')   # <--- ADD THIS LINE

    payment_rows = []
    deduction_rows = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # --- HEADER DETECTION (updates current_header) ---
        if 'Period Ending' in line:
            date_match = re.search(r'Period Ending\s*(\d{1,2}/\d{1,2}/\d{2,4})', line, re.IGNORECASE)
            if date_match:
                current_header['Date'] = parse_date(date_match.group(1))
            continue

        if 'Unit #' in line or 'Unit#' in line:
            match = re.search(r'Unit\s*#?\s*([A-Z]\d{6})', line, re.IGNORECASE)
            if match:
                current_header['Truck #'] = match.group(1)
                continue
            match = re.search(r'Unit\s*#?\s*([A-Z0-9]+)', line, re.IGNORECASE)
            if match:
                truck_num = match.group(1)
                if truck_num not in ['FID', 'PID', 'EFS', 'Truck', 'Trip', 'Unit', 'Earnings', 'Year']:
                    current_header['Truck #'] = truck_num
            continue

        if 'Escrow Balance' in line:
            match = re.search(r'Escrow Balance\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if match:
                current_header['Escrow Balance'] = match.group(1).replace(',', '')
            continue

        if 'FID' in line or 'PID' in line:
            match = re.search(r'[FP]ID\s*\*?(\d+)', line, re.IGNORECASE)
            if match:
                current_header['Control #'] = match.group(1)
            continue

        if 'Direct Deposit' in line:
            check_match = re.search(r'Direct Deposit\s+Check\s+#?\s*(\d+)', line, re.IGNORECASE)
            if check_match:
                current_header['Direct_Deposit_Check#'] = check_match.group(1)
            amount_match = re.search(r'Direct Deposit\s+Check\s+#?\s*\d+\s*\$?([\d,]+\.?\d*)', line, re.IGNORECASE)
            if amount_match:
                current_header['Direct_Deposit_Amount'] = amount_match.group(1).replace(',', '')
            continue

        # --- SKIP NON-DATA LINES ---
        if 'P/U' in line and 'Trip' in line:
            continue
        if 'Transaction' in line or 'Original' in line or 'Remaining' in line:
            continue
        if 'Scheduled Deductions' in line or 'WEEKLY DEDUCTIONS' in line:
            continue
        if 'GROSS COST' in line:
            continue
        if 'Totals' in line and '----------' in line:
            continue
        if '-----' in line:
            continue
        if 'Subtotal' in line:
            continue

        # --- STRIP LEADING PIPE ---
        if line.startswith('|'):
            line = line[1:].lstrip()

        row_data = None
        if re.match(r'^\d{1,2}-\d{1,2}-\d{2}\s+', line):
            row_data = extract_landstar_deduction_row(line)
        elif re.match(r'^\d{1,2}-\d{2}\s+', line):
            row_data = extract_landstar_row(line)
        elif re.search(r'[A-Z]+\s*\d{7,}', line):
            row_data = extract_landstar_row(line)

        if row_data:
            # --- Apply header to row_data ---
            row_data['truck_number'] = row_data.get('truck_number', '') or current_header.get('Truck #', '')
            row_data['control_number'] = row_data.get('control_number', '') or current_header.get('Control #', '')
            row_data['escrow_balance'] = row_data.get('escrow_balance', '') or current_header.get('Escrow Balance', '')
            row_data['total_1099_revenue'] = row_data.get('total_1099_revenue', '') or current_header.get('Total_1099_Revenue', '')
            row_data['direct_deposit_check'] = row_data.get('direct_deposit_check', '') or current_header.get('Direct_Deposit_Check#', '')
            row_data['direct_deposit_amount'] = row_data.get('direct_deposit_amount', '') or current_header.get('Direct_Deposit_Amount', '')

            # --- FORMAT THE ROW using add_landstar_row ---
            add_landstar_row(row_data, current_header, payment_rows, deduction_rows)

    print(f"  Found {len(payment_rows)} payments, {len(deduction_rows)} deductions")
    return payment_rows, deduction_rows

# ---------- Split Origin/Destination ----------
def split_origin_destination(text):
    """
    Split the text block into Description, Origin, and Destination.
    Uses word-based parsing to find city/state pairs.
    Example: "TRAILER L/H FRANKLIN WI N ANDOVER MA"
             -> desc="TRAILER L/H", orig="FRANKLIN WI", dest="N ANDOVER MA"
    """
    if not text:
        return '', '', ''

    # Remove commas and extra spaces
    clean = re.sub(r'\s*,\s*', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    words = clean.split()
    if len(words) < 3:
        return clean, '', ''

    # Find state indices: words of length 2 and uppercase (e.g., WI, MA, OK, LA)
    state_indices = [i for i, w in enumerate(words) if len(w) == 2 and w.isupper()]
    if not state_indices:
        return clean, '', ''

    # Collect city/state pairs
    pairs = []  # each: {'city_start': int, 'city_words': list, 'state': str}
    for idx in state_indices:
        # Scan backwards from idx-1 to collect city words
        city_words = []
        j = idx - 1
        while j >= 0:
            # If we hit another state, stop
            if j in state_indices:
                break
            # If the word contains only uppercase letters (no punctuation), it's part of the city
            if re.match(r'^[A-Z]+$', words[j]):
                city_words.insert(0, words[j])
                j -= 1
            else:
                # Stop at a word that is not all uppercase (contains punctuation or lowercase)
                break
        if city_words:
            pairs.append({
                'city_start': j + 1,  # index of first city word
                'city_words': city_words,
                'state': words[idx]
            })

    # Now we have pairs in order of appearance
    if len(pairs) >= 2:
        # Origin is second-last pair, Destination is last pair
        origin_pair = pairs[-2]
        dest_pair = pairs[-1]
        origin = ' '.join(origin_pair['city_words']) + ' ' + origin_pair['state']
        dest = ' '.join(dest_pair['city_words']) + ' ' + dest_pair['state']
        # Description: all words before the first city word of origin_pair
        desc_words = words[:origin_pair['city_start']]
        desc = ' '.join(desc_words)
        return desc, origin, dest

    elif len(pairs) == 1:
        # Only one city/state pair – treat as Destination
        dest = ' '.join(pairs[0]['city_words']) + ' ' + pairs[0]['state']
        desc = ' '.join(words[:pairs[0]['city_start']])
        return desc, '', dest

    else:
        return clean, '', ''

def extract_landstar_row(text):
    """
    Extract data from a single Landstar table row using pipe-splitting.
    
    Handles formats like:
    "| 4-11 CMK 6423817 TRAILER L/H FRANKLIN , WI N ANDOVER , MA 4,127.26 8.0%| 330.18 | | | |"
    "| 4-05 PKL 6157851 TRAILER L/H SAND SPRS , OK PRT ALLEN , LA 3,009.00 8.0%| 240.72 | | | |"
    """
    text = text.strip()
    if not text:
        return None
    
    # Step 1: Strip leading pipe if present
    if text.startswith('|'):
        text = text[1:].lstrip()
    
    # Step 2: Split by pipe to get columns
    parts = text.split('|')
    
    # Part 0: Date, Trip #, Description, Line Haul, Rate Base
    main_part = parts[0].strip() if len(parts) > 0 else ''
    
    # Part 1: 1099 Revenue
    revenue_1099 = parts[1].strip() if len(parts) > 1 else ''
    
    # Part 2: Refunds
    refunds = parts[2].strip() if len(parts) > 2 else ''
    
    # Part 3: Deductions
    deductions = parts[3].strip() if len(parts) > 3 else ''
    
    # Part 4: Net
    net = parts[4].strip() if len(parts) > 4 else ''
    
    # Step 3: Extract date (M-DD at the start of main_part)
    date_match = re.match(r'^(\d{1,2}-\d{2})\s+', main_part)
    if not date_match:
        return None
    
    date_val = date_match.group(1)
    remaining = main_part[date_match.end():]
    
    # Step 4: Extract trip number (letters + 7+ digits)
    trip_match = re.search(r'([A-Z]+)\s*(\d{7,})', remaining)
    if trip_match:
        trip_prefix = trip_match.group(1)
        trip_num = trip_match.group(2)
        remaining = remaining[:trip_match.start()] + remaining[trip_match.end():]
    else:
        trip_match = re.search(r'(\d{7,})', remaining)
        if trip_match:
            trip_num = trip_match.group(1)
            trip_prefix = ''
            remaining = remaining[:trip_match.start()] + remaining[trip_match.end():]
        else:
            trip_num = ''
            trip_prefix = ''
    
    # Step 5: Extract Line Haul and Rate Base from remaining
    line_haul = ''
    rate_base = ''
    
    # Find all numbers in remaining
    numbers = re.findall(r'([\d,]+\.?\d*)', remaining)
    
    # Find rate base (percentage)
    rate_base_match = re.search(r'([\d.]+)%', remaining)
    if rate_base_match:
        rate_base = rate_base_match.group(1)
    
    # Line haul is typically the last number before the rate base
    if rate_base:
        # Remove the number that matches the rate base from consideration
        for num in reversed(numbers):
            if num != rate_base:
                line_haul = num.replace(',', '')
                break
    elif numbers:
        line_haul = numbers[-1].replace(',', '')
    
    # Step 6: Clean the description (remove numbers and percentages)
    desc = re.sub(r'[\d,]+\.?\d*%?', '', remaining)
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    # Step 7: Split description into Description, Origin, Destination
    desc, orig, dest = split_origin_destination(desc)
    
    # Step 8: Clean the numeric values
    def clean_number(value):
        if not value:
            return ''
        value = value.replace(',', '').strip()
        if value.endswith('-'):
            value = '-' + value[:-1]
        return value
    
    # Step 9: Build row data
    row_data = {
        'date': date_val,
        'trip_number': f"{trip_prefix} {trip_num}".strip(),
        'trip_prefix': trip_prefix,
        'trip_num': trip_num,
        'rate_base': rate_base,
        'line_haul': line_haul,
        'line_1099': clean_number(revenue_1099),
        'refunds': clean_number(refunds),
        'deductions': clean_number(deductions),
        'net': clean_number(net),
        'description': desc,
        'origin': orig,
        'destination': dest,
        'is_negative': False,
        'is_deduction': False
    }
    
    # Step 10: Determine if this is a deduction
    # Check if deductions column has a value
    if row_data['deductions'] and row_data['deductions'] != '0':
        row_data['is_deduction'] = True
        row_data['deductions'] = row_data['deductions'].replace('-', '')
    
    # Check if line_haul is negative
    if row_data['line_haul'] and row_data['line_haul'].startswith('-'):
        row_data['is_deduction'] = True
        row_data['deductions'] = row_data['line_haul'].replace('-', '')
        row_data['line_haul'] = ''
    
   
    # Check description for deduction keywords
    desc_lower = row_data['description'].lower()
    deduction_keywords = [
        'trkstp', 'escrow', 'fee', 'tax',
        'ad valorem', 'charge', 'refund', 'deduction', 'prepass',
        'tire purchase', 'log scanning', 'unladen liability'
    ]
    if any(keyword in desc_lower for keyword in deduction_keywords):
        row_data['is_deduction'] = True

        # FUEL SURCHARGE is always income, not a deduction
    if 'FUEL SURCHARGE' in row_data.get('description', '').upper():
        row_data['is_deduction'] = False
        row_data['deductions'] = ''

    return row_data


# ---------- Add Landstar Row ----------
def add_landstar_row(row_data, header, payment_rows, deduction_rows):
    """
    Add a parsed Landstar row to the appropriate list (payment or deduction).
    """
    row = header.copy()
    
    # ---------- Common fields ----------
    row['Process #'] = row_data.get('trip_number', '')
    row['Truck #'] = row_data.get('truck_number', '')
    row['Orig'] = row_data.get('origin', '')
    row['Dest'] = row_data.get('destination', '')
    row['Check Amount'] = header.get('Check Amount', '')
    
    # --- HEADER FIELDS (applied to all rows) ---
    row['Total_1099_Revenue'] = header.get('Total_1099_Revenue', '')
    row['Direct_Deposit_Check#'] = header.get('Direct_Deposit_Check#', '')
    row['Direct_Deposit_Amount'] = header.get('Direct_Deposit_Amount', '')
    row['Escrow Balance'] = header.get('Escrow Balance', '')
    row['Total Deductions'] = header.get('Total Deductions', '')
    row['Net'] = row_data.get('net', '')   # Direct copy from PDF — NO calculation!
    row['Total Refunds'] = header.get('Total Refunds', '')

    # ---------- 1099 Revenue and Rate Base ----------
    line_1099 = row_data.get('line_1099', '')
    row['Line_1099_Revenue'] = line_1099
    row['Rate Base'] = row_data.get('rate_base', '')
    
    # ---------- Deduction Amount ----------
    raw_deduction = row_data.get('deductions', '')
    deduction_amt = ''
    if raw_deduction and raw_deduction != '0.00':
        cleaned = raw_deduction.replace(',', '').strip()
        if cleaned.startswith('-'):
            deduction_amt = cleaned
        else:
            deduction_amt = f"-{cleaned}"
    row['Deduction Amount'] = deduction_amt
    
    # ---------- Dates ----------
    def format_date(date_str):
        if not date_str:
            return ''
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
            return date_str
        month_map = {
            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
        }
        match = re.match(r'(\d{1,2})-([A-Za-z]{3})', date_str)
        if match:
            day = match.group(1).zfill(2)
            month = month_map.get(match.group(2), '01')
            return f"{month}/{day}/2022"
        match = re.match(r'(\d{1,2})-(\d{1,2})', date_str)
        if match:
            month = match.group(1).zfill(2)
            day = match.group(2).zfill(2)
            return f"{month}/{day}/2022"
        return date_str
    
    raw_date = row_data.get('date', '')
    formatted_date = format_date(raw_date)
    row['Entered Date'] = formatted_date
    row['Entered Processed Date'] = formatted_date
    
    # ---------- Rate Base as percentage ----------
    if row['Rate Base'] and row['Rate Base'] != '':
        try:
            rate_val = float(row['Rate Base'])
            row['Rate Base'] = f"{rate_val:.2f}%"
        except:
            pass
    
    # ---------- Determine if this is a deduction ----------
    is_deduction = row_data.get('is_deduction', False)
    
    desc = row_data.get('description', '')
    desc_lower = desc.lower()
    deduction_keywords = [
        'trkstp', 'escrow', 'fee', 'tax',
        'ad valorem', 'charge', 'refund', 'deduction', 'prepass',
        'tire purchase', 'log scanning', 'unladen liability'
    ]
    if any(keyword in desc_lower for keyword in deduction_keywords):
        is_deduction = True
    
    if 'FUEL SURCHARGE' in desc.upper():
        is_deduction = False
    if 'TARP CHARGES' in desc.upper():
        is_deduction = False
    
    if deduction_amt and deduction_amt != '0.00':
        is_deduction = True
    
    # ---------- Add to the appropriate list ----------
    if is_deduction:
        # DEDUCTION ROW
        row['Deduction Entered Date'] = row['Entered Date']
        row['Deduction Processed Date'] = row['Entered Processed Date']
        row['Deduction Description'] = desc
        
        # Clear payment fields
        row['Entered Description'] = ''
        row['Entered Amount'] = ''
              
        deduction_rows.append(row)
    else:
        # PAYMENT ROW
        row['Entered Description'] = desc
        row['Entered Amount'] = line_1099
        
        # Clear deduction fields
        row['Deduction Entered Date'] = ''
        row['Deduction Processed Date'] = ''
        row['Deduction Description'] = ''
        row['Deduction Amount'] = ''
        
        payment_rows.append(row)

def format_date_universal(date_str):
    """Convert date to MM/DD/YYYY format"""
    if not date_str:
        return ''
    
    # If it's already MM/DD/YYYY
    if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
        return date_str
    
    # If it's DD-MMM format (11-Apr)
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    match = re.match(r'(\d{1,2})-([A-Za-z]{3})', date_str)
    if match:
        day = match.group(1).zfill(2)
        month = month_map.get(match.group(2), '01')
        return f"{month}/{day}/2022"
    
    # If it's MM-DD (4-11)
    match = re.match(r'(\d{1,2})-(\d{1,2})', date_str)
    if match:
        month = match.group(1).zfill(2)
        day = match.group(2).zfill(2)
        return f"{month}/{day}/2022"
    
    return date_str
# ---------- Company Detection ----------
def detect_company(text):
    if 'Bennett' in text or 'BENNETT' in text or 'Bennett Motor Express' in text:
        return 'BENNETT'
    elif 'Landstar' in text or 'LANDSTAR' in text or 'Landstar Ranger' in text or 'Contractor Statement' in text:
        return 'LANDSTAR'
    else:
        return 'BENNETT'

# ---------- Process PDF ----------

def process_pdf(pdf_file):
    print(f"\n📄 Processing: {pdf_file}")
    text = extract_text_from_pdf(pdf_file)
    if not text or len(text.strip()) < 50:
        print(f"  ❌ No text could be extracted from this PDF")
        return []
    lines = text.split('\n')
    company = detect_company(text)
    print(f"  🔍 Detected company: {company}")
    if company == 'BENNETT':
        payment_rows, deduction_rows = parse_bennett(text, lines)
        all_rows = payment_rows + deduction_rows
    elif company == 'LANDSTAR':
        payment_rows, deduction_rows = parse_landstar(text, lines)
        all_rows = payment_rows + deduction_rows
    else:
        payment_rows, deduction_rows = parse_bennett(text, lines)
        all_rows = payment_rows + deduction_rows
    print(f"  Found {len(all_rows)} total rows")
    return all_rows

# ---------- Main ----------
def main():
    print("🔍 Entering main() function...")
    print("⏳ Opening file picker...")
    
    root = tk.Tk()
    root.attributes('-topmost', True)
    root.withdraw()
    
    pdf_files = filedialog.askopenfilenames(
        title="Select Settlement PDFs",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
    )
    
    if not pdf_files:
        print("\n❌ No files selected. Exiting.")
        input("\nPress Enter to exit...")
        return
    
    print(f"\n📁 Selected {len(pdf_files)} files to process")
    
    all_rows = []
    
    print("\n🔄 Processing files...")
    for i, pdf_file in enumerate(pdf_files):
        percent = (i + 1) / len(pdf_files) * 100
        bar_length = 30
        filled = int(bar_length * (i + 1) // len(pdf_files))
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\rProgress: |{bar}| {i+1}/{len(pdf_files)} ({percent:.1f}%)", end="")
        
        rows = process_pdf(pdf_file)
        all_rows.extend(rows)
    
    print()
    
    if all_rows:
        # ---------- ADD NET CALCULATION HERE ----------
        for row in all_rows:
            entered_amt = row.get('Entered Amount', '')
            deduction_amt = row.get('Deduction Amount', '')
            net = ''
            
            # Try to calculate net from Entered Amount and Deduction Amount
            if entered_amt:
                try:
                    net = float(entered_amt)
                except:
                    pass
            
            if deduction_amt:
                try:
                    ded = float(deduction_amt)
                    if net:
                        net += ded
                    else:
                        net = ded
                except:
                    pass
            
            # If net is still empty, try Total_1099_Revenue
            if net == '':
                revenue = row.get('Line_1099_Revenue', '')
                if revenue:
                    try:
                        net = float(revenue)
                    except:
                        pass
            
            # Format net with 2 decimal places if it's a number
            if net != '':
                try:
                    row['Net'] = f"{net:.2f}"
                except:
                    row['Net'] = str(net)
            else:
                row['Net'] = ''
        # ---------- END NET CALCULATION ----------
        
        output = "UNIVERSAL_SETTLEMENTS_FINAL.csv"
        fieldnames = [
            'Company', 'Control #', 'Terminal', 'EFS #', 'Driver', 'Date',
            'Truck #', 'Billed Miles', 'Trailer #', 'Check Amount',
            'Process #', 'Orig', 'Dest', 'Miles',
            'Truck Repair Fund',
            'Escrow Balance', 'T_Truck #', 'Total_1099_Revenue',
            'Rate Base', 'Line_1099_Revenue', 'Original Balance',
            'Remaining Balance', 'Gross_Revenue', 'Last_Statement_Balance',
            'Direct_Deposit_Check#', 'Direct_Deposit_Amount',
            'Entered Date', 'Entered Processed Date', 'Entered Description',
            'Entered Amount', 'Total Deductions', 'Balance to be Paid',
            'Deduction Entered Date', 'Deduction Processed Date',
            'Deduction Description', 'Deduction Amount',
            'Net', 'Total Refunds'
        ]        
        
        with open(output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)

        print(f"\n{'='*80}")
        print("✅ EXTRACTION COMPLETE!")
        print(f"{'='*80}")
        print(f"   Output file: {output}")
        print(f"   Total rows: {len(all_rows)}")
        print(f"{'='*80}")
        
        payments = sum(1 for r in all_rows if r.get('Entered Description'))
        deductions = sum(1 for r in all_rows if r.get('Deduction Description'))
        print(f"\n📊 Summary: {payments} payments, {deductions} deductions")
        
        qb_rows = export_to_quickbooks(all_rows, "QUICKBOOKS_IMPORT.csv")
        print(f"  📊 QuickBooks import file created: QUICKBOOKS_IMPORT.csv ({qb_rows} rows)")
        
        print("\n🎯 Press Enter to open Excel and exit...")
        input()

        os.startfile(output)
        os.startfile("QUICKBOOKS_IMPORT.csv")
        print(f"  📊 Both CSV files opened in Excel")
        
    else:
        print("\n❌ No data extracted")
        print("\n🎯 Press Enter to exit...")
        input()
    
    print("✅ Processing complete. Exiting...")
    sys.exit()

if __name__ == "__main__":
    main()