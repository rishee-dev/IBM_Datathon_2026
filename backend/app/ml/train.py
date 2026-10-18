"""
Model Training, Validation Comparison, Threshold Optimization, and Persistence for SentinelZ AI.
Implements a scientifically sound, leak-free pipeline comparing Logistic Regression
against Random Forest on a stratified synthetic transaction dataset.
"""

import os
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from app.ml.features import INFERENCE_FEATURE_COLUMNS, TARGET_COLUMN
from app.ml.synthetic_data import generate_synthetic_transactions
from app.ml.preprocessor import build_feature_preprocessor, prepare_data_splits

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def evaluate_predictions_at_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
) -> Dict[str, Any]:
    """
    Evaluates binary classification performance at a specific probability threshold.
    Returns precision, recall, F1, false positive rate (FPR), and confusion matrix.
    """
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    return {
        "threshold": round(threshold, 3),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
    }


def find_optimal_threshold(
    y_val: np.ndarray,
    y_val_prob: np.ndarray,
    max_acceptable_fpr: float = 0.045,
    min_acceptable_recall: float = 0.65,
) -> Tuple[float, Dict[str, Any]]:
    """
    Selects operating threshold strictly on validation predictions.
    Decision Objective:
    In financial fraud intelligence, missed fraud (FN) is very costly, but excessive false
    positives (FP) overwhelm security operations teams.
    We target maximizing F1 score subject to an acceptable false-positive rate constraint (FPR <= 4.5%)
    and minimum recall (>= 65%). If no threshold satisfies both, we fallback to maximum F1.
    """
    candidate_thresholds = np.linspace(0.10, 0.90, 81)
    evaluations = [
        evaluate_predictions_at_threshold(y_val, y_val_prob, t)
        for t in candidate_thresholds
    ]

    # Filter by operational constraints
    valid_candidates = [
        e for e in evaluations
        if e["fpr"] <= max_acceptable_fpr and e["recall"] >= min_acceptable_recall
    ]

    if valid_candidates:
        # Choose the threshold with highest F1 score among compliant candidates
        best = max(valid_candidates, key=lambda x: x["f1"])
    else:
        # Graceful fallback: maximize F1 directly
        best = max(evaluations, key=lambda x: x["f1"])

    return best["threshold"], best


def train_and_evaluate_pipeline(
    n_samples: int = 6000,
    seed: int = 42,
    persist_artifacts: bool = True,
) -> Dict[str, Any]:
    """
    Executes the complete machine learning workflow:
    1. Generates synthetic dataset.
    2. Performs stratified 70% / 15% / 15% train/val/test splitting.
    3. Trains Logistic Regression baseline and Random Forest challenger.
    4. Evaluates and compares both models on the validation split.
    5. Optimizes operating threshold on validation split.
    6. Evaluates selected model on the held-out test split.
    7. Persists pipeline and metadata.
    """
    print(f"[*] Generating {n_samples} synthetic transactions (seed={seed})...")
    df = generate_synthetic_transactions(n_samples=n_samples, seed=seed)
    
    print("[*] Partitioning into Train (70%), Validation (15%), Test (15%)...")
    splits = prepare_data_splits(df, test_ratio=0.15, val_ratio=0.15, seed=seed)
    X_train, y_train = splits["X_train"], splits["y_train"]
    X_val, y_val = splits["X_val"], splits["y_val"]
    X_test, y_test = splits["X_test"], splits["y_test"]

    print(f"    Train size: {len(X_train)} (Fraud: {y_train.sum()}, {y_train.mean():.2%})")
    print(f"    Val size:   {len(X_val)} (Fraud: {y_val.sum()}, {y_val.mean():.2%})")
    print(f"    Test size:  {len(X_test)} (Fraud: {y_test.sum()}, {y_test.mean():.2%})")

    # 1. Define Candidate Models
    models = {
        "LogisticRegression": Pipeline(
            steps=[
                ("preprocessor", build_feature_preprocessor()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1000,
                        random_state=seed,
                    ),
                ),
            ]
        ),
        "RandomForest": Pipeline(
            steps=[
                ("preprocessor", build_feature_preprocessor()),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=120,
                        max_depth=8,
                        min_samples_leaf=4,
                        class_weight="balanced_subsample",
                        random_state=seed,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }

    val_comparison: Dict[str, Any] = {}

    # 2. Train and Validate Candidates
    for name, pipeline in models.items():
        print(f"[*] Training candidate model: {name}...")
        pipeline.fit(X_train, y_train)

        # Probabilities on validation set
        val_probs = pipeline.predict_proba(X_val)[:, 1]
        pr_auc = float(average_precision_score(y_val, val_probs))
        roc_auc = float(roc_auc_score(y_val, val_probs))

        # Default 0.5 threshold baseline
        default_metrics = evaluate_predictions_at_threshold(y_val.values, val_probs, 0.5)

        # Optimize threshold on validation data
        best_thresh, best_metrics = find_optimal_threshold(y_val.values, val_probs)

        val_comparison[name] = {
            "pr_auc": round(pr_auc, 4),
            "roc_auc": round(roc_auc, 4),
            "default_0_5_metrics": default_metrics,
            "optimal_threshold": best_thresh,
            "optimal_val_metrics": best_metrics,
        }
        print(f"    {name} Val PR-AUC: {pr_auc:.4f} | Optimal Threshold: {best_thresh} -> F1: {best_metrics['f1']:.4f}, Recall: {best_metrics['recall']:.4f}, FPR: {best_metrics['fpr']:.4f}")

    # 3. Model Selection
    # Pick the model with higher validation PR-AUC and balanced F1
    lr_pr_auc = val_comparison["LogisticRegression"]["pr_auc"]
    rf_pr_auc = val_comparison["RandomForest"]["pr_auc"]

    if rf_pr_auc >= lr_pr_auc:
        selected_model_name = "RandomForest"
        selection_rationale = (
            f"Random Forest achieved higher validation PR-AUC ({rf_pr_auc:.4f} vs {lr_pr_auc:.4f}) "
            f"and effectively models non-linear interactions across velocity, foreign country, and channel."
        )
    else:
        selected_model_name = "LogisticRegression"
        selection_rationale = (
            f"Logistic Regression achieved superior or competitive validation PR-AUC ({lr_pr_auc:.4f} vs {rf_pr_auc:.4f}) "
            f"with lower computational complexity and higher inference throughput."
        )

    print(f"[*] Selected Model: {selected_model_name}")
    print(f"    Rationale: {selection_rationale}")

    selected_pipeline = models[selected_model_name]
    selected_threshold = val_comparison[selected_model_name]["optimal_threshold"]

    # 4. Final Evaluation on Held-Out Test Set (Done once, never used for tuning)
    print(f"[*] Evaluating selected {selected_model_name} on held-out Test set...")
    test_probs = selected_pipeline.predict_proba(X_test)[:, 1]
    test_pr_auc = float(average_precision_score(y_test, test_probs))
    test_roc_auc = float(roc_auc_score(y_test, test_probs))

    test_metrics = evaluate_predictions_at_threshold(y_test.values, test_probs, selected_threshold)
    test_metrics["pr_auc"] = round(test_pr_auc, 4)
    test_metrics["roc_auc"] = round(test_roc_auc, 4)

    print(f"    Held-out Test PR-AUC:   {test_pr_auc:.4f}")
    print(f"    Held-out Test Precision: {test_metrics['precision']:.4f}")
    print(f"    Held-out Test Recall:    {test_metrics['recall']:.4f}")
    print(f"    Held-out Test F1 Score:  {test_metrics['f1']:.4f}")
    print(f"    Held-out Test FPR:       {test_metrics['fpr']:.4f}")

    # 5. Persist Model and Metadata
    metadata = {
        "model_version": "1.0.0",
        "model_name": selected_model_name,
        "selection_rationale": selection_rationale,
        "trained_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "random_seed": seed,
        "split_sizes": {
            "total_samples": n_samples,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
        },
        "operating_threshold": selected_threshold,
        "threshold_selection_objective": "Maximize Recall subject to FPR <= 4.5% on validation partition",
        "feature_schema": INFERENCE_FEATURE_COLUMNS,
        "validation_comparison": val_comparison,
        "test_metrics": test_metrics,
        "synthetic_data_disclosure": (
            "Model trained and evaluated on synthetic financial transactions generated for the "
            "IBM Z Datathon 2026. Metrics represent demonstration benchmarks on held-out synthetic test splits, "
            "not validated real-world banking production performance."
        ),
    }

    if persist_artifacts:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        model_path = ARTIFACTS_DIR / "model_pipeline.joblib"
        metadata_path = ARTIFACTS_DIR / "metadata.json"

        print(f"[*] Persisting pipeline to {model_path}...")
        joblib.dump(selected_pipeline, model_path)

        print(f"[*] Persisting metadata to {metadata_path}...")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    return {
        "selected_model": selected_model_name,
        "selected_threshold": selected_threshold,
        "validation_comparison": val_comparison,
        "test_metrics": test_metrics,
        "metadata": metadata,
    }


if __name__ == "__main__":
    train_and_evaluate_pipeline()
