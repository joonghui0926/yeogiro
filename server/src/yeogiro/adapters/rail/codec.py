from __future__ import annotations

from datetime import datetime
from typing import Any

from yeogiro.config import KST
from yeogiro.domain.models import Hold, Train


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
        seats_available=bool(data.get("seatsAvailable", True)),
    )


def hold_to_dict(hold: Hold) -> dict[str, Any]:
    return {
        "pnr": hold.pnr,
        "train": train_to_dict(hold.train),
        "fareTotal": hold.fare_total,
        "seat": hold.seat,
        "payBy": hold.pay_by.isoformat() if hold.pay_by else None,
        "provider": hold.provider,
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
    )


def mask_pnr(pnr: str) -> str:
    if len(pnr) <= 4:
        return "••••"
    return f"{pnr[:2]}{'•' * (len(pnr) - 4)}{pnr[-2:]}"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=KST)
