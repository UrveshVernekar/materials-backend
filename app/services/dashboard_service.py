from sqlalchemy.orm import Session
from app.crud.material import get_dashboard_kpis, get_filtered_materials
from app.schemas.dashboard import DashboardKPIResponse, DashboardTableResponse
from app.schemas.material import MaterialFilter

def get_dashboard_data(db: Session):
    kpis = get_dashboard_kpis(db)
    return DashboardKPIResponse(**kpis)

def get_dashboard_table(db: Session, filters: MaterialFilter, user_id: int):
    data = get_filtered_materials(db, filters, user_id)
    return DashboardTableResponse(**data)