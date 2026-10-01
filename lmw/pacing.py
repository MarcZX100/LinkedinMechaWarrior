"""Request pacing for LinkedIn's internal API.

Account restrictions are mostly triggered by volume and by machine-like
regularity, so every Voyager request goes through a pacer that:

- waits a randomized delay since the previous request, also across separate
  CLI invocations because the log is persisted on disk;
- enforces hourly and daily request budgets and refuses to go over them;
- enforces a cooldown after LinkedIn pushes back (challenge, 429, 999), so we
  never keep hammering a session that is already under suspicion.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .errors import BudgetExceededError, CooldownActiveError

HOUR_S = 3600
DAY_S = 24 * HOUR_S


@dataclass
class PacerState:
    requests: list[float] = field(default_factory=list)
    cooldown_until: float | None = None
    cooldown_reason: str | None = None


@dataclass(frozen=True)
class PacerUsage:
    last_hour: int
    last_day: int
    hourly_budget: int
    daily_budget: int
    cooldown_until: float | None
    cooldown_reason: str | None


@dataclass
class RequestPacer:
    state_file: Path
    min_delay_s: float
    max_delay_s: float
    hourly_budget: int
    daily_budget: int
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    rng: random.Random = field(default_factory=random.Random)

    def before_request(self) -> None:
        """Block until the next request is allowed, or raise if it is not allowed at all."""
        state = self._load()
        now = self.clock()

        if state.cooldown_until and now < state.cooldown_until:
            until = datetime.fromtimestamp(state.cooldown_until).strftime("%H:%M")
            raise CooldownActiveError(
                f"Requests are paused until {until} because LinkedIn pushed back: {state.cooldown_reason}. "
                "Check the account in the browser with `lmw open`. "
                "Use `lmw limits --clear-cooldown` only once you are sure it is fine."
            )
        if len(state.requests) >= self.daily_budget:
            raise BudgetExceededError(
                f"Daily request budget reached ({self.daily_budget} requests in 24h). "
                "Try again later or raise DAILY_REQUEST_BUDGET carefully."
            )
        if sum(1 for ts in state.requests if now - ts < HOUR_S) >= self.hourly_budget:
            raise BudgetExceededError(
                f"Hourly request budget reached ({self.hourly_budget} requests in 1h). "
                "Try again later or raise HOURLY_REQUEST_BUDGET carefully."
            )

        if state.requests:
            wait = self._next_delay() - (now - state.requests[-1])
            if wait > 0:
                logging.debug("Pacing: waiting %.1fs before the next request", wait)
                self.sleep(wait)

    def record_request(self) -> None:
        state = self._load()
        state.requests.append(self.clock())
        self._save(state)

    def start_cooldown(self, seconds: float, reason: str) -> None:
        state = self._load()
        state.cooldown_until = self.clock() + seconds
        state.cooldown_reason = reason
        self._save(state)

    def clear_cooldown(self) -> None:
        state = self._load()
        state.cooldown_until = None
        state.cooldown_reason = None
        self._save(state)

    def usage(self) -> PacerUsage:
        state = self._load()
        now = self.clock()
        active = state.cooldown_until is not None and now < state.cooldown_until
        return PacerUsage(
            last_hour=sum(1 for ts in state.requests if now - ts < HOUR_S),
            last_day=len(state.requests),
            hourly_budget=self.hourly_budget,
            daily_budget=self.daily_budget,
            cooldown_until=state.cooldown_until if active else None,
            cooldown_reason=state.cooldown_reason if active else None,
        )

    def _next_delay(self) -> float:
        delay = self.rng.uniform(self.min_delay_s, self.max_delay_s)
        # Occasionally take a longer pause, like a person stopping to read something.
        if self.rng.random() < 0.1:
            delay += self.rng.uniform(self.max_delay_s, self.max_delay_s * 3)
        return delay

    def _load(self) -> PacerState:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return PacerState()
        except (OSError, ValueError):
            logging.warning("Request log %s is unreadable; starting a new one", self.state_file)
            return PacerState()
        if not isinstance(raw, dict):
            return PacerState()

        now = self.clock()
        requests = sorted(
            float(ts) for ts in raw.get("requests", []) if isinstance(ts, (int, float)) and now - ts < DAY_S
        )
        cooldown_until = raw.get("cooldown_until")
        return PacerState(
            requests=requests,
            cooldown_until=float(cooldown_until) if isinstance(cooldown_until, (int, float)) else None,
            cooldown_reason=raw.get("cooldown_reason"),
        )

    def _save(self, state: PacerState) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self.state_file.with_suffix(".tmp")
        payload = {
            "requests": state.requests,
            "cooldown_until": state.cooldown_until,
            "cooldown_reason": state.cooldown_reason,
        }
        tmp_file.write_text(json.dumps(payload), encoding="utf-8")
        tmp_file.replace(self.state_file)
