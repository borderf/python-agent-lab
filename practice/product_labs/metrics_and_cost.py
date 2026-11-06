"""Fictional cohort and cost lesson. No market or causal claims."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class Event:
    event_id: str
    account: str
    name: str
    at: datetime


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def main() -> None:
    invited = {f"a{i:02d}" for i in range(1, 21)}
    start = instant("2026-10-05T00:00:00+00:00")
    week2 = instant("2026-10-12T00:00:00+00:00")
    end = instant("2026-10-19T00:00:00+00:00")
    events = [
        Event(f"first-{i}", f"a{i:02d}", "task_completed", start)
        for i in range(1, 9)
    ] + [
        Event(f"return-{i}", f"a{i:02d}", "task_completed", week2)
        for i in range(1, 6)
    ]
    events.extend([
        events[0],  # Delivery duplicate: same event ID and content.
        Event("extra-first", "a01", "task_completed", start),
        Event("not-cohort", "a19", "task_completed", week2),
        Event("outside-window", "a06", "task_completed", end),
        Event("internal", "staff", "task_completed", start),
    ])
    unique: dict[str, Event] = {}
    for event in events:
        if event.event_id in unique and unique[event.event_id] != event:
            raise ValueError("event ID reused with changed content")
        unique[event.event_id] = event
    eligible = [e for e in unique.values()
                if e.account in invited and e.name == "task_completed"]
    cohort = {e.account for e in eligible if start <= e.at < week2}
    returned = {e.account for e in eligible
                if e.account in cohort and week2 <= e.at < end}
    assert len(cohort) == 8 and len(returned) == 5
    assert ratio(len(cohort), len(invited)) == 0.4
    assert ratio(len(returned), len(cohort)) == 0.625
    assert ratio(0, 0) is None

    revenue, model, infrastructure, support = map(Decimal, ["2000", "400", "200", "500"])
    contribution = revenue - model - infrastructure - support
    assert contribution == Decimal("900")
    assert contribution / revenue == Decimal("0.45")
    assert Decimal("3600") / contribution == Decimal("4")
    assert revenue - model * 2 - infrastructure - support == Decimal("500")
    assert revenue - model - infrastructure - support * 2 == Decimal("400")
    print("PASS: deduplication, cohort, time boundaries, denominator, cost scenarios")
    print("Activation=8/20=40%; week-2 cohort retention=5/8=62.5%")
    print("Contribution=900; not net profit or a market validation")


if __name__ == "__main__":
    main()
