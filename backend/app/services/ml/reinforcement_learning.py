"""
Multi-Armed Bandit Reinforcement Learning Reward Layer

Implements Thompson Sampling and Epsilon-Greedy strategies for campaign
variant selection and optimization. Pure Python -- no numpy dependency.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RewardMetrics:
    """Observed performance metrics for a single campaign variant."""

    open_rate: float = 0.0
    click_through_rate: float = 0.0
    conversion_rate: float = 0.0
    revenue_per_lead: float = 0.0

    def composite_reward(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Collapse multi-dimensional metrics into a single scalar reward.

        Default weights emphasise conversion and revenue while still
        rewarding upstream engagement.
        """
        w = weights or {
            "open_rate": 0.15,
            "click_through_rate": 0.25,
            "conversion_rate": 0.35,
            "revenue_per_lead": 0.25,
        }
        total_weight = sum(w.values())
        if total_weight == 0:
            return 0.0

        raw = (
            w.get("open_rate", 0) * self.open_rate
            + w.get("click_through_rate", 0) * self.click_through_rate
            + w.get("conversion_rate", 0) * self.conversion_rate
            + w.get("revenue_per_lead", 0) * min(self.revenue_per_lead / 100.0, 1.0)
        )
        return raw / total_weight


@dataclass
class CampaignVariant:
    """A single arm in the multi-armed bandit experiment."""

    variant_id: str
    content: Dict[str, str]  # e.g. {"subject": "...", "body": "..."}
    metrics: RewardMetrics = field(default_factory=RewardMetrics)
    pull_count: int = 0
    total_reward: float = 0.0

    # Beta distribution parameters for Thompson Sampling
    alpha: float = 1.0  # successes + prior
    beta_param: float = 1.0  # failures + prior

    @property
    def average_reward(self) -> float:
        if self.pull_count == 0:
            return 0.0
        return self.total_reward / self.pull_count


class Strategy(str, Enum):
    THOMPSON_SAMPLING = "thompson_sampling"
    EPSILON_GREEDY = "epsilon_greedy"


# ---------------------------------------------------------------------------
# Sampling helpers (pure Python replacements for scipy/numpy)
# ---------------------------------------------------------------------------


def _beta_sample(alpha: float, beta_val: float) -> float:
    """Draw a single sample from Beta(alpha, beta) using the Johnk algorithm.

    Falls back to a gamma-ratio method for numerical stability when
    parameters are large.
    """
    if alpha <= 0 or beta_val <= 0:
        raise ValueError(f"Beta parameters must be positive: alpha={alpha}, beta={beta_val}")

    # Gamma-ratio method: Beta(a,b) = G(a) / (G(a) + G(b))
    x = _gamma_sample(alpha)
    y = _gamma_sample(beta_val)
    if x + y == 0:
        return 0.5
    return x / (x + y)


def _gamma_sample(shape: float, scale: float = 1.0) -> float:
    """Draw from Gamma(shape, scale) using Marsaglia and Tsang's method."""
    if shape <= 0:
        raise ValueError(f"Gamma shape must be positive, got {shape}")

    if shape < 1.0:
        # Boost: Gamma(a) = Gamma(a+1) * U^(1/a)
        return _gamma_sample(shape + 1.0, scale) * (random.random() ** (1.0 / shape))

    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)

    while True:
        while True:
            x = random.gauss(0, 1)
            v = (1.0 + c * x) ** 3
            if v > 0:
                break
        u = random.random()
        if u < 1.0 - 0.0331 * (x * x) ** 2:
            return d * v * scale
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v * scale


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


class ThompsonSampling:
    """Thompson Sampling: sample from each arm's posterior Beta distribution
    and pick the arm with the highest sample."""

    @staticmethod
    def select(variants: List[CampaignVariant]) -> CampaignVariant:
        if not variants:
            raise ValueError("No variants to select from")

        best_sample = -1.0
        best_variant: Optional[CampaignVariant] = None

        for v in variants:
            sample = _beta_sample(v.alpha, v.beta_param)
            logger.debug(
                "Thompson sample for %s: %.4f (alpha=%.2f, beta=%.2f)",
                v.variant_id,
                sample,
                v.alpha,
                v.beta_param,
            )
            if sample > best_sample:
                best_sample = sample
                best_variant = v

        return best_variant  # type: ignore[return-value]

    @staticmethod
    def update(variant: CampaignVariant, reward: float) -> None:
        """Update Beta posterior. Reward is clamped to [0, 1]."""
        clamped = max(0.0, min(1.0, reward))
        variant.alpha += clamped
        variant.beta_param += 1.0 - clamped


class EpsilonGreedy:
    """Epsilon-Greedy: exploit the best arm most of the time, explore
    uniformly at random with probability epsilon."""

    def __init__(self, epsilon: float = 0.1):
        self.epsilon = max(0.0, min(1.0, epsilon))

    def select(self, variants: List[CampaignVariant]) -> CampaignVariant:
        if not variants:
            raise ValueError("No variants to select from")

        if random.random() < self.epsilon:
            chosen = random.choice(variants)
            logger.debug("Epsilon-greedy exploring: chose %s", chosen.variant_id)
            return chosen

        best = max(variants, key=lambda v: v.average_reward)
        logger.debug("Epsilon-greedy exploiting: chose %s (avg_reward=%.4f)", best.variant_id, best.average_reward)
        return best

    @staticmethod
    def update(variant: CampaignVariant, reward: float) -> None:
        """Simple incremental mean update."""
        variant.total_reward += reward
        variant.pull_count += 1


# ---------------------------------------------------------------------------
# Experiment logging
# ---------------------------------------------------------------------------


@dataclass
class ExperimentDecision:
    """A single logged decision within an experiment."""

    timestamp: float
    variant_id: str
    strategy: str
    reward: Optional[float] = None
    outcome_recorded: bool = False


class ExperimentLog:
    """Append-only log of all bandit decisions and outcomes."""

    def __init__(self) -> None:
        self._decisions: List[ExperimentDecision] = []
        self._outcomes: Dict[str, List[float]] = {}

    def record_decision(self, variant_id: str, strategy: str) -> int:
        """Log a selection event. Returns the decision index."""
        idx = len(self._decisions)
        self._decisions.append(
            ExperimentDecision(
                timestamp=time.time(),
                variant_id=variant_id,
                strategy=strategy,
            )
        )
        return idx

    def record_outcome(self, decision_index: int, reward: float) -> None:
        """Attach an observed reward to a previous decision."""
        if decision_index < 0 or decision_index >= len(self._decisions):
            logger.warning("Invalid decision index %d for outcome recording", decision_index)
            return
        dec = self._decisions[decision_index]
        dec.reward = reward
        dec.outcome_recorded = True
        self._outcomes.setdefault(dec.variant_id, []).append(reward)

    def summary(self) -> Dict[str, Dict[str, float]]:
        """Return per-variant aggregate statistics."""
        result: Dict[str, Dict[str, float]] = {}
        for vid, rewards in self._outcomes.items():
            n = len(rewards)
            mean = sum(rewards) / n if n else 0.0
            variance = (sum((r - mean) ** 2 for r in rewards) / n) if n > 1 else 0.0
            result[vid] = {
                "count": n,
                "mean_reward": round(mean, 6),
                "variance": round(variance, 6),
                "min": round(min(rewards), 6) if rewards else 0.0,
                "max": round(max(rewards), 6) if rewards else 0.0,
            }
        return result

    @property
    def total_decisions(self) -> int:
        return len(self._decisions)

    @property
    def decisions(self) -> List[ExperimentDecision]:
        return list(self._decisions)


# ---------------------------------------------------------------------------
# Main bandit orchestrator
# ---------------------------------------------------------------------------


class MultiArmedBandit:
    """Orchestrates multi-armed bandit experiments for campaign optimization.

    Supports Thompson Sampling and Epsilon-Greedy selection strategies.
    """

    # Thresholds that flag a variant as potentially high-risk
    HIGH_REWARD_THRESHOLD = 0.95
    LOW_PULL_MINIMUM = 5
    RISK_VOLATILITY_THRESHOLD = 0.3

    def __init__(
        self,
        strategy: str = "thompson_sampling",
        epsilon: float = 0.1,
        exploration_bonus: float = 0.5,
    ) -> None:
        self.strategy_name = Strategy(strategy)
        self.epsilon = epsilon
        self.exploration_bonus = exploration_bonus

        self._variants: Dict[str, CampaignVariant] = {}
        self._log = ExperimentLog()

        # Instantiate the chosen strategy
        self._strategy: ThompsonSampling | EpsilonGreedy
        if self.strategy_name == Strategy.THOMPSON_SAMPLING:
            self._strategy = ThompsonSampling()
        else:
            self._strategy = EpsilonGreedy(epsilon=self.epsilon)

        logger.info(
            "MultiArmedBandit initialised with strategy=%s, epsilon=%.2f, exploration_bonus=%.2f",
            self.strategy_name.value,
            self.epsilon,
            self.exploration_bonus,
        )

    # -- Variant management --------------------------------------------------

    def register_variant(self, variant: CampaignVariant) -> None:
        """Add a variant to the experiment."""
        self._variants[variant.variant_id] = variant
        logger.info("Registered variant %s", variant.variant_id)

    def register_variants(self, variants: List[CampaignVariant]) -> None:
        for v in variants:
            self.register_variant(v)

    # -- Selection -----------------------------------------------------------

    def select_variant(self, variants: Optional[List[CampaignVariant]] = None) -> CampaignVariant:
        """Choose the next variant to serve.

        If *variants* is not provided the bandit uses its internally
        registered variants.  An exploration bonus is applied to arms
        with very few pulls to encourage initial sampling.
        """
        pool = variants or list(self._variants.values())
        if not pool:
            raise ValueError("No variants available for selection")

        # Apply UCB-style exploration bonus for under-sampled arms
        total_pulls = sum(v.pull_count for v in pool)
        if total_pulls > 0 and self.exploration_bonus > 0:
            for v in pool:
                if v.pull_count < self.LOW_PULL_MINIMUM:
                    bonus = self.exploration_bonus * math.sqrt(math.log(total_pulls + 1) / (v.pull_count + 1))
                    v.alpha += bonus  # temporarily inflate optimism

        chosen = self._strategy.select(pool)

        # Undo temporary bonus inflation
        if total_pulls > 0 and self.exploration_bonus > 0:
            for v in pool:
                if v.pull_count < self.LOW_PULL_MINIMUM:
                    bonus = self.exploration_bonus * math.sqrt(math.log(total_pulls + 1) / (v.pull_count + 1))
                    v.alpha = max(1.0, v.alpha - bonus)

        chosen.pull_count += 1
        decision_idx = self._log.record_decision(
            variant_id=chosen.variant_id,
            strategy=self.strategy_name.value,
        )

        logger.info(
            "Selected variant %s (pull #%d) | decision_idx=%d",
            chosen.variant_id,
            chosen.pull_count,
            decision_idx,
        )
        return chosen

    # -- Reward update -------------------------------------------------------

    def update_reward(
        self,
        variant_id: str,
        reward: float,
        metrics: Optional[RewardMetrics] = None,
    ) -> None:
        """Record an observed reward for *variant_id*.

        If *metrics* are supplied, the variant's running metrics are
        updated and the composite reward overrides the raw *reward*.
        """
        variant = self._variants.get(variant_id)
        if variant is None:
            logger.error("Unknown variant_id %s -- reward discarded", variant_id)
            return

        if metrics is not None:
            variant.metrics = metrics
            reward = metrics.composite_reward()

        # Strategy-specific posterior update
        self._strategy.update(variant, reward)

        # Also maintain variant-level totals (Thompson already adjusts alpha/beta)
        if self.strategy_name == Strategy.THOMPSON_SAMPLING:
            variant.total_reward += reward
            # pull_count already incremented on select

        # Log the outcome against the most recent decision for this variant
        for i in range(self._log.total_decisions - 1, -1, -1):
            dec = self._log.decisions[i]
            if dec.variant_id == variant_id and not dec.outcome_recorded:
                self._log.record_outcome(i, reward)
                break

        logger.info(
            "Updated reward for %s: reward=%.4f, total=%.4f, pulls=%d",
            variant_id,
            reward,
            variant.total_reward,
            variant.pull_count,
        )

    # -- Reporting -----------------------------------------------------------

    def get_experiment_summary(self) -> Dict:
        """Return a comprehensive summary of the running experiment."""
        variant_stats = []
        for v in self._variants.values():
            variant_stats.append(
                {
                    "variant_id": v.variant_id,
                    "pull_count": v.pull_count,
                    "total_reward": round(v.total_reward, 4),
                    "average_reward": round(v.average_reward, 4),
                    "alpha": round(v.alpha, 4),
                    "beta": round(v.beta_param, 4),
                    "metrics": {
                        "open_rate": v.metrics.open_rate,
                        "click_through_rate": v.metrics.click_through_rate,
                        "conversion_rate": v.metrics.conversion_rate,
                        "revenue_per_lead": v.metrics.revenue_per_lead,
                    },
                }
            )

        # Sort by average reward descending
        variant_stats.sort(key=lambda s: float(s["average_reward"]), reverse=True)

        return {
            "strategy": self.strategy_name.value,
            "total_decisions": self._log.total_decisions,
            "variants": variant_stats,
            "log_summary": self._log.summary(),
        }

    # -- Safety --------------------------------------------------------------

    def safety_check(self, variant: CampaignVariant) -> Dict[str, object]:
        """Determine whether a variant requires human review before wider rollout.

        Returns a dict with ``safe`` (bool) and ``reasons`` (list of strings).
        High-risk situations include:
        - Extremely high reward with very few observations (likely noise)
        - High variance in observed rewards (unstable performance)
        - Metrics that look anomalously good (possible tracking error)
        """
        reasons: List[str] = []

        # 1. Too-good-to-be-true with small sample
        if variant.average_reward > self.HIGH_REWARD_THRESHOLD and variant.pull_count < self.LOW_PULL_MINIMUM * 3:
            reasons.append(
                f"Average reward ({variant.average_reward:.2f}) is unusually high "
                f"with only {variant.pull_count} observations -- possible noise."
            )

        # 2. High variance (check from experiment log)
        log_stats = self._log.summary().get(variant.variant_id, {})
        variance = log_stats.get("variance", 0.0)
        if variance > self.RISK_VOLATILITY_THRESHOLD:
            reasons.append(
                f"Reward variance ({variance:.4f}) exceeds volatility threshold "
                f"({self.RISK_VOLATILITY_THRESHOLD}) -- performance is unstable."
            )

        # 3. Anomalous metrics
        if variant.metrics.open_rate > 0.90:
            reasons.append(
                f"Open rate ({variant.metrics.open_rate:.0%}) is suspiciously high -- "
                "check tracking pixel and deliverability."
            )
        if variant.metrics.conversion_rate > 0.50:
            reasons.append(
                f"Conversion rate ({variant.metrics.conversion_rate:.0%}) is unusually "
                "high -- verify attribution model."
            )

        is_safe = len(reasons) == 0
        if not is_safe:
            logger.warning(
                "Safety check FAILED for variant %s: %s",
                variant.variant_id,
                "; ".join(reasons),
            )
        else:
            logger.debug("Safety check passed for variant %s", variant.variant_id)

        return {"safe": is_safe, "reasons": reasons, "variant_id": variant.variant_id}
