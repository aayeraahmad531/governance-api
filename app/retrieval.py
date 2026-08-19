import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def search(index_name: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Search stub for Phase 1.
    Will perform NumPy dot-product vector search over precomputed .npz indexes in Phase 2.
    """
    return []
