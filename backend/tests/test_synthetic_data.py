"""
Automated unit tests for synthetic transaction generator.
Validates determinism, feature integrity, absence of data leakage, and realistic distributions.
"""

import pandas as pd
import numpy as np
from app.ml.synthetic_data import generate_synthetic_transactions
from app.ml.features import (
    split_features_and_target,
    get_feature_columns,
    get_target_column,
    TARGET_COLUMN,
    INTERNAL_GENERATION_SIGNALS,
)


def test_generator_determinism():
    """Verify that identical seeds produce bitwise identical DataFrames."""
    df1 = generate_synthetic_transactions(n_samples=250, seed=123)
    df2 = generate_synthetic_transactions(n_samples=250, seed=123)
    pd.testing.assert_frame_equal(df1, df2)

    # Different seeds should produce different samples
    df3 = generate_synthetic_transactions(n_samples=250, seed=456)
    assert not df1["amount"].equals(df3["amount"])


def test_no_data_leakage_in_feature_split():
    """Verify ground-truth label and internal generator signals are completely excluded from X."""
    df = generate_synthetic_transactions(n_samples=300, seed=42)
    X, y = split_features_and_target(df)

    # X must match get_feature_columns() exactly
    assert list(X.columns) == get_feature_columns()

    # Neither target nor internal probability signals may be present in X
    assert TARGET_COLUMN not in X.columns
    for internal in INTERNAL_GENERATION_SIGNALS:
        assert internal not in X.columns

    # y must have same row count and only contain binary 0 or 1
    assert len(y) == len(X)
    assert set(y.unique()).issubset({0, 1})


def test_data_types_and_value_ranges():
    """Verify generated features obey physical and financial constraints."""
    df = generate_synthetic_transactions(n_samples=500, seed=99)

    # Amounts must be strictly positive
    assert (df["amount"] > 0).all()
    assert (df["customer_baseline"] > 0).all()
    assert (df["amount_to_baseline_ratio"] > 0).all()

    # Channels must belong to allowed financial channels
    allowed_channels = {"Wire", "Card", "ACH", "Mobile"}
    assert set(df["channel"].unique()).issubset(allowed_channels)

    # Device risk must be between 0.0 and 1.0
    assert (df["device_risk_score"] >= 0.0).all()
    assert (df["device_risk_score"] <= 1.0).all()

    # Velocity must be non-negative integers
    assert (df["recent_transaction_count"] >= 0).all()
    assert (df["time_since_previous_seconds"] >= 0).all()


def test_realistic_class_imbalance():
    """Verify empirical fraud rate is realistically imbalanced (~2% - 5%), not a 50/50 toy."""
    df = generate_synthetic_transactions(n_samples=3000, seed=77)
    fraud_rate = df[TARGET_COLUMN].mean()
    assert 0.015 <= fraud_rate <= 0.065, f"Unexpected fraud rate: {fraud_rate:.3f}"


def test_no_trivial_shortcuts():
    """
    Verify the dataset contains realistic false positives and false negatives:
    - High-amount legitimate transactions exist (e.g. authorized large purchases/wires).
    - Lower-amount fraudulent transactions exist (e.g. card testing).
    """
    df = generate_synthetic_transactions(n_samples=2000, seed=88)

    median_amount = df["amount"].median()

    high_amount_legit = df[(df["amount"] > median_amount * 2) & (df[TARGET_COLUMN] == 0)]
    assert len(high_amount_legit) > 0, "No high-amount legitimate transactions found (model would learn trivial threshold shortcut)"

    low_amount_fraud = df[(df["amount"] < median_amount) & (df[TARGET_COLUMN] == 1)]
    assert len(low_amount_fraud) > 0, "No lower-amount fraudulent transactions found (card testing scenario absent)"
