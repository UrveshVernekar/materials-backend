from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.crud.purchase_order import (
    get_purchase_orders_by_material,
    get_purchase_order,
    create_purchase_order,
    update_purchase_order,
)
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderResponse,
    PurchaseOrderListResponse,
)
from app.routers.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/purchase_orders", tags=["purchase_orders"])

@router.get("/", response_model=PurchaseOrderListResponse)
def list_purchase_orders(
    material_code: str = Query(..., description="Material code to fetch purchase orders for"),
    db: Session = Depends(get_db)
):
    items = get_purchase_orders_by_material(db, material_code)
    return {"items": items, "total": len(items)}

@router.get("/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order_by_id(po_id: int, db: Session = Depends(get_db)):
    po = get_purchase_order(db, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po

@router.post("/", response_model=PurchaseOrderResponse)
def create_purchase_order_endpoint(
    po_in: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    po, error = create_purchase_order(db, po_in, user_id=current_user.id)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return po

@router.put("/{po_id}", response_model=PurchaseOrderResponse)
def update_purchase_order_endpoint(
    po_id: int,
    po_in: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    po, error = update_purchase_order(db, po_id, po_in)
    if error:
        if error == "Purchase order not found":
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=400, detail=error)
    return po
