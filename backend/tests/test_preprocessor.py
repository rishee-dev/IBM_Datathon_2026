"""
Unit tests for preprocessing and data splitting module.
Verifies stratified partition proportions, leakage prevention, and robust handling of unknown categories.
"""

import pandas as pd
import numpy as np
from app.ml.synthetic_data import generate_synthetic_transactions
from app.ml.preprocessor import build_feature_preprocessor, prepare_data_splits
from app.ml.features import INFERENCE_FEATURE_COLUMNS, TARGET_COLUMN


def test_stratified_split_proportions():
    """Verify that splits accurately partition data into 70% / 15% / 15%."""
    df = generate_synthetic_transactions(n_samples=1000, seed=42)
    splits = prepare_data_splits(df, test_ratio=0.15, val_ratio=0.15, seed=42)

    n_total = len(df)
    n_train = len(splits["X_train"])
    n_val = len(splits["X_val"])
    n_test = len(splits["X_test"])

    assert n_train + n_val + n_test == n_total
    assert n_train == 700
    assert n_val == 150
    assert n_test == 150


def test_stratified_split_preserves_class_balance():
    """Verify that fraud rate is nearly identical across train, val, and test splits."""
    df = generate_synthetic_transactions(n_samples=2000, seed=42)
    splits = prepare_data_splits(df, test_ratio=0.15, val_ratio=0.15, seed=42)

    overall_rate = df[TARGET_COLUMN].mean()
    train_rate = splits["y_train"].mean()
    val_rate = splits["y_val"].mean()
    test_rate = splits["y_test"].mean()

    # Stratified split ensures fraud rate is within 0.5% across splits
    assert abs(train_rate - overall_rate) < 0.005
    assert abs(val_rate - overall_rate) < 0.010
    assert abs(test_rate - overall_rate) < 0.010


def test_no_target_or_metadata_in_features():
    """Verify that feature matrices contain only permitted inference columns."""
    df = generate_synthetic_transactions(n_samples=500, seed=42)
    splits = prepare_data_splits(df, seed=42)

    for split_name in ["X_train", "X_val", "X_test"]:
        X = splits[split_name]
        assert TARGET_COLUMN not in X.columns
        assert "transaction_id" not in X.columns
        assert "customer_id" not in X.columns
        assert list(X.columns) == INFERENCE_FEATURE_COLUMNS


def test_preprocessor_handles_unknown_categories():
    """Verify preprocessor transforms unseen/novel categories gracefully without throwing exceptions."""
    df = generate_synthetic_transactions(n_samples=500, seed=42)
    splits = prepare_data_splits(df, seed=42)

    preprocessor = build_feature_preprocessor()
    X_train_trans = preprocessor.fit_transform(splits["X_train"])

    # Create unseen inference payload with novel categorical values
    unseen_data = splits["X_val"].copy()
    unseen_data.loc[0, "channel"] = "CryptocurrencyRail"
    unseen_data.loc[0, "merchant_category"] = "unseen_blackmarket"

    # Must transform without error
    X_unseen_trans = preprocessor.transform(unseen_data)
    assert X_unseen_trans.shape[1] == X_train_trans.shape[1]


def test_preprocessor_handles_missing_values():
    """Verify preprocessor imputes missing numerical and categorical values safely."""
    df = generate_synthetic_transactions(n_samples=500, seed=42)
    splits = prepare_data_splits(df, seed=42)

    preprocessor = build_feature_preprocessor()
    preprocessor.fit(splits["X_train"])

    sample = splits["X_val"].copy()
    sample.loc[0, "amount"] = np.nan
    sample.loc[0, "customer_baseline"] = np.nan
    sample.loc[0, "channel"] = np.nan

    transformed = preprocessor.transform(sample)
    assert not np.isnan(transformed[0]).any()
