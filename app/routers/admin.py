from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import pandas as pd
import numpy as np
import io
import re
import traceback
import uuid
import csv

upload_tasks = {}

def psql_insert_copy(table, conn, keys, data_iter):
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        s_buf = io.StringIO()
        writer = csv.writer(s_buf)
        for row in data_iter:
            clean_row = []
            for val in row:
                if pd.isna(val):
                    clean_row.append(None)
                elif isinstance(val, float) and val.is_integer():
                    clean_row.append(int(val))
                else:
                    clean_row.append(val)
            writer.writerow(clean_row)
        s_buf.seek(0)
        columns = ', '.join([f'"{k}"' for k in keys])
        table_name = f'{table.schema}.{table.name}' if table.schema else table.name
        sql = f'COPY {table_name} ({columns}) FROM STDIN WITH CSV'
        cur.copy_expert(sql=sql, file=s_buf)

from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from sqlalchemy import text
from app.core.database import engine

router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# =========================================================
# MONTH PARSING
# =========================================================
month_map = {
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12
}

MONTH_PATTERN = re.compile(
    r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-_ ]?\d{2,4}$',
    re.IGNORECASE
)

def parse_period(col_name):
    match = re.match(r'([A-Za-z]+)[-_ ]?(\d+)', col_name)

    if match:
        mon_str, yr_str = match.groups()

        year = (
            2000 + int(yr_str)
            if len(yr_str) == 2
            else int(yr_str)
        )

        month = month_map.get(mon_str[:3].title())

        return year, month

    return None, None

# =========================================================
# NORMALIZATION
# =========================================================
def normalize_column(col):
    return (
        str(col)
        .strip()
        .lower()
        .replace("\n", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace(".", " ")
        .replace("  ", " ")
    )

# =========================================================
# SCHEMA DEFINITIONS
# =========================================================
SCHEMA_FIELDS = {
    "material_code": [
        "material",
        "material code",
        "part code",
        "item code"
    ],

    "material_description": [
        "material description",
        "description",
        "dec"
    ],

    "product_category": [
        "product cat",
        "prod cat",
        "product category",
        "prod category"
    ],

    "product_status": [
        "product status",
        "prod status",
        "status",
        "product stat"
    ],

    "vendor": [
        "vendor",
        "supplier"
    ],

    "machine_population": [
        "machine population",
        "machine production population",
        "population"
    ],

    "last_production_year": [
        "last production year",
        "last prod year"
    ],

    "serv_per_left": [
        "serv per left",
        "left serv period"
    ],

    "inh": [
        "inh"
    ],

    "inh_s_obslte": [
        "inhs/obslte",
        "obsolete"
    ],

    "alt_token": [
        "alt token"
    ],

    "alt": [
        "alt"
    ],

    "price": [
        "price"
    ],

    "moq": [
        "moq",
        "minimum order quantity"
    ],

    "lead_time": [
        "lead time",
        "lead time days"
    ],

    "delta": [
        "delta",
        "delta days"
    ],

    "cov_in_days": [
        "cov in days",
        "coverage in days"
    ],

    "branch_pend": [
        "branch pend 22.04",
        "branch pend 21.04",
        "branch pending"
    ],

    "no_trace_damage": [
        "no trace / damage",
        "damage"
    ],

    "po_balance": [
        "po balance 22.04",
        "po balance 21.04",
        "po balance"
    ],

    "gpc_stk": [
        "gpc stk 22.04",
        "gpc stk 21.04",
        "gpc stock"
    ],

    "gpc_free_stk": [
        "gpc free stk 22.04",
        "gpc free stk 21.04",
        "gpc free stock"
    ],

    "branch_stk": [
        "branch stk 22.04",
        "branch stk 21.04",
        "branch stock"
    ],

    "for_1_day_req": [
        "for 1 day req",
        "1 day requirement"
    ],

    "stk_in_alt_part": [
        "stk in alt part"
    ],

    "req_on_12m_avg": [
        "req on 12 m avg"
    ],

    "req_on_03m_avg": [
        "req on 03 m avg"
    ],

    "average": [
        "average"
    ],

    "aging_more_than_120_days": [
        "aginge more than 120 days",
        "aging more than 120 days"
    ],

    "blocked_code_in_aging": [
        "blocked code in aging"
    ],

    "remarks": [
        "remarks"
    ]
}

# =========================================================
# EMBEDDING CACHE
# =========================================================
schema_embeddings = {}

for db_col, aliases in SCHEMA_FIELDS.items():
    schema_embeddings[db_col] = embedding_model.encode(aliases)

# =========================================================
# COLUMN MATCHER
# =========================================================
def find_best_match(excel_col):

    normalized_excel = normalize_column(excel_col)

    best_score = 0
    best_field = None

    excel_embedding = embedding_model.encode([normalized_excel])[0]

    for db_col, aliases in SCHEMA_FIELDS.items():

        # ==========================================
        # EXACT MATCH BOOST
        # ==========================================
        for alias in aliases:

            normalized_alias = normalize_column(alias)

            if normalized_excel == normalized_alias:
                return db_col, 100

        # ==========================================
        # FUZZY MATCH
        # ==========================================
        fuzzy_score = max(
            fuzz.token_sort_ratio(
                normalized_excel,
                normalize_column(alias)
            )
            for alias in aliases
        )

        # ==========================================
        # SEMANTIC MATCH
        # ==========================================
        semantic_scores = cosine_similarity(
            [excel_embedding],
            schema_embeddings[db_col]
        )[0]

        semantic_score = max(semantic_scores) * 100

        # ==========================================
        # COMBINED SCORE
        # ==========================================
        final_score = (
            fuzzy_score * 0.7
            +
            semantic_score * 0.3
        )

        if final_score > best_score:
            best_score = final_score
            best_field = db_col

    return best_field, best_score


# =========================================================
# MAIN UPLOAD API
# =========================================================
@router.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    if task_id not in upload_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return upload_tasks[task_id]

@router.post("/upload")
async def upload_data(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Only Excel files are allowed."
        )

    content = await file.read()
    task_id = str(uuid.uuid4())
    upload_tasks[task_id] = {"status": "processing", "progress": 0, "message": "Initializing upload..."}
    
    background_tasks.add_task(process_upload_task, task_id, content)
    
    return {
        "message": "Upload started",
        "task_id": task_id
    }

def process_upload_task(task_id: str, content: bytes):
    try:
        upload_tasks[task_id] = {"status": "processing", "progress": 10, "message": "Reading Excel file..."}

        # READ EXCEL
        df_raw = pd.read_excel(
            io.BytesIO(content),
            sheet_name='IND',
            header=None
        )

        # =====================================================
        upload_tasks[task_id] = {"status": "processing", "progress": 20, "message": "Finding header row..."}
        
        # FIND HEADER ROW
        # =====================================================
        best_row_idx = 0
        best_row_score = -1

        # CHECK FIRST 30 ROWS TO FIND THE ROW WITH MOST SCHEMA MATCHES
        for idx in range(min(30, len(df_raw))):
            row_values = df_raw.iloc[idx].values
            score = 0
            
            for val in row_values:
                if pd.isna(val):
                    continue
                
                norm_val = normalize_column(val)
                if not norm_val:
                    continue
                    
                # EXACT OR PARTIAL MATCH IN SCHEMA ALIASES
                for db_col, aliases in SCHEMA_FIELDS.items():
                    if any(normalize_column(a) == norm_val for a in aliases):
                        score += 2
                        break
                    elif any(len(norm_val) > 3 and normalize_column(a) in norm_val for a in aliases):
                        score += 1
                        break
                        
            if score > best_row_score:
                best_row_score = score
                best_row_idx = idx

        # SET THE BEST ROW AS HEADER ROW
        header_row = df_raw.iloc[best_row_idx].copy()
        
        cleaned_header_row = []
        for i, val in enumerate(header_row):
            if pd.isna(val):
                cleaned_header_row.append(f"Unnamed_{i}")
            elif hasattr(val, 'strftime'):
                cleaned_header_row.append(val.strftime('%b-%y'))
            else:
                val_str = str(val).strip()
                if re.match(r'^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$', val_str):
                    try:
                        dt = pd.to_datetime(val_str)
                        val_str = dt.strftime('%b-%y')
                    except:
                        pass
                cleaned_header_row.append(val_str)
        header_row = cleaned_header_row
        
        df = df_raw.copy()
        df.columns = header_row
        df = df.iloc[best_row_idx + 1:].reset_index(drop=True)

        # =====================================================
        # CLEAN COLUMNS
        # =====================================================
        cleaned_cols = []

        for col in df.columns:

            if hasattr(col, 'strftime'):
                col = col.strftime('%b-%y')

            cleaned_cols.append(str(col).strip())

        df.columns = cleaned_cols

        # =====================================================
        # MONTHLY COLUMNS
        # =====================================================
        monthly_cols = [
            col for col in df.columns
            if MONTH_PATTERN.match(str(col))
        ]

        # =====================================================
        # INTELLIGENT COLUMN MAPPING
        # =====================================================
        upload_tasks[task_id] = {"status": "processing", "progress": 40, "message": "Mapping columns..."}
        column_mapping = {}
        schema_field_scores = {}

        for col in df.columns:
            if col in monthly_cols or col.startswith("Unnamed_"):
                continue

            best_field, score = find_best_match(col)

            print(f"{col} --> {best_field} ({score:.2f})")

            if score >= 65:
                # PREVENT DUPLICATE MAPPINGBY KEEPING ONLY THE HIGHEST SCORE
                if best_field in schema_field_scores:
                    if score > schema_field_scores[best_field]:
                        # REMOVE THE PREVIOUS LOWER-SCORING MATCH
                        keys_to_remove = [k for k, v in column_mapping.items() if v == best_field]
                        for k in keys_to_remove:
                            del column_mapping[k]
                        
                        column_mapping[col] = best_field
                        schema_field_scores[best_field] = score
                else:
                    column_mapping[col] = best_field
                    schema_field_scores[best_field] = score

        # =====================================================
        # MATERIALS DATAFRAME
        # =====================================================
        materials_df = df[list(column_mapping.keys())].copy()

        materials_df.rename(columns=column_mapping, inplace=True)

        # =====================================================
        # COERCE NUMERIC COLUMNS
        # =====================================================
        NUMERIC_FIELDS = [
            "machine_population", "last_production_year", "serv_per_left",
            "inh", "price", "moq", "cov_in_days", "branch_pend",
            "no_trace_damage", "po_balance", "gpc_stk",
            "gpc_free_stk", "branch_stk", "for_1_day_req",
            "stk_in_alt_part", "req_on_12m_avg", "req_on_03m_avg",
            "average", "aging_more_than_120_days",
            "lead_time", "delta"
        ]

        for col in NUMERIC_FIELDS:
            if col in materials_df.columns:
                materials_df[col] = pd.to_numeric(materials_df[col], errors='coerce')

        # =====================================================
        # CLEAN DATA
        # =====================================================
        if 'material_code' not in materials_df.columns:
            raise HTTPException(
                status_code=400,
                detail="Material code column could not be identified."
            )

        materials_df.dropna(
            subset=['material_code'],
            inplace=True
        )

        materials_df.drop_duplicates(
            subset=['material_code'],
            inplace=True
        )

        # =====================================================
        # MONTHLY DATA
        # =====================================================
        upload_tasks[task_id] = {"status": "processing", "progress": 60, "message": "Parsing monthly data..."}
        monthly_records = []

        material_col = None

        for excel_col, mapped_col in column_mapping.items():
            if mapped_col == 'material_code':
                material_col = excel_col
                break

        for _, row in df.iterrows():
            material_code = row.get(material_col)
            
            if isinstance(material_code, pd.Series):
                material_code = material_code.iloc[0]

            if pd.isna(material_code):
                continue

            for month_col in monthly_cols:
                value = row.get(month_col)
                
                if isinstance(value, pd.Series):
                    value = value.iloc[0]

                if pd.isna(value):
                    continue

                year, month = parse_period(month_col)

                if year and month:
                    try:
                        consumption_val = float(value)
                    except (ValueError, TypeError):
                        continue

                    monthly_records.append({
                        "material_code": material_code,
                        "year": year,
                        "month": month,
                        "consumption": consumption_val
                    })

        monthly_df = pd.DataFrame(monthly_records)


        # =====================================================
        # DATABASE INSERTION
        # =====================================================
        upload_tasks[task_id] = {"status": "processing", "progress": 90, "message": "Saving to database..."}

        with engine.begin() as conn:

            conn.execute(text("DELETE FROM materials CASCADE"))

            if not materials_df.empty:
                materials_df.to_sql(
                    'materials',
                    con=conn,
                    if_exists='append',
                    index=False,
                    method=psql_insert_copy
                )

            if not monthly_df.empty:
                monthly_df.to_sql(
                    'material_monthly_data',
                    con=conn,
                    if_exists='append',
                    index=False,
                    method=psql_insert_copy
                )

        upload_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Data imported successfully",
            "materials_count": len(materials_df),
            "monthly_records_count": len(monthly_df)
        }

    except Exception as e:

        traceback.print_exc()

        upload_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": "Import failed",
            "error": str(e)
        }