import plotly.express as px
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ========================= DATABASE CONFIG =========================
DATABASE_URL = "postgresql+psycopg2://materialsuser:materials1234%23%24@localhost:5432/materials_db"

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
# =================================================================

def execute_query(query: str):
    """Execute query and return pandas DataFrame."""
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    return df


query_materials = """
    SELECT DISTINCT
        m.material_code,
        m.material_description,
        m.machine_population,
        m.last_production_year,
        m.serv_per_left,
        m.price,
        m.moq,
        mmd.year,
        mmd.month,
        mmd.consumption
    FROM public.materials m
    JOIN public.material_monthly_data mmd
        ON m.material_code = mmd.material_code
    WHERE m.material_code = 'TL221ECPBD030'
    ORDER BY
        m.material_code,
        mmd.year,
        mmd.month;
"""

# Execute query
df_materials = execute_query(query_materials)

print(f"[OK] Loaded data: {df_materials.shape}")

print(df_materials.head())

ts = df_materials[['year', 'month', 'consumption']].copy()
ts['date'] = pd.to_datetime(
    ts['year'].astype(str) + '-' + ts['month'].astype(str) + '-01'
)
ts = ts.set_index('date')
monthly_ts = ts['consumption'].resample('ME').sum().fillna(0)

print(monthly_ts.values)

plt.figure(figsize=(10,5))
plt.bar(monthly_ts.index, monthly_ts.values, label='Train', color='blue')
plt.show()