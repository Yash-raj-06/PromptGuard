"""Attack-type categorisation for PromptGuard.

IMPORTANT: this is a transparent RULE-BASED HEURISTIC, not a trained
multi-class classifier. The available datasets only contain binary
Safe/Malicious labels, so there is no honest way to train and validate a
multi-class attack-type model without inventing labels. The output is
therefore explicitly reported as a heuristic estimate with supporting
evidence, and is kept separate from the binary Safe/Malicious prediction.

Only prompts the binary model already classifies as "Malicious" are
categorised. Prompts classified "Safe" return an "unknown" category with
``applicable: false`` so that harmless discussion or quotation of an attack
is not mislabelled as an attack.
"""

import re

CATEGORY_LABELS = {
    "instruction_override": "Instruction Override",
    "jailbreak": "Jailbreak / Role-play",
    "system_prompt_extraction": "System Prompt Extraction",
    "indirect_injection": "Indirect Prompt Injection",
    "obfuscation": "Obfuscation-based Attack",
    "unknown": "Unknown / Uncertain",
}

# Each rule is (compiled pattern, weight, human-readable evidence label).
# Weights are heuristic evidence points, NOT probabilities.
_RULES = {
    "instruction_override": [
        (re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b.{0,45}"
            r"\b(previous|prior|above|earlier|all)\b.{0,30}"
            r"\b(instructions?|rules?|directives?|guidelines?|training|polic(?:y|ies)|prompts?)\b",
            re.IGNORECASE), 3.0, "override of prior instructions"),
        (re.compile(
            r"\b(override|disregard)\b.{0,35}\b(system|developer|safety)\b.{0,25}"
            r"\b(message|prompt|instructions?|directive)\b",
            re.IGNORECASE), 2.0, "override of system/developer instructions"),
        (re.compile(
            r"\b(follow|obey|do)\b.{0,20}\b(my|only my)\b.{0,15}\b(commands?|instructions?|orders?)\b",
            re.IGNORECASE), 1.5, "demand for obedience"),
        (re.compile(r"\b(ignore|disregard|forget)\b.{0,20}\b(above|previous|prior)\b",
                    re.IGNORECASE), 1.5, "ignore the above"),
    ],
    "jailbreak": [
        (re.compile(
            r"\b(jailbreak|jailbroken|DAN|STAN|developer mode|unrestricted mode|maintenance mode)\b",
            re.IGNORECASE), 3.0, "explicit jailbreak/role framing"),
        (re.compile(
            r"\b(act|behave|pretend|role[- ]?play|imagine|simulate)\b.{0,45}"
            r"\b(unrestricted|no restrictions|no rules|no ethical|without (?:any )?"
            r"(?:rules|limits|restrictions)|evil|amoral|jailbroken)\b",
            re.IGNORECASE), 3.0, "persona with removed restrictions"),
        (re.compile(
            r"\b(no (?:content|safety) (?:policy|filters?)|filters? (?:are )?(?:disabled|off)|"
            r"safety (?:checks?|guidelines?) (?:are )?(?:off|disabled)|unrestricted AI)\b",
            re.IGNORECASE), 2.0, "claims that safety filters are disabled"),
        (re.compile(r"\bbypass\b.{0,25}\b(safety|guardrails|filters?|restrictions?|content policy)\b",
                    re.IGNORECASE), 2.0, "explicit safety bypass"),
        (re.compile(r"\b(grandmother|deceased)\b.{0,45}\b(recipe|password|secret|forbidden)\b",
                    re.IGNORECASE), 1.0, "grandmother exploit framing"),
    ],
    "system_prompt_extraction": [
        (re.compile(
            r"\b(system|hidden|initial|developer|confidential|secret)\b.{0,30}"
            r"\b(prompt|instructions?|message|configuration|directives?|rules?)\b",
            re.IGNORECASE), 2.0, "reference to hidden/system instructions"),
        (re.compile(
            r"\b(reveal|show|print|leak|dump|expose|disclose|repeat|output|share|tell|give)\b.{0,35}"
            r"\b(system prompt|hidden instructions?|configuration|system message|"
            r"secret (?:rules|instructions)|initial prompt|developer message|governing instructions)\b",
            re.IGNORECASE), 3.0, "request to reveal system instructions"),
        (re.compile(
            r"\b(what|which|tell me)\b.{0,25}\b(instructions|rules)\b.{0,25}"
            r"\b(given|told|programmed|configured|initiali[sz]ed)\b",
            re.IGNORECASE), 2.0, "question about hidden instructions"),
        (re.compile(
            r"\brepeat\b.{0,25}\b(text|message|prompt)\b.{0,25}"
            r"\b(above|before|verbatim|word for word)\b",
            re.IGNORECASE), 2.0, "repeat the preceding text"),
        (re.compile(r"\b(configuration|instruction template|initiali[sz]ation prompt)\b",
                    re.IGNORECASE), 1.5, "reference to configuration/template"),
    ],
    "indirect_injection": [
        (re.compile(
            r"\b(set aside|suspend|temporarily (?:disable|ignore)|treat .{0,25} as optional|"
            r"consider .{0,25} void|cancell?ed)\b.{0,45}"
            r"\b(guidelines?|rules?|instructions?|restrictions?|safety|concerns?|policy)\b",
            re.IGNORECASE), 3.0, "asks to suspend safety guidance"),
        (re.compile(
            r"\b(assume|pretend)\b.{0,35}\b(prior|previous|earlier)\b.{0,25}"
            r"\b(directions?|instructions?|rules?)\b.{0,30}"
            r"\b(mistake|void|never existed|not apply)\b",
            re.IGNORECASE), 3.0, "reframes prior instructions as void"),
        (re.compile(r"\b(?:the )?(?:rules|instructions) above (?:are|were) (?:a )?(?:test|decoy)\b",
                    re.IGNORECASE), 3.0, "claims prior rules were a test"),
        (re.compile(r"\b(just between us|quietly|do not tell|between you and me)\b.{0,45}"
                    r"\b(reveal|share|tell|disclose)\b",
                    re.IGNORECASE), 2.0, "covert disclosure request"),
        (re.compile(r"\b(before we continue|let us pretend|let's pretend)\b.{0,45}"
                    r"\b(rules|guidelines|restrictions|policy)\b",
                    re.IGNORECASE), 2.0, "conversational reframing of rules"),
    ],
    "obfuscation": [
        (re.compile(r"\b(1gn0r3|1gnore|4ll|pr3v10us|1nstruct10ns|syst3m|pr0mpt|r3v3al)\b",
                    re.IGNORECASE), 4.0, "leetspeak substitution"),
        (re.compile(r"\b[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\s+[A-Za-z]\b"), 3.0, "letters separated by spaces"),
        (re.compile(r"\b[A-Za-z](?:-[A-Za-z]){3,}\b"), 3.0, "letters separated by hyphens"),
        (re.compile(r"\[system\]|<\|im_start\|>|<\|im_end\|>|\[/system\]", re.IGNORECASE),
         4.0, "fake system/chat control tokens"),
        (re.compile(r"[\u200b\u200c\u200d\ufeff]"), 3.0, "zero-width characters"),
        (re.compile(r"\b\w*\d\w*\b.{0,40}\b(ignore|instructions?|system|prompt)\b", re.IGNORECASE),
         1.5, "character/number mixing near injection keywords"),
        (re.compile(r"[A-Za-z0-9+/]{24,}={0,2}"), 1.0, "long encoded-looking token"),
    ],
}

MAX_EVIDENCE = 4


def _evidence_strength(score: float) -> str:
    if score >= 4.0:
        return "high"
    if score >= 2.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "none"


def _matched_snippet(match) -> str:
    text = match.group(0).strip()
    if len(text) > 80:
        text = text[:77].rstrip() + "..."
    return text


def classify_attack_type(prompt: str, prediction: str) -> dict:
    """Return a heuristic attack-type estimate.

    ``prediction`` must be the binary classifier's label ("Safe"/"Malicious").
    The category is only asserted for Malicious prompts.
    """
    base = {
        "category": "unknown",
        "label": CATEGORY_LABELS["unknown"],
        "method": "rule_based_heuristic",
        "is_learned": False,
        "is_heuristic": True,
        "applicable": False,
        "evidence_strength": "none",
        "evidence": [],
        "scores": {},
    }

    if prediction != "Malicious":
        base["reason"] = (
            "The binary classifier rated this prompt Safe, so no attack category "
            "is asserted. Heuristic estimate only."
        )
        return base

    text = prompt or ""
    scores = {}
    evidence = {}
    for category, rules in _RULES.items():
        category_score = 0.0
        category_evidence = []
        for pattern, weight, label in rules:
            match = pattern.search(text)
            if match:
                category_score += weight
                category_evidence.append(
                    {"signal": label, "matched": _matched_snippet(match), "weight": weight}
                )
        scores[category] = round(category_score, 2)
        evidence[category] = category_evidence

    best_category = max(scores, key=lambda key: scores[key])
    best_score = scores[best_category]

    base["scores"] = scores

    # Insufficient evidence -> stay honest with "Unknown / Uncertain".
    if best_score < 2.0:
        base["applicable"] = True
        base["reason"] = (
            "The prompt was classified Malicious, but no single attack category "
            "had enough rule evidence. Reported as Unknown/Uncertain. "
            "Heuristic estimate only."
        )
        return base

    base.update(
        {
            "category": best_category,
            "label": CATEGORY_LABELS[best_category],
            "applicable": True,
            "evidence_strength": _evidence_strength(best_score),
            "evidence": evidence[best_category][:MAX_EVIDENCE],
            "reason": (
                f"Matched {len(evidence[best_category])} "
                f"{CATEGORY_LABELS[best_category].lower()} signal(s) "
                f"(evidence score {best_score:.1f}). This is a transparent "
                "rule-based estimate, not a trained multi-class prediction."
            ),
        }
    )
    return base
