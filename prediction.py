import plotly.express as px
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import time
from statsmodels.tsa.holtwinters import Holt, ExponentialSmoothing
from sqlalchemy import create_engine, text
import scipy.stats as stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, root_mean_squared_error

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


# ==========================================
# 1. DOUBLE EXPONENTIAL SMOOTHING FUNCTION
# ==========================================

# ==========================================
# 3. TSB (TEUNTER-SYNTETOS-BABAI) FUNCTION
# ==========================================
def forecast_tsb(series, alpha=0.2, beta=0.2, forecast_steps=3):
    """
    Industry standard for intermittent, lumpy, or slow-moving spare parts.
    Updates demand probability every period to capture sudden obsolescence.
    """
    y = np.asarray(series, dtype=float)
    n = len(y)
    
    z = np.zeros(n)  # Demand size component
    p = np.zeros(n)  # Demand probability component
    forecast = np.zeros(n + forecast_steps)
    
    # Initialize using non-zero elements
    non_zero = y[y > 0]
    z[0] = non_zero[0] if len(non_zero) > 0 else 0
    p[0] = len(non_zero) / n if n > 0 else 0
    forecast[0] = z[0] * p[0]
    
    # Historical timeline iteration
    for t in range(1, n):
        # Forecast for period t is determined by parameters calculated up to t-1
        forecast[t] = z[t-1] * p[t-1]
        
        # Update components with current period observation
        if y[t] > 0:
            z[t] = alpha * y[t] + (1 - alpha) * z[t-1]
            p[t] = beta * 1 + (1 - beta) * p[t-1]
        else:
            z[t] = z[t-1]
            p[t] = (1 - beta) * p[t-1]
            
    # Out-of-sample forecast (parameters remain static at the final horizon boundary)
    for h in range(0, forecast_steps):
        forecast[n + h] = z[-1] * p[-1]
        
    # Split historical vs future forecast to match statsmodels formatting
    fitted_values = pd.Series(forecast[:n], index=series.index)
    future_forecast = pd.Series(forecast[n:], index=pd.date_range(
        start=series.index[-1] + pd.offsets.MonthEnd(1), 
        periods=forecast_steps, 
        freq='ME'
    ))
    
    return fitted_values, future_forecast


def forecast_double_smoothing(series, forecast_steps=3):
    model = Holt(series, initialization_method="estimated").fit()
    return model.forecast(steps=forecast_steps)

def forecast_triple_smoothing(series, seasonal_periods=3, forecast_steps=3):
    model = ExponentialSmoothing(series, trend="add", seasonal="add", 
                                 seasonal_periods=seasonal_periods, 
                                 initialization_method="estimated").fit()
    return model.forecast(steps=forecast_steps)

def forecast_tsb(series, alpha=0.2, beta=0.2, forecast_steps=3):
    y = np.asarray(series, dtype=float)
    n = len(y)
    z, p = np.zeros(n), np.zeros(n)
    forecast = np.zeros(n + forecast_steps)
    
    non_zero = y[y > 0]
    z[0] = non_zero[0] if len(non_zero) > 0 else 0
    p[0] = len(non_zero) / n if n > 0 else 0
    
    for t in range(1, n):
        if y[t] > 0:
            z[t] = alpha * y[t] + (1 - alpha) * z[t-1]
            p[t] = beta * 1 + (1 - beta) * p[t-1]
        else:
            z[t] = z[t-1]
            p[t] = (1 - beta) * p[t-1]
    for h in range(0, forecast_steps):
        forecast[n + h] = z[-1] * p[-1]
    return pd.Series(forecast[n:], index=pd.date_range(series.index[-1] + pd.offsets.MonthEnd(1), periods=forecast_steps, freq='ME'))


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
    'Material Code': sample_consumption['material_code'],
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


distinct_material_code = df_part[['Material Code', 'lead_time', 'delta']].drop_duplicates()
print(len(distinct_material_code))

report = []
for index, row in distinct_material_code.iterrows():
    filtered_df = df_part[df_part['Material Code'] == row['Material Code']]
    # print(filtered_df)
    time_series_data = filtered_df['Consumption']

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
    print(f"Validation Winner: {winning_model_name} (Lowest RMSE)")


    # --- STEP 3: GENERATE THE TRUE FUTURE FORECAST ---

    # Re-train the winning model on ALL 24 months of data to project into the real future
    if winning_model_name == 'Double_Smooth':
        future_forecast = forecast_double_smoothing(time_series_data, forecast_steps=3)
    elif winning_model_name == 'Triple_Smooth':
        future_forecast = forecast_triple_smoothing(time_series_data, seasonal_periods=3, forecast_steps=3)
    else:
        future_forecast = forecast_tsb(time_series_data, alpha=0.2, beta=0.2, forecast_steps=3)

    
    # Calculate the Average Monthly Demand from our future forecast
    avg_future_monthly_demand = future_forecast.mean()
    print(f"Projected Future Demand: {avg_future_monthly_demand:.2f} units/month")


    # --- STEP 4: THE MONTE CARLO MARRIAGE ENGINE ---

    # Convert monthly demand to daily demand (assuming 30-day month)
    mean_daily_demand = avg_future_monthly_demand / 30

    # Calculate the Standard Deviation of our model's residuals to act as our demand uncertainty
    # (This represents how much the model typically misses by)
    if winning_model_name == 'Double_Smooth':
        residuals = time_series_data - Holt(time_series_data).fit().fittedvalues
    else:
        residuals = time_series_data - time_series_data.mean() # Fallback variance proxy
    std_daily_demand = residuals.std() / np.sqrt(30)


    min_lt = row['lead_time']
    max_lt = row['lead_time'] + row['delta']

    # Assume the most likely delivery time is the average of the two, 
    # or use your domain knowledge (e.g., usually arrives in 85 days)
    most_likely_lt = (min_lt + max_lt) / 2  # 92.5 days

    # PERT distribution translates Min/Max/Mode into Beta distribution parameters (α, β)
    shape_alpha = 1 + 4 * ((most_likely_lt - min_lt) / (max_lt - min_lt))
    shape_beta = 1 + 4 * ((max_lt - most_likely_lt) / (max_lt - min_lt))

    # Define your Shifted Gamma Lead Time Parameters (Mean = 90 days, Max = 105 days)
    # shape_k = 5.44
    # scale_theta = 1.84
    # loc_shift = 80.0  # Absolute minimum physical lead time fallback

    # Run 10,000 simulated supplier replenishment cycles (vectorized for speed)
    simulations = 10000
    
    # 1. Pull 10,000 random delivery timelines from the Beta distribution
    simulated_lts = stats.beta.rvs(shape_alpha, shape_beta, loc=min_lt, scale=max_lt - min_lt, size=simulations)
    
    # 2. Simulate parts consumption during those specific delivery windows
    scale_params = np.maximum(0.1, std_daily_demand * np.sqrt(simulated_lts))
    total_demands = np.random.normal(
        loc = mean_daily_demand * simulated_lts, 
        scale = scale_params
    )
    # Ensure demands are non-negative
    total_demands = np.maximum(0, total_demands)
    
    df_ltd = pd.Series(total_demands)


    # --- STEP 5: EXTRACT THE INVENTORY DECISIONS ---

    average_ltd = df_ltd.mean()
    reorder_point_95 = df_ltd.quantile(0.95) # 95% availability target
    safety_stock_95 = reorder_point_95 - average_ltd

    print("\n" + "="*40 + "\n--- FINAL INVENTORY REPLENISHMENT PLAN ---")
    print(f"Expected Demand During Lead Time: {average_ltd:.1f} units")
    print(f"Safety Stock Buffer Required:     {safety_stock_95:.1f} units")
    print(f"-> REORDER POINT (ROP):           {reorder_point_95:.1f} units")
    print(f"Action: Reorder when stock hits {int(np.ceil(reorder_point_95))} units to protect against supplier delays.")
    print(f"Future Forecast:\n{future_forecast}")
    row_dict = {
        'Material Code': row['Material Code'],
        'Average_Demand': average_ltd,
        'Reorder_Point': reorder_point_95,
        'Safety_Stock': safety_stock_95,
    }
    # Dynamically append forecast columns with Month-Year format
    for date, val in future_forecast.items():
        if hasattr(date, 'strftime'):
            col_header = f"Forecast_{date.strftime('%b-%Y')}"
        else:
            col_header = f"Forecast_{date}"
        row_dict[col_header] = val
        
    print(row_dict)
    report.append(row_dict)
    # time.sleep(5)

final_df = pd.DataFrame(report)
output_filename = 'spare_parts_prediction_report.csv'
final_df.to_csv(output_filename, index=False)


# ts = df_materials[['material_code', 'year', 'month', 'consumption']].copy()
# ts['date'] = pd.to_datetime(
#     ts['year'].astype(str) + '-' + ts['month'].astype(str) + '-01'
# )
# ts = ts.set_index('date')
# monthly_ts = ts['consumption'].resample('ME').sum().fillna(0)

# print(monthly_ts.values)

# plt.figure(figsize=(10,5))
# plt.bar(monthly_ts.index, monthly_ts.values, label='Train', color='blue')
# plt.show()