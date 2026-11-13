from __future__ import annotations

from datetime import datetime
from typing import Any

from yeogiro.config import KST
from yeogiro.domain.models import Hold, Itinerary, Train


def train_to_dict(train: Train) -> dict[str, Any]:
    return {
        "trainNo": train.train_no,
        "grade": train.grade,
        "dep": train.dep,
        "arr": train.arr,
        "departsAt": train.departs_at.isoformat(),
        "arrivesAt": train.arrives_at.isoformat(),
        "fare": train.fare,
        "seatsAvailable": train.seats_available,
    }


def train_from_dict(data: dict[str, Any]) -> Train:
    return Train(
        train_no=str(data["trainNo"]),
        grade=str(data["grade"]),
        dep=str(data["dep"]),
        arr=str(data["arr"]),
        departs_at=_aware(datetime.fromisoformat(data["departsAt"])),
        arrives_at=_aware(datetime.fromisoformat(data["arrivesAt"])),
        fare=int(data.get("fare") or 0),
        seats_available=data.get("seatsAvailable"),
    )


def hold_to_dict(hold: Hold) -> dict[str, Any]:
    return {
        "pnr": hold.pnr,
        "train": train_to_dict(hold.train),
        "fareTotal": hold.fare_total,
        "seat": hold.seat,
        "payBy": hold.pay_by.isoformat() if hold.pay_by else None,
        "provider": hold.provider,
        "itinerary": itinerary_to_dict(hold.itinerary) if hold.itinerary else None,
        "legHolds": [hold_to_dict(leg) for leg in hold.leg_holds],
    }


def hold_from_dict(data: dict[str, Any]) -> Hold:
    pay_by = data.get("payBy")
    return Hold(
        pnr=str(data["pnr"]),
        train=train_from_dict(data["train"]),
        fare_total=int(data["fareTotal"]),
        seat=data.get("seat"),
        pay_by=_aware(datetime.fromisoformat(pay_by)) if pay_by else None,
        provider=str(data["provider"]),
        itinerary=itinerary_from_dict(data["itinerary"]) if data.get("itinerary") else None,
        leg_holds=tuple(hold_from_dict(leg) for leg in data.get("legHolds", [])),
    )


def itinerary_to_dict(route: Itinerary) -> dict[str, Any]:
    return {
        "kind": "transfer" if len(route.legs) > 1 else "direct",
        "legs": [train_to_dict(t) for t in route.legs],
        "transferCount": len(route.legs) - 1,
        "transferStation": route.legs[0].arr if len(route.legs) > 1 else None,
        "waitMinutes": route.wait_minutes,
        "durationMinutes": int(route.duration.total_seconds() // 60),
        "fare": route.fare,
        "seatAvailability": "unknown" if any(t.seats_available is None for t in route.legs)
        else "available" if all(t.seats_available for t in route.legs) else "unavailable",
    }


def itinerary_from_dict(data: dict[str, Any]) -> Itinerary:
    return Itinerary(tuple(train_from_dict(leg) for leg in data["legs"]))


def mask_pnr(pnr: str) -> str:
    if len(pnr) <= 4:
        return "••••"
    return f"{pnr[:2]}{'•' * (len(pnr) - 4)}{pnr[-2:]}"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=KST)
