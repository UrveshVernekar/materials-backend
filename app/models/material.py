from sqlalchemy import Column, Integer, String, Numeric, DateTime
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
    delta = Column(Numeric)
    price = Column(Numeric(12, 2))
    moq = Column(Integer)
    cov_in_days = Column(Numeric)
    status = Column(String(50))  # Running, New, Obsolete, Slow
    
    # Stock and tracking fields
    gpc_stk = Column(Numeric(12, 2))
    gpc_free_stk = Column(Numeric(12, 2))
    branch_stk = Column(Numeric(12, 2))
    po_balance = Column(Numeric(12, 2))
    
    # ... Add others as needed for KPIs
    created_at = Column(DateTime(timezone=True), server_default=func.now())