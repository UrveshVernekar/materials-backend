from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.material import MaterialFilter
from app.services.dashboard_service import get_dashboard_data, get_dashboard_table
from app.schemas.dashboard import DashboardKPIResponse, DashboardTableResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/kpis", response_model=DashboardKPIResponse)
def get_kpis(db: Session = Depends(get_db)):
    return get_dashboard_data(db)

@router.get("/table", response_model=DashboardTableResponse)
def get_table(
    search: str = Query(None),
    vendor: str = Query(None),
    status: str = Query(None),
    min_coverage: float = Query(None),
    max_coverage: float = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    filters = MaterialFilter(
        search=search, 
        vendor=vendor, 
        status=status,
        min_coverage=min_coverage, 
        max_coverage=max_coverage,
        page=page, 
        size=size
    )
    return get_dashboard_table(db, filters)