from uuid import UUID

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_leads: int
    active_consents: int
    touches_sent: int
    response_rate: float


class DeliverabilityStats(BaseModel):
    total_sent: int
    total_bounced: int
    bounce_rate: float
    spam_complaints: int
    spam_rate: float
    warmup_active: int
    warmup_completed: int


class SequencePerformance(BaseModel):
    sequence_id: UUID
    sequence_name: str
    enrolled: int
    active: int
    completed: int
    open_rate: float
    reply_rate: float
    bounce_rate: float


class AnalyticsSequencesResponse(BaseModel):
    sequences: list[SequencePerformance]
