"""Inference wrapper around the trained category/urgency classifiers."""

from dataclasses import dataclass
from functools import lru_cache

import joblib

from app.ml.train_classifier import ARTIFACT_PATH

# Below this confidence, don't trust the winning urgency class — fall back
# toward a safe middle score rather than guessing high or low (App Flow,
# "Failure paths to handle": low classifier confidence -> safe middle urgency).
LOW_CONFIDENCE_THRESHOLD = 0.45

_URGENCY_SCORE_BY_LEVEL = {"low": 0.0, "medium": 0.5, "high": 1.0}


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    category_confidence: float
    urgency_score: float
    urgency_confidence: float


@lru_cache(maxsize=1)
def _load_artifact() -> dict:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"No trained classifier artifact at {ARTIFACT_PATH}. Run "
            "`uv run python -m app.ml.train_classifier` first."
        )
    return joblib.load(ARTIFACT_PATH)


def classify(text: str) -> ClassificationResult:
    artifact = _load_artifact()
    category_pipeline = artifact["category_pipeline"]
    urgency_pipeline = artifact["urgency_pipeline"]

    category_proba = category_pipeline.predict_proba([text])[0]
    category_classes = category_pipeline.classes_
    category_idx = category_proba.argmax()
    category = str(category_classes[category_idx])
    category_confidence = float(category_proba[category_idx])

    urgency_proba = urgency_pipeline.predict_proba([text])[0]
    urgency_classes = urgency_pipeline.classes_
    urgency_idx = urgency_proba.argmax()
    urgency_confidence = float(urgency_proba[urgency_idx])

    # Continuous urgency_score as a probability-weighted blend across all
    # three classes, not just the winning label — a low-confidence "high"
    # prediction with real probability mass on "medium"/"low" naturally
    # pulls the score down instead of committing to the extreme.
    urgency_score = sum(
        _URGENCY_SCORE_BY_LEVEL[level] * float(prob)
        for level, prob in zip(urgency_classes, urgency_proba)
    )

    if urgency_confidence < LOW_CONFIDENCE_THRESHOLD:
        urgency_score = (urgency_score + 0.5) / 2

    return ClassificationResult(
        category=category,
        category_confidence=category_confidence,
        urgency_score=urgency_score,
        urgency_confidence=urgency_confidence,
    )
