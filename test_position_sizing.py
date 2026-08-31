"""Manually verify confidence-scaled risk sizing and the $2000 hard cap."""

from run_agent import calculate_contracts, RISK_FRACTION_BY_CONFIDENCE, HARD_CAP_USD

SCENARIOS = [
    ("Scenario 1: cheap option, MEDIUM confidence", 100_000, 2.50, "MEDIUM"),
    ("Scenario 2: pricier option, MEDIUM confidence", 100_000, 15.00, "MEDIUM"),
    ("Scenario 3: very cheap option, MEDIUM confidence", 100_000, 0.50, "MEDIUM"),
    ("Scenario 4: big account hits the hard cap, HIGH confidence", 300_000, 2.50, "HIGH"),
    # Same cash and premium as Scenario 1, but LOW vs HIGH confidence — this
    # pair is what actually proves confidence scales position size.
    ("Scenario 5: same setup as #1, LOW confidence", 100_000, 2.50, "LOW"),
    ("Scenario 6: same setup as #1, HIGH confidence", 100_000, 2.50, "HIGH"),
]

results = {}
for label, cash, premium, confidence in SCENARIOS:
    contracts = calculate_contracts(cash, premium, confidence)
    dollars_risked = contracts * premium * 100
    risk_pct = RISK_FRACTION_BY_CONFIDENCE[confidence] * 100

    print(f"{label}: cash=${cash}, premium=${premium}, confidence={confidence}")
    print(f"  contracts bought: {contracts}")
    print(f"  $ risked:         ${dollars_risked:.2f}")
    print(f"  ({risk_pct}% of cash = ${cash * RISK_FRACTION_BY_CONFIDENCE[confidence]:.2f}, hard cap = ${HARD_CAP_USD})\n")

    assert dollars_risked <= HARD_CAP_USD, f"{label} exceeded the hard cap!"
    results[label] = contracts

# Scenario 4: 1.5% of $300k is $4500, so this only proves the cap works if
# $ risked lands at $2000, not $4500.
assert results["Scenario 4: big account hits the hard cap, HIGH confidence"] * 2.50 * 100 == HARD_CAP_USD, \
    "hard cap did not actually bind on scenario 4"

# The core claim of confidence-based sizing: same cash and premium, but
# LOW buys fewer contracts than HIGH, with MEDIUM (scenario 1) in between.
low = results["Scenario 5: same setup as #1, LOW confidence"]
medium = results["Scenario 1: cheap option, MEDIUM confidence"]
high = results["Scenario 6: same setup as #1, HIGH confidence"]
assert low < medium < high, f"expected LOW < MEDIUM < HIGH, got {low} < {medium} < {high}"

print(f"Confirmed scaling for the same premium: LOW={low} < MEDIUM={medium} < HIGH={high} contracts.")
print("All scenarios stayed within the $2000 hard cap.")
