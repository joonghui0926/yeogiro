from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from yeogiro.config import KST
from yeogiro.domain.models import Hold, Train
from yeogiro.ports import HoldFailed, RailUnavailable


class KorailClient:
    """Blocking client over korail2. Only the rail worker uses it, one job at a time."""

    def __init__(self, member_id: str, password: str) -> None:
        try:
            from korail2 import Korail
        except ImportError as error:
            raise RailUnavailable("korail2 is not installed (pip install .[korail])") from error
        self._korail = Korail(member_id, password, auto_login=False)
        self._logged_in = False
        self._raw_trains: dict[str, Any] = {}

    def login(self) -> None:
        try:
            ok = self._korail.login()
        except Exception as error:
            raise RailUnavailable(f"login error: {error}") from error
        if not ok:
            raise RailUnavailable("login rejected")
        self._logged_in = True

    def search(self, dep: str, arr: str, day: date, after: time | None) -> list[Train]:
        from korail2 import NoResultsError, TrainType

        self._ensure_login()
        start = (after or time(5, 0)).strftime("%H%M%S")
        try:
            raw_trains = self._korail.search_train(
                dep,
                arr,
                day.strftime("%Y%m%d"),
                start,
                train_type=TrainType.ALL,
                include_no_seats=True,
            )
        except NoResultsError:
            return []
        except Exception as error:
            raise RailUnavailable(f"search error: {error}") from error

        trains = []
        for raw in raw_trains:
            train = _to_train(raw, dep, arr)
            self._raw_trains[train.key] = raw
            trains.append(train)
        return trains

    def hold(self, train: Train, party: int, senior: bool) -> Hold:
        from korail2 import AdultPassenger, ReserveOption, SeniorPassenger

        self._ensure_login()
        raw = self._raw_trains.get(train.key)
        if raw is None:
            self.search(train.dep, train.arr, train.departs_at.date(), train.departs_at.time())
            raw = self._raw_trains.get(train.key)
        if raw is None:
            raise HoldFailed("열차를 다시 찾지 못함")

        passengers = [SeniorPassenger(1) if senior else AdultPassenger(1)]
        if party > 1:
            passengers.append(AdultPassenger(party - 1))
        try:
            reservation = self._korail.reserve(
                raw, passengers=passengers, option=ReserveOption.GENERAL_ONLY
            )
        except Exception as error:
            raise HoldFailed(f"예약 실패: {error}") from error

        return Hold(
            pnr=str(reservation.rsv_id),
            train=train,
            fare_total=int(getattr(reservation, "price", 0) or 0),
            seat=None,
            pay_by=_deadline(reservation),
            provider="korail",
        )

    def cancel(self, pnr: str) -> bool:
        self._ensure_login()
        for reservation in self._korail.reservations():
            if str(reservation.rsv_id) == pnr:
                self._korail.cancel(reservation)
                return True
        return False

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self.login()


def _to_train(raw: Any, dep: str, arr: str) -> Train:
    departs = datetime.strptime(f"{raw.dep_date}{raw.dep_time}", "%Y%m%d%H%M%S")
    arrives = datetime.strptime(f"{raw.arr_date}{raw.arr_time}", "%Y%m%d%H%M%S")
    has_seat = raw.has_general_seat() if hasattr(raw, "has_general_seat") else True
    return Train(
        train_no=str(int(raw.train_no)),
        grade=str(raw.train_type_name),
        dep=dep,
        arr=arr,
        departs_at=departs.replace(tzinfo=KST),
        arrives_at=arrives.replace(tzinfo=KST),
        fare=0,
        seats_available=bool(has_seat),
    )


def _deadline(reservation: Any) -> datetime | None:
    limit_date = getattr(reservation, "buy_limit_date", None)
    limit_time = getattr(reservation, "buy_limit_time", None)
    if not limit_date or not limit_time:
        return None
    try:
        return datetime.strptime(f"{limit_date}{limit_time}", "%Y%m%d%H%M%S").replace(tzinfo=KST)
    except ValueError:
        return None
