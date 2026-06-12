from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.material import MaterialFilter
from app.services.dashboard_service import get_dashboard_data, get_dashboard_table
from app.schemas.dashboard import (
    DashboardKPIResponse, 
    DashboardTableResponse, 
    MaterialCheckRequest, 
    MaterialCheckResponse,
    MaterialRemarksRequest,
    MaterialRemarksResponse
)
from app.routers.auth import get_current_user
from app.models.user import User
from app.crud.material import toggle_material_check, update_material_remarks

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/kpis", response_model=DashboardKPIResponse)
def get_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_dashboard_data(db)

@router.get("/table", response_model=DashboardTableResponse)
def get_table(
    search: str = Query(None),
    vendor: str = Query(None),
    status: str = Query(None),
    min_coverage: float = Query(None),
    max_coverage: float = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filters = MaterialFilter(
        search=search, 
        vendor=vendor, 
        status=status,
        min_coverage=min_coverage, 
        max_coverage=max_coverage
    )
    return get_dashboard_table(db, filters, user_id=current_user.id)

@router.post("/check", response_model=MaterialCheckResponse)
def check_material(
    payload: MaterialCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_check = toggle_material_check(
        db, 
        material_code=payload.material_code, 
        user_id=current_user.id, 
        is_checked=payload.is_checked
    )
    if not db_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with code {payload.material_code} not found"
        )
    return MaterialCheckResponse(
        material_code=db_check.material_code,
        is_checked=db_check.is_checked,
        checked_at=db_check.checked_at,
        unchecked_at=db_check.unchecked_at,
        message="Material check status updated successfully"
    )

@router.post("/remarks", response_model=MaterialRemarksResponse)
def update_remarks(
    payload: MaterialRemarksRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_material = update_material_remarks(
        db,
        material_code=payload.material_code,
        remarks=payload.remarks
    )
    if not db_material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with code {payload.material_code} not found"
        )
    return MaterialRemarksResponse(
        material_code=db_material.material_code,
        remarks=db_material.remarks,
        message="Remarks updated successfully"
    )