from pydantic import BaseModel
from typing import List, Optional
from datetime import date

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
    month1_prediction: Optional[float] = None
    month2_prediction: Optional[float] = None
    month3_prediction: Optional[float] = None
    month1_date: Optional[date] = None
    month2_date: Optional[date] = None
    month3_date: Optional[date] = None

class DashboardTableResponse(BaseModel):
    items: List[MaterialTableRow]
    total: int