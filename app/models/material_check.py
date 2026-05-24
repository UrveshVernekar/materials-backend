from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class MaterialCheck(Base):
    __tablename__ = "material_checks"

    id = Column(Integer, primary_key=True, index=True)
    material_code = Column(String(50), ForeignKey("materials.material_code", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_checked = Column(Boolean, nullable=False, default=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    unchecked_at = Column(DateTime(timezone=True), nullable=True)
