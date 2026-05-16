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
    material_description: str
    vendor: Optional[str]
    current_stock: Optional[float] = 0
    coverage_days: Optional[float] = 0
    three_m_avg: Optional[float] = 0
    twelve_m_avg: Optional[float] = 0
    price: Optional[float]
    status: str

class DashboardTableResponse(BaseModel):
    items: List[MaterialTableRow]
    total: int
    page: int
    size: int