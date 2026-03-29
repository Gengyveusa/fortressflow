"""
FortressFlow ML Services

Machine learning modules for campaign optimization, churn prediction,
and data deduplication.
"""

from .reinforcement_learning import (
    MultiArmedBandit,
    CampaignVariant,
    RewardMetrics,
    ExperimentLog,
)
from .churn_predictor import (
    ChurnPredictor,
    ChurnFeatures,
    ChurnPrediction,
    RetentionWorkflow,
)
from .deduplication import (
    DeduplicationEngine,
    DuplicateCandidate,
    MatchScore,
)

__all__ = [
    "MultiArmedBandit",
    "CampaignVariant",
    "RewardMetrics",
    "ExperimentLog",
    "ChurnPredictor",
    "ChurnFeatures",
    "ChurnPrediction",
    "RetentionWorkflow",
    "DeduplicationEngine",
    "DuplicateCandidate",
    "MatchScore",
]
