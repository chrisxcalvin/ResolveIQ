"""Trains the category + urgency classifiers.

Structured/schema-validated output from a small trained classifier, not an
LLM guess (TRD section 2/3) — two TF-IDF + Logistic Regression pipelines,
one per label. Evaluates on a held-out split first (the PRD's "measurable
accuracy on a held-out test set" goal), then refits on the full dataset for
the artifact that actually ships.
"""

from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from app.ml.data import CATEGORIES, URGENCY_LEVELS, generate_dataset

ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "classifier.joblib"


def _make_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def main() -> None:
    examples = generate_dataset()
    texts = [e.text for e in examples]
    categories = [e.category for e in examples]
    urgencies = [e.urgency for e in examples]
    strata = [f"{c}|{u}" for c, u in zip(categories, urgencies)]

    (
        texts_train,
        texts_test,
        cat_train,
        cat_test,
        urg_train,
        urg_test,
    ) = train_test_split(texts, categories, urgencies, test_size=0.2, random_state=42, stratify=strata)

    category_pipeline = _make_pipeline().fit(texts_train, cat_train)
    urgency_pipeline = _make_pipeline().fit(texts_train, urg_train)

    category_accuracy = accuracy_score(cat_test, category_pipeline.predict(texts_test))
    urgency_accuracy = accuracy_score(urg_test, urgency_pipeline.predict(texts_test))

    print(f"Dataset size: {len(examples)} ({len(texts_train)} train / {len(texts_test)} test)")
    print(f"Category held-out accuracy: {category_accuracy:.3f}")
    print(f"Urgency held-out accuracy:  {urgency_accuracy:.3f}")

    # Refit on the full dataset for the artifact that actually ships.
    category_pipeline = _make_pipeline().fit(texts, categories)
    urgency_pipeline = _make_pipeline().fit(texts, urgencies)

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "category_pipeline": category_pipeline,
            "urgency_pipeline": urgency_pipeline,
            "categories": CATEGORIES,
            "urgency_levels": URGENCY_LEVELS,
        },
        ARTIFACT_PATH,
    )
    print(f"Saved artifact to {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
