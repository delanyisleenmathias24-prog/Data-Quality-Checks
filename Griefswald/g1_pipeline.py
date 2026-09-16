import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
import re 
import pandas as pd
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Define column mappings from Studienliste to text_csv
column_mapping = {
    'Studie': 'title',  
    'Acronym': 'acronym',
    'EU-CT No': 'ref_id',
    'Registrierungsnummer Clinical trials gov': 'nct_id',
    'Erkrankung': 'organsystem',
    'Phase': 'phase',
    'Status recruitment': 'status',
    'IIT': 'styp',  
    'Inititated by UMG': 'styp1',  # Note: two 't's in the Excel column name!
    'durchführende Einheit': 'department',
    'PI UMG': 'controller',
    'Altersgruppe': 'altersgruppe',
    'Therapielinie': 'therapielinie'
}

# Status mapping (English to German)
status_mapping = {
    'Recruitment ongoing': 'Rekrutierung läuft',
    'Recruitment closed, FU ongoing': 'Rekrutierung abgeschlossen - Follow-Up läuft',
    'Recruitment closed, FU closed': 'Rekrutierung abgeschlossen - Follow-Up abgeschlossen',
    'Recruitment temporarily hold': 'Ausgesetzt',
    'Recruitment terminated prematurely': 'Vorzeitig abgebrochen',
    'completed': 'Beendet',
    'Study participation planned': 'Studienteilnahme geplant',
    'Canceled': 'Abgebrochen'
}

# Status values to skip comparison (these studies will be ignored entirely)
SKIP_STATUS_VALUES = ['Study participation planned', 'Studienteilnahme geplant']

location_mapping = {
    'Universitätsmedizin Greifswald': 'Greifswald UMG',
    'Greifswald UMG': 'Greifswald UMG'
}

# Phase mapping (simplify phase names)
phase_mapping = {
    'AMG Phase I': 'I',
    'AMG Phase I/II': 'I-II',
    'AMG Phase II': 'II',
    'AMG Phase II/III': 'II-III',
    'AMG Phase III': 'III',
    'AMG Phase IV': 'IV',
    'I': 'I',
    'I/II': 'I-II',
    'II': 'II',
    'II/III': 'II-III',
    'III': 'III',
    'IV': 'IV',
    'Keine angabe': 'Keine angabe',
    'n.a.': 'Keine angabe'
}

# Age group mapping
age_mapping = {
    '< 18': 'Kinder und Jugendliche',
    '≥ 18': 'Erwachsene',
    '18-60': 'Erwachsene',
    '> 60': 'Senioren',
    '30-45': 'Erwachsene',
    'Kinder': 'Kinder und Jugendliche'
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_text(text):
    """
    Normalize text for comparison by:
    - Removing newlines, carriage returns, tabs
    - Standardizing spaces around commas
    - Removing multiple spaces
    - Stripping leading/trailing whitespace
    - Converting to lowercase
    """
    if text is None or pd.isna(text):
        return ''
    
    text = str(text)
    
    # Replace newlines, carriage returns, tabs with space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # Remove spaces before commas
    text = re.sub(r'\s+,', ',', text)
    
    # Ensure space after commas
    text = re.sub(r',(?!\s)', ', ', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Remove trailing commas
    text = re.sub(r',+$', '', text)
    
    # Remove quotes
    text = text.strip('"\'')
    
    # Convert to lowercase for case-insensitive comparison
    return text.lower()

def safe_str(value):
    """Safely convert to string, handling NaN/None"""
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()

def calculate_styp(row):
    """
    Calculate the styp (study type) for Greifswald
    Same logic as Rostock but with different column names
    """
    region = row.get('region', 'Greifswald') 
    iit = str(row.get('IIT', '')).lower().strip()
    umr_init = str(row.get('Inititated by UMG', '')).lower().strip()
    
    # If the value is 'nan' or empty, treat it as empty string
    if umr_init == 'nan' or umr_init == '':
        umr_init = ''
    
    if region == 'Greifswald':
        if iit == 'yes' and umr_init == 'yes':
            return 'IIT von Einrichtung initiiert'
        elif iit == 'yes' and umr_init == 'no':
            return 'IIT von anderer Einrichtung initiiert'
        elif iit == 'yes' and umr_init == '':
            return 'IIT von anderer Einrichtung initiiert'
        else:
            return 'Non-IIT'
    return 'Non-IIT'

# ============================================================================
# MAIN COMPARISON FUNCTION
# ============================================================================

def compare_studies(df_studien, df_text_csv, debug=False):
    """
    Compare studies between the two dataframes and return:
    - mismatches_df: DataFrame of all mismatches
    - matched_count: Number of studies that were matched
    - unmatched_count: Number of studies that were NOT matched
    """
    mismatches = []
    matched_count = 0
    unmatched_count = 0
    skipped_count = 0
    not_found_in_mapped = []  # Track acronyms not found in mapped file
    
    print("\n" + "="*80)
    print("🔍 STARTING COMPARISON")
    print("="*80)
    
    # Debug: Print column info
    print("\nSTUDIENLISTE COLUMNS:")
    print("-"*40)
    for i, col in enumerate(df_studien.columns):
        print(f"  [{i}] {col}")
    
    print("\nTEXT CSV COLUMNS:")
    print("-"*40)
    for i, col in enumerate(df_text_csv.columns):
        print(f"  [{i}] {col}")
    print("="*80 + "\n")
    
    # Ensure text_csv has acronym column
    if 'acronym' not in df_text_csv.columns:
        print("WARNING: 'acronym' column not found in text CSV!")
        for col in df_text_csv.columns:
            if col.lower() in ['acronym', 'akronym', 'studie', 'trial', 'study']:
                print(f"  Using '{col}' as acronym column")
                df_text_csv['acronym'] = df_text_csv[col]
                break
        else:
            print("  Creating empty acronym column")
            df_text_csv['acronym'] = ''
    
    # Create a dictionary for faster lookup
    text_dict = {}
    for _, row in df_text_csv.iterrows():
        acr = safe_str(row.get('acronym', ''))
        if acr:
            text_dict[acr.lower()] = row.to_dict()
    
    # Process each study in the master list
    for idx, study_row in df_studien.iterrows():
        # Get the acronym
        acronym = safe_str(study_row.get('Acronym', ''))
        if not acronym:
            continue
        
        if debug:
            print(f"\n🔍 Processing: {acronym}")
        
        # Check if this study should be skipped based on status
        status_value = safe_str(study_row.get('Status recruitment', ''))
        if status_value in SKIP_STATUS_VALUES:
            if debug:
                print(f"  ⏭️ Skipping '{acronym}' (Status: '{status_value}' - ignored in mapped file)")
            skipped_count += 1
            continue
        
        # Find matching row in text_csv
        acr_lower = acronym.lower()
        if acr_lower not in text_dict:
            if debug:
                print(f"  ❌ No match found for '{acronym}' - will be discarded")
            unmatched_count += 1
            not_found_in_mapped.append(acronym)
            continue  # Skip this study entirely - don't add to mismatches
        
        matched_count += 1
        text_row = text_dict[acr_lower]
        
        if debug:
            print(f"  ✅ Match found in mapped file")
            print(f"  📝 Title: {safe_str(text_row.get('title', ''))[:60]}...")
        
        # ---- COMPARE EACH FIELD ----
        # Use the same logic as Rostock for each field comparison
        
        # 1. Compare Title
        expected_title = study_row.get('Studie')
        actual_title = text_row.get('title')
        if pd.notna(expected_title) and pd.notna(actual_title):
            expected_normalized = normalize_text(str(expected_title)).lower()
            actual_normalized = normalize_text(str(actual_title)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'title',
                    'issue': 'title mismatch',
                    'wrong_value': actual_title,
                    'corrected_value': expected_title
                })
        
        # 2. Compare ref_id (EU-CT No)
        expected_ref_id = study_row.get('EU-CT No')
        actual_ref_id = text_row.get('ref_id')
        if pd.notna(expected_ref_id) and pd.notna(actual_ref_id):
            expected_normalized = normalize_text(str(expected_ref_id)).lower()
            actual_normalized = normalize_text(str(actual_ref_id)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'ref_id',
                    'issue': 'ref_id mismatch',
                    'wrong_value': actual_ref_id,
                    'corrected_value': expected_ref_id
                })
        
        # 3. Compare nct_id
        expected_nct = study_row.get('Registrierungsnummer Clinical trials gov')
        actual_nct = text_row.get('nct_id')
        if pd.notna(expected_nct) and pd.notna(actual_nct):
            expected_normalized = normalize_text(str(expected_nct)).lower()
            actual_normalized = normalize_text(str(actual_nct)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'nct_id',
                    'issue': 'nct_id mismatch',
                    'wrong_value': actual_nct,
                    'corrected_value': expected_nct
                })
        
        # 4. Compare organsystem
        expected_organ = study_row.get('Erkrankung')
        actual_organ = text_row.get('organsystem')
        if pd.notna(expected_organ) and pd.notna(actual_organ):
            expected_normalized = normalize_text(str(expected_organ)).lower()
            actual_normalized = normalize_text(str(actual_organ)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'organsystem',
                    'issue': 'organsystem mismatch',
                    'wrong_value': actual_organ,
                    'corrected_value': expected_organ
                })
        
        # 5. Compare phase - FIXED: Handle 'Keine angabe' vs nan properly
        expected_phase = study_row.get('Phase')
        actual_phase = text_row.get('phase')
        
        # Check if expected_phase exists
        if pd.notna(expected_phase):
            # Get the normalized expected value
            expected_normalized = phase_mapping.get(str(expected_phase).strip(), str(expected_phase).strip())
            
            # Check if actual_phase is NaN or empty
            if pd.isna(actual_phase) or actual_phase == '' or actual_phase is None:
                # If expected is 'Keine angabe', report as mismatch
                if expected_normalized  == 'Keine Angabe':
                    mismatches.append({
                        'acronym': acronym,
                        'column': 'phase',
                        'issue': 'phase mismatch',
                        'wrong_value': 'nan',
                        'corrected_value': 'Keine angabe'
                    })
                # If expected is not 'Keine angabe' and actual is empty, report as mismatch
                else:
                    mismatches.append({
                        'acronym': acronym,
                        'column': 'phase',
                        'issue': 'phase mismatch',
                        'wrong_value': 'nan',
                        'corrected_value': expected_phase
                    })
            else:
                # Both exist, compare them
                actual_normalized = phase_mapping.get(str(actual_phase).strip(), str(actual_phase).strip())
                
                # If expected is 'Keine angabe' and actual is something else (not empty)
                if expected_normalized.lower() == 'keine angabe' and actual_normalized.lower() != 'keine angabe':
                    mismatches.append({
                        'acronym': acronym,
                        'column': 'phase',
                        'issue': 'phase mismatch',
                        'wrong_value': actual_phase,
                        'corrected_value': 'Keine angabe'
                    })
                elif expected_normalized.lower() != actual_normalized.lower():
                    mismatches.append({
                        'acronym': acronym,
                        'column': 'phase',
                        'issue': 'phase mismatch',
                        'wrong_value': actual_phase,
                        'corrected_value': expected_phase
                    })
        
        # 6. Compare status - EXACT SAME LOGIC AS ROSTOCK
        expected_status_en = study_row.get('Status recruitment')
        if pd.notna(expected_status_en):
            expected_status_de = status_mapping.get(str(expected_status_en).strip(), str(expected_status_en).strip())
            actual_status = text_row.get('status')
            if pd.notna(actual_status):
                expected_normalized = normalize_text(expected_status_de).lower()
                actual_normalized = normalize_text(str(actual_status)).lower()
                if expected_normalized != actual_normalized:
                    mismatches.append({
                        'acronym': acronym,
                        'column': 'status',
                        'issue': 'status mismatch',
                        'wrong_value': actual_status,
                        'corrected_value': expected_status_de
                    })
        
        # 7. Compare styp
        expected_styp = calculate_styp(study_row)
        actual_styp = text_row.get('styp')
        if pd.notna(actual_styp):
            expected_normalized = normalize_text(expected_styp).lower()
            actual_normalized = normalize_text(str(actual_styp)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'styp',
                    'issue': 'styp mismatch',
                    'wrong_value': actual_styp,
                    'corrected_value': expected_styp
                })
        
        # 8. Compare department
        expected_dept = study_row.get('durchführende Einheit')
        actual_dept = text_row.get('department')
        if pd.notna(expected_dept) and pd.notna(actual_dept):
            expected_normalized = normalize_text(str(expected_dept))
            actual_normalized = normalize_text(str(actual_dept))
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'department',
                    'issue': 'department mismatch',
                    'wrong_value': actual_dept,
                    'corrected_value': expected_dept
                })
        
        # 9. Compare controller (PI UMG)
        expected_pi = study_row.get('PI UMG')
        actual_pi = text_row.get('controller')
        if pd.notna(expected_pi) and pd.notna(actual_pi):
            expected_normalized = normalize_text(str(expected_pi))
            actual_normalized = normalize_text(str(actual_pi))
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'controller',
                    'issue': 'controller mismatch',
                    'wrong_value': actual_pi,
                    'corrected_value': expected_pi
                })
        
        # 10. Compare altersgruppe
        expected_age = study_row.get('Altersgruppe')
        actual_age = text_row.get('altersgruppe')
        if pd.notna(expected_age) and pd.notna(actual_age):
            # Map German age groups if needed
            expected_age_de = age_mapping.get(str(expected_age).strip(), str(expected_age).strip())
            expected_normalized = normalize_text(expected_age_de).lower()
            actual_normalized = normalize_text(str(actual_age)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'altersgruppe',
                    'issue': 'altersgruppe mismatch',
                    'wrong_value': actual_age,
                    'corrected_value': expected_age_de
                })
        
        # 11. Compare therapielinie
        expected_line = study_row.get('Therapielinie')
        actual_line = text_row.get('therapielinie')
        if pd.notna(expected_line) and pd.notna(actual_line):
            expected_normalized = normalize_text(str(expected_line)).lower()
            actual_normalized = normalize_text(str(actual_line)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'therapielinie',
                    'issue': 'therapielinie mismatch',
                    'wrong_value': actual_line,
                    'corrected_value': expected_line
                })
    
    # Print summary
    print("\n" + "="*80)
    print("COMPARISON SUMMARY:")
    print("-"*80)
    
    # Count studies with acronym
    studies_with_acronym = 0
    for _, row in df_studien.iterrows():
        if safe_str(row.get('Acronym', '')):
            studies_with_acronym += 1
    
    print(f"  Location detected: Greifswald")
    print(f"  Total studies in master list: {len(df_studien)}")
    print(f"  Studies with acronym: {studies_with_acronym}")
    print(f"  Studies skipped (Status = 'Study participation planned'): {skipped_count}")
    print(f"  Studies matched: {matched_count}")
    print(f"  Studies unmatched (discarded): {unmatched_count}")
    if not_found_in_mapped:
        print(f"  Unmatched acronyms: {', '.join(not_found_in_mapped[:10])}{'...' if len(not_found_in_mapped) > 10 else ''}")
    print(f"  Total mismatches found: {len(mismatches)}")
    print("="*80 + "\n")
    
    # Prepare the mismatches DataFrame - ONLY include studies that were matched
    if mismatches:
        df_mismatches = pd.DataFrame(mismatches)
        df_mismatches = df_mismatches.drop_duplicates(subset=['acronym', 'column'])
        df_mismatches = df_mismatches.sort_values(['acronym', 'column'])
    else:
        df_mismatches = pd.DataFrame(columns=['acronym', 'column', 'issue', 'wrong_value', 'corrected_value'])
    
    return df_mismatches, matched_count, unmatched_count

# ============================================================================
# GUI APPLICATION
# ============================================================================

class ComparisonApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Study Comparison Tool - Greifswald")
        self.root.geometry("600x380")
        self.root.resizable(False, False)
        
        self.excel_file_path = None
        self.mapped_file_path = None
        self.debug_mode = tk.BooleanVar(value=True)  # Enable debug by default
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Study Comparison Tool - Greifswald", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=10)
        
        subtitle_label = ttk.Label(main_frame, text="Compare Studienliste Excel with mapped dataset", 
                                   font=('Arial', 10), foreground='gray')
        subtitle_label.grid(row=1, column=0, columnspan=2, pady=(0, 15))
        
        # File 1 selection
        ttk.Label(main_frame, text="1. Studienliste Excel File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.excel_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.excel_label.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_excel_file).grid(row=2, column=2, pady=5)
        
        # File 2 selection
        ttk.Label(main_frame, text="2. Mapped File (Excel or CSV):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.mapped_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.mapped_label.grid(row=3, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_mapped_file).grid(row=3, column=2, pady=5)
        
        # Info label
        info_label = ttk.Label(main_frame, 
                               text="ℹ️ Studies with status 'Study participation planned' will be skipped",
                               foreground="gray", font=('Arial', 9))
        info_label.grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Debug mode checkbox
        debug_check = ttk.Checkbutton(main_frame, text="Enable Debug Mode (shows detailed console output)", 
                                      variable=self.debug_mode)
        debug_check.grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=3, pady=10)
        
        self.process_button = ttk.Button(button_frame, text="Start Comparison", 
                                         command=self.start_comparison, state='disabled', width=15)
        self.process_button.grid(row=0, column=0, padx=5)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
    
    def select_excel_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Studienliste Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if file_path:
            self.excel_file_path = file_path
            self.excel_label.config(text=os.path.basename(file_path), foreground="black")
            self.check_ready()
    
    def select_mapped_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Mapped File (Excel or CSV)",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.mapped_file_path = file_path
            self.mapped_label.config(text=os.path.basename(file_path), foreground="black")
            self.check_ready()
    
    def check_ready(self):
        if self.excel_file_path and self.mapped_file_path:
            self.process_button.config(state='normal')
            self.status_label.config(text="Files selected. Ready to compare.")
        else:
            self.process_button.config(state='disabled')
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def start_comparison(self):
        if not self.excel_file_path or not self.mapped_file_path:
            messagebox.showerror("Error", "Please select both files")
            return
        
        self.process_button.config(state='disabled')
        self.progress.start()
        self.update_status("Processing...")
        
        thread = threading.Thread(target=self.process_files, daemon=True)
        thread.start()
    
    def process_files(self):
        try:
            script_directory = os.path.dirname(os.path.abspath(__file__))
            if not script_directory:
                script_directory = os.getcwd()
            
            debug = self.debug_mode.get()
            
            # ================================================================
            # Load Studienliste Excel
            # ================================================================
            print("\n" + "="*80)
            print(f"📂 LOADING STUDIENLISTE: {self.excel_file_path}")
            print("="*80)
            
            df_studien = None
            
            # Try different header rows
            for header_row in [0, 1, 2, 3, 4]:
                try:
                    df_studien = pd.read_excel(self.excel_file_path, sheet_name='Studienliste', header=header_row)
                    print(f"Loaded with header={header_row}")
                    print(f"   Columns: {len(df_studien.columns)}")
                    print(f"   Rows: {len(df_studien)}")
                    
                    # Check if this looks like the right header
                    sample_columns = [col.lower() for col in df_studien.columns]
                    expected_cols = ['acronym', 'studie', 'phase', 'status']
                    found_count = sum(1 for col in expected_cols if any(col in c for c in sample_columns))
                    
                    if found_count >= 2:
                        print(f"   ✅ Found {found_count}/{len(expected_cols)} expected columns - using this header")
                        break
                    else:
                        print(f"   ⚠️ Only found {found_count}/{len(expected_cols)} expected columns - trying next header")
                except Exception as e:
                    print(f"   Error with header={header_row}: {e}")
            
            if df_studien is None:
                raise Exception("Could not load Studienliste Excel file")
            
            # ================================================================
            # Load Mapped File
            # ================================================================
            print("\n" + "="*80)
            print(f"📂 LOADING MAPPED FILE: {self.mapped_file_path}")
            print("="*80)
            
            file_extension = os.path.splitext(self.mapped_file_path)[1].lower()
            df_text = None
            
            if file_extension in ['.xlsx', '.xls']:
                try:
                    df_text = pd.read_excel(self.mapped_file_path, sheet_name=0)
                    print(f"✅ Loaded Excel file")
                except Exception as e:
                    print(f"Error loading Excel: {e}")
                    raise
            else:
                encodings = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252', 'iso-8859-1']
                for enc in encodings:
                    try:
                        df_text = pd.read_csv(self.mapped_file_path, encoding=enc, low_memory=False)
                        print(f"✅ Loaded CSV with encoding: {enc}")
                        break
                    except Exception as e:
                        print(f"   Failed with {enc}: {str(e)[:50]}")
                        continue
                
                if df_text is None:
                    raise Exception("Could not load CSV file with any encoding")
            
            print(f"   Columns: {len(df_text.columns)}")
            print(f"   Rows: {len(df_text)}")
            
            # ================================================================
            # Clean the data
            # ================================================================
            print("\n" + "="*80)
            print("🧹 CLEANING DATA")
            print("="*80)
            
            # Strip whitespace from string columns
            for col in df_studien.columns:
                if df_studien[col].dtype == 'object':
                    df_studien[col] = df_studien[col].astype(str).str.strip()
            
            for col in df_text.columns:
                if df_text[col].dtype == 'object':
                    df_text[col] = df_text[col].astype(str).str.strip()
            
            df_studien = df_studien.replace('', np.nan)
            df_text = df_text.replace('', np.nan)
            
            # ================================================================
            # Run Comparison
            # ================================================================
            print("\n" + "="*80)
            print("🔍 RUNNING COMPARISON")
            print("="*80)
            
            mismatches_df, matched_count, unmatched_count = compare_studies(df_studien, df_text, debug=debug)
            
            # ================================================================
            # Save Results
            # ================================================================
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"mismatches_{timestamp}.xlsx"
            output_path = os.path.join(script_directory, output_filename)
            
            # Save only the mismatches
            mismatches_df.to_excel(output_path, index=False, engine='openpyxl')
            
            print(f"\n✅ Results saved to:")
            print(f"   📄 {output_path}")
            print("="*80 + "\n")
            
            # Show result to user
            if len(mismatches_df) == 0:
                self.update_status("Complete - No mismatches found!")
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    "✅ Comparison completed successfully!\n\n" +
                    "All studies match perfectly!\n\n" +
                    f"Output saved to:\n{output_path}"))
            else:
                self.update_status(f"Complete - {len(mismatches_df)} mismatches found")
                
                # Group mismatches by type
                issue_counts = mismatches_df['issue'].value_counts()
                issue_summary = "\n".join([f"  • {k}: {v}" for k, v in issue_counts.items()])
                
                self.root.after(0, lambda: messagebox.showwarning("Comparison Complete", 
                    f"⚠️ Found {len(mismatches_df)} mismatches!\n\n" +
                    f"Issue breakdown:\n{issue_summary}\n\n" +
                    f"Output saved to:\n{output_path}"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.update_status("Error occurred")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        
        finally:
            self.root.after(0, self.processing_complete)
    
    def processing_complete(self):
        self.progress.stop()
        self.process_button.config(state='normal')
        self.update_status("Ready")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = ComparisonApp(root)
    root.mainloop()