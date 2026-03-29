"""
Predictive Churn Detection Service

Implements a logistic-regression-style scoring model for customer churn
prediction, risk segmentation, and automated retention workflow triggering.
Pure Python -- no numpy/sklearn dependency.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ChurnFeatures:
    """Input feature vector for churn prediction."""

    days_since_last_activity: float = 0.0
    email_open_rate_trend: float = 0.0   # negative = declining
    login_frequency: float = 0.0          # logins per week
    support_tickets: int = 0
    deal_stage_velocity: float = 0.0      # days per stage transition
    engagement_score: float = 0.0         # 0-100 composite

    def to_vector(self) -> List[float]:
        """Return a flat numeric list suitable for the scoring function."""
        return [
            self.days_since_last_activity,
            self.email_open_rate_trend,
            self.login_frequency,
            self.support_tickets,
            self.deal_stage_velocity,
            self.engagement_score,
        ]


@dataclass
class ChurnPrediction:
    """Output of the churn predictor for a single customer."""

    customer_id: str
    churn_probability: float
    risk_level: RiskLevel
    contributing_factors: List[Dict[str, Any]]
    recommended_actions: List[str]
    predicted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "churn_probability": round(self.churn_probability, 4),
            "risk_level": self.risk_level.value,
            "contributing_factors": self.contributing_factors,
            "recommended_actions": self.recommended_actions,
            "predicted_at": self.predicted_at,
        }


# ---------------------------------------------------------------------------
# Logistic regression helpers (pure Python)
# ---------------------------------------------------------------------------

def _sigmoid(z: float) -> float:
    """Numerically stable sigmoid function."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _dot(a: List[float], b: List[float]) -> float:
    """Dot product of two equal-length vectors."""
    return sum(ai * bi for ai, bi in zip(a, b))


def _normalize_feature(value: float, mean: float, std: float) -> float:
    """Z-score normalisation with guard against zero std."""
    if std == 0:
        return 0.0
    return (value - mean) / std


# ---------------------------------------------------------------------------
# Churn predictor
# ---------------------------------------------------------------------------

class ChurnPredictor:
    """Logistic-regression-style churn scorer.

    Weights and normalisation statistics are initialised to sensible
    defaults calibrated against typical B2B SaaS engagement data.
    In production these would be learned from labelled data via a
    training pipeline; here they are hand-tuned for realism.
    """

    # Feature order matches ChurnFeatures.to_vector()
    FEATURE_NAMES = [
        "days_since_last_activity",
        "email_open_rate_trend",
        "login_frequency",
        "support_tickets",
        "deal_stage_velocity",
        "engagement_score",
    ]

    # Pre-calibrated weights (positive = increases churn probability)
    DEFAULT_WEIGHTS: List[float] = [
        0.035,   # days_since_last_activity  -- more days = higher churn
        -1.8,    # email_open_rate_trend     -- declining trend = higher churn
        -0.25,   # login_frequency           -- fewer logins = higher churn
        0.30,    # support_tickets           -- more tickets = higher churn
        0.020,   # deal_stage_velocity       -- slower movement = higher churn
        -0.04,   # engagement_score          -- lower score = higher churn
    ]
    DEFAULT_BIAS: float = -0.5

    # Normalisation stats (mean, std) per feature
    FEATURE_STATS: List[Tuple[float, float]] = [
        (15.0, 12.0),   # days_since_last_activity
        (0.0, 0.15),    # email_open_rate_trend
        (3.0, 2.5),     # login_frequency
        (1.5, 2.0),     # support_tickets
        (14.0, 10.0),   # deal_stage_velocity
        (55.0, 20.0),   # engagement_score
    ]

    # Risk-level thresholds
    RISK_THRESHOLDS = {
        RiskLevel.CRITICAL: 0.80,
        RiskLevel.HIGH: 0.60,
        RiskLevel.MEDIUM: 0.35,
    }

    def __init__(
        self,
        weights: Optional[List[float]] = None,
        bias: Optional[float] = None,
    ) -> None:
        self.weights = weights or list(self.DEFAULT_WEIGHTS)
        self.bias = bias if bias is not None else self.DEFAULT_BIAS

        if len(self.weights) != len(self.FEATURE_NAMES):
            raise ValueError(
                f"Expected {len(self.FEATURE_NAMES)} weights, got {len(self.weights)}"
            )

        self._prediction_cache: Dict[str, ChurnPrediction] = {}
        logger.info("ChurnPredictor initialised with %d features", len(self.weights))

    # -- Single prediction ---------------------------------------------------

    def predict_churn(
        self,
        customer_id: str,
        features: ChurnFeatures,
    ) -> ChurnPrediction:
        """Score a single customer and return a full prediction."""
        raw = features.to_vector()

        # Normalise
        normed = [
            _normalize_feature(v, mean, std)
            for v, (mean, std) in zip(raw, self.FEATURE_STATS)
        ]

        # Linear combination + sigmoid
        z = _dot(self.weights, normed) + self.bias
        prob = _sigmoid(z)

        # Identify risk level
        risk = RiskLevel.LOW
        for level, threshold in sorted(
            self.RISK_THRESHOLDS.items(), key=lambda kv: kv[1], reverse=True
        ):
            if prob >= threshold:
                risk = level
                break

        # Determine contributing factors (features that push churn up)
        contributions = self._compute_contributions(normed)
        factors = self._rank_factors(contributions, raw)

        # Generate recommendations
        actions = self._get_retention_recommendations_internal(risk, factors)

        prediction = ChurnPrediction(
            customer_id=customer_id,
            churn_probability=prob,
            risk_level=risk,
            contributing_factors=factors,
            recommended_actions=actions,
        )

        self._prediction_cache[customer_id] = prediction
        logger.info(
            "Churn prediction for %s: prob=%.3f risk=%s",
            customer_id, prob, risk.value,
        )
        return prediction

    # -- Batch prediction ----------------------------------------------------

    def batch_predict(
        self,
        customer_list: List[Dict[str, Any]],
    ) -> List[ChurnPrediction]:
        """Predict churn for multiple customers.

        Each dict in *customer_list* must contain ``customer_id`` and
        feature keys matching :class:`ChurnFeatures` field names.
        """
        predictions: List[ChurnPrediction] = []
        for entry in customer_list:
            cid = entry.get("customer_id", str(uuid.uuid4()))
            features = ChurnFeatures(
                days_since_last_activity=float(entry.get("days_since_last_activity", 0)),
                email_open_rate_trend=float(entry.get("email_open_rate_trend", 0)),
                login_frequency=float(entry.get("login_frequency", 0)),
                support_tickets=int(entry.get("support_tickets", 0)),
                deal_stage_velocity=float(entry.get("deal_stage_velocity", 0)),
                engagement_score=float(entry.get("engagement_score", 0)),
            )
            predictions.append(self.predict_churn(cid, features))

        logger.info("Batch prediction completed for %d customers", len(predictions))
        return predictions

    # -- Risk segmentation ---------------------------------------------------

    def get_risk_segments(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group all cached predictions by risk level."""
        segments: Dict[str, List[Dict[str, Any]]] = {
            level.value: [] for level in RiskLevel
        }
        for pred in self._prediction_cache.values():
            segments[pred.risk_level.value].append(pred.to_dict())

        # Sort each segment by churn probability descending
        for level in segments:
            segments[level].sort(
                key=lambda p: p["churn_probability"], reverse=True
            )

        counts = {k: len(v) for k, v in segments.items()}
        logger.info("Risk segments: %s", counts)
        return segments

    # -- Retention workflow trigger -------------------------------------------

    def trigger_retention_workflow(
        self,
        prediction: ChurnPrediction,
        workflow_callback: Optional[Callable[[ChurnPrediction], None]] = None,
    ) -> Dict[str, Any]:
        """Decide whether to auto-trigger a retention workflow.

        Only HIGH and CRITICAL risks auto-trigger. Returns a status dict.
        """
        if prediction.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            logger.info(
                "Triggering retention workflow for customer %s (risk=%s)",
                prediction.customer_id, prediction.risk_level.value,
            )
            if workflow_callback:
                workflow_callback(prediction)

            return {
                "triggered": True,
                "customer_id": prediction.customer_id,
                "risk_level": prediction.risk_level.value,
                "actions": prediction.recommended_actions,
            }

        logger.debug(
            "No retention trigger for customer %s (risk=%s)",
            prediction.customer_id, prediction.risk_level.value,
        )
        return {
            "triggered": False,
            "customer_id": prediction.customer_id,
            "risk_level": prediction.risk_level.value,
            "reason": "Risk level does not meet auto-trigger threshold",
        }

    # -- Public recommendations API ------------------------------------------

    def get_retention_recommendations(
        self, prediction: ChurnPrediction
    ) -> List[str]:
        """Return personalized retention recommendations for a prediction."""
        return self._get_retention_recommendations_internal(
            prediction.risk_level,
            prediction.contributing_factors,
        )

    # -- Internal helpers ----------------------------------------------------

    def _compute_contributions(self, normed: List[float]) -> List[float]:
        """Per-feature contribution to the churn logit."""
        return [w * x for w, x in zip(self.weights, normed)]

    def _rank_factors(
        self, contributions: List[float], raw_values: List[float]
    ) -> List[Dict[str, Any]]:
        """Rank features by their absolute contribution magnitude."""
        paired = [
            {
                "feature": name,
                "contribution": round(c, 4),
                "direction": "increases churn" if c > 0 else "decreases churn",
                "raw_value": round(rv, 4),
            }
            for name, c, rv in zip(self.FEATURE_NAMES, contributions, raw_values)
        ]
        paired.sort(key=lambda f: abs(f["contribution"]), reverse=True)
        return paired

    def _get_retention_recommendations_internal(
        self,
        risk: RiskLevel,
        factors: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate actionable retention recommendations based on risk and top
        contributing factors."""
        recommendations: List[str] = []

        # Top 3 contributing factors that push toward churn
        churn_drivers = [
            f for f in factors if f["direction"] == "increases churn"
        ][:3]

        for factor in churn_drivers:
            name = factor["feature"]
            if name == "days_since_last_activity":
                recommendations.append(
                    "Send a personalized re-engagement email with recent product updates."
                )
            elif name == "email_open_rate_trend":
                recommendations.append(
                    "A/B test new subject lines and send-time optimization for this contact."
                )
            elif name == "login_frequency":
                recommendations.append(
                    "Trigger an in-app walkthrough highlighting unused features."
                )
            elif name == "support_tickets":
                recommendations.append(
                    "Escalate to customer success manager for proactive outreach."
                )
            elif name == "deal_stage_velocity":
                recommendations.append(
                    "Schedule a deal review call to unblock stalled pipeline."
                )
            elif name == "engagement_score":
                recommendations.append(
                    "Enrol in a nurture sequence with high-value content assets."
                )

        # Risk-level-specific extras
        if risk == RiskLevel.CRITICAL:
            recommendations.insert(
                0, "URGENT: Assign dedicated CSM and schedule executive check-in within 48 hours."
            )
        elif risk == RiskLevel.HIGH:
            recommendations.insert(
                0, "Schedule a customer health review with the account team this week."
            )

        return recommendations


# ---------------------------------------------------------------------------
# Retention workflow engine
# ---------------------------------------------------------------------------

class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    action: str
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    outcome: Optional[str] = None


@dataclass
class RetentionWorkflowInstance:
    workflow_id: str
    customer_id: str
    prediction: ChurnPrediction
    steps: List[WorkflowStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "created"


class RetentionWorkflow:
    """Creates and manages multi-step retention workflows triggered by churn
    predictions."""

    # Default workflow templates keyed by risk level
    TEMPLATES: Dict[str, List[Dict[str, str]]] = {
        RiskLevel.CRITICAL.value: [
            {"name": "Assign CSM", "action": "assign_csm"},
            {"name": "Executive outreach email", "action": "send_exec_email"},
            {"name": "Schedule health-check call", "action": "schedule_call"},
            {"name": "Offer retention incentive", "action": "create_offer"},
            {"name": "Track 7-day re-engagement", "action": "monitor_engagement"},
        ],
        RiskLevel.HIGH.value: [
            {"name": "CSM notification", "action": "notify_csm"},
            {"name": "Personalised nurture email", "action": "send_nurture_email"},
            {"name": "Feature adoption nudge", "action": "in_app_nudge"},
            {"name": "Track 14-day re-engagement", "action": "monitor_engagement"},
        ],
        RiskLevel.MEDIUM.value: [
            {"name": "Automated re-engagement email", "action": "send_reengagement_email"},
            {"name": "Content recommendation", "action": "recommend_content"},
            {"name": "Track 30-day engagement", "action": "monitor_engagement"},
        ],
        RiskLevel.LOW.value: [
            {"name": "Quarterly check-in flag", "action": "flag_for_checkin"},
        ],
    }

    def __init__(self) -> None:
        self._workflows: Dict[str, RetentionWorkflowInstance] = {}

    def create_workflow(self, prediction: ChurnPrediction) -> RetentionWorkflowInstance:
        """Instantiate a retention workflow from the appropriate template."""
        template = self.TEMPLATES.get(prediction.risk_level.value, [])
        steps = [
            WorkflowStep(
                step_id=f"step_{i}",
                name=s["name"],
                action=s["action"],
            )
            for i, s in enumerate(template)
        ]

        instance = RetentionWorkflowInstance(
            workflow_id=str(uuid.uuid4()),
            customer_id=prediction.customer_id,
            prediction=prediction,
            steps=steps,
        )
        self._workflows[instance.workflow_id] = instance

        logger.info(
            "Created retention workflow %s for customer %s (%d steps, risk=%s)",
            instance.workflow_id,
            prediction.customer_id,
            len(steps),
            prediction.risk_level.value,
        )
        return instance

    def execute_step(
        self,
        workflow_id: str,
        step_id: str,
        executor: Optional[Callable[[WorkflowStep], str]] = None,
    ) -> WorkflowStep:
        """Execute (or simulate) a single workflow step.

        If *executor* is provided it is called with the step and its return
        value is stored as the outcome.  Otherwise the step is marked as
        completed with a default outcome message.
        """
        wf = self._workflows.get(workflow_id)
        if wf is None:
            raise ValueError(f"Unknown workflow_id: {workflow_id}")

        step = next((s for s in wf.steps if s.step_id == step_id), None)
        if step is None:
            raise ValueError(f"Unknown step_id {step_id} in workflow {workflow_id}")

        step.status = WorkflowStepStatus.IN_PROGRESS
        step.started_at = time.time()

        try:
            if executor:
                step.outcome = executor(step)
            else:
                step.outcome = f"Step '{step.name}' executed successfully (simulated)"
            step.status = WorkflowStepStatus.COMPLETED
        except Exception as exc:
            logger.error("Workflow step %s failed: %s", step_id, exc)
            step.status = WorkflowStepStatus.FAILED
            step.outcome = str(exc)

        step.completed_at = time.time()

        # Update overall workflow status
        all_done = all(
            s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED, WorkflowStepStatus.FAILED)
            for s in wf.steps
        )
        if all_done:
            wf.status = "completed"
        else:
            wf.status = "in_progress"

        logger.info(
            "Executed step %s/%s -> %s", workflow_id, step_id, step.status.value,
        )
        return step

    def track_outcome(self, workflow_id: str) -> Dict[str, Any]:
        """Return current status and step-level outcomes for a workflow."""
        wf = self._workflows.get(workflow_id)
        if wf is None:
            raise ValueError(f"Unknown workflow_id: {workflow_id}")

        return {
            "workflow_id": wf.workflow_id,
            "customer_id": wf.customer_id,
            "status": wf.status,
            "risk_level": wf.prediction.risk_level.value,
            "churn_probability": round(wf.prediction.churn_probability, 4),
            "created_at": wf.created_at,
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "action": s.action,
                    "status": s.status.value,
                    "outcome": s.outcome,
                    "duration_seconds": (
                        round(s.completed_at - s.started_at, 2)
                        if s.started_at and s.completed_at
                        else None
                    ),
                }
                for s in wf.steps
            ],
        }

    def get_all_workflows(self) -> List[Dict[str, Any]]:
        """Return summaries of all tracked workflows."""
        return [self.track_outcome(wid) for wid in self._workflows]
