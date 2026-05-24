from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class KPICard(BaseModel):
    title: str
    value: float | int | str
    subtitle: Optional[str] = None
    color: Optional[str] = None

class DashboardKPIResponse(BaseModel):
    total_materials: int
    active_materials: int
    critical_stock: int
    low_stock: int
    avg_coverage_days: float
    obsolete_count: int

class UserCheckDetail(BaseModel):
    email: str
    first_name: str
    last_name: str
    is_checked: bool
    checked_at: Optional[datetime] = None
    unchecked_at: Optional[datetime] = None

class MaterialTableRow(BaseModel):
    material_code: str
    material_description: Optional[str]
    vendor: Optional[str]
    machine_population: Optional[float] = 0
    current_stock: Optional[float] = 0
    coverage_days: Optional[float] = 0
    lead_time: Optional[float] = 0
    lead_time_qty: Optional[float] = 0
    delta: Optional[float] = 0
    total_lead_time: Optional[float] = 0
    three_m_avg: Optional[float] = 0
    twelve_m_avg: Optional[float] = 0
    price: Optional[float]
    status: str
    product_category: Optional[str] = None
    month1_prediction: Optional[float] = None
    month1_prediction_days: Optional[float] = 0
    month1_po: Optional[float] = 0
    month1_po_days: Optional[float] = 0
    month1_mes: Optional[float] = 0
    month1_mes_days: Optional[float] = 0
    month2_prediction: Optional[float] = None
    month2_prediction_days: Optional[float] = 0
    month2_po: Optional[float] = 0
    month2_po_days: Optional[float] = 0
    month2_mes: Optional[float] = 0
    month2_mes_days: Optional[float] = 0
    month3_prediction: Optional[float] = None
    month3_prediction_days: Optional[float] = 0
    month3_po: Optional[float] = 0
    month3_po_days: Optional[float] = 0
    month3_mes: Optional[float] = 0
    month3_mes_days: Optional[float] = 0
    month1_date: Optional[date] = None
    month2_date: Optional[date] = None
    month3_date: Optional[date] = None
    is_checked: bool = False
    checks: List[UserCheckDetail] = []

class DashboardTableResponse(BaseModel):
    items: List[MaterialTableRow]
    total: int

class MaterialCheckRequest(BaseModel):
    material_code: str
    is_checked: bool

class MaterialCheckResponse(BaseModel):
    material_code: str
    is_checked: bool
    checked_at: Optional[datetime] = None
    unchecked_at: Optional[datetime] = None
    message: str