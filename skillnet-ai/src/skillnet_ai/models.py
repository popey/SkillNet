from typing import Optional, List, Literal
from pydantic import BaseModel, Field

class SkillModel(BaseModel):
    """Represents a Skill object returned from the search API."""
    skill_name: str
    skill_description: Optional[str] = None
    author: Optional[str] = None
    stars: int = 0
    skill_url: Optional[str] = None
    category: Optional[str] = None

class MetaModel(BaseModel):
    """
    Pagination and query metadata.
    Contains fields for both Keyword and Vector search modes.
    """
    # Common fields
    query: Optional[str] = None
    search_mode: str = "keyword"
    category: Optional[str] = None
    limit: int = 20
    total: int = 0

    # Keyword mode specific fields (may be None in Vector mode)
    page: Optional[int] = None
    min_stars: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None

    # Vector mode specific fields (may be None in Keyword mode)
    threshold: Optional[float] = None 

    class Config:
        extra = "ignore" 

class SearchResponse(BaseModel):
    """Wrapper for the search API response."""
    data: List[SkillModel]
    meta: MetaModel
    success: bool