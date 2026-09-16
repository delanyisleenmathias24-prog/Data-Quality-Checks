import pandas as pd
import chardet
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import threading
import re

def clean_illegal_chars(value):
    """Remove illegal characters that Excel cannot handle"""
    if isinstance(value, str):
        # Remove control characters except tab, newline, carriage return
        # \x00-\x08, \x0b-\x0c, \x0e-\x1f, \x7f
        cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', value)
        # Replace any other problematic characters
        cleaned = cleaned.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return cleaned
    return value

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read(10000)  # Read first 10000 bytes
        result = chardet.detect(raw_data)
        return result['encoding']

def map_ids_to_values(file1_path, file2_path, output_path):
    #print("Detecting file encodings...")
    encoding1 = detect_encoding(file1_path)
    encoding2 = detect_encoding(file2_path)
    print(f"  File 1 encoding: {encoding1}")
    print(f"  File 2 encoding: {encoding2}")
    
    print("\nSource File...")
    # Try different encodings if needed
    encodings_to_try = [encoding1, 'utf-8', 'latin1', 'cp1252', 'iso-8859-1']
    
    df_data = None
    used_encoding = None
    for enc in encodings_to_try:
        try:
            df_data = pd.read_csv(file1_path, encoding=enc)
            used_encoding = enc
            print(f"Successfully Completed: {enc}")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if df_data is None:
        raise Exception("Could not read the file with any common encoding")
    
    print(f"Loaded {len(df_data)} rows and {len(df_data.columns)} columns")
    
    print("\nLoading ID mapping file...")
    df_id_mapping = None
    for enc in [encoding2, 'utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
        try:
            df_id_mapping = pd.read_csv(file2_path, encoding=enc)
            print(f"Successfully loaded with encoding: {enc}")
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if df_id_mapping is None:
        raise Exception("Could not read the mapping file with any common encoding")
    
    #print(f"Loaded {len(df_id_mapping)} mapping entries")
    # Define the mapping between File1 columns and File2 lookup categories
    column_mapping = {
        'orientation': 'Studienausrichtung',
        'location': 'Standort',
        'region': 'Region',
        'organsystem': 'Organsystem',
        'stadium': 'Stadium',
        'phase': 'Phase',
        'status': 'Studienstatus',
        'styp': 'Studientyp',
        'altersgruppe': 'Altersgruppe',
        'therapielinie': 'Therapielinie'
    }
    
    # Create a copy of the original dataframe
    df_mapped = df_data.copy()
    print("\nMapped Dataframe\n") 
    print(df_mapped)
    
    print("\nMapping IDs to values...")
    print("-" * 40)
    
    # For each column that needs mapping
    for target_col, lookup_category in column_mapping.items():
        if target_col in df_data.columns:
            print(f"\nProcessing '{target_col}'...")
            
            category_mapping = df_id_mapping[df_id_mapping.iloc[:, 2] == lookup_category]
            
            if not category_mapping.empty:
                id_to_value = dict(zip(category_mapping.iloc[:, 0], category_mapping.iloc[:, 1]))
                #print(f"Found {len(id_to_value)} mapping values")
                
                # Show first few mappings as example
                #sample_items = list(id_to_value.items())[:3]
                #if sample_items:
                    #print(f"Example mappings: {sample_items}")
                
                # Apply mapping
                def map_value(cell):
                    if pd.isna(cell):
                        return cell
                    try:
                        if isinstance(cell, str):
                            cell = cell.strip()
                        id_val = int(int(cell)) if isinstance(cell, (int, int)) else int(cell)
                        return id_to_value.get(id_val, cell)
                    except (ValueError, TypeError):
                        return cell
                
                df_mapped[target_col] = df_data[target_col].apply(map_value)
                
                # Count how many were mapped
                changed = (df_data[target_col] != df_mapped[target_col]).sum()
                print(f"Mapped {changed} out of {len(df_data)} values")
            else:
                print(f"mapping found for '{lookup_category}'")
                print(f"Available categories: {df_id_mapping.iloc[:, 2].unique()[:5]}...")
        else:
            print(f"Column '{target_col}' not found in data file")
    
    print("\n" + "="*40)
    print("Saving mapped data...")
    
    # Convert any non-string columns to string to avoid encoding issues
    for col in df_mapped.columns:
        if df_mapped[col].dtype == 'object':
            df_mapped[col] = df_mapped[col].astype(str).fillna('')
    
    df_mapped.to_csv(output_path, index=False, encoding='utf-8-sig', errors='replace')
    #print(f"File saved to: {output_path}")
    #print(f"Total rows: {len(df_mapped)}")
    #print(f"Total columns: {len(df_mapped.columns)}")
    
    # Show a preview of the mapped columns
    #print("\n" + "="*40)
    #print("PREVIEW OF FIRST 3 ROWS (Mapped columns only)")
    #print("="*40)
    
    """preview_cols = ['title'] + [col for col in column_mapping.keys() if col in df_mapped.columns]
    for idx in range(min(3, len(df_mapped))):
        print(f"\nRow {idx}:")
        for col in preview_cols:
            if col in df_mapped.columns:
                value = df_mapped.loc[idx, col]
                if len(str(value)) > 50:
                    value = str(value)[:50] + "..."
                print(f"  {col}: {value}")"""
    
    return df_mapped

class IDMapperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ID Mapping Tool")
        self.root.geometry("500x250")
        self.root.resizable(False, False)
        
        self.file1_path = None
        self.file2_path = None
        self.output_path = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="ID Mapping Tool", font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=10)
        
        # File 1 selection
        ttk.Label(main_frame, text="Source CSV File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.file1_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.file1_label.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_file1).grid(row=1, column=2, pady=5)
        
        # File 2 selection
        ttk.Label(main_frame, text="ID Mapping File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.file2_label = ttk.Label(main_frame, text="No file selected", foreground="gray", width=40)
        self.file2_label.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Button(main_frame, text="Browse", command=self.select_file2).grid(row=2, column=2, pady=5)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=15)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=10)
        
        self.process_button = ttk.Button(button_frame, text="Start Processing", command=self.start_processing, state='disabled')
        self.process_button.grid(row=0, column=0, padx=5)
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
    
    def select_file1(self):
        file_path = filedialog.askopenfilename(
            title="Select Source CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.file1_path = file_path
            self.file1_label.config(text=os.path.basename(file_path), foreground="black")
            self.check_ready()
    
    def select_file2(self):
        file_path = filedialog.askopenfilename(
            title="Select ID Mapping CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.file2_path = file_path
            self.file2_label.config(text=os.path.basename(file_path), foreground="black")
            self.check_ready()
    
    def check_ready(self):
        if self.file1_path and self.file2_path:
            self.process_button.config(state='normal')
            self.status_label.config(text="Files selected. Ready to process.")
        else:
            self.process_button.config(state='disabled')
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def start_processing(self):
        if not self.file1_path or not self.file2_path:
            messagebox.showerror("Error", "Please select both files")
            return
        
        # Disable process button during processing
        self.process_button.config(state='disabled')
        self.progress.start()
        self.update_status("Processing...")
        
        # Run processing in a separate thread to keep GUI responsive
        thread = threading.Thread(target=self.process_files, daemon=True)
        thread.start()
    
    def process_files(self):
        try:
            # Get the directory where the script is running
            output_directory = os.path.dirname(os.path.abspath(__file__))
            if not output_directory:
                output_directory = os.getcwd()
            
            # Create results folder if it doesn't exist
            results_folder = os.path.join(output_directory, "results")
            if not os.path.exists(results_folder):
                os.makedirs(results_folder)
            
            # Create output path in the results folder
            base_name = os.path.splitext(os.path.basename(self.file1_path))[0]
            output_filename = f"{base_name}_mapped.xlsx"
            output_path = os.path.join(results_folder, output_filename)
            
            # Run the mapping
            print("\n" + "="*40)
            print("STARTING ID MAPPING PROCESS")
            print("="*40)
            
            df_result = map_ids_to_values(self.file1_path, self.file2_path, output_path.replace('.xlsx', '.csv'))
            
            # Convert CSV to Excel
            print("\n" + "="*40)
            print("Converting to Excel format...")
            df_excel = pd.read_csv(output_path.replace('.xlsx', '.csv'), encoding='utf-8-sig')
            
            # Clean illegal characters from all string columns
            print("Cleaning illegal characters for Excel...")
            for col in df_excel.columns:
                if df_excel[col].dtype == 'object':
                    df_excel[col] = df_excel[col].apply(clean_illegal_chars)
            
            # Save to Excel
            try:
                df_excel.to_excel(output_path, index=False, engine='openpyxl')
                print("Excel file saved successfully")
            except Exception as excel_error:
                print(f"Excel save failed: {excel_error}")
                # Fallback: Save as CSV
                csv_fallback_path = output_path.replace('.xlsx', '_fallback.csv')
                df_excel.to_csv(csv_fallback_path, index=False, encoding='utf-8-sig')
                print(f"Saved as CSV fallback: {csv_fallback_path}")
                raise Exception(f"Could not save as Excel. Saved as CSV instead: {csv_fallback_path}")
            
            # Remove the temporary CSV file
            os.remove(output_path.replace('.xlsx', '.csv'))
            
            print(f"\nProcess completed successfully!")
            print(f"Excel file saved to: {output_path}")
            self.update_status("Process completed successfully!")
            
            # Show success message
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Processing completed!\n\nOutput saved to:\n{output_path}"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"\n{error_msg}")
            self.update_status("Error occurred during processing")
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            import traceback
            traceback.print_exc()
        
        finally:
            # Re-enable process button and stop progress bar
            self.root.after(0, self.processing_complete)
    
    def processing_complete(self):
        self.progress.stop()
        self.process_button.config(state='normal')
        if self.file1_path and self.file2_path:
            self.update_status("Ready for next process")
        else:
            self.update_status("Ready")

try:
    import chardet
except ImportError:
    print("Installing required package 'chardet'...")
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "chardet"])
    import chardet

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = IDMapperApp(root)
    root.mainloop()