from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud.inventory import get_aging_inventory, get_inventory_distribution

router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("/aging")
def get_aging(
    search: str = Query(None),
    db: Session = Depends(get_db)
):
    return get_aging_inventory(db, search)

@router.get("/distribution")
def get_distribution(
    search: str = Query(None),
    db: Session = Depends(get_db)
):
    return get_inventory_distribution(db, search)
