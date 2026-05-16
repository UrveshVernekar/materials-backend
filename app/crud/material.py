# app/crud/material.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.material import MaterialFilter

def get_dashboard_kpis(db: Session):
    query = text("""
        WITH categorized_materials AS (
            SELECT 
                cov_in_days,
                CASE 
                    WHEN inh_s_obslte = 'OBSOLETE' THEN 'Obsolete'
                    WHEN last_production_year >= 2025 THEN 'New'
                    ELSE 'Running' 
                END as status
            FROM materials
        )
        SELECT 
            COUNT(*) as total_materials,
            COUNT(CASE WHEN status = 'Running' THEN 1 END) as active_materials,
            COUNT(CASE WHEN status = 'Obsolete' THEN 1 END) as obsolete_count,
            COALESCE(AVG(cov_in_days), 0) as avg_coverage_days,
            COUNT(CASE WHEN cov_in_days < 30 THEN 1 END) as critical_stock,
            COUNT(CASE WHEN cov_in_days BETWEEN 30 AND 60 THEN 1 END) as low_stock
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
        WITH material_data AS (
            SELECT 
                m.material_code,
                m.material_description,
                m.vendor,
                COALESCE(m.gpc_free_stk_22_04 + m.branch_stk_22_04, 0) as current_stock,
                m.cov_in_days as coverage_days,
                s.three_m_av as three_m_avg,
                s.twelve_m_mean as twelve_m_avg,
                m.price,
                CASE 
                    WHEN m.inh_s_obslte = 'OBSOLETE' THEN 'Obsolete'
                    WHEN m.last_production_year >= 2025 THEN 'New'
                    ELSE 'Running' 
                END as status
            FROM materials m
            LEFT JOIN material_summary s ON m.material_code = s.material_code
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