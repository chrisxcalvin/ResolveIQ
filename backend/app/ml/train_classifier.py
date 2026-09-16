"""Trains the category + urgency classifiers.

Data provenance differs between the two labels, deliberately — see DATA.md:

* CATEGORY is trained on REAL data: ~10k CFPB Consumer Complaint Database
  narratives (app/ml/cfpb_data.py), labelled by mapping each complaint's own
  CFPB `issue` field onto ResolveIQ's 5 categories.

* URGENCY stays on the SYNTHETIC template data (app/ml/data.py), because
  CFPB carries no urgency ground truth and inventing one would produce
  another meaningless accuracy number. Its reported accuracy is therefore
  NOT a generalisation estimate and is labelled as such below.

Before trusting the category split, this checks for near-duplicate leakage
across the train/test boundary — the failure that made the old
template-generated dataset report a fake 1.000.
"""

from collections import Counter
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.ml.cfpb_data import CATEGORIES as CFPB_CATEGORIES
from app.ml.cfpb_data import load as load_cfpb
from app.ml.data import URGENCY_LEVELS, generate_dataset

ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "classifier.joblib"

# Cosine similarity above which two narratives are treated as near-duplicates.
NEAR_DUPLICATE_THRESHOLD = 0.9


def _make_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=2000)),
        ]
    )


def _drop_near_duplicates(texts: list[str], labels: list[str]) -> tuple[list[str], list[str]]:
    """Removes near-duplicate narratives before splitting.

    Exact string dedup isn't enough: CFPB contains complaints that differ
    only in whitespace/punctuation, plus boilerplate that consumers copy
    from advocacy sites and file near-verbatim. Left in, those land on both
    sides of the split and inflate the score — a milder version of exactly
    the leakage that made the old template dataset report 1.000.

    Keeps the first occurrence of each near-duplicate cluster.
    """
    vec = TfidfVectorizer(ngram_range=(1, 1), min_df=1, sublinear_tf=True)
    matrix = vec.fit_transform(texts)

    drop: set[int] = set()
    for start in range(0, matrix.shape[0], 256):
        block = matrix[start : start + 256]
        sims = (block @ matrix.T).toarray()
        for local_i, row in enumerate(sims):
            i = start + local_i
            if i in drop:
                continue
            # Only look forward, so the earliest member of a cluster survives.
            for j in (row[i + 1 :] >= NEAR_DUPLICATE_THRESHOLD).nonzero()[0]:
                drop.add(i + 1 + int(j))

    if drop:
        print(f"  dropped {len(drop)} near-duplicate narrative(s) before splitting")
    kept = [k for k in range(len(texts)) if k not in drop]
    return [texts[k] for k in kept], [labels[k] for k in kept]


def _check_split_leakage(train_texts: list[str], test_texts: list[str]) -> int:
    """Counts test rows that are near-duplicates of some training row.

    Real complaint narratives are independently written, so this should be
    near zero — unlike the template-generated data it replaced, where every
    test row shared a phrasing skeleton with training rows and the split was
    effectively meaningless.
    """
    vec = TfidfVectorizer(ngram_range=(1, 1), min_df=1, sublinear_tf=True)
    train_m = vec.fit_transform(train_texts)
    test_m = vec.transform(test_texts)

    leaked = 0
    worst = 0.0
    # Chunked so the dense similarity block stays small.
    for start in range(0, test_m.shape[0], 256):
        block = test_m[start : start + 256]
        sims = (block @ train_m.T).toarray()
        block_max = sims.max(axis=1)
        worst = max(worst, float(block_max.max()))
        leaked += int((block_max >= NEAR_DUPLICATE_THRESHOLD).sum())

    print(
        f"  near-duplicate check: {leaked} of {len(test_texts)} test rows have a "
        f"training row at cosine >= {NEAR_DUPLICATE_THRESHOLD} "
        f"(highest single similarity seen: {worst:.3f})"
    )
    return leaked


def _train_category() -> Pipeline:
    print("\n=== CATEGORY classifier — REAL CFPB data ===")
    complaints = load_cfpb()

    # Drop exact duplicate narratives (same text filed under different
    # complaint ids) so identical text can't land on both sides of the split.
    seen: set[str] = set()
    deduped = []
    for c in complaints:
        if c.text in seen:
            continue
        seen.add(c.text)
        deduped.append(c)
    if len(deduped) != len(complaints):
        print(f"  dropped {len(complaints) - len(deduped)} exact-duplicate narrative(s)")

    texts = [c.text for c in deduped]
    labels = [c.category for c in deduped]
    texts, labels = _drop_near_duplicates(texts, labels)

    print(f"  dataset: {len(texts)} narratives across {len(set(labels))} categories")
    for cat, n in sorted(Counter(labels).items()):
        print(f"    {n:>5}  {cat}")

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    print(f"  split: {len(x_train)} train / {len(x_test)} test (stratified)")

    _check_split_leakage(x_train, x_test)

    pipeline = _make_pipeline().fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    accuracy = accuracy_score(y_test, predictions)

    print(f"\n  HELD-OUT ACCURACY: {accuracy:.3f}")
    print("\n" + classification_report(y_test, predictions, digits=3))

    labels_sorted = sorted(set(labels))
    cm = confusion_matrix(y_test, predictions, labels=labels_sorted)
    width = max(len(c) for c in labels_sorted)
    print("  confusion matrix (rows = true, cols = predicted):")
    print(" " * (width + 4) + "  ".join(c[:8].rjust(8) for c in labels_sorted))
    for label, row in zip(labels_sorted, cm):
        print(f"    {label.rjust(width)}  " + "  ".join(str(v).rjust(8) for v in row))

    # Refit on everything for the artifact that ships.
    return _make_pipeline().fit(texts, labels)


def _train_urgency() -> Pipeline:
    print("\n=== URGENCY classifier — SYNTHETIC template data ===")
    print("  CFPB has no urgency ground truth, so this stays on generated")
    print("  templates. Its accuracy below is a pipeline sanity check, NOT a")
    print("  generalisation estimate — train/test rows share phrasing skeletons.")

    examples = generate_dataset()
    texts = [e.text for e in examples]
    urgencies = [e.urgency for e in examples]

    x_train, x_test, y_train, y_test = train_test_split(
        texts, urgencies, test_size=0.2, random_state=42, stratify=urgencies
    )
    pipeline = _make_pipeline().fit(x_train, y_train)
    accuracy = accuracy_score(y_test, pipeline.predict(x_test))
    print(f"  dataset: {len(texts)} generated examples")
    print(f"  held-out accuracy (NOT a generalisation estimate): {accuracy:.3f}")

    return _make_pipeline().fit(texts, urgencies)


def main() -> None:
    category_pipeline = _train_category()
    urgency_pipeline = _train_urgency()

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "category_pipeline": category_pipeline,
            "urgency_pipeline": urgency_pipeline,
            "categories": CFPB_CATEGORIES,
            "urgency_levels": URGENCY_LEVELS,
            "category_data_source": "cfpb",
            "urgency_data_source": "synthetic_templates",
        },
        ARTIFACT_PATH,
    )
    print(f"\nSaved artifact to {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
