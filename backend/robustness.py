"""Controlled robustness testing for PromptGuard.

This module applies deterministic, local text transformations and measures how
often the classifier's predicted label changes. It is intentionally SEPARATE
from normal prediction and never modifies the original prompt or the model.

Paraphrasing here is a small, deterministic synonym substitution, not an LLM or
a true paraphrase model. A handful of transformations proves nothing about
resistance to arbitrary attacks; results are reported as a limited consistency
check only.
"""

import re

# Small, documented synonym map used by the limited "paraphrase" transform.
# This is NOT a general paraphrase model.
SYNONYMS = {
    "ignore": "disregard",
    "disregard": "ignore",
    "previous": "prior",
    "prior": "earlier",
    "instructions": "directions",
    "instruction": "direction",
    "reveal": "show",
    "show": "display",
    "all": "every",
    "system": "platform",
    "prompt": "request",
    "hidden": "secret",
    "obey": "follow",
    "unrestricted": "unlimited",
    "rules": "guidelines",
    "policy": "guideline",
    "policies": "guidelines",
    "safety": "security",
    "secret": "private",
    "confidential": "private",
    "forget": "disregard",
    "override": "overrule",
    "bypass": "circumvent",
    "tell": "say",
}


class UnsupportedTransform(Exception):
    """Raised when a transform cannot be applied to the given text."""


# ---------------------------------------------------------------------------
# Individual transforms
# ---------------------------------------------------------------------------

def _uppercase(text):
    return text.upper()


def _extra_whitespace(text):
    spaced = re.sub(r"\s+", "  ", text.strip())
    return f"  {spaced}  "


def _punctuation_spacing(text):
    return re.sub(r"([,.;:!?])", r" \1 ", text)


def _strip_punctuation(text):
    return re.sub(r"[^\w\s]", "", text)


def _leet_substitution(text):
    return text.translate(str.maketrans("aeios", "43105"))


def _spaced_letters(text):
    return re.sub(r"[A-Za-z]{3,}", lambda m: " ".join(m.group(0)), text)


def _hyphenated_letters(text):
    return re.sub(r"[A-Za-z]{3,}", lambda m: "-".join(m.group(0)), text)


def _swap_last_two(match):
    word = match.group(0)
    return word[:-2] + word[-1] + word[-2]


def _typo_transposition(text):
    return re.sub(r"[A-Za-z]{4,}", _swap_last_two, text)


def _paraphrase(text):
    replaced = {"count": 0}

    def swap(match):
        word = match.group(0)
        replacement = SYNONYMS.get(word.lower())
        if not replacement:
            return word
        replaced["count"] += 1
        if word[0].isupper():
            return replacement.capitalize()
        return replacement

    result = re.sub(r"\b[A-Za-z]+\b", swap, text)
    if replaced["count"] == 0:
        raise UnsupportedTransform("No known synonyms were present in this prompt.")
    return result


# (name, description, callable)
TRANSFORMS = [
    ("uppercase", "Convert all characters to uppercase.", _uppercase),
    ("extra_whitespace", "Double the spaces and add leading/trailing whitespace.", _extra_whitespace),
    ("punctuation_spacing", "Insert spaces around punctuation.", _punctuation_spacing),
    ("strip_punctuation", "Remove all punctuation characters.", _strip_punctuation),
    ("character_substitution", "Leetspeak character substitution (a=4, e=3, i=1, o=0, s=5).", _leet_substitution),
    ("spaced_letters", "Separate the letters of each word with spaces.", _spaced_letters),
    ("hyphenated_letters", "Separate the letters of each word with hyphens.", _hyphenated_letters),
    ("typo_transposition", "Swap the last two letters of longer words (spelling perturbation).", _typo_transposition),
    ("paraphrase", "Limited synonym substitution (documented small word map).", _paraphrase),
]


def apply_transformations(prompt: str, include_paraphrase: bool = True) -> list:
    """Apply every transform and report per-transform status.

    Does not mutate ``prompt``. Never raises for an individual transform.
    """
    results = []
    for name, description, func in TRANSFORMS:
        entry = {
            "name": name,
            "description": description,
            "status": "ok",
            "transformed_text": None,
            "reason": None,
        }
        if name == "paraphrase" and not include_paraphrase:
            entry["status"] = "skipped"
            entry["reason"] = "Paraphrase disabled for this request."
            results.append(entry)
            continue
        try:
            transformed = func(prompt)
            if not isinstance(transformed, str) or not transformed.strip():
                entry["status"] = "skipped"
                entry["reason"] = "Transform produced empty output."
            elif transformed == prompt:
                entry["status"] = "skipped"
                entry["reason"] = "Transform produced no change."
            else:
                entry["transformed_text"] = transformed
        except UnsupportedTransform as exc:
            entry["status"] = "skipped"
            entry["reason"] = str(exc)
        except Exception:  # noqa: BLE001 - a failing transform must not break others
            entry["status"] = "failed"
            entry["reason"] = "This transformation could not be applied."
        results.append(entry)
    return results


def compute_consistency(original_label: str, evaluated_labels: list):
    """Return the percentage of variants that kept the original label.

    consistency = 100 * (unchanged predictions) / (evaluated transformations)

    Returns ``None`` when no transformation could be evaluated.
    """
    if not evaluated_labels:
        return None
    unchanged = sum(1 for label in evaluated_labels if label == original_label)
    return round(100.0 * unchanged / len(evaluated_labels), 2)


def evaluate_robustness(prompt: str, predict_fn, include_paraphrase: bool = True) -> dict:
    """Run all transforms through ``predict_fn`` and summarise consistency.

    ``predict_fn(text)`` must return a dict with at least ``prediction``,
    ``safe_probability`` and ``malicious_probability``.
    """
    original = predict_fn(prompt)
    variants = apply_transformations(prompt, include_paraphrase=include_paraphrase)

    evaluated_labels = []
    for variant in variants:
        if variant["status"] != "ok":
            continue
        try:
            prediction = predict_fn(variant["transformed_text"])
            variant["prediction"] = prediction["prediction"]
            variant["safe_probability"] = prediction["safe_probability"]
            variant["malicious_probability"] = prediction["malicious_probability"]
            variant["changed"] = prediction["prediction"] != original["prediction"]
            evaluated_labels.append(prediction["prediction"])
        except Exception:  # noqa: BLE001
            variant["status"] = "failed"
            variant["reason"] = "Prediction failed for this transformation."
            variant["transformed_text"] = None

    evaluated = sum(1 for v in variants if v["status"] == "ok")
    failed = sum(1 for v in variants if v["status"] == "failed")
    skipped = sum(1 for v in variants if v["status"] == "skipped")
    changed = sum(1 for v in variants if v.get("changed") is True)

    consistency = compute_consistency(original["prediction"], evaluated_labels)

    summary = {
        "total_transformations": len(variants),
        "evaluated": evaluated,
        "failed": failed,
        "skipped": skipped,
        "changed_predictions": changed,
        "unchanged_predictions": evaluated - changed,
        "consistency_score": consistency,
        "consistency_formula": (
            "100 * unchanged_predictions / evaluated transformations"
        ),
    }

    notes = [
        "This tests a small, deterministic set of local transformations only.",
        "A high consistency score does not prove robustness against real attacks.",
        "The original prompt and the production model are not modified.",
    ]

    return {
        "original": {
            "prediction": original["prediction"],
            "safe_probability": original["safe_probability"],
            "malicious_probability": original["malicious_probability"],
        },
        "transformations": variants,
        "summary": summary,
        "notes": notes,
    }
