from __future__ import annotations

from typing import List, Union

from langchain_core.tools import tool
from langsmith import traceable

from core.services.memory_service import MemoryService

MEMORY = MemoryService()


@tool("extract_long_term_facts")
@traceable(name="tool.extract_long_term_facts")
def extract_long_term_facts_tool(user_id: Union[int, str], message: str) -> List[str]:
    """
    Extract atomic long-term facts from a message and persist them to long-term memory.
    Returns the list of persisted facts.
    """
    facts = MEMORY.extract_long_term_facts(message=message)
    persisted: List[str] = []
    for f in facts:
        try:
            MEMORY.add_long_term_memory(user_id=user_id, content=f, source="extracted")
            persisted.append(f)
        except Exception:
            continue
    return persisted


