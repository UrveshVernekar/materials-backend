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
            conn.execute(text("DELETE FROM material_monthly_data CASCADE"))

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

            # Update lead_time_qty using the monthly consumption and lead_time values
            if not materials_df.empty and not monthly_df.empty:
                update_query = """
                WITH ranked_data AS (
                    SELECT
                        mmd.material_code,
                        mmd.consumption,
                        m.lead_time,
                        ROW_NUMBER() OVER (
                            PARTITION BY mmd.material_code
                            ORDER BY mmd.year DESC, mmd.month DESC
                        ) AS rn
                    FROM public.material_monthly_data mmd
                    JOIN public.materials m
                        ON m.material_code = mmd.material_code
                ),
                calculated_qty AS (
                    SELECT
                        material_code,
                        (AVG(consumption) / 30) * MAX(lead_time) AS lead_time_qty
                    FROM ranked_data
                    WHERE rn <= 12
                    GROUP BY material_code
                )
                UPDATE public.materials m
                SET lead_time_qty = cq.lead_time_qty
                FROM calculated_qty cq
                WHERE m.material_code = cq.material_code;
                """
                conn.execute(text(update_query))

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


# =========================================================
# PREDICTION ENGINE ENDPOINTS & WORKER
# =========================================================
prediction_tasks = {}

def process_prediction_task(task_id: str):
    try:
        from statsmodels.tsa.holtwinters import Holt, ExponentialSmoothing
        import scipy.stats as stats
        try:
            from sklearn.metrics import root_mean_squared_error
        except ImportError:
            from sklearn.metrics import mean_squared_error
            def root_mean_squared_error(y_true, y_pred):
                return np.sqrt(mean_squared_error(y_true, y_pred))
    except Exception as import_err:
        prediction_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": "Failed to import required scientific libraries (statsmodels, scikit-learn, scipy). Please ensure they are installed.",
            "error": str(import_err)
        }
        return

    try:
        prediction_tasks[task_id] = {"status": "processing", "progress": 10, "message": "Loading materials and consumption history from DB..."}

        # Helper forecasting functions
        def forecast_double_smoothing(series, forecast_steps=3):
            try:
                model = Holt(series, initialization_method="estimated").fit()
                raw_forecast = model.forecast(steps=forecast_steps)
                
                # timeline fix
                last_date = series.index[-1]
                forecast_start_date = last_date + pd.DateOffset(months=1)
                future_dates = pd.date_range(start=forecast_start_date, periods=forecast_steps, freq='MS')
                
                return pd.Series(raw_forecast.values, index=future_dates)
            except Exception:
                mean_val = series.mean() if len(series) > 0 else 0.0
                idx = pd.date_range(series.index[-1] + pd.offsets.MonthEnd(1), periods=forecast_steps, freq='ME')
                return pd.Series([mean_val]*forecast_steps, index=idx)

        def forecast_triple_smoothing(series, seasonal_periods=3, forecast_steps=3):
            try:
                if len(series) < 2 * seasonal_periods:
                    return forecast_double_smoothing(series, forecast_steps=forecast_steps)
                model = ExponentialSmoothing(series, trend="add", seasonal="add", 
                                             seasonal_periods=seasonal_periods, 
                                             initialization_method="estimated").fit()
                raw_forecast = model.forecast(steps=forecast_steps)
                
                # timeline fix
                last_date = series.index[-1]
                forecast_start_date = last_date + pd.DateOffset(months=1)
                future_dates = pd.date_range(start=forecast_start_date, periods=forecast_steps, freq='MS')
                
                return pd.Series(raw_forecast.values, index=future_dates)
            except Exception:
                return forecast_double_smoothing(series, forecast_steps=forecast_steps)

        def forecast_tsb(series, alpha=0.2, beta=0.2, forecast_steps=3):
            try:
                y = np.asarray(series, dtype=float)
                n = len(y)
                if n == 0:
                    return pd.Series(np.zeros(forecast_steps))
                z, p = np.zeros(n), np.zeros(n)
                forecast = np.zeros(n + forecast_steps)
                
                non_zero = y[y > 0]
                z[0] = non_zero[0] if len(non_zero) > 0 else 0.0
                p[0] = len(non_zero) / n if n > 0 else 0.0
                
                for t in range(1, n):
                    if y[t] > 0:
                        z[t] = alpha * y[t] + (1 - alpha) * z[t-1]
                        p[t] = beta * 1.0 + (1 - beta) * p[t-1]
                    else:
                        z[t] = z[t-1]
                        p[t] = (1 - beta) * p[t-1]
                for h in range(0, forecast_steps):
                    forecast[n + h] = z[-1] * p[-1]
                
                # timeline fix
                forecast_start_date = series.index[-1] + pd.DateOffset(months=1)
                future_dates = pd.date_range(start=forecast_start_date, periods=forecast_steps, freq='MS')
                return pd.Series(forecast[n:], index=future_dates)
            except Exception:
                mean_val = series.mean() if len(series) > 0 else 0.0
                idx = pd.date_range(series.index[-1] + pd.offsets.MonthEnd(1), periods=forecast_steps, freq='ME')
                return pd.Series([mean_val]*forecast_steps, index=idx)

        query_materials = """
            SELECT DISTINCT
                m.material_code,
                m.material_description,
                m.machine_population,
                m.last_production_year,
                m.lead_time,
                m.delta,
                m.req_on_12m_avg,
                m.serv_per_left,
                m.price,
                m.moq,
                m.gpc_stk,
                m.lead_time_qty,
                mmd.year,
                mmd.month,
                mmd.consumption
            FROM public.materials m
            JOIN public.material_monthly_data mmd
                ON m.material_code = mmd.material_code
            ORDER BY
                m.material_code,
                mmd.year,
                mmd.month;
        """

        with engine.connect() as conn:
            df_materials = pd.read_sql(text(query_materials), conn)

        if df_materials.empty:
            raise Exception("No material monthly data found in the database. Please import data first.")

        prediction_tasks[task_id] = {"status": "processing", "progress": 30, "message": "Pre-processing data..."}

        sorted_parts = df_materials[['material_code', 'month', 'year', 'consumption', 'lead_time', 'delta', 'req_on_12m_avg', 'gpc_stk', 'lead_time_qty']].sort_values(by='req_on_12m_avg', ascending=False)
        sorted_parts['period'] = pd.to_datetime(sorted_parts[['year', 'month']].assign(day=1))
        
        dates = sorted_parts['period']
        sample_consumption = sorted_parts[['material_code', 'consumption', 'lead_time', 'delta', 'gpc_stk', 'lead_time_qty']]

        df_part = pd.DataFrame({
            'Material_Code': sample_consumption['material_code'],
            'Consumption': sample_consumption['consumption'],
            'lead_time': sample_consumption['lead_time'],
            'delta': sample_consumption['delta'],
            'gpc_stk': sample_consumption['gpc_stk'],
            'lead_time_qty': sample_consumption['lead_time_qty'],
        })
        df_part.index = dates
        df_part = df_part.sort_index()
        df_part.index.name = 'Month-Year'

        distinct_material_code = df_part['Material_Code'].drop_duplicates()
        total_materials = len(distinct_material_code)
        
        prediction_tasks[task_id] = {"status": "processing", "progress": 40, "message": f"Running forecasts for {total_materials} materials..."}

        prediction_records = []
        
        for i, mat_code in enumerate(distinct_material_code):
            # Update progress periodically
            if i % 10 == 0:
                progress_pct = 40 + int((i / total_materials) * 50)
                prediction_tasks[task_id] = {
                    "status": "processing",
                    "progress": progress_pct,
                    "message": f"Forecasting {i}/{total_materials} ({mat_code})..."
                }

            try:
                res = df_part.query("Material_Code == @mat_code").copy()
                res['year'] = res.index.year
                res['month'] = res.index.month
                
                # Construct period column
                res['period'] = pd.to_datetime(res[['year', 'month']].assign(day=1)) 

                dates_res = res['period']
                cons_res = res['Consumption']

                df_ts = pd.DataFrame({
                    'Consumption': cons_res
                })
                df_ts.index = dates_res
                df_ts = df_ts.sort_index()
                df_ts.index.name = 'Month-Year'

                time_series_data = df_ts['Consumption']
                
                # Need at least some historical data to split and train
                if len(time_series_data) < 4:
                    future_forecast = forecast_tsb(time_series_data, alpha=0.2, beta=0.2, forecast_steps=3)
                    winning_model_name = 'TSB_Method'
                else:
                    train_series = time_series_data.iloc[:-3]
                    actual_test  = time_series_data.iloc[-3:]
                    HORIZON = len(actual_test)

                    # Generate predictions on holdout slice
                    fc_double = forecast_double_smoothing(train_series, forecast_steps=HORIZON)
                    fc_triple = forecast_triple_smoothing(train_series, seasonal_periods=3, forecast_steps=HORIZON)
                    fc_tsb    = forecast_tsb(train_series, alpha=0.2, beta=0.2, forecast_steps=HORIZON)

                    # Calculate RMSE
                    try:
                        err_double = root_mean_squared_error(actual_test, fc_double)
                    except Exception:
                        err_double = 999999.0
                    try:
                        err_triple = root_mean_squared_error(actual_test, fc_triple)
                    except Exception:
                        err_triple = 999999.0
                    try:
                        err_tsb = root_mean_squared_error(actual_test, fc_tsb)
                    except Exception:
                        err_tsb = 999999.0

                    errors = {
                        'Double_Smooth': err_double,
                        'Triple_Smooth': err_triple,
                        'TSB_Method': err_tsb
                    }
                    winning_model_name = min(errors, key=errors.get)

                    # Generate actual future forecast
                    if winning_model_name == 'Double_Smooth':
                        future_forecast = forecast_double_smoothing(time_series_data, forecast_steps=3)
                    elif winning_model_name == 'Triple_Smooth':
                        future_forecast = forecast_triple_smoothing(time_series_data, seasonal_periods=3, forecast_steps=3)
                    else:
                        future_forecast = forecast_tsb(time_series_data, alpha=0.2, beta=0.2, forecast_steps=3)

                # Monte Carlo and Safety Stock logic
                avg_future_monthly_demand = future_forecast.mean()

                if winning_model_name == 'Double_Smooth':
                    try:
                        residuals = time_series_data - Holt(time_series_data).fit().fittedvalues
                    except Exception:
                        residuals = time_series_data - time_series_data.mean()
                else:
                    residuals = time_series_data - time_series_data.mean()

                std_monthly_demand = float(residuals.std()) if len(residuals) > 1 else 0.0
                std_daily_demand = std_monthly_demand / np.sqrt(30.0)
                mean_daily_demand = float(time_series_data.mean()) / 30.0

                min_lt = float(res['lead_time'].min())
                max_lt = float((res['lead_time'] + res['delta']).max())

                if pd.isna(max_lt):
                    max_lt = min_lt + 5

                most_likely_lt = (min_lt + max_lt) / 2.0

                shape_alpha = 1.0 + 4.0 * ((most_likely_lt - min_lt) / (max_lt - min_lt))
                shape_beta = 1.0 + 4.0 * ((max_lt - most_likely_lt) / (max_lt - min_lt))

                # Vectorized Monte Carlo Simulation
                simulations = 10000
                simulated_lts = stats.beta.rvs(shape_alpha, shape_beta, loc=min_lt, scale=max_lt - min_lt, size=simulations)
                scale_params = np.maximum(0.1, std_daily_demand * np.sqrt(simulated_lts))
                total_demands = np.random.normal(loc=mean_daily_demand * simulated_lts, scale=scale_params)
                total_demands = np.maximum(0.0, total_demands)

                df_ltd = pd.Series(total_demands)
                average_ltd = df_ltd.mean()
                reorder_point_95 = df_ltd.quantile(0.95)
                safety_stock_95 = reorder_point_95 - average_ltd

                # Risk-Adjusted forecast
                adjusted_monthly_forecast = future_forecast.copy()
                safety_stock_per_month = safety_stock_95 / len(future_forecast) if len(future_forecast) > 0 else 0.0
                adjusted_monthly_forecast = adjusted_monthly_forecast + safety_stock_per_month

                # Reformat future forecast to save in DB
                ff_dates = list(adjusted_monthly_forecast.index)
                ff_vals = list(adjusted_monthly_forecast.values)

                m1_date = ff_dates[0].to_pydatetime().date() if len(ff_dates) > 0 else None
                m1_pred = float(ff_vals[0]) if len(ff_vals) > 0 else 0.0

                m2_date = ff_dates[1].to_pydatetime().date() if len(ff_dates) > 1 else None
                m2_pred = float(ff_vals[1]) if len(ff_vals) > 1 else 0.0

                m3_date = ff_dates[2].to_pydatetime().date() if len(ff_dates) > 2 else None
                m3_pred = float(ff_vals[2]) if len(ff_vals) > 2 else 0.0

                gpc_stk = float(res['gpc_stk'].iloc[0]) if len(res) > 0 and not pd.isna(res['gpc_stk'].iloc[0]) else 0.0
                lead_time_qty = float(res['lead_time_qty'].iloc[0]) if len(res) > 0 and not pd.isna(res['lead_time_qty'].iloc[0]) else 0.0

                m1_po = max(0.0, lead_time_qty - gpc_stk + m1_pred)
                m1_mes = max(0.0, gpc_stk - m1_pred + m1_po)

                # m2_po = max(0.0, m1_po + m2_pred)
                m2_po = max(0.0, m2_pred - (safety_stock_95 / 2))
                m2_mes = max(0.0, m1_mes + m2_po - m2_pred)

                # m3_po = max(0.0, m2_po + m3_pred)
                m3_po = max(0.0, m3_pred - (safety_stock_95 * 0.63))
                m3_mes = max(0.0, m2_mes + m3_po - m3_pred)

                # Calculate days equivalent using mean daily demand
                daily_demand = float(time_series_data.mean()) / 30.0 if len(time_series_data) > 0 else 0.0
                if daily_demand > 0.0:
                    m1_pred_days = m1_pred / daily_demand
                    m1_po_days = m1_po / daily_demand
                    m1_mes_days = m1_mes / daily_demand

                    m2_pred_days = m2_pred / daily_demand
                    m2_po_days = m2_po / daily_demand
                    m2_mes_days = m2_mes / daily_demand

                    m3_pred_days = m3_pred / daily_demand
                    m3_po_days = m3_po / daily_demand
                    m3_mes_days = m3_mes / daily_demand
                else:
                    m1_pred_days = 0.0
                    m1_po_days = 0.0
                    m1_mes_days = 0.0

                    m2_pred_days = 0.0
                    m2_po_days = 0.0
                    m2_mes_days = 0.0

                    m3_pred_days = 0.0
                    m3_po_days = 0.0
                    m3_mes_days = 0.0

                prediction_records.append({
                    'material_code': mat_code,
                    'month1_date': m1_date,
                    'month1_prediction': m1_pred,
                    'month1_prediction_days': m1_pred_days,
                    'month1_po': m1_po,
                    'month1_po_days': m1_po_days,
                    'month1_mes': m1_mes,
                    'month1_mes_days': m1_mes_days,
                    'month2_date': m2_date,
                    'month2_prediction': m2_pred,
                    'month2_prediction_days': m2_pred_days,
                    'month2_po': m2_po,
                    'month2_po_days': m2_po_days,
                    'month2_mes': m2_mes,
                    'month2_mes_days': m2_mes_days,
                    'month3_date': m3_date,
                    'month3_prediction': m3_pred,
                    'month3_prediction_days': m3_pred_days,
                    'month3_po': m3_po,
                    'month3_po_days': m3_po_days,
                    'month3_mes': m3_mes,
                    'month3_mes_days': m3_mes_days
                })
            except Exception as item_err:
                print(f"Error predicting for material {mat_code}: {item_err}")
                prediction_records.append({
                    'material_code': mat_code,
                    'month1_date': None,
                    'month1_prediction': 0.0,
                    'month1_prediction_days': 0.0,
                    'month1_po': 0.0,
                    'month1_po_days': 0.0,
                    'month1_mes': 0.0,
                    'month1_mes_days': 0.0,
                    'month2_date': None,
                    'month2_prediction': 0.0,
                    'month2_prediction_days': 0.0,
                    'month2_po': 0.0,
                    'month2_po_days': 0.0,
                    'month2_mes': 0.0,
                    'month2_mes_days': 0.0,
                    'month3_date': None,
                    'month3_prediction': 0.0,
                    'month3_prediction_days': 0.0,
                    'month3_po': 0.0,
                    'month3_po_days': 0.0,
                    'month3_mes': 0.0,
                    'month3_mes_days': 0.0
                })

        prediction_tasks[task_id] = {"status": "processing", "progress": 90, "message": "Saving predictions to database..."}

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM consumption_prediction"))
            if prediction_records:
                pred_df = pd.DataFrame(prediction_records)
                pred_df.to_sql(
                    'consumption_prediction',
                    con=conn,
                    if_exists='append',
                    index=False,
                    method=psql_insert_copy
                )

        prediction_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Predictions generated and saved successfully",
            "predictions_count": len(prediction_records)
        }

    except Exception as e:
        traceback.print_exc()
        prediction_tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": "Prediction failed",
            "error": str(e)
        }

@router.post("/predict")
async def start_prediction(background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    prediction_tasks[task_id] = {"status": "processing", "progress": 0, "message": "Initializing prediction task..."}
    background_tasks.add_task(process_prediction_task, task_id)
    return {
        "message": "Prediction task started",
        "task_id": task_id
    }

@router.get("/predict/status/{task_id}")
async def get_prediction_status(task_id: str):
    if task_id not in prediction_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return prediction_tasks[task_id]