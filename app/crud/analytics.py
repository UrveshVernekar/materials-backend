from sqlalchemy.orm import Session
from sqlalchemy import text

def get_monthly_consumption_trend(db: Session, material_code: str = None):
    params = {}
    
    base_query = """
        SELECT 
            year, 
            month, 
            TO_CHAR(MAKE_DATE(year::integer, month::integer, 1), 'Mon YY') as formatted_date,
            SUM(consumption) as total_consumption
        FROM material_monthly_data
        WHERE 1=1
    """
    
    if material_code:
        base_query += " AND material_code = :material_code"
        params['material_code'] = material_code
        
    base_query += """
        GROUP BY year, month
        ORDER BY year ASC, month ASC
    """
    
    result = db.execute(text(base_query), params).fetchall()
    
    items = []
    for row in result:
        items.append({
            "year": row.year,
            "month": row.month,
            "formatted_date": row.formatted_date,
            "total_consumption": float(row.total_consumption or 0)
        })
        
    return items
