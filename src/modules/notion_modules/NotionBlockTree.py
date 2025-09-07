from __future__ import annotations
from dataclasses import dataclass


@dataclass
class NotionBlockTree:
    """Notion 块的树形结构表示"""
    notion_id: str
    val: dict | None = None
    children_block: NotionBlockTree | None = None
    next_block: NotionBlockTree | None = None

