# app/crud/material.py
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.sql import func
from app.schemas.material import MaterialFilter
from app.models.material_check import MaterialCheck
from app.models.material import Material

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



def get_filtered_materials(db: Session, filters: MaterialFilter, user_id: int):
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
                COALESCE(m.pending_reorders, 0) as pending_reorders,
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
                m.remarks,
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
                p.month3_date,
                (
                    SELECT SUM(po.order_qty)
                    FROM purchase_orders po
                    WHERE po.material_code = m.material_code
                      AND po.year = EXTRACT(YEAR FROM p.month1_date)
                      AND po.month = EXTRACT(MONTH FROM p.month1_date)
                ) as actual_month1_po,
                (
                    SELECT SUM(po.order_qty)
                    FROM purchase_orders po
                    WHERE po.material_code = m.material_code
                      AND po.year = EXTRACT(YEAR FROM p.month2_date)
                      AND po.month = EXTRACT(MONTH FROM p.month2_date)
                ) as actual_month2_po,
                (
                    SELECT SUM(po.order_qty)
                    FROM purchase_orders po
                    WHERE po.material_code = m.material_code
                      AND po.year = EXTRACT(YEAR FROM p.month3_date)
                      AND po.month = EXTRACT(MONTH FROM p.month3_date)
                ) as actual_month3_po,
                COALESCE(mc.is_checked, FALSE) as is_checked,
                (
                    SELECT COALESCE(json_agg(json_build_object(
                        'email', u.email,
                        'first_name', u.first_name,
                        'last_name', u.last_name,
                        'is_checked', COALESCE(mc_all.is_checked, FALSE),
                        'checked_at', mc_all.checked_at,
                        'unchecked_at', mc_all.unchecked_at
                    )), '[]'::json)
                    FROM users u
                    LEFT JOIN material_checks mc_all ON u.id = mc_all.user_id AND mc_all.material_code = m.material_code
                ) as checks
            FROM materials m
            LEFT JOIN calc_summary s ON m.material_code = s.material_code
            LEFT JOIN consumption_prediction p ON m.material_code = p.material_code
            LEFT JOIN material_checks mc ON m.material_code = mc.material_code AND mc.user_id = :user_id
        )
        SELECT * FROM material_data
        WHERE 1=1
    """
    
    params = {'user_id': user_id}
    
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

    items = []
    for row in result:
        item = dict(row._mapping)
        
        # Get predictions
        m1_pred = float(item.get("month1_prediction") or 0.0)
        m2_pred = float(item.get("month2_prediction") or 0.0)
        m3_pred = float(item.get("month3_prediction") or 0.0)
        
        # Get actual POs
        act_m1_po = item.get("actual_month1_po")
        act_m2_po = item.get("actual_month2_po")
        act_m3_po = item.get("actual_month3_po")
        
        # Calculate actual MES values using actual POs if entered, else 0
        act_m1_po_val = float(act_m1_po) if act_m1_po is not None else 0.0
        act_m2_po_val = float(act_m2_po) if act_m2_po is not None else 0.0
        act_m3_po_val = float(act_m3_po) if act_m3_po is not None else 0.0
        
        # Current stock
        gpc_stk = float(item.get("current_stock") or 0.0)
        
        # Calculate actual MES
        act_m1_mes = max(0.0, gpc_stk - m1_pred + act_m1_po_val)
        act_m2_mes = max(0.0, act_m1_mes - m2_pred + act_m2_po_val)
        act_m3_mes = max(0.0, act_m2_mes - m3_pred + act_m3_po_val)
        
        item["actual_month1_mes"] = act_m1_mes
        item["actual_month2_mes"] = act_m2_mes
        item["actual_month3_mes"] = act_m3_mes
        
        # Calculate actual MES in days
        twelve_m_avg = float(item.get("twelve_m_avg") or 0.0)
        daily_demand = twelve_m_avg / 30.0 if twelve_m_avg > 0 else 0.0
        
        if daily_demand > 0:
            item["actual_month1_mes_days"] = act_m1_mes / daily_demand
            item["actual_month2_mes_days"] = act_m2_mes / daily_demand
            item["actual_month3_mes_days"] = act_m3_mes / daily_demand
        else:
            item["actual_month1_mes_days"] = 0.0
            item["actual_month2_mes_days"] = 0.0
            item["actual_month3_mes_days"] = 0.0
            
        items.append(item)

    # Fetch and map alternative parts
    try:
        alt_query = text("""
            SELECT master_code, master_mat_desc, substitute, substitute_mat_desc
            FROM alternative_parts
        """)
        alt_rows = db.execute(alt_query).fetchall()
        
        # Map to store group members: master_code -> dict of part_code -> description
        groups = {}
        # Map to store substitute's master: substitute_code -> master_code
        substitute_to_master = {}
        
        for row in alt_rows:
            m_code = row.master_code
            m_desc = row.master_mat_desc
            s_code = row.substitute
            s_desc = row.substitute_mat_desc
            
            if m_code == s_code:
                continue
                
            if m_code not in groups:
                groups[m_code] = {m_code: m_desc}
            groups[m_code][s_code] = s_desc
            substitute_to_master[s_code] = m_code

        for item in items:
            code = item["material_code"]
            alternatives = {}
            
            # Determine part type
            if code in groups:
                item["part_type"] = "Master"
            elif code in substitute_to_master:
                item["part_type"] = "Substitute"
            else:
                item["part_type"] = "Independent"
            
            # 1. If it's a master code, add all its substitutes
            if code in groups:
                for part_code, part_desc in groups[code].items():
                    if part_code != code:
                        alternatives[part_code] = part_desc
                            
            item["alternative_parts"] = [
                {"part_code": pc, "part_description": pd}
                for pc, pd in alternatives.items()
            ]
    except Exception as e:
        print(f"Error mapping alternative parts: {e}")
        for item in items:
            item["alternative_parts"] = []
            item["part_type"] = "Independent"

    # Apply part_type filter if provided
    if filters.part_type:
        items = [item for item in items if item.get("part_type") == filters.part_type]
        total = len(items)

    return {"items": items, "total": total or 0}


def toggle_material_check(db: Session, material_code: str, user_id: int, is_checked: bool):
    # Verify material exists
    material = db.query(Material).filter(Material.material_code == material_code).first()
    if not material:
        return None

    # Check if a record already exists
    db_check = db.query(MaterialCheck).filter(
        MaterialCheck.material_code == material_code,
        MaterialCheck.user_id == user_id
    ).first()

    now = datetime.now(timezone.utc)

    if db_check:
        db_check.is_checked = is_checked
        if is_checked:
            db_check.checked_at = now
            db_check.unchecked_at = None
        else:
            db_check.unchecked_at = now
    else:
        db_check = MaterialCheck(
            material_code=material_code,
            user_id=user_id,
            is_checked=is_checked,
            checked_at=now if is_checked else None,
            unchecked_at=None if is_checked else now
        )
        db.add(db_check)

    db.commit()
    db.refresh(db_check)
    return db_check


def update_material_remarks(db: Session, material_code: str, remarks: str | None):
    material = db.query(Material).filter(Material.material_code == material_code).first()
    if not material:
        return None
    material.remarks = remarks
    db.commit()
    db.refresh(material)
    return material