"""Generate a sample Excel file showing the expected format for the Meridian MMM Dashboard."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from utils.data_loader import generate_sample_data
import pandas as pd

data = generate_sample_data()

output_path = os.path.join(os.path.dirname(__file__), "sample_meridian_output.xlsx")

with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    for sheet_name, df in data.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"Sample Excel file generated: {output_path}")
print(f"Sheets: {list(data.keys())}")
for name, df in data.items():
    print(f"  - {name}: {df.shape[0]} rows × {df.shape[1]} columns")
