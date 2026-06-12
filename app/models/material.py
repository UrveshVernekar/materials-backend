from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.orm import synonym
from sqlalchemy.sql import func
from app.core.database import Base

class Material(Base):
    __tablename__ = "materials"

    material_code = Column(String(50), primary_key=True, index=True, nullable=False)
    material_description = Column(String(500))
    vendor = Column(String(200))
    machine_population = Column(Integer)
    last_production_year = Column(Integer)
    lead_time = Column(Numeric)
    lead_time_qty = Column(Numeric(12, 2), default=0)
    delta = Column(Numeric)
    price = Column(Numeric(12, 2))
    moq = Column(Integer)
    cov_in_days = Column(Numeric)
    product_status = Column("product_status", String(100))
    status = synonym("product_status")  # Running, New, Obsolete, Slow
    
    # Stock and tracking fields
    gpc_stk = Column(Numeric(12, 2))
    gpc_free_stk = Column(Numeric(12, 2))
    branch_stk = Column(Numeric(12, 2))
    po_balance = Column(Numeric(12, 2))
    
    remarks = Column(String(1000), nullable=True)
    
    # ... Add others as needed for KPIs
    created_at = Column(DateTime(timezone=True), server_default=func.now())