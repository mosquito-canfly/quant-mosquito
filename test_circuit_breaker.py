"""Verify check_circuit_breaker() triggers at -5% and not before."""

from run_agent import check_circuit_breaker

SCENARIOS = [
    ("3% down", 100_000, 97_000, False),
    ("6% down", 100_000, 94_000, True),
    ("0.5% up", 100_000, 100_500, False),
]

for label, starting, current, expected in SCENARIOS:
    triggered, daily_loss_pct = check_circuit_breaker(starting, current)
    print(f"{label}: starting=${starting}, current=${current} -> "
          f"triggered={triggered} (loss={daily_loss_pct:.1%}), expected={expected}")
    assert triggered == expected, f"FAILED: {label}"

print("All circuit breaker scenarios passed.")
