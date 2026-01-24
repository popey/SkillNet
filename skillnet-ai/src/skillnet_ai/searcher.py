import requests
import logging
from typing import Optional, List, Dict, Any, Literal
from skillnet_ai.models import SearchResponse

# Configure logger
logger = logging.getLogger(__name__)

class SkillNetSearcher:
    """
    Skiil Searcher for interacting with the SkillNet Search API.
    """
    
    def __init__(self, skillnet_url: str = "https://skillnet.openkg.cn"):
        self.skillnet_url = skillnet_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SkillNet-Python-SDK/0.1.0"
        })

    def search(
        self, 
        q: str, 
        mode: Literal["keyword", "vector"] = "keyword",
        category: Optional[str] = None, 
        limit: int = 20,
        # --- Keyword mode ---
        page: int = 1,
        min_stars: int = 0, 
        sort_by: str = "stars",
        # --- Vector mode ---
        threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Unified search for skills (supports both Keyword and AI Vector search).
        
        Args:
            q: Search query (Keywords or Natural Language).
            mode: 'keyword' for exact/fuzzy match, 'vector' for semantic AI search.
            category: Filter by category (e.g., 'Development').
            limit: Items per page (keyword) or Match count (vector).
            
            # Keyword specific:
            page: Page number.
            min_stars: Minimum stars filter.
            sort_by: Sort field ('stars' or 'recent').
            
            # Vector specific:
            threshold: Similarity threshold (0.0 to 1.0).

        Returns:
            A list of skill dictionaries.
        """
        endpoint = f"{self.skillnet_url}/search"
        
        # 1. Construct base parameters
        params = {
            "q": q,
            "mode": mode,
            "category": category,
            "limit": limit
        }

        # 2. Add mode-specific parameters
        if mode == "keyword":
            params.update({
                "page": page,
                "min_stars": min_stars,
                "sort_by": sort_by,
            })
        elif mode == "vector":
            params.update({
                "threshold": threshold
            })

        # 3. Clean None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            logger.debug(f"Searching skills ({mode} mode) with params: {params}")
            
            # Make the request
            response = self.session.get(endpoint, params=params, timeout=15)
            response.raise_for_status()
            
            # Parse response
            search_res = SearchResponse(**response.json())
            
            if not search_res.success:
                logger.warning(f"Search API returned success=False")
                return []

            return search_res.data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Search request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Data parsing failed: {e}")
            raise