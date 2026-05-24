# app/crud/material.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.material import MaterialFilter

def get_dashboard_kpis(db: Session):
    query = text("""
        WITH latest_months AS (
            SELECT 
                material_code, 
                consumption,
                ROW_NUMBER() OVER(PARTITION BY material_code ORDER BY year DESC, month DESC) as rn
            FROM material_monthly_data
            WHERE consumption IS NOT NULL
        ),
        calc_summary AS (
            SELECT 
                material_code,
                ROUND(AVG(CASE WHEN rn <= 12 THEN consumption END)::numeric, 2) as twelve_m_avg
            FROM latest_months
            GROUP BY material_code
        ),
        categorized_materials AS (
            SELECT 
                m.material_code,
                m.gpc_stk,
                s.twelve_m_avg,
                CASE 
                    WHEN m.product_status ILIKE '%obsolete%' OR m.product_status = 'NOT RUN' THEN 'Obsolete'
                    WHEN m.product_status = 'New Part' THEN 'New'
                    ELSE 'Running' 
                END as status,
                CASE
                    WHEN s.twelve_m_avg IS NOT NULL AND s.twelve_m_avg > 0 
                        THEN (m.gpc_stk / s.twelve_m_avg) * 30
                    WHEN m.gpc_stk > 0 THEN 999999
                    ELSE 0
                END as calculated_coverage
            FROM materials m
            LEFT JOIN calc_summary s ON m.material_code = s.material_code
        )
        SELECT 
            COUNT(*) as total_materials,
            COUNT(CASE WHEN status = 'Running' THEN 1 END) as active_materials,
            COUNT(CASE WHEN status = 'Obsolete' THEN 1 END) as obsolete_count,
            COALESCE(AVG(CASE WHEN status != 'Obsolete' AND calculated_coverage < 999999 THEN calculated_coverage END), 0) as avg_coverage_days,
            COUNT(CASE WHEN calculated_coverage < 30 THEN 1 END) as critical_stock,
            COUNT(CASE WHEN calculated_coverage >= 30 AND calculated_coverage <= 60 THEN 1 END) as low_stock
        FROM categorized_materials
    """)
    result = db.execute(query).fetchone()
    
    return {
        "total_materials": result.total_materials or 0,
        "active_materials": result.active_materials or 0,
        "obsolete_count": result.obsolete_count or 0,
        "avg_coverage_days": float(result.avg_coverage_days or 0),
        "critical_stock": result.critical_stock or 0,
        "low_stock": result.low_stock or 0,
    }



def get_filtered_materials(db: Session, filters: MaterialFilter):
    base_query = """
        WITH latest_months AS (
            SELECT 
                material_code, 
                consumption,
                ROW_NUMBER() OVER(PARTITION BY material_code ORDER BY year DESC, month DESC) as rn
            FROM material_monthly_data
            WHERE consumption IS NOT NULL
        ),
        calc_summary AS (
            SELECT 
                material_code,
                ROUND(AVG(CASE WHEN rn <= 3 THEN consumption END)::numeric, 2) as three_m_avg,
                ROUND(AVG(CASE WHEN rn <= 12 THEN consumption END)::numeric, 2) as twelve_m_avg
            FROM latest_months
            GROUP BY material_code
        ),
        material_data AS (
            SELECT 
                m.material_code,
                m.material_description,
                m.vendor,
                COALESCE(m.machine_population, 0) as machine_population,
                -- COALESCE(m.gpc_free_stk + m.branch_stk, 0) as current_stock,
                m.gpc_stk as current_stock,
                COALESCE(m.lead_time, 0) as lead_time,
                COALESCE(m.lead_time_qty, 0) as lead_time_qty,
                COALESCE(m.delta, 0) as delta,
                (COALESCE(m.lead_time, 0) + COALESCE(m.delta, 0)) as total_lead_time,
                m.cov_in_days as coverage_days,
                s.three_m_avg,
                s.twelve_m_avg,
                m.price,
                -- CASE 
                --    WHEN m.inh_s_obslte = 'OBSOLETE' THEN 'Obsolete'
                --    WHEN m.last_production_year >= 2025 THEN 'New'
                --    ELSE 'Running' 
                -- END as status,
                m.product_status AS status,
                m.product_category,
                p.month1_prediction,
                p.month1_prediction_days,
                p.month1_po,
                p.month1_po_days,
                p.month1_mes,
                p.month1_mes_days,
                p.month2_prediction,
                p.month2_prediction_days,
                p.month2_po,
                p.month2_po_days,
                p.month2_mes,
                p.month2_mes_days,
                p.month3_prediction,
                p.month3_prediction_days,
                p.month3_po,
                p.month3_po_days,
                p.month3_mes,
                p.month3_mes_days,
                p.month1_date,
                p.month2_date,
                p.month3_date
            FROM materials m
            LEFT JOIN calc_summary s ON m.material_code = s.material_code
            LEFT JOIN consumption_prediction p ON m.material_code = p.material_code
        )
        SELECT * FROM material_data
        WHERE 1=1
    """
    
    params = {}
    
    if filters.search:
        base_query += """
            AND (material_code ILIKE :search OR material_description ILIKE :search OR vendor ILIKE :search)
        """
        params['search'] = f"%{filters.search}%"
    
    if filters.vendor:
        base_query += " AND vendor = :vendor"
        params['vendor'] = filters.vendor
    
    if filters.status:
        base_query += " AND status = :status"
        params['status'] = filters.status
    
    if filters.min_coverage is not None:
        base_query += " AND coverage_days >= :min_coverage"
        params['min_coverage'] = filters.min_coverage
    
    if filters.max_coverage is not None:
        base_query += " AND coverage_days <= :max_coverage"
        params['max_coverage'] = filters.max_coverage

    # Count total
    count_query = text(f"SELECT COUNT(*) FROM ({base_query}) as sub")
    total = db.execute(count_query, params).scalar()

    # Return all data
    base_query += " ORDER BY coverage_days ASC, material_code"
    
    result = db.execute(text(base_query), params).fetchall()

    items = [dict(row._mapping) for row in result]

    return {"items": items, "total": total or 0}