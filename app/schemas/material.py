from pydantic import BaseModel
from typing import Optional

class MaterialFilter(BaseModel):
    search: Optional[str] = None
    vendor: Optional[str] = None
    status: Optional[str] = None
    min_coverage: Optional[float] = None
    max_coverage: Optional[float] = None