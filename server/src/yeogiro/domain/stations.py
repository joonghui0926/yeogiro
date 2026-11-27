"""Every passenger station the call can book, and how to tell apart names that sound alike.

The bundled list covers the Korail and SR stations with passenger stops. When the TAGO station
directory loads, its names are added, so a station missing here still resolves in production.
"""

from __future__ import annotations

from dataclasses import dataclass

# (station, province) for the stations Korail and SR stop at.
_BUNDLED: tuple[tuple[str, str], ...] = (
    # 서울·수도권
    ("서울", "서울"),
    ("용산", "서울"),
    ("영등포", "서울"),
    ("청량리", "서울"),
    ("상봉", "서울"),
    ("수서", "서울"),
    ("행신", "경기도"),
    ("광명", "경기도"),
    ("안양", "경기도"),
    ("수원", "경기도"),
    ("오산", "경기도"),
    ("서정리", "경기도"),
    ("평택", "경기도"),
    ("평택지제", "경기도"),
    ("동탄", "경기도"),
    ("양평", "경기도"),
    ("용문", "경기도"),
    ("평내호평", "경기도"),
    ("가평", "경기도"),
    # 경부선
    ("성환", "충청남도"),
    ("천안", "충청남도"),
    ("천안아산", "충청남도"),
    ("오송", "충청북도"),
    ("조치원", "세종"),
    ("전의", "세종"),
    ("부강", "세종"),
    ("신탄진", "대전"),
    ("대전", "대전"),
    ("서대전", "대전"),
    ("옥천", "충청북도"),
    ("이원", "충청북도"),
    ("심천", "충청북도"),
    ("영동", "충청북도"),
    ("황간", "충청북도"),
    ("추풍령", "충청북도"),
    ("김천", "경상북도"),
    ("김천구미", "경상북도"),
    ("구미", "경상북도"),
    ("약목", "경상북도"),
    ("왜관", "경상북도"),
    ("서대구", "대구"),
    ("대구", "대구"),
    ("동대구", "대구"),
    ("경산", "경상북도"),
    ("청도", "경상북도"),
    ("밀양", "경상남도"),
    ("삼랑진", "경상남도"),
    ("물금", "경상남도"),
    ("화명", "부산"),
    ("구포", "부산"),
    ("사상", "부산"),
    ("부산", "부산"),
    # 호남선
    ("공주", "충청남도"),
    ("계룡", "충청남도"),
    ("연산", "충청남도"),
    ("논산", "충청남도"),
    ("강경", "충청남도"),
    ("함열", "전라북도"),
    ("익산", "전라북도"),
    ("김제", "전라북도"),
    ("신태인", "전라북도"),
    ("정읍", "전라북도"),
    ("백양사", "전라남도"),
    ("장성", "전라남도"),
    ("광주송정", "광주"),
    ("광주", "광주"),
    ("극락강", "광주"),
    ("나주", "전라남도"),
    ("함평", "전라남도"),
    ("무안", "전라남도"),
    ("몽탄", "전라남도"),
    ("일로", "전라남도"),
    ("임성리", "전라남도"),
    ("목포", "전라남도"),
    # 전라선
    ("삼례", "전라북도"),
    ("전주", "전라북도"),
    ("임실", "전라북도"),
    ("오수", "전라북도"),
    ("남원", "전라북도"),
    ("곡성", "전라남도"),
    ("구례구", "전라남도"),
    ("순천", "전라남도"),
    ("여천", "전라남도"),
    ("여수엑스포", "전라남도"),
    # 장항선
    ("아산", "충청남도"),
    ("온양온천", "충청남도"),
    ("신창", "충청남도"),
    ("도고온천", "충청남도"),
    ("신례원", "충청남도"),
    ("예산", "충청남도"),
    ("삽교", "충청남도"),
    ("홍성", "충청남도"),
    ("광천", "충청남도"),
    ("청소", "충청남도"),
    ("대천", "충청남도"),
    ("웅천", "충청남도"),
    ("판교", "충청남도"),
    ("서천", "충청남도"),
    ("장항", "충청남도"),
    ("군산", "전라북도"),
    ("대야", "전라북도"),
    # 경전선
    ("진영", "경상남도"),
    ("창원중앙", "경상남도"),
    ("창원", "경상남도"),
    ("마산", "경상남도"),
    ("중리", "경상남도"),
    ("함안", "경상남도"),
    ("군북", "경상남도"),
    ("반성", "경상남도"),
    ("진주", "경상남도"),
    ("완사", "경상남도"),
    ("북천", "경상남도"),
    ("하동", "경상남도"),
    ("광양", "전라남도"),
    ("벌교", "전라남도"),
    ("보성", "전라남도"),
    ("화순", "전라남도"),
    # 중앙선·경강선·영동선·태백선
    ("서원주", "강원도"),
    ("원주", "강원도"),
    ("만종", "강원도"),
    ("횡성", "강원도"),
    ("둔내", "강원도"),
    ("평창", "강원도"),
    ("진부", "강원도"),
    ("강릉", "강원도"),
    ("정동진", "강원도"),
    ("묵호", "강원도"),
    ("동해", "강원도"),
    ("삼척", "강원도"),
    ("제천", "충청북도"),
    ("단양", "충청북도"),
    ("풍기", "경상북도"),
    ("영주", "경상북도"),
    ("안동", "경상북도"),
    ("의성", "경상북도"),
    ("영천", "경상북도"),
    ("하양", "경상북도"),
    ("영월", "강원도"),
    ("예미", "강원도"),
    ("민둥산", "강원도"),
    ("사북", "강원도"),
    ("고한", "강원도"),
    ("태백", "강원도"),
    ("철암", "강원도"),
    ("도계", "강원도"),
    ("춘양", "경상북도"),
    ("봉화", "경상북도"),
    ("분천", "경상북도"),
    ("남춘천", "강원도"),
    ("춘천", "강원도"),
    # 충북선·경북선
    ("오근장", "충청북도"),
    ("청주공항", "충청북도"),
    ("청주", "충청북도"),
    ("증평", "충청북도"),
    ("음성", "충청북도"),
    ("주덕", "충청북도"),
    ("충주", "충청북도"),
    ("점촌", "경상북도"),
    ("예천", "경상북도"),
    ("상주", "경상북도"),
    # 동해선
    ("경주", "경상북도"),
    ("포항", "경상북도"),
    ("영덕", "경상북도"),
    ("후포", "경상북도"),
    ("울진", "경상북도"),
    ("울산", "울산"),
    ("태화강", "울산"),
    ("북울산", "울산"),
    ("기장", "부산"),
    ("신해운대", "부산"),
    ("센텀", "부산"),
    ("부전", "부산"),
)

STATIONS: tuple[str, ...] = tuple(name for name, _ in _BUNDLED)
REGIONS: dict[str, str] = dict(_BUNDLED)

# A city name that is also a station, while callers often mean another station of that city.
CITY_STATIONS: dict[str, tuple[str, ...]] = {
    "광주": ("광주송정", "광주"),
    "대구": ("동대구", "대구", "서대구"),
    "천안": ("천안아산", "천안"),
    "김천": ("김천구미", "김천"),
    "평택": ("평택", "평택지제"),
    "울산": ("울산", "태화강"),
}

# Other ways callers and the speech recogniser name a station.
ALIASES: dict[str, str] = {
    "여수": "여수엑스포",
    "엑스포": "여수엑스포",
    "신경주": "경주",
    "통도사": "울산",
    "울산통도사": "울산",
    "진부오대산": "진부",
    "오대산": "진부",
    "청주공항역": "청주공항",
}

KTX_MINUTES_FROM_SEOUL: dict[str, int] = {
    "서울": 0,
    "용산": 0,
    "영등포": 10,
    "광명": 16,
    "수원": 32,
    "평택": 48,
    "천안아산": 38,
    "오송": 47,
    "대전": 61,
    "서대전": 66,
    "김천구미": 88,
    "동대구": 106,
    "경주": 124,
    "울산": 136,
    "부산": 157,
    "포항": 145,
    "익산": 86,
    "전주": 102,
    "광주송정": 112,
    "목포": 140,
    "순천": 158,
    "여수엑스포": 175,
    "청량리": 0,
    "강릉": 114,
}

CONVENTIONAL_ONLY: frozenset[str] = frozenset({"영등포", "수원", "평택", "서대전"})


# Places callers name that no train reaches, so a near-sounding station is never offered.
NO_TRAIN: frozenset[str] = frozenset({"제주", "제주도", "서귀포", "울릉도", "독도", "백령도"})

_catalogue: set[str] = set(STATIONS)


def register(names: list[str]) -> None:
    """Add station names from the live directory. Only plain Hangul names are spoken as is."""
    for raw in names:
        name = raw.replace("(", "").replace(")", "").replace(" ", "")
        if name and all("가" <= ch <= "힣" for ch in name):
            _catalogue.add(name)


def is_supported(name: str) -> bool:
    return name in _catalogue


def normalize(heard: str) -> str:
    name = "".join(heard.split())
    if name in ALIASES:
        return ALIASES[name]
    if name.endswith("역") and len(name) > 1:
        name = name[:-1]
    return ALIASES.get(name, name)


@dataclass(frozen=True, slots=True)
class StationMatch:
    """What a heard name points to.

    station is set when the name is a real station; certain is False when the caller should
    confirm it, because another station sounds alike or the name stands for several stations.
    candidates lists what to offer, best first.
    """

    station: str | None
    candidates: tuple[str, ...]
    certain: bool


def match(heard: str) -> StationMatch:
    name = normalize(heard)
    if name in NO_TRAIN:
        return StationMatch(None, (), False)
    if name in CITY_STATIONS:
        group = tuple(s for s in CITY_STATIONS[name] if s in _catalogue)
        return StationMatch(None, group, False)
    if name in _catalogue:
        alike = sorted(
            (s for s in _catalogue if s != name and sounds_alike(name, s)), key=_order(name)
        )
        return StationMatch(name, (name, *alike[:2]), not alike)
    close = sorted((s for s in _catalogue if _close(name, s)), key=_order(name))
    return StationMatch(None, tuple(close[:3]), False)


def label(name: str) -> str:
    """The station as read to the caller, with its province when that helps tell it apart."""
    region = REGIONS.get(name)
    if region is None or not region.endswith("도"):
        return f"{name}역"
    return f"{region} {name}역"


def sounds_alike(a: str, b: str) -> bool:
    distance = _distance(_jamo(a), _jamo(b))
    longest = max(len(_jamo(a)), len(_jamo(b)))
    return distance <= 1 or (distance <= 2 and longest >= 8)


def _close(heard: str, station: str) -> bool:
    distance = _distance(_jamo(heard), _jamo(station))
    return distance <= 2 or (distance <= 3 and len(_jamo(station)) >= 9)


def _order(heard: str):  # type: ignore[no-untyped-def]
    target = _jamo(heard)
    return lambda s: (_distance(target, _jamo(s)), s not in REGIONS, s)


_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = ("", *"ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")


def _jamo(text: str) -> list[str]:
    out: list[str] = []
    for ch in text:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            out += [_CHO[code // 588], _JUNG[(code % 588) // 28]]
            if code % 28:
                out.append(_JONG[code % 28])
        else:
            out.append(ch)
    return out


def _distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]
