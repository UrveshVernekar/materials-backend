from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, FetchedValue, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    material_code = Column(String(50), nullable=False)
    po_number = Column(String(255), unique=True, nullable=False)
    order_qty = Column(Numeric, default=0)
    receive_qty = Column(Numeric, default=0)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    period_date = Column(Date, FetchedValue())  # Populated by PostgreSQL (GENERATED ALWAYS AS)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")

