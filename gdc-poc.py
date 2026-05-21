import plotly.express as px
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import scipy.stats as stats
import os
from sqlalchemy import create_engine, text
from statsmodels.tsa.holtwinters import Holt, ExponentialSmoothing
from sklearn.metrics import mean_absolute_error, mean_squared_error, root_mean_squared_error

DATABASE_URL = "postgresql+psycopg2://materialsuser:materials1234%23%24@localhost:5432/materials_db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

def forecast_double_smoothing(series, forecast_steps=3):
    model = Holt(series, initialization_method="estimated").fit()
   
    # 2. Generate the raw numeric forecasts (returns a numpy array or pandas series)
    raw_forecast = model.forecast(steps=forecast_steps)
    
    # --- THE TIMELINE FIX START ---
    # Grab the last historical date (e.g., 2026-03-01)
    last_date = time_series_data.index[-1]
    
    # Dynamically shift the start point forward by exactly 1 month (to 2026-04-01)
    forecast_start_date = last_date + pd.DateOffset(months=1)
    
    # Generate the clean future Month-Start ('MS') index
    future_dates = pd.date_range(
        start=forecast_start_date, 
        periods=forecast_steps, 
        freq='MS'
    )
    # --- THE TIMELINE FIX END ---
    
    # 3. Package the raw numbers with the correct future dates
    future_forecast = pd.Series(raw_forecast.values, index=future_dates)
    
    return future_forecast

def forecast_triple_smoothing(series, seasonal_periods=3, forecast_steps=3):
    model = ExponentialSmoothing(series, trend="add", seasonal="add", 
                                 seasonal_periods=seasonal_periods, 
                                 initialization_method="estimated").fit()

    raw_forecast = model.forecast(steps=forecast_steps)
    
    # --- THE TIMELINE FIX START ---
    # Grab the last historical date (e.g., 2026-03-01)
    last_date = time_series_data.index[-1]
    
    # Dynamically shift the start point forward by exactly 1 month (to 2026-04-01)
    forecast_start_date = last_date + pd.DateOffset(months=1)
    
    # Generate the clean future Month-Start ('MS') index
    future_dates = pd.date_range(
        start=forecast_start_date, 
        periods=forecast_steps, 
        freq='MS'
    )
    # --- THE TIMELINE FIX END ---
    
    # 3. Package the raw numbers with the correct future dates
    future_forecast = pd.Series(raw_forecast.values, index=future_dates)
    
    return future_forecast

def forecast_tsb(series, alpha=0.2, beta=0.2, forecast_steps=3):
    # 1. Convert input to a clean, flat NumPy array
    y = np.asarray(series, dtype=float)
    n = len(y)
    
    # Handle an empty series gracefully
    if n == 0:
        return pd.Series(np.zeros(forecast_steps))
        
    # Initialize arrays to track demand size (z) and demand probability (p)
    z = np.zeros(n)
    p = np.zeros(n)
    
    # Initialize the first period based on historical non-zero items
    non_zero = y[y > 0]
    z[0] = non_zero[0] if len(non_zero) > 0 else 0.0
    p[0] = len(non_zero) / n if n > 0 else 0.0
    
    # 2. RUN THE HISTORICAL TSB SMOOTHING LOOP
    for t in range(1, n):
        if y[t] > 0:
            # If demand occurs, update both size and probability
            z[t] = alpha * y[t] + (1 - alpha) * z[t-1]
            p[t] = beta * 1.0 + (1 - beta) * p[t-1]
        else:
            # If no demand occurs, size carries forward, probability decays
            z[t] = z[t-1]
            p[t] = (1 - beta) * p[t-1]
            
    # 3. GENERATE OUT-OF-SAMPLE FUTURE VALUES
    # TSB projects a flat future line: last size multiplied by last probability
    future_value = z[-1] * p[-1]
    raw_forecast = np.full(shape=forecast_steps, fill_value=future_value)
    
    # --- THE TIMELINE FIX ---
    # Shift the last historical date (e.g., 2026-03-01) forward by exactly 1 month
    forecast_start_date = series.index[-1] + pd.DateOffset(months=1)
    
    # Create the clean future Month-Start ('MS') index grid
    future_dates = pd.date_range(
        start=forecast_start_date, 
        periods=forecast_steps, 
        freq='MS'
    )
    
    # 4. Package numbers neatly with their corresponding future dates
    return pd.Series(raw_forecast, index=future_dates)

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
        m.lead_time,
        m.delta,
        m.req_on_12m_avg,
        m.serv_per_left,
        m.price,
        m.moq,
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

# Execute query
df_materials = execute_query(query_materials)

print(f"[OK] Loaded data: {df_materials.shape}")

# print(df_materials.head())

sorted_parts = df_materials[['material_code', 'month', 'year','consumption', 'lead_time', 'delta', 'req_on_12m_avg']].sort_values(by='req_on_12m_avg', 
    ascending=False)
# print(sorted_parts)

# sorted_parts[['year', 'month']]

sorted_parts['period'] = pd.to_datetime(sorted_parts[['year', 'month']].assign(day=1))
# print(sorted_parts)

# start = sorted_parts['period'].min().strftime('%m-%Y')
# end = sorted_parts['period'].max().strftime('%m-%Y')

start = sorted_parts['period'].min()
# 1. Simulating a sample intermittent/lumpy spare part history matching your layout
dates = sorted_parts['period']
sample_consumption = sorted_parts[['material_code', 'consumption', 'lead_time', 'delta']]

df_part = pd.DataFrame({
    'Material_Code': sample_consumption['material_code'],
    'Consumption': sample_consumption['consumption'],
    'lead_time': sample_consumption['lead_time'],
    'delta': sample_consumption['delta'],
})

# 3. Assign the dates as the formal row index and sort it chronologically
df_part.index = dates
df_part = df_part.sort_index()

# 4. Give the index a clean name
df_part.index.name = 'Month-Year'

# 5. Print it directly (Do not wrap it in brackets!)
print("--- YOUR CLEAN TIME SERIES DATA ---")
# print(df_part)
# exit()

# distinct_material_code = df_part[['Material Code', 'lead_time', 'delta']].drop_duplicates()
# print(len(distinct_material_code))
# file_path1 = r'/mnt/d/work/ifb/kamal/gdc/data/gdc_material_monthly_data.csv'


# Read in the data
# df_consumption = pd.read_csv(file_path1, header=0)
# file_path2 = r'/mnt/d/work/ifb/kamal/gdc/data/gdc_materials.csv'

# Adding explicit encoding and engine fixes standard local windows glitches
# df_Mat = pd.read_csv(file_path2, header=0, encoding='latin1')

# sorted_parts = df_Mat[['material_code', 'lead_time', 'delta', 'req_on_12m_avg']].sort_values(by='req_on_12m_avg', 
    # ascending=False)

# merged_df = pd.merge( 
#     df_consumption,         # The right dataframe (consumption data)
#     sorted_parts,           # The left dataframe
#     left_on='material_code',# The matching key in sorted_parts
#     right_on='material_code',    # The matching key in your consumption excel
#     how='left'              # Keep all records from sorted_parts, match what exists in consumption
# )

distinct_material_code = df_part['Material_Code'].drop_duplicates()
print(len(distinct_material_code))
# distinct_material_code = merged_df['material_code'].drop_duplicates()
# filtered_df = merged_df.query('material_code == "UF321ECECB450"')
# distinct_material_code = filtered_df['material_code'].drop_duplicates()

# print(filtered_df)

report = []
for mat_code in distinct_material_code:
    # Use pandas query with backticks for column name with space
    # print("mat_code", mat_code)
    # print("df_part", df_part[df_part['Material_Code'] == mat_code])
    res = df_part.query("Material_Code == @mat_code").copy()
    # Extract year and month from the datetime index
    res['year'] = res.index.year
    res['month'] = res.index.month
    # print(res)
    # exit()
    # Construct period column
    res['period'] = pd.to_datetime(res[['year', 'month']].assign(day=1)) 

    # ==========================================
    # EXAMPLE EXECUTION WORKFLOW
    # ==========================================

    start = res['period'].min()
    # 1. Simulating a sample intermittent/lumpy spare part history matching your layout
    dates = res['period']
    sample_consumption = res['Consumption']

    df_ts = pd.DataFrame({
        'Consumption': sample_consumption
    })

    # 3. Assign the dates as the formal row index and sort it chronologically
    df_ts.index = dates
    df_ts = df_ts.sort_index()

    # 4. Give the index a clean name
    df_ts.index.name = 'Month-Year'
    # print(df_ts)
    # exit()

    # 5. Print it directly (Do not wrap it in brackets!)
    # print("--- YOUR CLEAN TIME SERIES DATA ---")
    # print(df_part)


    time_series_data = df_ts['Consumption']
    # Dynamic Train/Test Split (Last 3 months held out)
    train_series = time_series_data.iloc[:-3]
    actual_test  = time_series_data.iloc[-3:]
    HORIZON = len(actual_test)

    # Generate predictions on the holdout slice
    fc_double = forecast_double_smoothing(train_series, forecast_steps=HORIZON)
    fc_triple = forecast_triple_smoothing(train_series, seasonal_periods=3, forecast_steps=HORIZON)
    fc_tsb    = forecast_tsb(train_series, alpha=0.2, beta=0.2, forecast_steps=HORIZON)

    # Calculate RMSE to find the winner
    errors = {
        'Double_Smooth': root_mean_squared_error(actual_test, fc_double),
        'Triple_Smooth': root_mean_squared_error(actual_test, fc_triple),
        'TSB_Method':    root_mean_squared_error(actual_test, fc_tsb)
    }
    winning_model_name = min(errors, key=errors.get)
    # print(f"🏆 Validation Winner: {winning_model_name} (Lowest RMSE)")
    # print(time_series_data)
    # print(actual_test)
    # print(fc_double)
    # print(fc_triple)
    # print(fc_tsb) 


    # --- STEP 3: GENERATE THE TRUE FUTURE FORECAST ---


    # Re-train the winning model on ALL 24 months of data to project into the real future
    if winning_model_name == 'Double_Smooth':
        future_forecast = forecast_double_smoothing(time_series_data, forecast_steps=3)
    elif winning_model_name == 'Triple_Smooth':
        future_forecast = forecast_triple_smoothing(time_series_data, seasonal_periods=3, forecast_steps=3)
    else:
        future_forecast = forecast_tsb(time_series_data, alpha=0.2, beta=0.2, forecast_steps=3)
        
    # print(f"Historical data actually ends on: {time_series_data.index[-1]}")
    # print(f"Total rows in historical series: {len(time_series_data)}")

    # Calculate the Average Monthly Demand from our future forecast
    avg_future_monthly_demand = future_forecast.mean()
    # print(f"Projected Future Demand: {avg_future_monthly_demand:.2f} units/month")


    # --- STEP 4: THE MONTE CARLO MARRIAGE ENGINE ---

    # Convert monthly demand to daily demand (assuming 30-day month)
    mean_daily_demand = avg_future_monthly_demand / 30

    # --- STEP 1: CALCULATE THE STANDARD DEVIATION AS A PURE NUMBER ---
    if winning_model_name == 'Double_Smooth':
        # .fittedvalues returns an array, so residuals becomes an array
        residuals = time_series_data - Holt(time_series_data).fit().fittedvalues
    else:
        residuals = time_series_data - time_series_data.mean()

    # Force standard deviation to be a pure scalar float
    std_monthly_demand = float(residuals.std())
    std_daily_demand = std_monthly_demand / np.sqrt(30)

    # Force mean daily demand to be a pure scalar float
    # (Assuming time_series_data is monthly demand, divide monthly mean by 30)
    mean_daily_demand = float(time_series_data.mean()) / 30.0


    # --- STEP 2: PREPARE PERT DISTRIBUTION ---
    min_lt = float(res['lead_time'].min())
    max_lt = float((res['lead_time'] + res['delta']).max())

    # print(f"Shape ......{min_lt, max_lt}")
    most_likely_lt = (min_lt + max_lt) / 2 

    shape_alpha = 1 + 4 * ((most_likely_lt - min_lt) / (max_lt - min_lt))
    shape_beta = 1 + 4 * ((max_lt - most_likely_lt) / (max_lt - min_lt))


    # --- STEP 3: THE SIMULATION LOOP ---
    simulations = 10000
    ltd_distributions = []

    for _ in range(simulations):
        # 1. Pull a single random lead time value (e.g., 87.4 days)
        simulated_lt = float(stats.beta.rvs(shape_alpha, shape_beta, loc=min_lt, scale=max_lt - min_lt))
        
        # 2. Scale the demand parameters to match this specific lead time window
        # Mean demand over the whole lead time = daily mean * total days
        expected_ltd_mean = mean_daily_demand * simulated_lt
        
        # Standard deviation over the whole lead time = daily std * square root of total days
        expected_ltd_std = max(0.1, std_daily_demand * np.sqrt(simulated_lt))
        
        # 3. Draw a SINGLE total demand value for this entire cycle
        total_demand_this_cycle = np.random.normal(loc=expected_ltd_mean, scale=expected_ltd_std)
        
        # Append the single scalar number, ensuring it can't fall below zero
        ltd_distributions.append(max(0.0, float(total_demand_this_cycle)))


    # --- STEP 4: CREATE THE SERIES ---
    # This will now be a clean Series of pure floats!
    df_ltd = pd.Series(ltd_distributions)

    # print(f"New Shape: {df_ltd.shape}")        # Will be (10000,)
    # print(f"New Data Type: {df_ltd.dtype}")    # Will be float64
    # print(df_ltd.head())                       # Brackets are gone!

    # --- STEP 5: CALCULATE DECISIONS ---
    average_ltd = df_ltd.mean()
    reorder_point_95 = df_ltd.quantile(0.95)   # Works perfectly now!
    safety_stock_95 = reorder_point_95 - average_ltd



    # 1. Get your raw, unadjusted future months from your winning model
    # (e.g., Month 1 = 100, Month 2 = 110, Month 3 = 95)
    adjusted_monthly_forecast = future_forecast.copy()

    # 2. Calculate how much Safety Stock you need per month of lead time
    # If your total safety stock is 45 units for a 3-month horizon, that's 15 units/month
    safety_stock_per_month = safety_stock_95 / len(future_forecast)

    # 3. Add the risk buffer to each specific month
    adjusted_monthly_forecast = adjusted_monthly_forecast + safety_stock_per_month

    # print("--- RISK-ADJUSTED MONTHLY FORECAST ---")
    # print(adjusted_monthly_forecast)

    # print("\n" + "="*40 + "\n--- FINAL INVENTORY REPLENISHMENT PLAN ---")
    # print(f"Expected Demand During Lead Time: {average_ltd:.1f} units")
    # print(f"Safety Stock Buffer Required:     {safety_stock_95:.1f} units")
    # print(f"👉 REORDER POINT (ROP):           {reorder_point_95:.1f} units")
    # print(f"Action: Reorder when stock hits {int(np.ceil(reorder_point_95))} units to protect against supplier delays.")

    row_dict = {
        'Material Code': mat_code,
        'Average_Demand': average_ltd,
        'Reorder_Point': reorder_point_95,
        'Safety_Stock': safety_stock_95,
    }
    
    # print(adjusted_monthly_forecast)
    # print(future_forecast)
    # # Dynamically append forecast columns with Month-Year format
    for date, val in adjusted_monthly_forecast.items():
        if hasattr(date, 'strftime'):
            col_header = f"Forecast_{date.strftime('%b-%Y')}"
        else:
            col_header = f"Forecast_{date}"
        row_dict[col_header] = val
        
    # print(row_dict)
    report.append(row_dict)
    
final_df = pd.DataFrame(report)
output_filename = 'spare_parts_prediction_report.csv'
final_df.to_csv(output_filename, index=False)

