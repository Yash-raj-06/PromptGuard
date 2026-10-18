"""Defensive decision policy for PromptGuard.

Maps the classifier's malicious probability to one of three decision-support
actions: Allow, Flag for Review, or Block. This is a transparent threshold
policy, not an enforcement guarantee, and it does not claim that a high
probability proves malicious intent (or that a low one proves safety).

Thresholds are configurable with environment variables:

    PROMPTGUARD_BLOCK_THRESHOLD   (default 0.85)
    PROMPTGUARD_REVIEW_THRESHOLD  (default 0.40)

Borderline/uncertain outputs (>= review threshold) are routed to review.
"""

import os

DEFAULT_BLOCK_THRESHOLD = 0.85
DEFAULT_REVIEW_THRESHOLD = 0.40

DISCLAIMER = (
    "Decision-support recommendation only. Probabilities are model estimates, "
    "not proof of malicious intent or safety. No enforcement integration is "
    "attached to this action."
)


def _read_threshold(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    if not 0.0 <= value <= 1.0:
        return default
    return value


def get_thresholds():
    """Return the active (block, review) thresholds, clamped to a valid order."""
    block = _read_threshold("PROMPTGUARD_BLOCK_THRESHOLD", DEFAULT_BLOCK_THRESHOLD)
    review = _read_threshold("PROMPTGUARD_REVIEW_THRESHOLD", DEFAULT_REVIEW_THRESHOLD)
    if review > block:
        # Invalid ordering: fall back to safe documented defaults.
        block, review = DEFAULT_BLOCK_THRESHOLD, DEFAULT_REVIEW_THRESHOLD
    return block, review


def recommend_action(malicious_probability) -> dict:
    """Return the recommended action and a short transparent reason.

    ``malicious_probability`` is a fraction in [0, 1].
    """
    try:
        probability = float(malicious_probability)
    except (TypeError, ValueError):
        probability = 0.0
    if not 0.0 <= probability <= 1.0:
        probability = min(1.0, max(0.0, probability))

    block, review = get_thresholds()
    percentage = round(probability * 100, 2)

    if probability >= block:
        action = "Block"
        reason = (
            f"Malicious probability {percentage}% is at or above the block "
            f"threshold ({round(block * 100, 1)}%)."
        )
    elif probability >= review:
        action = "Flag for Review"
        reason = (
            f"Malicious probability {percentage}% is uncertain/borderline "
            f"(review threshold {round(review * 100, 1)}%, block threshold "
            f"{round(block * 100, 1)}%). Route to human review."
        )
    else:
        action = "Allow"
        reason = (
            f"Malicious probability {percentage}% is below the review threshold "
            f"({round(review * 100, 1)}%). No automatic block is recommended."
        )

    return {
        "action": action,
        "reason": reason,
        "malicious_probability": percentage,
        "thresholds": {
            "block": block,
            "review": review,
        },
        "is_decision_support": True,
        "disclaimer": DISCLAIMER,
    }
