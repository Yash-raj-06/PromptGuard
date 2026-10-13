"""PromptGuard - model training and honest, leakage-safe evaluation.

Produces the artifacts the FastAPI backend loads:
    backend/model.pkl        (fitted classifier operating on TF-IDF vectors)
    backend/vectorizer.pkl   (fitted TF-IDF transformer)
    backend/model_info.json  (metadata + evaluation results)

Evaluation design (leakage-safe):
    * 0 = Safe, 1 = Malicious (contract expected by main.py).
    * The authored dataset is split into train/test BEFORE any fitting.
    * Model selection uses 5-fold cross-validation on training data only,
      with the whole feature+classifier PIPELINE inside GridSearchCV. This
      means TF-IDF is fitted separately inside every CV fold, so validation
      fold text never influences the vocabulary / IDF of that fold.
    * After selection, the best pipeline is refit on the full permitted
      training set (GridSearchCV refit=True).
    * dataset/external_test.csv (deepset/prompt-injections test split) is
      NEVER used for training or model selection. It is the independent,
      final evaluation only.
    * dataset/external_train.csv is real data added only for the
      "synthetic_plus_real" strategy.

Two training strategies are compared so the value of real data is visible:
    * synthetic_only      : authored prompts only
    * synthetic_plus_real : authored prompts + external real train split
The saved production model uses the synthetic_plus_real strategy.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

# ==================================================
# 1. Paths and configuration
# ==================================================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

DATASET_PATH = PROJECT_DIR / "dataset" / "prompts.csv"
EXTERNAL_TRAIN_PATH = PROJECT_DIR / "dataset" / "external_train.csv"
EXTERNAL_TEST_PATH = PROJECT_DIR / "dataset" / "external_test.csv"
MODEL_PATH = BACKEND_DIR / "model.pkl"
VECTORIZER_PATH = BACKEND_DIR / "vectorizer.pkl"
MODEL_INFO_PATH = BACKEND_DIR / "model_info.json"

RANDOM_STATE = 42
TEST_SIZE = 0.25
PRODUCTION_STRATEGY = "synthetic_plus_real"

LABEL_TO_INT = {"safe": 0, "malicious": 1}
INT_TO_LABEL = {0: "Safe", 1: "Malicious"}


# ==================================================
# 2. Data loading / validation
# ==================================================

def _clean(frame):
    frame = frame.dropna(subset=["prompt", "label"]).copy()
    frame["prompt"] = frame["prompt"].astype(str).str.strip()
    frame["label"] = frame["label"].astype(str).str.strip().str.lower()
    return frame[frame["prompt"] != ""]


def load_authored():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")
    data = pd.read_csv(DATASET_PATH)
    if not {"prompt", "label"}.issubset(data.columns):
        raise ValueError("CSV must contain 'prompt' and 'label' columns.")

    original_rows = len(data)
    data = _clean(data)
    if not set(data["label"].unique()).issubset(set(LABEL_TO_INT)):
        raise ValueError("Labels must be 'safe' or 'malicious'.")

    before = len(data)
    data = data.drop_duplicates(subset=["prompt"]).copy()
    duplicates_removed = before - len(data)

    conflicts = data.groupby("prompt")["label"].nunique()
    conflict_prompts = conflicts[conflicts > 1].index
    contradictory_removed = 0
    if len(conflict_prompts) > 0:
        print(f"WARNING: removing {len(conflict_prompts)} contradictory prompt(s).")
        data = data[~data["prompt"].isin(conflict_prompts)].copy()
        contradictory_removed = len(conflict_prompts)

    if data["label"].value_counts().min() < 2:
        raise ValueError("At least two examples of each class are required.")

    stats = {
        "rows_in_file": original_rows,
        "duplicates_removed": int(duplicates_removed),
        "contradictory_removed": int(contradictory_removed),
        "rows_used": int(len(data)),
    }
    return data, stats


def load_external(path, exclude_prompts):
    info = {
        "path": str(path.relative_to(PROJECT_DIR)),
        "source": "deepset/prompt-injections (HuggingFace)",
        "license": "Apache-2.0 / CC-BY-4.0",
        "samples": 0,
    }
    if not path.exists():
        info["status"] = "missing"
        return None, info

    data = pd.read_csv(path)
    if not {"prompt", "label"}.issubset(data.columns):
        info["status"] = "invalid"
        return None, info

    data = _clean(data)
    data = data[data["label"].isin(LABEL_TO_INT.keys())]
    data = data[~data["prompt"].isin(exclude_prompts)]
    data = data.drop_duplicates(subset=["prompt"]).copy()
    data["labels"] = data["label"].map(LABEL_TO_INT)
    info["samples"] = int(len(data))
    info["safe"] = int((data["labels"] == 0).sum())
    info["malicious"] = int((data["labels"] == 1).sum())
    info["status"] = "ok"
    return data, info


# ==================================================
# 3. Evaluation helpers
# ==================================================

def compute_metrics(y_true, predictions):
    matrix = confusion_matrix(y_true, predictions, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()

    per_class = {}
    for label_int, label_name in INT_TO_LABEL.items():
        per_class[label_name] = {
            "precision": round(float(precision_score(
                y_true, predictions, pos_label=label_int, zero_division=0)), 4),
            "recall": round(float(recall_score(
                y_true, predictions, pos_label=label_int, zero_division=0)), 4),
            "f1": round(float(f1_score(
                y_true, predictions, pos_label=label_int, zero_division=0)), 4),
        }

    return {
        "accuracy": round(float(accuracy_score(y_true, predictions)), 4),
        "precision": per_class["Malicious"]["precision"],
        "recall": per_class["Malicious"]["recall"],
        "f1_score": per_class["Malicious"]["f1"],
        "macro_f1": round(float(f1_score(y_true, predictions, average="macro")), 4),
        "weighted_f1": round(float(f1_score(y_true, predictions, average="weighted")), 4),
        "per_class": per_class,
        "confusion_matrix_values": matrix.tolist(),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }


def report_text(y_true, predictions):
    return classification_report(
        y_true, predictions, labels=[0, 1],
        target_names=["Safe", "Malicious"], zero_division=0,
    )


# ==================================================
# 4. Pipelines (TF-IDF + classifier) for leakage-safe CV
# ==================================================
# The whole pipeline is passed to GridSearchCV, so the TF-IDF step is fit on
# the training part of every fold and applied to the validation part. This is
# what prevents validation-fold text from leaking into the vocabulary/IDF.

def word_tfidf():
    return TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), sublinear_tf=True,
        min_df=1, strip_accents="unicode",
    )


def word_char_tfidf():
    return FeatureUnion([
        ("word", TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), sublinear_tf=True,
            min_df=1, strip_accents="unicode")),
        ("char", TfidfVectorizer(
            lowercase=True, analyzer="char_wb", ngram_range=(3, 5),
            sublinear_tf=True, min_df=1, strip_accents="unicode")),
    ])


def build_candidates():
    return {
        "word-tfidf + LogisticRegression": (
            Pipeline([
                ("features", word_tfidf()),
                ("clf", LogisticRegression(
                    max_iter=1000, class_weight="balanced",
                    random_state=RANDOM_STATE)),
            ]),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
        "word-tfidf + MultinomialNB": (
            Pipeline([("features", word_tfidf()), ("clf", MultinomialNB())]),
            {"clf__alpha": [0.1, 0.5, 1.0]},
        ),
        "word-tfidf + LinearSVC(calibrated)": (
            Pipeline([
                ("features", word_tfidf()),
                ("clf", CalibratedClassifierCV(
                    LinearSVC(random_state=RANDOM_STATE), cv=3)),
            ]),
            {"clf__estimator__C": [0.1, 1.0]},
        ),
        "word+char-tfidf + LogisticRegression": (
            Pipeline([
                ("features", word_char_tfidf()),
                ("clf", LogisticRegression(
                    max_iter=1000, class_weight="balanced",
                    random_state=RANDOM_STATE)),
            ]),
            {"clf__C": [0.1, 1.0, 10.0]},
        ),
    }


def run_strategy(train_texts, y_train, auth_test, ext_test):
    """Compare pipelines using training-only CV (TF-IDF fit inside each fold)."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    results = {}
    for name, (pipeline, grid) in build_candidates().items():
        search = GridSearchCV(pipeline, grid, scoring="f1_macro", cv=cv, n_jobs=1)
        search.fit(train_texts, y_train)  # raw text -> pipeline vectorizes per fold
        best = search.best_estimator_
        auth_metrics = compute_metrics(auth_test["labels"], best.predict(auth_test["prompt"]))
        ext_metrics = compute_metrics(ext_test["labels"], best.predict(ext_test["prompt"]))
        results[name] = {
            "pipeline": best,
            "cv_macro_f1": round(float(search.best_score_), 4),
            "best_params": search.best_params_,
            "auth": auth_metrics,
            "ext": ext_metrics,
        }
    return results


# ==================================================
# 5. Train, compare, select, evaluate
# ==================================================

def train_model():
    print("\n" + "=" * 66)
    print("                   PROMPTGUARD MODEL TRAINING")
    print("=" * 66)

    data, stats = load_authored()
    labels = data["label"].map(LABEL_TO_INT)

    print(f"\nRows in file:           {stats['rows_in_file']}")
    print(f"Duplicates removed:     {stats['duplicates_removed']}")
    print(f"Contradictory removed:  {stats['contradictory_removed']}")
    print(f"Authored samples:       {len(data)} "
          f"(safe={int((labels == 0).sum())}, malicious={int((labels == 1).sum())})")

    X_train, X_test, y_train, y_test = train_test_split(
        data["prompt"], labels, test_size=TEST_SIZE,
        random_state=RANDOM_STATE, stratify=labels,
    )
    auth_test = pd.DataFrame({"prompt": X_test.reset_index(drop=True),
                              "labels": y_test.reset_index(drop=True)})

    print(f"Authored train: {len(X_train)}  authored test: {len(X_test)}  "
          f"(seed={RANDOM_STATE})")

    exclude = set(data["prompt"])
    external_train, ext_train_info = load_external(EXTERNAL_TRAIN_PATH, exclude)
    exclude = exclude | (set(external_train["prompt"]) if external_train is not None else set())
    external_test, ext_test_info = load_external(EXTERNAL_TEST_PATH, exclude)

    if external_test is None or len(external_test) == 0:
        raise RuntimeError("Independent external test set is required but unavailable.")

    print(f"External TRAIN (real):   {ext_train_info.get('samples', 0)}")
    print(f"External TEST (holdout): {ext_test_info['samples']} "
          f"(safe={ext_test_info.get('safe')}, malicious={ext_test_info.get('malicious')})")

    # Strategy A: authored only.
    results = {"synthetic_only": run_strategy(X_train, y_train, auth_test, external_test)}

    # Strategy B: authored + real external train.
    if external_train is not None and len(external_train) > 0:
        combined_texts = pd.concat(
            [X_train.reset_index(drop=True), external_train["prompt"].reset_index(drop=True)],
            ignore_index=True,
        )
        combined_labels = pd.concat(
            [y_train.reset_index(drop=True), external_train["labels"].reset_index(drop=True)],
            ignore_index=True,
        )
        results["synthetic_plus_real"] = run_strategy(
            combined_texts, combined_labels, auth_test, external_test
        )
    else:
        results["synthetic_plus_real"] = results["synthetic_only"]

    # Dummy reference (strategy A data only), also via a pipeline.
    dummy_pipe = Pipeline([
        ("features", word_tfidf()),
        ("clf", DummyClassifier(strategy="most_frequent", random_state=RANDOM_STATE)),
    ])
    dummy_pipe.fit(X_train, y_train)
    dummy_ext = compute_metrics(external_test["labels"], dummy_pipe.predict(external_test["prompt"]))

    # Comparison table.
    print("\nModel comparison (macro-F1; CV uses pipeline so TF-IDF is per-fold):")
    header = f"  {'strategy':<20}{'algorithm':<38}{'cv':>7}{'auth':>8}{'external':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    comparison = {}
    for strategy, algos in results.items():
        comparison[strategy] = {}
        for name, res in algos.items():
            comparison[strategy][name] = {
                "cv_macro_f1": res["cv_macro_f1"],
                "best_params": res["best_params"],
                "auth_test": {"accuracy": res["auth"]["accuracy"],
                              "macro_f1": res["auth"]["macro_f1"]},
                "external_test": {"accuracy": res["ext"]["accuracy"],
                                  "macro_f1": res["ext"]["macro_f1"]},
            }
            print(f"  {strategy:<20}{name:<38}{res['cv_macro_f1']:>7.4f}"
                  f"{res['auth']['macro_f1']:>8.4f}{res['ext']['macro_f1']:>10.4f}")
    print(f"  {'synthetic_only':<20}{'Dummy (most_frequent)':<38}{'n/a':>7}"
          f"{'n/a':>8}{dummy_ext['macro_f1']:>10.4f}")

    # Select production model: best CV macro-F1 within the production strategy.
    prod = results[PRODUCTION_STRATEGY]
    best_name = max(prod, key=lambda n: prod[n]["cv_macro_f1"])
    pipeline = prod[best_name]["pipeline"]
    best_params = prod[best_name]["best_params"]
    internal_metrics = prod[best_name]["auth"]
    external_metrics = prod[best_name]["ext"]

    # Extract the two fitted steps so the backend contract is preserved.
    vectorizer = pipeline.named_steps["features"]
    model = pipeline.named_steps["clf"]

    print(f"\nProduction model: {PRODUCTION_STRATEGY} / {best_name}")
    print(f"Best params: {best_params}")

    print("\nAuthored held-out test report:")
    print(report_text(auth_test["labels"], pipeline.predict(auth_test["prompt"])))
    print("Independent external test report (deepset/prompt-injections):")
    print(report_text(external_test["labels"], pipeline.predict(external_test["prompt"])))

    # Diagnostic only (NOT used for tuning): show missed attacks so weaknesses
    # in the training distribution are visible.
    ext_pred = pipeline.predict(external_test["prompt"])
    missed = external_test[(external_test["labels"] == 1) & (ext_pred == 0)]
    print(f"\nDiagnostic: {len(missed)} malicious external prompts missed (no tuning on these):")
    for text in missed["prompt"].head(8):
        print(f"  - {text[:90]}")

    # ==================================================
    # 6. Verify saved artifacts reproduce pipeline output
    # ==================================================

    sample = list(auth_test["prompt"]) + list(external_test["prompt"])
    pipeline_pred = pipeline.predict(sample)
    separate_pred = model.predict(vectorizer.transform(sample))
    same_predictions = bool(np.array_equal(pipeline_pred, separate_pred))
    same_probabilities = bool(np.allclose(
        pipeline.predict_proba(sample),
        model.predict_proba(vectorizer.transform(sample)),
        atol=1e-6,
    ))
    print(f"\nArtifact equivalence check: predictions match={same_predictions} "
          f"probabilities match={same_probabilities}")
    if not (same_predictions and same_probabilities):
        raise RuntimeError("Saved vectorizer + model do not reproduce the pipeline.")
    if list(model.classes_) != [0, 1]:
        raise RuntimeError(f"Unexpected class order: {list(model.classes_)}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    # ==================================================
    # 7. Save metadata
    # ==================================================

    headline = external_metrics
    features_description = (
        "TF-IDF word(1,2)+char_wb(3,5)" if isinstance(vectorizer, FeatureUnion)
        else "TF-IDF word(1,2)"
    )
    model_info = {
        "model": best_name.split(" + ")[-1],
        "pipeline": best_name,
        "training_strategy": PRODUCTION_STRATEGY,
        "vectorizer": features_description,
        "ngram_range": [1, 2],
        "selection_method": (
            "5-fold StratifiedKFold cross-validation (macro-F1) with the "
            "TF-IDF vectorizer inside the pipeline (fit per fold, no leakage); "
            "best pipeline refit on the full training set."
        ),
        "total_samples": int(len(data) + ext_train_info.get("samples", 0)),
        "authored_samples": int(len(data)),
        "external_train_samples": int(ext_train_info.get("samples", 0)),
        "training_samples": int(len(X_train) + ext_train_info.get("samples", 0)),
        "testing_samples": int(ext_test_info["samples"]),
        "authored_test_samples": int(len(X_test)),
        "safe_samples": int((labels == 0).sum()),
        "malicious_samples": int((labels == 1).sum()),
        "feature_count": int(len(vectorizer.get_feature_names_out())),
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "best_params": best_params,
        "class_order": [int(c) for c in model.classes_],
        "evaluation_set": "Independent external test: deepset/prompt-injections (test split)",
        "accuracy": headline["accuracy"],
        "precision": headline["precision"],
        "recall": headline["recall"],
        "f1_score": headline["f1_score"],
        "macro_f1": headline["macro_f1"],
        "weighted_f1": headline["weighted_f1"],
        "per_class": headline["per_class"],
        "false_positives": headline["false_positives"],
        "false_negatives": headline["false_negatives"],
        "true_positives": headline["true_positives"],
        "true_negatives": headline["true_negatives"],
        "confusion_matrix": {
            "labels": ["Safe", "Malicious"],
            "values": headline["confusion_matrix_values"],
        },
        "authored_test": internal_metrics,
        "external_test": {**ext_test_info, **external_metrics},
        "model_comparison": comparison,
        "dummy_external_macro_f1": dummy_ext["macro_f1"],
        "dataset_provenance": {
            "training": "Hand-authored synthetic examples + deepset/prompt-injections train split.",
            "external_test": "deepset/prompt-injections test split (held out, never trained on).",
        },
        "limitations": (
            "Training mixes small hand-authored data with a public dataset. The "
            "independent external test is a different distribution, so metrics "
            "reflect realistic generalization and are NOT production-grade. "
            f"{headline['false_negatives']} malicious external prompts are still "
            "missed; a semantic/embedding model and more data are required to "
            "improve recall."
        ),
    }

    with open(MODEL_INFO_PATH, "w", encoding="utf-8") as file:
        json.dump(model_info, file, indent=4)

    # ==================================================
    # 8. Report
    # ==================================================

    print("\n" + "=" * 66)
    print("                     TRAINING COMPLETE")
    print("=" * 66)
    print(f"Saved model: {best_name} ({PRODUCTION_STRATEGY})")
    print("Headline = independent external test (deepset/prompt-injections):")
    print(f"  Accuracy:    {headline['accuracy']:.4f}")
    print(f"  Macro-F1:    {headline['macro_f1']:.4f}")
    print(f"  Weighted-F1: {headline['weighted_f1']:.4f}")
    print(f"  Malicious precision={headline['precision']:.4f} "
          f"recall={headline['recall']:.4f} f1={headline['f1_score']:.4f}")
    print(f"  Confusion matrix: TN={headline['true_negatives']} "
          f"FP={headline['false_positives']} FN={headline['false_negatives']} "
          f"TP={headline['true_positives']}")
    print(f"\nModel:      {MODEL_PATH}")
    print(f"Vectorizer: {VECTORIZER_PATH}")
    print(f"Model info: {MODEL_INFO_PATH}")
    print("=" * 66)


if __name__ == "__main__":
    train_model()
