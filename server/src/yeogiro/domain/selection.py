from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from yeogiro.domain.models import Choice, Itinerary, TimeAnchor, Train, TravelWindow

# Minutes of departure-time difference worth one minute of riding time. A caller who asks for
# "morning" is better served by a KTX twenty minutes later than a four-hour local at the exact time.
RIDE_WEIGHT = 0.3
# Standing on a platform between trains costs an older caller as much as leaving at another time.
WAIT_WEIGHT = 1.0


def _cost(train: Train, anchor: datetime) -> float:
    gap = abs((train.departs_at - anchor).total_seconds()) / 60
    ride = train.duration.total_seconds() / 60
    return gap + RIDE_WEIGHT * ride


def _asked_rank(train: Train, target: datetime, anchor: TimeAnchor) -> tuple[bool, float]:
    """Order for a time the caller named: at or before it first, then the smallest gap.

    Many early trains never outrank one that is just before the asked time, and a train after
    the asked time only comes up when nothing at or before it is bookable.
    """
    moment = train.arrives_at if anchor == "arrives" else train.departs_at
    return moment > target, abs((moment - target).total_seconds())


def choose_train(
    trains: Sequence[Train],
    window: TravelWindow,
    earliest_departure: datetime,
    force_preferred_sold_out: bool = False,
) -> Choice | None:
    bookable = [t for t in trains if t.departs_at >= earliest_departure]
    if not bookable:
        return None

    if window.asked is not None:
        return _choose_by_asked_time(bookable, window, earliest_departure, force_preferred_sold_out)

    center = datetime.combine(window.day, window.center, tzinfo=earliest_departure.tzinfo)
    in_window = sorted(
        (t for t in bookable if window.start <= t.departs_at.time() <= window.end),
        key=lambda t: _cost(t, center),
    )
    preferred = in_window[0] if in_window else min(bookable, key=lambda t: _cost(t, center))
    if preferred.seats_available is not False and not force_preferred_sold_out:
        return Choice(train=preferred, sold_out_preferred=None)

    with_seats = [t for t in bookable if t.seats_available is not False and t is not preferred]
    if not with_seats:
        return None
    alternative = min(with_seats, key=lambda t: _cost(t, preferred.departs_at))
    return Choice(train=alternative, sold_out_preferred=preferred)


def choose_route(
    routes: Sequence[Itinerary], window: TravelWindow, earliest_departure: datetime
) -> Itinerary | None:
    """The journey a caller asking for this time of day is best served by, weighed like a train.

    When the caller named a departure or arrival time, the same rule as for direct trains applies:
    at or before that time first, then the smallest gap.
    """
    bookable = [r for r in routes if r.legs[0].departs_at >= earliest_departure]
    if not bookable:
        return None

    if window.asked is not None:
        target = datetime.combine(window.day, window.asked, tzinfo=earliest_departure.tzinfo)

        def rank(route: Itinerary) -> tuple[bool, float]:
            moment = (
                route.legs[-1].arrives_at if window.anchor == "arrives" else route.legs[0].departs_at
            )
            return moment > target, abs((moment - target).total_seconds())

        return min(bookable, key=rank)

    center = datetime.combine(window.day, window.center, tzinfo=earliest_departure.tzinfo)

    def cost(route: Itinerary) -> float:
        gap = abs((route.legs[0].departs_at - center).total_seconds()) / 60
        ride = sum(t.duration.total_seconds() for t in route.legs) / 60
        return gap + RIDE_WEIGHT * ride + WAIT_WEIGHT * route.wait_minutes

    in_window = [r for r in bookable if window.start <= r.legs[0].departs_at.time() <= window.end]
    pool = in_window or bookable
    return min(pool, key=cost) if pool else None


def _choose_by_asked_time(
    bookable: Sequence[Train],
    window: TravelWindow,
    earliest_departure: datetime,
    force_preferred_sold_out: bool,
) -> Choice | None:
    assert window.asked is not None
    target = datetime.combine(window.day, window.asked, tzinfo=earliest_departure.tzinfo)
    by_arrival = window.anchor == "arrives"

    def rank(t: Train) -> tuple[bool, float]:
        return _asked_rank(t, target, window.anchor)

    preferred = min(bookable, key=rank)
    if preferred.seats_available is not False and not force_preferred_sold_out:
        return Choice(train=preferred, sold_out_preferred=None, by_arrival=by_arrival)

    with_seats = [t for t in bookable if t.seats_available is not False and t is not preferred]
    if not with_seats:
        return None
    return Choice(
        train=min(with_seats, key=rank), sold_out_preferred=preferred, by_arrival=by_arrival
    )


def adjacent_train(
    trains: Sequence[Train],
    current: Train,
    direction: Literal["earlier", "later"],
    earliest_departure: datetime,
) -> Train | None:
    pool = [
        t
        for t in trains
        if t.seats_available is not False and t.departs_at >= earliest_departure and t.key != current.key
    ]
    if direction == "later":
        later = [t for t in pool if t.departs_at > current.departs_at]
        return min(later, key=lambda t: t.departs_at) if later else None
    earlier = [t for t in pool if t.departs_at < current.departs_at]
    return max(earlier, key=lambda t: t.departs_at) if earlier else None
