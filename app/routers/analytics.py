from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud.analytics import get_monthly_consumption_trend

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/monthly-trend")
def get_monthly_trend(
    material_code: str = Query(None, description="Optional material code to filter by"),
    limit: int = Query(None, description="Number of months of historical data to fetch"),
    db: Session = Depends(get_db)
):
    trend_data = get_monthly_consumption_trend(db, material_code, limit)
    return {"data": trend_data}
