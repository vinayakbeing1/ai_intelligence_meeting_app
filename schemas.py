from typing import List, Literal, Optional

from pydantic import BaseModel


class ActionItem(BaseModel):
    task: str
    assignee: Optional[str]
    deadline: Optional[str]
    priority: Literal["high", "medium", "low"]
    status: str
    confidence: float


class MeetingAnalysis(BaseModel):
    summary: str
    decisions: List[str]
    action_items: List[ActionItem]
    risks_blockers: List[str]
    unresolved_items: List[str]
    participants: List[str]
    confidence: float


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]