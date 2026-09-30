import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
import re 
import pandas as pd

# Define column mappings from Studienliste to text_csv
column_mapping = {
    'Standort': 'location',
    'Studientitel deutsch': 'title',  
    'Studientitel': 'title',
    'Acronym': 'acronym',
    'EU-CT No': 'ref_id', 
    'Registrierungs-nummer DRKS': 'drks_id',
    'Registrierungsnummer Clinical trials gov': 'nct_id',
    #'Erkrankung': 'organsystem', 
    'Erkrankung vereinfacht': 'organsystem',
    'Art der Intervention und Stadium': 'stadium',
    'Phase': 'phase',
    'Rekrutierungsstatus': 'status',
    'IIT': 'styp',  
    'UMR-initiiert': 'styp1',
    'durchführende Einheit': 'department',
    'PI UMR': 'controller',
    'Altersgruppe': 'altersgruppe',
    'Therapielinie': 'therapielinie'
}

# Status mapping 
status_mapping = {
    'Recruitment ongoing': 'Rekrutierung läuft',
    'Recruitment closed, FU ongoing': 'Rekrutierung abgeschlossen - Follow-Up läuft',
    'Recruitment closed, FU closed': 'Rekrutierung abgeschlossen - Follow-Up abgeschlossen',
    'Recruitment temporarily hold': 'Ausgesetzt',
    'Recruitment terminated prematurely': 'Vorzeitig abgebrochen',
    'completed': 'Beendet'
}


location_mapping = {
    'Universitätsmedizin Rostock': 'Rostock UMR',
    'Rostock UMR': 'Rostock UMR',
    'UMR Rostock': 'Rostock UMR',
    'Universitätsklinikum Rostock': 'Rostock UMR',
    'Uniklinik Rostock': 'Rostock UMR',
    'Universitätsmedizin Greifswald': 'Greifswald UMG',
    'Greifswald UMG': 'Greifswald UMG',
    'Gemeinschaftspraxis Rostock' : 'Gemeinschaftspraxis Rostock, Wismarsche Str.'
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
    'IV': 'IV'
}

def normalize_text(text):
    """
    Normalize text for comparison by:
    - Removing newlines, carriage returns, tabs
    - Standardizing spaces around commas
    - Removing multiple spaces
    - Stripping leading/trailing whitespace
    - Converting to lowercase
    """
    if not isinstance(text, str):
        return text
    
    # Replace newlines, carriage returns, tabs with space
    text = re.sub(r'[\r\n\t]+', ' ', text)
    
    # Remove spaces before commas (e.g., "text ,text" -> "text,text")
    text = re.sub(r'\s+,', ',', text)
    
    # Ensure space after commas (e.g., "text,text" -> "text, text")
    text = re.sub(r',(?!\s)', ', ', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Convert to lowercase for case-insensitive comparison
    return text.lower()

def calculate_styp(row):
    region = row.get('region', 'Rostock') 
    iit = str(row.get('IIT', '')).lower().strip()
    umr_init = str(row.get('UMR-initiiert', '')).lower().strip()
    
    if region == 'Rostock':
        if iit == 'yes' and umr_init == 'yes':
            return 'IIT von Einrichtung initiiert'
        elif iit == 'yes' and umr_init == 'no':
            return 'IIT von anderer Einrichtung initiiert'
        elif iit == 'yes' and umr_init == ' ':
            return 'IIT von anderer Einrichtung initiiert'
        else:
            return 'Non-IIT'
    return 'Non-IIT'  

# Function to compare values
def compare_studies(df_studien, df_text_csv):
    mismatches = []
    
    for idx, study_row in df_studien.iterrows():
        acronym = study_row.get('Acronym')
        if pd.isna(acronym) or str(acronym).strip() == '':
            continue
            
        # Find matching rows in text_csv by acronym (case-insensitive)
        matching_rows = df_text_csv[df_text_csv['acronym'].astype(str).str.strip().str.lower() == str(acronym).strip().lower()]
        
        if len(matching_rows) == 0:
            mismatches.append({
                'acronym': acronym,
                'column': 'acronym',
                'issue': 'Not found in text_csv',
                'wrong_value': '',
                'corrected_value': 'Add entry'
            })
            continue
        
        # If multiple matches, try to find the one with matching location
        text_row = None
        if len(matching_rows) > 1:
            print(f"Multiple matches found for acronym '{acronym}', checking location...")
            expected_location = study_row.get('Standort')
            
            if pd.notna(expected_location):
                # Try to find match by location
                for _, row in matching_rows.iterrows():
                    actual_location = row.get('location')
                    if pd.notna(actual_location):
                        expected_normalized = location_mapping.get(str(expected_location).strip(), str(expected_location).strip())
                        actual_normalized = location_mapping.get(str(actual_location).strip(), str(actual_location).strip())
                        if expected_normalized == actual_normalized:
                            text_row = row
                            print(f"  Found match by location: {actual_location}")
                            break
            
            # If no location match found, use the first one
            if text_row is None:
                text_row = matching_rows.iloc[0]
                print(f"  No location match found, using first match")
        else:
            text_row = matching_rows.iloc[0]
        
        # Compare location with normalization
        expected_location = study_row.get('Standort')
        actual_location = text_row.get('location')
        if pd.notna(expected_location) and pd.notna(actual_location):
            expected_normalized = location_mapping.get(str(expected_location).strip(), str(expected_location).strip())
            actual_normalized = location_mapping.get(str(actual_location).strip(), str(actual_location).strip())
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'location',
                    'wrong_value': actual_location,
                    'corrected_value': expected_location
                })
        
        # Title comparison with normalization (case-insensitive)
        expected_title = study_row.get('Studientitel deutsch')
        if pd.isna(expected_title):
            expected_title = study_row.get('Studientitel')
        actual_title = text_row.get('title')
        if pd.notna(expected_title) and pd.notna(actual_title):
            # Normalize both values before comparison
            expected_normalized = normalize_text(str(expected_title)).lower()
            actual_normalized = normalize_text(str(actual_title)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'title',
                    'wrong_value': actual_title,
                    'corrected_value': expected_title
                })
        
        # Compare ref_id (EU-CT No) - case-insensitive with normalization
        expected_ref_id = study_row.get('EU-CT No')
        actual_ref_id = text_row.get('ref_id')
        if pd.notna(expected_ref_id) and pd.notna(actual_ref_id):
            expected_normalized = normalize_text(str(expected_ref_id)).lower()
            actual_normalized = normalize_text(str(actual_ref_id)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'ref_id',
                    'wrong_value': actual_ref_id,
                    'corrected_value': expected_ref_id
                })

        #Compare drks_id (DRKS_id) - case sensitive with normalization
        expected_ref_id = study_row.get('Registrierungs-nummer DRKS')
        actual_ref_id = text_row.get('drks_id')
        if pd.notna(expected_ref_id) and pd.notna(actual_ref_id):
            expected_normalized = normalize_text(str(expected_ref_id)).lower()
            actual_normalized = normalize_text(str(actual_ref_id)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'ref_id',
                    'wrong_value': actual_ref_id,
                    'corrected_value': expected_ref_id
                })

        # Compare nct_id - case-insensitive with normalization
        expected_nct = study_row.get('Registrierungsnummer Clinical trials gov')
        actual_nct = text_row.get('nct_id')
        if pd.notna(expected_nct) and pd.notna(actual_nct):
            expected_normalized = normalize_text(str(expected_nct)).lower()
            actual_normalized = normalize_text(str(actual_nct)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'nct_id',
                    'wrong_value': actual_nct,
                    'corrected_value': expected_nct
                })
        
        # Compare organsystem (Erkrankung) - case-insensitive with normalization
       #expected_organ = study_row.get('Erkrankung')
        #actual_organ = text_row.get('organsystem')
        #if pd.notna(expected_organ) and pd.notna(actual_organ):
            #expected_normalized = normalize_text(str(expected_organ)).lower()
            #actual_normalized = normalize_text(str(actual_organ)).lower()
            #if expected_normalized != actual_normalized:
                #mismatches.append({
                    #'acronym': acronym,
                    #'column': 'organsystem',
                    #'wrong_value': actual_organ,
                    #'corrected_value': expected_organ
                #})
        expected_organ = study_row.get('Erkrankung vereinfacht')
        actual_organ = text_row.get('organsystem')
        if pd.notna(expected_organ) and pd.notna(actual_organ):
            expected_normalized = normalize_text(str(expected_organ)).lower()
            actual_normalized = normalize_text(str(actual_organ)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'organsystem',
                    'wrong_value': actual_organ,
                    'corrected_value': expected_organ
                })
        
        # Compare stadium (Art der Intervention und Stadium) with normalization
        expected_stadium = study_row.get('Art der Intervention und Stadium')
        actual_stadium = text_row.get('stadium')
        if pd.notna(expected_stadium) and pd.notna(actual_stadium):
            expected_normalized = normalize_text(str(expected_stadium)).lower()
            actual_normalized = normalize_text(str(actual_stadium)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'stadium',
                    'wrong_value': actual_stadium,
                    'corrected_value': expected_stadium
                })
        
        # Compare phase with normalization and case-insensitive
        expected_phase = study_row.get('Phase')
        actual_phase = text_row.get('phase')
        if pd.notna(expected_phase) and pd.notna(actual_phase):
            # Normalize using mapping if available, otherwise use original
            expected_normalized = phase_mapping.get(str(expected_phase).strip(), str(expected_phase).strip())
            actual_normalized = phase_mapping.get(str(actual_phase).strip(), str(actual_phase).strip())
            if expected_normalized.lower() != actual_normalized.lower():
                mismatches.append({
                    'acronym': acronym,
                    'column': 'phase',
                    'wrong_value': actual_phase,
                    'corrected_value': expected_phase
                })
        
        # Compare status (with German translation) - with normalization
        expected_status_en = study_row.get('Rekrutierungsstatus')
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
                        'wrong_value': actual_status,
                        'corrected_value': expected_status_de
                    })
        
        # Compare styp - case-insensitive with normalization
        region = 'Rostock'
        expected_styp = calculate_styp(study_row)
        actual_styp = text_row.get('styp')
        if pd.notna(actual_styp):
            expected_normalized = normalize_text(expected_styp).lower()
            actual_normalized = normalize_text(str(actual_styp)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'styp',
                    'wrong_value': actual_styp,
                    'corrected_value': expected_styp
                })
        
        # Compare department - case-insensitive with advanced normalization
        expected_dept = study_row.get('durchführende Einheit')
        actual_dept = text_row.get('department')
        if pd.notna(expected_dept) and pd.notna(actual_dept):
            # Normalize both values: remove newlines, extra spaces, standardize commas
            expected_normalized = normalize_text(str(expected_dept))
            actual_normalized = normalize_text(str(actual_dept))
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'department',
                    'wrong_value': actual_dept,
                    'corrected_value': expected_dept
                })
        
        # Compare controller (PI UMR) - case-insensitive with normalization
        expected_pi = study_row.get('PI UMR')
        actual_pi = text_row.get('controller')
        if pd.notna(expected_pi) and pd.notna(actual_pi):
            expected_normalized = normalize_text(str(expected_pi))
            actual_normalized = normalize_text(str(actual_pi))
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'controller',
                    'wrong_value': actual_pi,
                    'corrected_value': expected_pi
                })
        
        # Compare altersgruppe - case-insensitive with normalization
        expected_age = study_row.get('Altersgruppe')
        actual_age = text_row.get('altersgruppe')
        if pd.notna(expected_age) and pd.notna(actual_age):
            # Map German age groups if needed
            age_mapping = {
                '< 18': 'Kinder und Jugendliche',
                '≥ 18': 'Erwachsene',
                '18-60': 'Erwachsene',
                '> 60': 'Senioren'
            }
            expected_age_de = age_mapping.get(str(expected_age).strip(), str(expected_age).strip())
            expected_normalized = normalize_text(expected_age_de).lower()
            actual_normalized = normalize_text(str(actual_age)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'altersgruppe',
                    'wrong_value': actual_age,
                    'corrected_value': expected_age_de
                })
        
        # Compare therapielinie - case-insensitive with normalization
        expected_line = study_row.get('Therapielinie')
        actual_line = text_row.get('therapielinie')
        if pd.notna(expected_line) and pd.notna(actual_line):
            expected_normalized = normalize_text(str(expected_line)).lower()
            actual_normalized = normalize_text(str(actual_line)).lower()
            if expected_normalized != actual_normalized:
                mismatches.append({
                    'acronym': acronym,
                    'column': 'therapielinie',
                    'wrong_value': actual_line,
                    'corrected_value': expected_line
                })
    
    return pd.DataFrame(mismatches)

class ComparisonApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Study Comparison Tool")
        self.root.geometry("550x300")
        self.root.resizable(False, False)
        
        self.excel_file_path = None
        self.mapped_file_path = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Study Comparison Tool", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # File 1 selection (Excel)
        ttk.Label(main_frame, text="Studienliste Excel File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.excel_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.excel_label.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_excel_file).grid(row=1, column=2, pady=5)
        
        # File 2 selection (Excel or CSV)
        ttk.Label(main_frame, text="Mapped File (Excel or CSV):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.mapped_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.mapped_label.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_mapped_file).grid(row=2, column=2, pady=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.process_button = ttk.Button(button_frame, text="Start Comparison", command=self.start_comparison, state='disabled')
        self.process_button.grid(row=0, column=0, padx=5)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
    
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
            
            # Load Excel file
            print(f"Loading Excel file: {self.excel_file_path}")
            df_studien = pd.read_excel(self.excel_file_path, sheet_name='Studienliste', header=4)
            
            # Load the mapped file (could be CSV or Excel)
            print(f"Loading mapped file: {self.mapped_file_path}")
            
            # Check file extension to determine how to read it
            file_extension = os.path.splitext(self.mapped_file_path)[1].lower()
            
            df_text_csv = None
            used_method = None
            
            if file_extension in ['.xlsx', '.xls']:
                # It's an Excel file
                print("Detected Excel file format")
                try:
                    df_text_csv = pd.read_excel(self.mapped_file_path)
                    used_method = "Excel direct read"
                    print(f"Successfully loaded Excel file")
                except Exception as e:
                    print(f"Error loading Excel file: {e}")
                    raise Exception(f"Could not read Excel file: {e}")
            else:
                # It's a CSV file, try different encodings
                print("Detected CSV file format")
                
                # First, detect the encoding using chardet
                try:
                    import chardet
                    with open(self.mapped_file_path, 'rb') as file:
                        raw_data = file.read(50000)
                        result = chardet.detect(raw_data)
                        detected_encoding = result['encoding']
                        confidence = result['confidence']
                        print(f"Detected encoding: {detected_encoding} (confidence: {confidence:.2%})")
                except ImportError:
                    print("chardet not installed, trying common encodings...")
                    detected_encoding = None
                
                # Try to read CSV with detected encoding or fallback to common ones
                encodings_to_try = []
                
                if detected_encoding:
                    encodings_to_try.append(detected_encoding)
                
                # Add common encodings
                encodings_to_try.extend([
                    'utf-8-sig',  # UTF-8 with BOM
                    'utf-8',
                    'latin1',
                    'cp1252',
                    'iso-8859-1',
                    'cp850',
                    'mac_roman',
                    'utf-16'
                ])
                
                # Remove duplicates
                seen = set()
                encodings_to_try = [x for x in encodings_to_try if not (x in seen or seen.add(x))]
                
                for enc in encodings_to_try:
                    try:
                        print(f"Trying encoding: {enc}")
                        df_text_csv = pd.read_csv(self.mapped_file_path, encoding=enc)
                        used_method = f"CSV with encoding: {enc}"
                        print(f"Successfully loaded with encoding: {enc}")
                        break
                    except (UnicodeDecodeError, UnicodeError) as e:
                        print(f"  Failed with {enc}: {str(e)[:50]}")
                        continue
                    except Exception as e:
                        print(f"  Error with {enc}: {str(e)[:50]}")
                        continue
                
                if df_text_csv is None:
                    # Last resort: Use open with 'rb' and decode with latin1 and replace errors
                    print("\nLast resort: Reading binary file with error replacement...")
                    try:
                        with open(self.mapped_file_path, 'rb') as file:
                            content = file.read()
                            decoded_content = content.decode('latin1', errors='replace')
                            from io import StringIO
                            df_text_csv = pd.read_csv(StringIO(decoded_content))
                            used_method = "binary+latin1 (error replacement)"
                            print("Successfully loaded with binary decoding")
                    except Exception as e:
                        raise Exception(f"Could not read CSV file: {e}")
            
            if df_text_csv is None:
                raise Exception("Could not read the mapped file")
            
            print(f"\nFinal used method: {used_method}")
            print(f"Mapped file has {len(df_text_csv)} rows and {len(df_text_csv.columns)} columns")
            
            # Run comparison
            print("\nComparing studies...")
            mismatches_df = compare_studies(df_studien, df_text_csv)
            
            # Save results
            output_filename = "mismatches.xlsx"
            output_path = os.path.join(script_directory, output_filename)
            mismatches_df.to_excel(output_path, index=False, engine='openpyxl')
            
            print(f"\nFound {len(mismatches_df)} mismatches")
            print(f"Saved to: {output_path}")
            
            self.update_status("Comparison completed successfully!")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Comparison completed!\n\nFound {len(mismatches_df)} mismatches.\n\nOutput saved to:\n{output_path}"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"\n{error_msg}")
            self.update_status("Error occurred during comparison")
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            import traceback
            traceback.print_exc()
        
        finally:
            self.root.after(0, self.processing_complete)
    
    def processing_complete(self):
        self.progress.stop()
        self.process_button.config(state='normal')
        self.update_status("Ready")

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = ComparisonApp(root)
    root.mainloop()