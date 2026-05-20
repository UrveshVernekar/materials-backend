from pydantic import BaseModel, constr, conint, confloat
from typing import Optional
from datetime import date, datetime

class PurchaseOrderBase(BaseModel):
    material_code: constr(strip_whitespace=True, min_length=1, max_length=50)
    po_number: constr(strip_whitespace=True, min_length=1, max_length=255)
    order_qty: Optional[confloat(ge=0)] = 0
    receive_qty: Optional[confloat(ge=0)] = 0
    year: conint(ge=1900, le=2100)
    month: conint(ge=1, le=12)

class PurchaseOrderCreate(PurchaseOrderBase):
    pass

class PurchaseOrderUpdate(BaseModel):
    po_number: Optional[constr(strip_whitespace=True, min_length=1, max_length=255)] = None
    order_qty: Optional[confloat(ge=0)] = None
    receive_qty: Optional[confloat(ge=0)] = None
    year: Optional[conint(ge=1900, le=2100)] = None
    month: Optional[conint(ge=1, le=12)] = None

class PurchaseOrderResponse(BaseModel):
    id: int
    material_code: str
    po_number: str
    order_qty: float | int
    receive_qty: float | int
    year: int
    month: int
    period_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderResponse]
    total: int
