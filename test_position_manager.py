"""Verify check_exit_conditions() against four fake position scenarios."""

from datetime import date, timedelta
from types import SimpleNamespace

from position_manager import check_exit_conditions

far_expiration = (date.today() + timedelta(days=30)).strftime("%y%m%d")
tomorrow_expiration = (date.today() + timedelta(days=1)).strftime("%y%m%d")


def fake_position(plpc, expiration_str):
    # Only unrealized_plpc and symbol matter to check_exit_conditions.
    return SimpleNamespace(
        unrealized_plpc=plpc,
        symbol=f"SPY{expiration_str}C00700000",
    )


SCENARIOS = [
    ("55% gain, far from expiration", fake_position(0.55, far_expiration), "TAKE_PROFIT"),
    ("35% loss, far from expiration", fake_position(-0.35, far_expiration), "STOP_LOSS"),
    ("small 5% gain, expires tomorrow", fake_position(0.05, tomorrow_expiration), "TIME_EXIT"),
    ("small 10% gain, far from expiration", fake_position(0.10, far_expiration), None),
]

for label, position, expected in SCENARIOS:
    result = check_exit_conditions(position)
    print(f"{label}: got {result} (expected {expected})")
    assert result == expected, f"FAILED: {label}"

print("All exit-condition scenarios passed.")
