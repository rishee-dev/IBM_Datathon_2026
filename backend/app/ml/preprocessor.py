"""
Preprocessing and Stratified Data Splitting for SentinelZ AI ML Pipeline.
Ensures zero data leakage by isolating training, validation, and test partitions,
and fitting transformations strictly on the training partition.
"""

from typing import Dict, Tuple
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.features import (
    CATEGORICAL_FEATURES,
    INFERENCE_FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    split_features_and_target,
)


def build_feature_preprocessor() -> ColumnTransformer:
    """
    Constructs an unfitted scikit-learn ColumnTransformer.
    - Numeric features: Imputed with median, scaled with StandardScaler.
    - Categorical features: Imputed with most frequent, encoded with OneHotEncoder(handle_unknown="ignore").
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_FEATURES),
            ("cat", categorical_pipeline, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


def prepare_data_splits(
    df: pd.DataFrame,
    test_ratio: float = 0.15,
    val_ratio: float = 0.15,
    seed: int = 42,
) -> Dict[str, pd.DataFrame]:
    """
    Splits the dataset into 70% Train, 15% Validation, and 15% Test partitions.
    Uses stratification on the target label to preserve the true class imbalance across all splits.

    Parameters:
    - df: Raw DataFrame containing metadata, observable features, and 'is_fraud' label.
    - test_ratio: Fraction reserved for final evaluation (default: 0.15).
    - val_ratio: Fraction reserved for model selection and threshold tuning (default: 0.15).
    - seed: Random seed for exact partition reproducibility.

    Returns:
    - Dict with keys: 'X_train', 'y_train', 'X_val', 'y_val', 'X_test', 'y_test'.
    """
    # 1. Extract feature matrix X and target y, strictly excluding metadata and labels from X
    X, y = split_features_and_target(df)

    if y is None:
        raise ValueError("Cannot split dataset: target column 'is_fraud' is missing.")

    temp_ratio = test_ratio + val_ratio  # 0.30
    if not (0.0 < temp_ratio < 1.0):
        raise ValueError(f"Invalid split ratios: test_ratio ({test_ratio}) + val_ratio ({val_ratio}) must be < 1.0")

    # First split: Separate 70% Train from 30% Temp (Validation + Test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X,
        y,
        test_size=temp_ratio,
        stratify=y,
        random_state=seed,
    )

    # Second split: Divide the 30% Temp equally into 15% Validation and 15% Test
    val_proportion_of_temp = val_ratio / temp_ratio  # 0.15 / 0.30 = 0.50
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp,
        y_temp,
        test_size=(1.0 - val_proportion_of_temp),
        stratify=y_temp,
        random_state=seed,
    )

    return {
        "X_train": X_train.reset_index(drop=True),
        "y_train": y_train.reset_index(drop=True),
        "X_val": X_val.reset_index(drop=True),
        "y_val": y_val.reset_index(drop=True),
        "X_test": X_test.reset_index(drop=True),
        "y_test": y_test.reset_index(drop=True),
    }
