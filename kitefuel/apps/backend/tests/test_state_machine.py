import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.state_machine import (
    VALID_TRANSITIONS,
    InvalidTransition,
    can_transition,
    transition,
    next_action,
)

# ---------------------------------------------------------------------------
# Test: all valid transitions succeed
# ---------------------------------------------------------------------------

HAPPY_PATH_SEQUENCE = [
    ("task_created",     "credit_requested"),
    ("credit_requested", "credit_approved"),
    ("credit_approved",  "funds_locked"),
    ("funds_locked",     "data_purchased"),
    ("data_purchased",   "result_generated"),
    ("result_generated", "user_paid"),
    ("user_paid",        "lender_repaid"),
    ("lender_repaid",    "task_closed"),
]


@pytest.mark.parametrize("from_state,to_state", HAPPY_PATH_SEQUENCE)
def test_valid_transitions_succeed(from_state, to_state):
    result = transition(from_state, to_state)
    assert result == to_state


# ---------------------------------------------------------------------------
# Test: any non-terminal state can transition to task_failed
# ---------------------------------------------------------------------------

NON_TERMINAL_STATES = [s for s, targets in VALID_TRANSITIONS.items() if "task_failed" in targets]


@pytest.mark.parametrize("from_state", NON_TERMINAL_STATES)
def test_any_state_can_fail(from_state):
    result = transition(from_state, "task_failed")
    assert result == "task_failed"


# ---------------------------------------------------------------------------
# Test: invalid transition raises InvalidTransition
# ---------------------------------------------------------------------------

def test_invalid_transition_raises():
    with pytest.raises(InvalidTransition) as exc_info:
        transition("task_created", "task_closed")
    assert exc_info.value.from_state == "task_created"
    assert exc_info.value.to_state == "task_closed"


def test_invalid_transition_backwards_raises():
    with pytest.raises(InvalidTransition):
        transition("lender_repaid", "task_created")


# ---------------------------------------------------------------------------
# Test: terminal states return None from next_action
# ---------------------------------------------------------------------------

def test_next_action_task_closed_returns_none():
    assert next_action("task_closed") is None


def test_next_action_task_failed_returns_none():
    assert next_action("task_failed") is None


# ---------------------------------------------------------------------------
# Test: non-terminal states return a non-empty string from next_action
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", [s for s in VALID_TRANSITIONS if s not in ("task_closed", "task_failed")])
def test_next_action_non_terminal_returns_label(state):
    label = next_action(state)
    assert isinstance(label, str) and label
