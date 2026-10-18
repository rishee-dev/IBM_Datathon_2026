"""
Feature schema definitions and validation utilities for SentinelZ AI.
Ensures strict separation between inference features and ground-truth labels.
"""

from typing import List
import pandas as pd

# Numerical features available at transaction inference time
NUMERIC_FEATURES: List[str] = [
    "amount",
    "customer_baseline",
    "amount_to_baseline_ratio",
    "recent_transaction_count",
    "time_since_previous_seconds",
    "device_risk_score",
]

# Categorical features available at transaction inference time
CATEGORICAL_FEATURES: List[str] = [
    "channel",
    "merchant_category",
    "is_foreign_country",
]

# Complete set of observable features for model training and live inference
INFERENCE_FEATURE_COLUMNS: List[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Contextual metadata retained for logging, auditing, and UI display (not directly fed into ML model)
METADATA_COLUMNS: List[str] = [
    "transaction_id",
    "customer_id",
    "timestamp",
]

# Supervised ground-truth label (strictly kept out of inference features)
TARGET_COLUMN: str = "is_fraud"

# Internal generation signals that must never leak into training or inference datasets
INTERNAL_GENERATION_SIGNALS: List[str] = [
    "latent_risk_score",
    "fraud_probability",
]


def get_feature_columns() -> List[str]:
    """Returns the strict list of features permitted for inference and training."""
    return list(INFERENCE_FEATURE_COLUMNS)


def get_target_column() -> str:
    """Returns the supervised target label name."""
    return TARGET_COLUMN


def split_features_and_target(df: pd.DataFrame):
    """
    Splits a DataFrame into feature matrix X and target series y.
    Enforces that target and internal generator signals are completely excluded from X.
    """
    for forbidden in [TARGET_COLUMN] + INTERNAL_GENERATION_SIGNALS:
        if forbidden in INFERENCE_FEATURE_COLUMNS:
            raise ValueError(f"CRITICAL LEAKAGE: Forbidden column '{forbidden}' found in INFERENCE_FEATURE_COLUMNS!")

    missing = [col for col in INFERENCE_FEATURE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required feature columns in dataset: {missing}")

    X = df[INFERENCE_FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].copy() if TARGET_COLUMN in df.columns else None
    return X, y
