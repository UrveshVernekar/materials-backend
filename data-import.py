import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np
from datetime import datetime
import re
import sys
import os

# Set up path to allow importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.core.init_db import init_db

# ================== CONFIG ==================
EXCEL_PATH = './procurement-data.xlsx'   # Update this
DB_URI = "postgresql+psycopg2://materialsuser:materials1234#$@localhost:5432/materials_db"

engine = create_engine(DB_URI)

# Initialize/update database schema first
print("Initializing/updating database schema...")
init_db()

# Month mapping (Excel headers like "Apr-25")
month_map = {
    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
}

def parse_period(col_name):
    """Convert 'Apr-25' → (2025, 4)"""
    match = re.match(r'([A-Za-z]+)-(\d+)', col_name)
    if match:
        mon_str, yr_str = match.groups()
        year = 2000 + int(yr_str) if int(yr_str) < 50 else int(yr_str)
        month = month_map.get(mon_str[:3])
        return year, month
    return None, None

# ================== LOAD MAIN SHEET ==================
df = pd.read_excel(EXCEL_PATH, sheet_name='IND', header=0)

# Clean column names and handle duplicates
new_cols = []
counts = {}
for col in df.columns:
    clean_name = (col.strftime('%b-%y') if hasattr(col, 'strftime') else str(col)).strip().replace('\n', ' ')
    if clean_name in counts:
        counts[clean_name] += 1
        new_cols.append(f"{clean_name}.{counts[clean_name]}")
    else:
        counts[clean_name] = 0
        new_cols.append(clean_name)
df.columns = new_cols

# Identify monthly columns
monthly_cols = [col for col in df.columns if re.match(r'[A-Za-z]+-\d+', col)]

print(f"Found {len(monthly_cols)} monthly columns: {monthly_cols[:10]}...")

# ================== 1. MATERIALS TABLE ==================
static_cols = [
    'sr no', 'Material', 'Machine population', 'Last Production Year',
    'SERV PER LEFT', 'INH', 'INHS/OBSLTE', 'ALT TOKEN', 'ALT',
    'Material Description', 'vendor', 'price', 'MOQ', 'COV IN DAYS',
    'branch pend 22.04', 'NO TRACE / Damage', 'PO BALLANCE 22.04',
    'GPC stk  22.04', 'GPC FREE STK 22.04', 'Branch stk 22.04',
    'FOR  1 DAY REQ', 'STK IN ALT PART', 'req on 12 m avg',
    'req on 03 m avg', 'average', 'aginge more than 120 days',
    'blocked code in Aging', 'remarks'
]

materials_df = df[static_cols].copy()
materials_df.rename(columns={
    'sr no': 'sr_no',
    'Material': 'material_code',
    'Material Description': 'material_description',
    'Last Production Year': 'last_production_year',
    'Machine population': 'machine_population',
    'SERV PER LEFT': 'serv_per_left',
    'INH': 'inh',
    'INHS/OBSLTE': 'inh_s_obslte',
    'ALT TOKEN': 'alt_token',
    'ALT': 'alt',
    'vendor': 'vendor',
    'price': 'price',
    'MOQ': 'moq',
    'COV IN DAYS': 'cov_in_days',
    'branch pend 22.04': 'branch_pend',
    'NO TRACE / Damage': 'no_trace_damage',
    'PO BALLANCE 22.04': 'po_balance',
    'GPC stk  22.04': 'gpc_stk',
    'GPC FREE STK 22.04': 'gpc_free_stk',
    'Branch stk 22.04': 'branch_stk',
    'FOR  1 DAY REQ': 'for_1_day_req',
    'STK IN ALT PART': 'stk_in_alt_part',
    'req on 12 m avg': 'req_on_12m_avg',
    'req on 03 m avg': 'req_on_03m_avg',
    'average': 'average',
    'aginge more than 120 days': 'aging_more_than_120_days',
    'blocked code in Aging': 'blocked_code_in_aging',
    'remarks': 'remarks'
}, inplace=True)

# Drop sr_no as it is not part of the database schema
if 'sr_no' in materials_df.columns:
    materials_df.drop(columns=['sr_no'], inplace=True)

# ================== 2. MONTHLY DATA ==================
monthly_records = []

for _, row in df.iterrows():
    mat_code = row['Material']
    if pd.isna(mat_code):
        continue
    
    for col in monthly_cols:
        value = row[col]
        if pd.isna(value):
            continue
        year, month = parse_period(col)
        if year and month:
            monthly_records.append({
                'material_code': mat_code,
                'year': year,
                'month': month,
                'consumption': float(value)
            })

# ================== 4. DATABASE INSERTION (SAFE ORDER) ==================
print("Inserting data into database...")
monthly_df = pd.DataFrame(monthly_records)

with engine.begin() as conn:
    # Safely clear old records while keeping schema intact
    conn.execute(text("DELETE FROM material_monthly_data CASCADE"))
    conn.execute(text("DELETE FROM materials CASCADE"))

    # Append new data to existing structured schema
    if not materials_df.empty:
        materials_df.to_sql('materials', con=conn, if_exists='append', index=False)
    if not monthly_df.empty:
        monthly_df.to_sql('material_monthly_data', con=conn, if_exists='append', index=False)

print(f"Inserted {len(materials_df)} materials and {len(monthly_df)} monthly records.")