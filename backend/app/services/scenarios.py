"""
Controlled Synthetic Scenario Generator for SentinelZ AI Simulation.
Generates realistic, reproducible transaction inputs reflecting different behavioral scenarios.

CRITICAL INTEGRITY PRINCIPLE:
Scenarios define observable input feature distributions (e.g., amount, cadence, device score).
They do NOT determine model outputs, pre-assign risk scores, or include ground-truth labels.
Each scenario payload is evaluated naturally by the actual machine-learning pipeline.
"""

from enum import Enum
from typing import Any, Dict, Optional
import datetime
import numpy as np


class ScenarioType(str, Enum):
    NORMAL = "normal"
    UNUSUAL_AMOUNT = "unusual_amount"
    VELOCITY_BURST = "velocity_burst"
    ELEVATED_DEVICE_RISK = "elevated_device_risk"
    CROSS_BORDER_WIRE = "cross_border_wire"


SCENARIO_DESCRIPTIONS: Dict[ScenarioType, str] = {
    ScenarioType.NORMAL: "Standard routine customer activity with typical spending and recognized device.",
    ScenarioType.UNUSUAL_AMOUNT: "Transaction amount significantly exceeds customer's historical baseline.",
    ScenarioType.VELOCITY_BURST: "High frequency of transactions in a very short time interval (< 60s cadence).",
    ScenarioType.ELEVATED_DEVICE_RISK: "Transaction initiated from an unrecognized device profile or proxy.",
    ScenarioType.CROSS_BORDER_WIRE: "High-value cross-border wire transfer into digital/luxury category.",
}


def build_scenario_payload(
    scenario: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs an observable transaction input dictionary according to the requested scenario.
    
    Parameters:
    - scenario: Optional name of scenario ("normal", "unusual_amount", "velocity_burst", 
                "elevated_device_risk", "cross_border_wire"). Defaults to random choice.
    - seed: Optional integer seed for exact deterministic payload generation.
    
    Returns:
    - Dict with raw transaction inputs (amount, channel, customer_baseline, etc.)
      strictly excluding ground-truth labels or latent risk scores.
    """
    rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()

    # Determine scenario
    valid_scenarios = [s.value for s in ScenarioType]
    if scenario and scenario.lower() in valid_scenarios:
        selected_scenario = ScenarioType(scenario.lower())
    else:
        # Default distribution: 40% normal, 60% across anomalous patterns
        selected_scenario = rng.choice(
            list(ScenarioType),
            p=[0.40, 0.15, 0.15, 0.15, 0.15]
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%H:%M:%S.%f")[:-3]
    cust_id = f"CUST-{rng.randint(1000, 1100)}"

    if selected_scenario == ScenarioType.NORMAL:
        baseline = float(round(rng.uniform(50.0, 300.0), 2))
        amount = float(round(baseline * rng.uniform(0.6, 1.3), 2))
        channel = rng.choice(["Card", "Mobile", "ACH"], p=[0.60, 0.30, 0.10])
        merchant = rng.choice(["retail", "groceries", "utilities"])
        velocity = int(rng.choice([1, 2], p=[0.8, 0.2]))
        time_since_prev = int(rng.uniform(1800, 7200))
        is_foreign = 0
        device_risk = float(round(rng.uniform(0.05, 0.25), 3))

    elif selected_scenario == ScenarioType.UNUSUAL_AMOUNT:
        baseline = float(round(rng.uniform(80.0, 250.0), 2))
        multiplier = float(round(rng.uniform(5.0, 12.0), 2))
        amount = float(round(baseline * multiplier, 2))
        channel = rng.choice(["Card", "Wire", "ACH"])
        merchant = rng.choice(["electronics", "travel", "crypto_luxury"])
        velocity = int(rng.choice([1, 2, 3]))
        time_since_prev = int(rng.uniform(300, 3600))
        is_foreign = 1 if rng.uniform() < 0.3 else 0
        device_risk = float(round(rng.uniform(0.20, 0.55), 3))

    elif selected_scenario == ScenarioType.VELOCITY_BURST:
        baseline = float(round(rng.uniform(50.0, 400.0), 2))
        amount = float(round(rng.uniform(30.0, 180.0), 2))
        channel = rng.choice(["Mobile", "Card"])
        merchant = rng.choice(["digital_transfer", "electronics", "retail"])
        velocity = int(rng.randint(5, 11))  # 5 to 10 tx in 1hr
        time_since_prev = int(rng.randint(10, 45))  # 10 to 45 seconds cadence
        is_foreign = 0
        device_risk = float(round(rng.uniform(0.30, 0.65), 3))

    elif selected_scenario == ScenarioType.ELEVATED_DEVICE_RISK:
        baseline = float(round(rng.uniform(100.0, 500.0), 2))
        amount = float(round(baseline * rng.uniform(1.2, 3.5), 2))
        channel = rng.choice(["Mobile", "Card"])
        merchant = rng.choice(["digital_transfer", "retail"])
        velocity = int(rng.randint(2, 5))
        time_since_prev = int(rng.uniform(60, 600))
        is_foreign = 1 if rng.uniform() < 0.5 else 0
        device_risk = float(round(rng.uniform(0.75, 0.96), 3))  # High device risk score

    elif selected_scenario == ScenarioType.CROSS_BORDER_WIRE:
        baseline = float(round(rng.uniform(1000.0, 4000.0), 2))
        amount = float(round(rng.uniform(12000.0, 65000.0), 2))
        channel = "Wire"
        merchant = rng.choice(["crypto_luxury", "digital_transfer", "travel"])
        velocity = int(rng.randint(1, 4))
        time_since_prev = int(rng.uniform(120, 1800))
        is_foreign = 1  # Cross-border
        device_risk = float(round(rng.uniform(0.40, 0.85), 3))

    ratio = float(round(amount / max(baseline, 1.0), 3))

    return {
        "scenario": selected_scenario.value,
        "scenario_description": SCENARIO_DESCRIPTIONS[selected_scenario],
        "customerId": cust_id,
        "timestamp": timestamp_str,
        "amount": amount,
        "channel": channel,
        "merchant_category": merchant,
        "customer_baseline": baseline,
        "amount_to_baseline_ratio": ratio,
        "recent_transaction_count": velocity,
        "time_since_previous_seconds": time_since_prev,
        "is_foreign_country": is_foreign,
        "device_risk_score": device_risk,
    }
