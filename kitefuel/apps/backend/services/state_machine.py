from typing import Optional

# ---------------------------------------------------------------------------
# Valid state transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, list[str]] = {
    "task_created":      ["credit_requested", "task_failed"],
    "credit_requested":  ["credit_approved",  "task_failed"],
    "credit_approved":   ["funds_locked",      "task_failed"],
    "funds_locked":      ["data_purchased",    "task_failed"],
    "data_purchased":    ["result_generated",  "task_failed"],
    "result_generated":  ["user_paid",         "task_failed"],
    "user_paid":         ["lender_repaid",     "task_failed"],
    "lender_repaid":     ["task_closed",       "task_failed"],
    "task_closed":       [],
    "task_failed":       [],
}

# ---------------------------------------------------------------------------
# Next action labels
# ---------------------------------------------------------------------------

_NEXT_ACTION: dict[str, Optional[str]] = {
    "task_created":     "Request Credit",
    "credit_requested": "Approve Credit",
    "credit_approved":  "Fund Escrow",
    "funds_locked":     "Buy Data",
    "data_purchased":   "Generate Report",
    "result_generated": "User Payment",
    "user_paid":        "Settle",
    "lender_repaid":    "Close Task",
    "task_closed":      None,
    "task_failed":      None,
}

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class InvalidTransition(Exception):
    def __init__(self, from_state: str, to_state: str, message: str = "") -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.message = message or f"Cannot transition from '{from_state}' to '{to_state}'"
        super().__init__(self.message)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, [])


def transition(from_state: str, to_state: str) -> str:
    if not can_transition(from_state, to_state):
        raise InvalidTransition(from_state, to_state)
    return to_state


def next_action(current_state: str) -> Optional[str]:
    return _NEXT_ACTION.get(current_state)
