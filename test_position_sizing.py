"""Manually verify the 1% risk rule and $2000 hard cap in calculate_contracts."""

from run_agent import calculate_contracts, RISK_FRACTION, HARD_CAP_USD

SCENARIOS = [
    ("Scenario 1: cheap option", 100_000, 2.50),
    ("Scenario 2: pricier option", 100_000, 15.00),
    ("Scenario 3: very cheap option", 100_000, 0.50),
    ("Scenario 4: big account hits the hard cap", 300_000, 2.50),
]

for label, cash, premium in SCENARIOS:
    contracts = calculate_contracts(cash, premium)
    dollars_risked = contracts * premium * 100

    print(f"{label}: cash=${cash}, premium=${premium}")
    print(f"  contracts bought: {contracts}")
    print(f"  $ risked:         ${dollars_risked:.2f}")
    print(f"  (1% of cash = ${cash * RISK_FRACTION:.2f}, hard cap = ${HARD_CAP_USD})\n")

    # The function must never risk more than the $2000 hard cap.
    assert dollars_risked <= HARD_CAP_USD, f"{label} exceeded the hard cap!"

# Scenario 4 specifically: 1% of $300k is $3000, so this only proves the
# cap works if $ risked lands at $2000, not $3000.
assert dollars_risked == HARD_CAP_USD, "hard cap did not actually bind on scenario 4"

print("All scenarios stayed within the $2000 hard cap.")
