from fastapi import APIRouter, UploadFile, File, HTTPException
import pandas as pd
from sqlalchemy import create_engine, text
import re
import io
import traceback
from app.core.database import SessionLocal, engine

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

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

@router.post("/upload")
async def upload_data(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files are allowed.")

    try:
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content), sheet_name='IND', header=0)

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

        # Only select columns that actually exist in the dataframe to prevent errors
        available_cols = [col for col in static_cols if col in df.columns]
        materials_df = df[available_cols].copy()
        
        rename_map = {
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
            'branch pend 22.04': 'branch_pend_22_04',
            'NO TRACE / Damage': 'no_trace_damage',
            'PO BALLANCE 22.04': 'po_balance_22_04',
            'GPC stk  22.04': 'gpc_stk_22_04',
            'GPC FREE STK 22.04': 'gpc_free_stk_22_04',
            'Branch stk 22.04': 'branch_stk_22_04',
            'FOR  1 DAY REQ': 'for_1_day_req',
            'STK IN ALT PART': 'stk_in_alt_part',
            'req on 12 m avg': 'req_on_12m_avg',
            'req on 03 m avg': 'req_on_03m_avg',
            'average': 'average',
            'aginge more than 120 days': 'aging_more_than_120_days',
            'blocked code in Aging': 'blocked_code_in_aging',
            'remarks': 'remarks'
        }
        materials_df.rename(columns=rename_map, inplace=True)
        # Drop rows where material_code is completely null
        if 'material_code' in materials_df.columns:
            materials_df.dropna(subset=['material_code'], inplace=True)
            materials_df.drop_duplicates(subset=['material_code'], inplace=True)

        # ================== 2. MONTHLY DATA ==================
        monthly_records = []
        for _, row in df.iterrows():
            mat_code = row.get('Material')
            if pd.isna(mat_code):
                continue
            
            for col in monthly_cols:
                value = row.get(col)
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

        # ================== 3. SUMMARY ==================
        summary_cols = ['Material', '3 M av', '3 m max', '3 m mean', '12 m MAX', '12 M AV', '12 m mean']
        avail_summary_cols = [col for col in summary_cols if col in df.columns]
        summary_df = df[avail_summary_cols].copy()
        
        # User explicitly requested fixing the summary column renaming
        summary_rename_map = {
            'Material': 'material_code',
            '3 M av': 'three_m_av',
            '3 m max': 'three_m_max',
            '3 m mean': 'three_m_mean',
            '12 m MAX': 'twelve_m_max',
            '12 M AV': 'twelve_m_av',
            '12 m mean': 'twelve_m_mean'
        }
        summary_df.rename(columns=summary_rename_map, inplace=True)
        if 'material_code' in summary_df.columns:
            summary_df.dropna(subset=['material_code'], inplace=True)
            summary_df.drop_duplicates(subset=['material_code'], inplace=True)

        # ================== 4. DATABASE INSERTION ==================
        # Replace data using pandas to_sql
        # Notice we reuse the SQLAlchemy engine
        
        monthly_df = pd.DataFrame(monthly_records)
        
        # NOTE: to_sql replace drops the table and re-creates it.
        # This might lose primary keys or foreign keys unless done carefully.
        # For this prototype it mirrors the data-import.py behavior.
        monthly_df.to_sql('material_monthly_data', con=engine, if_exists='replace', index=False)
        summary_df.to_sql('material_summary', con=engine, if_exists='replace', index=False)
        materials_df.to_sql('materials', con=engine, if_exists='replace', index=False)
        
        # It's generally better to set primary keys back after replace
        with engine.connect() as con:
            con.execute(text("ALTER TABLE materials ADD PRIMARY KEY (material_code);"))
            con.execute(text("ALTER TABLE material_summary ADD PRIMARY KEY (material_code);"))
            con.commit()

        return {
            "message": "Data imported successfully", 
            "materials_count": len(materials_df),
            "monthly_records_count": len(monthly_df)
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
