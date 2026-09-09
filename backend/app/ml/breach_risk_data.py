"""Synthetic labeled dataset for the SLA breach-risk classifier.

Per TRD section 4: "SLA breach-risk model: synthetic. Auto-labeled from
ticket age, category, urgency, and queue depth using a simple rule, then a
small classifier trained on that synthetic label." This is explicitly not
real breach data — it's a demonstration of the mechanism (rule -> label ->
trained classifier -> queue reorder), not a production forecasting model.
"""

import random
from dataclasses import dataclass

CATEGORIES = ["payment_failure", "refund_delay", "account_lock", "dispute", "general_query"]

# Rough proxy for how much SLA/compliance pressure a category carries —
# dispute and account_lock skew toward regulatory/security urgency,
# general_query rarely has a hard SLA at all.
CATEGORY_RISK_WEIGHT = {
    "dispute": 0.9,
    "account_lock": 0.8,
    "payment_failure": 0.5,
    "refund_delay": 0.4,
    "general_query": 0.2,
}

# Saturation points for the two continuous inputs — beyond these, more
# age/queue-depth stops adding marginal risk in the synthetic rule.
AGE_SATURATION_MINUTES = 240.0
QUEUE_DEPTH_SATURATION = 20.0

BREACH_LABEL_THRESHOLD = 0.5
LABEL_NOISE_RATE = 0.05


@dataclass(frozen=True)
class BreachRiskExample:
    age_minutes: float
    category: str
    urgency_score: float
    queue_depth: int
    breach_risk_label: int  # 0/1, the synthetic ground truth the classifier learns


def synthetic_breach_risk_score(
    age_minutes: float, category: str, urgency_score: float, queue_depth: int
) -> float:
    """The hand-written rule the classifier is trained to approximate —
    a weighted blend of normalized age, category risk, urgency, and how
    backed up the queue is.
    """
    age_component = min(age_minutes / AGE_SATURATION_MINUTES, 1.0)
    queue_component = min(queue_depth / QUEUE_DEPTH_SATURATION, 1.0)
    category_component = CATEGORY_RISK_WEIGHT.get(category, 0.3)

    return (
        0.35 * age_component
        + 0.30 * category_component
        + 0.20 * urgency_score
        + 0.15 * queue_component
    )


def generate_dataset(n: int = 1500, seed: int = 42) -> list[BreachRiskExample]:
    rng = random.Random(seed)
    examples = []

    for _ in range(n):
        age_minutes = rng.uniform(0, 480)
        category = rng.choice(CATEGORIES)
        urgency_score = rng.uniform(0, 1)
        queue_depth = rng.randint(0, 30)

        score = synthetic_breach_risk_score(age_minutes, category, urgency_score, queue_depth)
        label = 1 if score >= BREACH_LABEL_THRESHOLD else 0

        # A deterministic rule gives a trivially separable dataset — flip a
        # small fraction of labels so the classifier has to actually
        # generalize instead of memorizing a linear boundary exactly.
        if rng.random() < LABEL_NOISE_RATE:
            label = 1 - label

        examples.append(
            BreachRiskExample(
                age_minutes=age_minutes,
                category=category,
                urgency_score=urgency_score,
                queue_depth=queue_depth,
                breach_risk_label=label,
            )
        )

    return examples
