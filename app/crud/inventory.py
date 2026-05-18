from sqlalchemy.orm import Session
from sqlalchemy import text

def get_aging_inventory(db: Session, search: str = None):
    params = {}
    
    base_query = """
        FROM materials
        WHERE (aging_more_than_120_days > 0 OR inh_s_obslte = 'OBSOLETE')
    """
    
    if search:
        base_query += " AND (material_code ILIKE :search OR material_description ILIKE :search OR vendor ILIKE :search)"
        params['search'] = f"%{search}%"
        
    # Get KPIs
    kpi_query = f"""
        SELECT 
            COUNT(*) as total_aging_items,
            SUM(aging_more_than_120_days) as total_aging_qty,
            SUM(aging_more_than_120_days * price) as total_locked_capital,
            COUNT(CASE WHEN inh_s_obslte = 'OBSOLETE' THEN 1 END) as obsolete_items
        {base_query}
    """
    kpis = db.execute(text(kpi_query), params).fetchone()
    
    # Get List
    list_query = f"""
        SELECT 
            material_code,
            material_description,
            vendor,
            COALESCE(aging_more_than_120_days, 0) as aging_qty,
            COALESCE(price, 0) as price,
            COALESCE(aging_more_than_120_days * price, 0) as locked_capital,
            CASE 
                WHEN inh_s_obslte = 'OBSOLETE' THEN 'Obsolete'
                ELSE 'Aging' 
            END as status
        {base_query}
        ORDER BY locked_capital DESC NULLS LAST
    """
    items = [dict(row._mapping) for row in db.execute(text(list_query), params).fetchall()]
    
    return {
        "kpis": dict(kpis._mapping) if kpis else {},
        "items": items,
        "total": kpis.total_aging_items if kpis else 0
    }


def get_inventory_distribution(db: Session, search: str = None):
    params = {}
    
    base_query = """
        FROM materials
        WHERE COALESCE(gpc_stk, 0) > 0 OR COALESCE(branch_stk, 0) > 0
    """
    
    if search:
        base_query += " AND (material_code ILIKE :search OR material_description ILIKE :search OR vendor ILIKE :search)"
        params['search'] = f"%{search}%"
        
    # Get KPIs
    kpi_query = f"""
        SELECT 
            COUNT(*) as total_items_with_stock,
            SUM(COALESCE(gpc_stk, 0)) as total_central_stock,
            SUM(COALESCE(branch_stk, 0)) as total_branch_stock,
            COUNT(CASE WHEN COALESCE(gpc_stk, 0) = 0 AND COALESCE(branch_stk, 0) > 0 THEN 1 END) as branch_heavy_items,
            COUNT(CASE WHEN COALESCE(branch_stk, 0) = 0 AND COALESCE(gpc_stk, 0) > 0 THEN 1 END) as central_heavy_items
        {base_query}
    """
    kpis = db.execute(text(kpi_query), params).fetchone()
    
    # Get List
    list_query = f"""
        SELECT 
            material_code,
            material_description,
            COALESCE(gpc_stk, 0) as central_stock,
            COALESCE(branch_stk, 0) as branch_stock,
            COALESCE(gpc_stk, 0) + COALESCE(branch_stk, 0) as total_stock,
            CASE 
                WHEN COALESCE(gpc_stk, 0) = 0 AND COALESCE(branch_stk, 0) > 0 THEN 'Imbalanced (Branch Heavy)'
                WHEN COALESCE(branch_stk, 0) = 0 AND COALESCE(gpc_stk, 0) > 0 THEN 'Imbalanced (Central Heavy)'
                ELSE 'Balanced'
            END as balance_status
        {base_query}
        ORDER BY total_stock DESC NULLS LAST
    """
    items = [dict(row._mapping) for row in db.execute(text(list_query), params).fetchall()]
    
    return {
        "kpis": dict(kpis._mapping) if kpis else {},
        "items": items,
        "total": kpis.total_items_with_stock if kpis else 0
    }
