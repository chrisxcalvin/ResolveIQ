"""Trains the SLA breach-risk classifier (Feature 3).

A small classifier (logistic regression over age/category/urgency/queue-depth
features) trained on the synthetic rule in app/ml/breach_risk_data.py —
mirrors the Day 2 category/urgency classifier's structure: evaluate on a
held-out split first, then refit on the full dataset for the shipped artifact.
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ml.breach_risk_data import CATEGORIES, generate_dataset

ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "breach_risk.joblib"

_FEATURE_COLUMNS = ["age_minutes", "category", "urgency_score", "queue_depth"]


def _make_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            ("category", OneHotEncoder(categories=[CATEGORIES], handle_unknown="ignore"), ["category"]),
        ],
        remainder="passthrough",
    )
    return Pipeline(
        [
            ("preprocess", preprocessor),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def _to_frame(examples) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age_minutes": [e.age_minutes for e in examples],
            "category": [e.category for e in examples],
            "urgency_score": [e.urgency_score for e in examples],
            "queue_depth": [e.queue_depth for e in examples],
        }
    )


def main() -> None:
    examples = generate_dataset()
    rows = _to_frame(examples)
    labels = [e.breach_risk_label for e in examples]

    rows_train, rows_test, labels_train, labels_test = train_test_split(
        rows, labels, test_size=0.2, random_state=42, stratify=labels
    )

    pipeline = _make_pipeline().fit(rows_train, labels_train)
    accuracy = accuracy_score(labels_test, pipeline.predict(rows_test))
    print(f"Dataset size: {len(examples)} ({len(rows_train)} train / {len(rows_test)} test)")
    print(f"Breach-risk held-out accuracy: {accuracy:.3f}")

    # Refit on the full dataset for the artifact that actually ships.
    pipeline = _make_pipeline().fit(rows, labels)

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline}, ARTIFACT_PATH)
    print(f"Saved artifact to {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
