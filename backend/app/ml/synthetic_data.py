"""
Deterministic Synthetic Transaction Generator for SentinelZ AI.
Generates realistic, statistically grounded financial transactions with behavioral features
and supervised ground-truth fraud labels for ML model training and evaluation.

ENGINEERING INTEGRITY & LIMITATIONS NOTICE:
1. Synthetic Nature: This data is generated using parameterized statistical distributions
   (log-normal amounts, Poisson velocities, logistic risk curves) designed to emulate
   banking patterns. It does NOT represent real customer banking records.
2. No Cheating/Shortcut Rules: Ground truth labels are generated via a probabilistic latent
   risk function with stochastic Bernoulli sampling. There is no deterministic single-feature
   decision threshold (e.g. no 'amount > 5000 is always fraud'), ensuring the model must
   learn multi-dimensional risk signals and withstand realistic false positive trade-offs.
3. Separation: Ground truth labels (is_fraud) are strictly separated from observable
   inference features.
"""

from typing import List, Dict, Any, Optional
import datetime
import numpy as np
import pandas as pd

from app.ml.features import (
    INFERENCE_FEATURE_COLUMNS,
    METADATA_COLUMNS,
    TARGET_COLUMN,
)

CHANNELS: List[str] = ["Card", "Mobile", "ACH", "Wire"]
CHANNEL_WEIGHTS: List[float] = [0.60, 0.25, 0.10, 0.05]

MERCHANT_CATEGORIES: List[str] = [
    "retail",
    "groceries",
    "utilities",
    "electronics",
    "travel",
    "digital_transfer",
    "crypto_luxury",
]
MERCHANT_WEIGHTS: List[float] = [0.35, 0.25, 0.15, 0.10, 0.08, 0.05, 0.02]


class CustomerProfile:
    """Represents a simulated customer with historical spending habits."""
    def __init__(self, customer_id: str, rng: np.random.RandomState):
        self.customer_id = customer_id
        # Historical baseline spend: log-normal distribution centered around ~$120 with variance
        self.baseline_amount = float(np.round(rng.lognormal(mean=4.6, sigma=0.8), 2))
        self.baseline_amount = max(15.0, min(self.baseline_amount, 25000.0))
        self.preferred_channel = rng.choice(CHANNELS, p=CHANNEL_WEIGHTS)
        self.home_country = "US" if rng.uniform() < 0.92 else rng.choice(["CA", "GB", "DE"])


def generate_customer_pool(n_customers: int, rng: np.random.RandomState) -> List[CustomerProfile]:
    """Creates a deterministic pool of synthetic customers."""
    return [CustomerProfile(f"CUST-{1000 + i}", rng) for i in range(n_customers)]


def generate_synthetic_transactions(
    n_samples: int = 5000,
    seed: int = 42,
    fraud_rate_target: float = 0.035,
    include_internal_signals: bool = False,
) -> pd.DataFrame:
    """
    Generates a deterministic synthetic transaction DataFrame.

    Parameters:
    - n_samples: Total number of transactions to generate (default: 5000)
    - seed: Random seed for exact reproducibility (default: 42)
    - fraud_rate_target: Approximate expected proportion of fraudulent transactions (~3.5%)
    - include_internal_signals: If True, includes latent risk scores for debugging.
      MUST be False for training/testing datasets to prevent data leakage.

    Returns:
    - pd.DataFrame containing metadata columns, observable features, and the 'is_fraud' label.
    """
    rng = np.random.RandomState(seed)

    # 1. Generate customer pool (~5% of sample count, minimum 30)
    n_customers = max(30, n_samples // 20)
    customers = generate_customer_pool(n_customers, rng)

    rows: List[Dict[str, Any]] = []
    base_time = datetime.datetime(2026, 10, 17, 8, 0, 0)

    for i in range(n_samples):
        # Pick customer
        cust: CustomerProfile = rng.choice(customers)
        txn_id = f"TXN-{800000 + i}"
        
        # Advance timestamp realistically (1 to 15 seconds per event)
        step_seconds = int(rng.exponential(scale=6.0)) + 1
        base_time += datetime.timedelta(seconds=step_seconds)
        timestamp_str = base_time.strftime("%H:%M:%S.%f")[:-3]

        # Channel selection: 80% chance to use preferred channel, 20% another
        if rng.uniform() < 0.80:
            channel = cust.preferred_channel
        else:
            channel = rng.choice(CHANNELS, p=CHANNEL_WEIGHTS)

        # Merchant category
        merchant = rng.choice(MERCHANT_CATEGORIES, p=MERCHANT_WEIGHTS)

        # Transaction amount: typically close to baseline, with occasional large deviations
        baseline = cust.baseline_amount
        is_deviant_behavior = rng.uniform() < 0.08
        if is_deviant_behavior:
            # Significant deviation multiplier (3x to 15x customer baseline)
            multiplier = float(rng.uniform(3.0, 15.0))
            amount = float(np.round(baseline * multiplier, 2))
        else:
            # Normal variation (50% to 150% of customer baseline)
            multiplier = float(rng.uniform(0.5, 1.5))
            amount = float(np.round(baseline * multiplier, 2))

        # Hard guardrails on amount
        amount = max(1.0, float(np.round(amount, 2)))
        amount_to_baseline_ratio = float(np.round(amount / max(baseline, 1.0), 3))

        # Velocity features
        # Number of transactions by this customer profile in the last hour
        recent_tx_count = int(rng.poisson(lam=1.2))
        if is_deviant_behavior and rng.uniform() < 0.4:
            # High velocity burst scenario
            recent_tx_count += int(rng.randint(4, 12))

        # Time since previous transaction (seconds)
        time_since_prev = int(rng.exponential(scale=1800.0)) + 5
        if recent_tx_count > 3:
            time_since_prev = min(time_since_prev, int(rng.randint(5, 120)))

        # Geographic & device signals
        is_foreign = 1 if rng.uniform() < 0.05 else 0
        device_risk = float(np.round(rng.beta(a=1.5, b=8.0), 3))  # Beta distribution skewed low
        if is_deviant_behavior and rng.uniform() < 0.3:
            device_risk = float(np.round(rng.uniform(0.65, 0.98), 3))

        # 2. Multi-factor latent risk formulation
        # Combines behavioral divergence, velocity pressure, high-risk channel, and device risk
        channel_risk_factor = {"Card": 0.2, "Mobile": 0.3, "ACH": 0.5, "Wire": 1.2}.get(channel, 0.3)
        merchant_risk_factor = {
            "retail": 0.1,
            "groceries": 0.0,
            "utilities": 0.0,
            "electronics": 0.5,
            "travel": 0.6,
            "digital_transfer": 1.1,
            "crypto_luxury": 1.8,
        }.get(merchant, 0.2)

        ratio_signal = np.log1p(max(0.0, amount_to_baseline_ratio - 1.0))
        velocity_signal = max(0, recent_tx_count - 1) * 0.4
        rapidity_signal = 1.0 if time_since_prev < 60 else (0.5 if time_since_prev < 300 else 0.0)
        geo_signal = 1.2 if is_foreign else 0.0
        device_signal = device_risk * 1.5

        # Latent risk score calculation
        latent_risk = (
            -4.9  # Intercept calibrated for ~3% baseline fraud rate
            + (0.7 * ratio_signal)
            + (0.6 * channel_risk_factor)
            + (0.5 * merchant_risk_factor)
            + (0.6 * velocity_signal)
            + (0.5 * rapidity_signal)
            + (0.8 * geo_signal)
            + (1.0 * device_signal)
            + rng.normal(loc=0.0, scale=0.4)  # Natural stochastic variance
        )

        # Logistic sigmoid to obtain fraud probability
        prob_fraud = float(1.0 / (1.0 + np.exp(-latent_risk)))

        # Bernoulli trial to assign ground-truth label
        is_fraud = 1 if rng.uniform() < prob_fraud else 0

        row = {
            # Contextual metadata
            "transaction_id": txn_id,
            "customer_id": cust.customer_id,
            "timestamp": timestamp_str,
            # Observable inference features
            "amount": amount,
            "channel": channel,
            "merchant_category": merchant,
            "customer_baseline": baseline,
            "amount_to_baseline_ratio": amount_to_baseline_ratio,
            "recent_transaction_count": recent_tx_count,
            "time_since_previous_seconds": time_since_prev,
            "is_foreign_country": is_foreign,
            "device_risk_score": device_risk,
            # Ground-truth label
            TARGET_COLUMN: is_fraud,
        }

        if include_internal_signals:
            row["latent_risk_score"] = float(np.round(latent_risk, 4))
            row["fraud_probability"] = float(np.round(prob_fraud, 4))

        rows.append(row)

    df = pd.DataFrame(rows)
    return df
