import random

import pytest

from linkedin_automation.errors import BudgetExceededError, CooldownActiveError
from linkedin_automation.pacing import DAY_S, HOUR_S, RequestPacer


class FakeClock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_pacer(tmp_path, clock, hourly=60, daily=300):
    return RequestPacer(
        state_file=tmp_path / "request-log.json",
        min_delay_s=2.0,
        max_delay_s=6.0,
        hourly_budget=hourly,
        daily_budget=daily,
        clock=clock,
        sleep=clock.sleep,
        rng=random.Random(42),
    )


def send(pacer):
    pacer.before_request()
    pacer.record_request()


def test_first_request_does_not_wait(tmp_path):
    clock = FakeClock()
    send(make_pacer(tmp_path, clock))
    assert clock.sleeps == []


def test_consecutive_requests_wait_a_randomized_delay(tmp_path):
    clock = FakeClock()
    pacer = make_pacer(tmp_path, clock)
    for _ in range(20):
        send(pacer)

    assert len(clock.sleeps) == 19
    assert all(delay >= 2.0 for delay in clock.sleeps)
    # Not a fixed cadence.
    assert len({round(delay, 3) for delay in clock.sleeps}) > 10


def test_spacing_is_kept_across_separate_pacer_instances(tmp_path):
    clock = FakeClock()
    send(make_pacer(tmp_path, clock))
    clock.now += 1.0
    send(make_pacer(tmp_path, clock))
    assert clock.sleeps and clock.sleeps[0] >= 1.0


def test_no_wait_when_enough_time_has_passed(tmp_path):
    clock = FakeClock()
    pacer = make_pacer(tmp_path, clock)
    send(pacer)
    clock.now += 600
    send(pacer)
    assert clock.sleeps == []


def test_hourly_budget_is_enforced_and_recovers(tmp_path):
    clock = FakeClock()
    pacer = make_pacer(tmp_path, clock, hourly=3)
    for _ in range(3):
        send(pacer)
    with pytest.raises(BudgetExceededError, match="Hourly"):
        pacer.before_request()

    clock.now += HOUR_S
    send(pacer)


def test_daily_budget_is_enforced(tmp_path):
    clock = FakeClock()
    pacer = make_pacer(tmp_path, clock, hourly=2, daily=3)
    for _ in range(3):
        send(pacer)
        clock.now += HOUR_S
    with pytest.raises(BudgetExceededError, match="Daily"):
        pacer.before_request()

    clock.now += DAY_S
    send(pacer)


def test_cooldown_blocks_requests_until_it_expires_or_is_cleared(tmp_path):
    clock = FakeClock()
    pacer = make_pacer(tmp_path, clock)
    pacer.start_cooldown(HOUR_S, "HTTP 429")

    with pytest.raises(CooldownActiveError, match="HTTP 429"):
        make_pacer(tmp_path, clock).before_request()
    assert pacer.usage().cooldown_reason == "HTTP 429"

    clock.now += HOUR_S + 1
    pacer.before_request()
    assert pacer.usage().cooldown_until is None

    pacer.start_cooldown(HOUR_S, "challenge")
    pacer.clear_cooldown()
    pacer.before_request()


def test_corrupted_log_is_ignored(tmp_path):
    clock = FakeClock()
    (tmp_path / "request-log.json").write_text("not json", encoding="utf-8")
    pacer = make_pacer(tmp_path, clock)
    send(pacer)
    assert pacer.usage().last_day == 1
