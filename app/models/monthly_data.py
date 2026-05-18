from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from app.core.database import Base

class MaterialMonthlyData(Base):
    __tablename__ = "material_monthly_data"

    id = Column(Integer, primary_key=True, index=True)
    material_code = Column(String(50), index=True) # Linked by code as per data-import
    year = Column(Integer)
    month = Column(Integer)
    consumption = Column(Numeric(12, 2))


