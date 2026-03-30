"""
Enrollment state machine — ensures idempotent, deterministic state transitions.

States:
    pending    → Initial enrollment, no touches yet
    active     → Sequence is running, between steps
    sent       → Touch dispatched, awaiting engagement signals
    opened     → Email/SMS opened (tracked via SES events)
    replied    → Lead replied (detected via webhook/IMAP)
    paused     → Manually paused or auto-paused (e.g., reply detected)
    escalated  → Escalated to a different channel (hole-filler triggered)
    completed  → All steps executed or goal reached
    failed     → Hard failure (bounce, complaint, unsubscribe)
    bounced    → Legacy compat, maps to failed
    unsubscribed → Legacy compat, maps to failed

Transitions are one-way except for pause/resume. The FSM prevents double-sends
by only allowing dispatch from states where a send is valid.
"""

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class EnrollmentState(StrEnum):
    pending = "pending"
    active = "active"
    sent = "sent"
    opened = "opened"
    replied = "replied"
    paused = "paused"
    escalated = "escalated"
    completed = "completed"
    failed = "failed"
    bounced = "bounced"
    unsubscribed = "unsubscribed"


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: str, target: str, reason: str = ""):
        self.current = current
        self.target = target
        self.reason = reason
        msg = f"Invalid transition {current} → {target}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


# Valid transitions: {current_state: {allowed_target_states}}
_TRANSITIONS: dict[str, set[str]] = {
    EnrollmentState.pending: {
        EnrollmentState.active,
        EnrollmentState.paused,
        EnrollmentState.failed,
    },
    EnrollmentState.active: {
        EnrollmentState.sent,
        EnrollmentState.paused,
        EnrollmentState.completed,
        EnrollmentState.failed,
        EnrollmentState.escalated,
    },
    EnrollmentState.sent: {
        EnrollmentState.active,      # Timer elapsed, ready for next step
        EnrollmentState.opened,
        EnrollmentState.replied,
        EnrollmentState.paused,
        EnrollmentState.completed,
        EnrollmentState.failed,
        EnrollmentState.bounced,
        EnrollmentState.escalated,
    },
    EnrollmentState.opened: {
        EnrollmentState.active,      # Continue sequence
        EnrollmentState.replied,
        EnrollmentState.paused,
        EnrollmentState.completed,
        EnrollmentState.escalated,
    },
    EnrollmentState.replied: {
        EnrollmentState.paused,      # Auto-pause on reply
        EnrollmentState.completed,
        EnrollmentState.escalated,
    },
    EnrollmentState.paused: {
        EnrollmentState.active,      # Resume
        EnrollmentState.completed,
        EnrollmentState.failed,
    },
    EnrollmentState.escalated: {
        EnrollmentState.active,      # Back to main flow
        EnrollmentState.sent,
        EnrollmentState.paused,
        EnrollmentState.completed,
        EnrollmentState.failed,
    },
    EnrollmentState.completed: set(),   # Terminal
    EnrollmentState.failed: set(),      # Terminal
    EnrollmentState.bounced: set(),     # Terminal (legacy)
    EnrollmentState.unsubscribed: set(),  # Terminal (legacy)
}

# States from which we can dispatch a touch
SENDABLE_STATES = {
    EnrollmentState.active,
    EnrollmentState.escalated,
}

# States that indicate the enrollment is still alive (not terminal)
LIVE_STATES = {
    EnrollmentState.pending,
    EnrollmentState.active,
    EnrollmentState.sent,
    EnrollmentState.opened,
    EnrollmentState.replied,
    EnrollmentState.paused,
    EnrollmentState.escalated,
}

# Terminal states
TERMINAL_STATES = {
    EnrollmentState.completed,
    EnrollmentState.failed,
    EnrollmentState.bounced,
    EnrollmentState.unsubscribed,
}


def can_transition(current: str, target: str) -> bool:
    """Check if a state transition is valid."""
    allowed = _TRANSITIONS.get(current, set())
    return target in allowed


def validate_transition(current: str, target: str) -> None:
    """Validate a state transition, raising StateTransitionError if invalid."""
    if not can_transition(current, target):
        raise StateTransitionError(current, target)


def transition(current: str, target: str) -> str:
    """
    Execute a state transition.

    Returns the new state. Raises StateTransitionError if invalid.
    """
    validate_transition(current, target)
    logger.debug("State transition: %s → %s", current, target)
    return target


def is_sendable(state: str) -> bool:
    """Check if a touch can be dispatched from this state."""
    return state in SENDABLE_STATES


def is_terminal(state: str) -> bool:
    """Check if this is a terminal (final) state."""
    return state in TERMINAL_STATES


def is_live(state: str) -> bool:
    """Check if this enrollment is still active (non-terminal)."""
    return state in LIVE_STATES


def get_available_transitions(state: str) -> set[str]:
    """Get all valid target states from the current state."""
    return _TRANSITIONS.get(state, set())


# ── Engagement Signal Handlers ─────────────────────────────────────────

def handle_open_signal(current: str) -> str:
    """Handle an open event — transitions sent→opened or stays if already past."""
    if current == EnrollmentState.sent:
        return transition(current, EnrollmentState.opened)
    # If already opened/replied/etc., stay in current state
    return current


def handle_reply_signal(current: str) -> str:
    """Handle a reply event — transitions to replied, then auto-pauses."""
    if current in (EnrollmentState.sent, EnrollmentState.opened):
        return transition(current, EnrollmentState.replied)
    return current


def handle_bounce_signal(current: str) -> str:
    """Handle a bounce event — transitions to failed."""
    if current in (EnrollmentState.sent, EnrollmentState.active):
        return transition(current, EnrollmentState.failed)
    return current


def handle_complaint_signal(current: str) -> str:
    """Handle a complaint/unsubscribe event — transitions to failed."""
    if not is_terminal(current):
        # Force transition to failed from any live state
        if can_transition(current, EnrollmentState.failed):
            return transition(current, EnrollmentState.failed)
    return current


# ── Condition Evaluator ────────────────────────────────────────────────

def evaluate_condition(
    condition: dict[str, Any],
    enrollment_state: str,
    touch_history: list[dict[str, Any]],
) -> bool:
    """
    Evaluate a branch condition against enrollment state and history.

    Condition format:
    {
        "type": "opened" | "replied" | "not_opened" | "not_replied" | "clicked" | "custom",
        "within_hours": 48,  # optional time window
        "step_position": 2,  # optional: specific step to check
    }
    """
    cond_type = condition.get("type", "")
    condition.get("within_hours")
    step_pos = condition.get("step_position")

    # Filter history by step if specified
    relevant = touch_history
    if step_pos is not None:
        relevant = [t for t in relevant if t.get("step_number") == step_pos]

    if cond_type == "opened":
        return enrollment_state in (
            EnrollmentState.opened,
            EnrollmentState.replied,
        ) or any(t.get("action") == "opened" for t in relevant)

    elif cond_type == "not_opened":
        opened = any(t.get("action") == "opened" for t in relevant)
        return not opened and enrollment_state not in (
            EnrollmentState.opened,
            EnrollmentState.replied,
        )

    elif cond_type == "replied":
        return enrollment_state == EnrollmentState.replied or any(
            t.get("action") == "replied" for t in relevant
        )

    elif cond_type == "not_replied":
        return enrollment_state != EnrollmentState.replied and not any(
            t.get("action") == "replied" for t in relevant
        )

    elif cond_type == "clicked":
        return any(t.get("action") == "clicked" for t in relevant)

    elif cond_type == "bounced":
        return enrollment_state in (
            EnrollmentState.bounced,
            EnrollmentState.failed,
        ) or any(t.get("action") == "bounced" for t in relevant)

    # Default: treat unknown conditions as false
    logger.warning("Unknown condition type: %s", cond_type)
    return False
