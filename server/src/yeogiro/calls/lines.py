"""Every fixed sentence the call says, in one place so the voice can be tuned without code changes.

Sentences the model composes on its own are limited to answers built from tool facts.
"""

GREETING = "여기로 기차 예약 AI예요. 어디로, 언제 가세요?"

ASK_DEPARTURE = "어디서 타세요?"
ASK_ARRIVAL = "어디로 가세요?"
ASK_DATE = "언제 가세요?"
ASK_SENIOR = "만 65세 넘으셨어요?"

NO_SEATS_THAT_DAY = "{day}에는 {arrival} 가는 기차 자리가 없어요. 다른 날로 찾아볼까요?"
NO_ADJACENT = "그 {side}에는 자리 있는 기차가 없어요. 아까 기차로 할까요?"
SENIOR_NOTED = "네, 알겠어요."

HOLDING = "자리 잡을게요. 잠시만요."
HOLDING_STILL = "자리 잡는 중이에요. 조금만 기다려 주세요."
SEAT_GONE = "그 기차는 방금 자리가 없어졌어요. 다른 기차로 찾아볼까요?"
RAIL_DOWN = "지금은 예약이 잘 안 돼요. 열차 정보만 문자로 보내드릴게요."

PAY_PROMPT = "화면에 노란 결제 버튼이 나왔어요. 눌러 주세요."
PAY_REMINDER = "전화기를 귀에서 떼고, 화면 아래 노란 버튼을 눌러 주세요."
PAY_REMINDER_LAST = "노란 버튼만 누르시면 끝나요."
PAY_EXPIRED = "결제가 안 돼서 자리는 풀어 둘게요. 다시 전화 주시면 도와드릴게요."
PAID = "결제됐어요. 문자로 표 보내드렸어요. 더 필요하신 거 있으세요?"

NOT_CONFIRMED_TWICE = "열차 정보만 문자로 보내드릴게요. 더 필요하신 거 있으세요?"
NUDGE = "천천히 말씀하셔도 돼요."
SILENT_GOODBYE = "다시 전화 주시면 도와드릴게요. 조심히 계세요."
GOODBYE = "조심히 다녀오세요."

NOTHING_TO_CANCEL = "취소할 예약이 없어요."
CANCELLED = "예약을 취소했어요."
TRIP_DROPPED = "네, 알겠어요. 더 필요하신 거 있으세요?"
THANKS_GOODBYE = "네, 감사합니다."
SOMETHING_WENT_WRONG = "잠깐 문제가 생겼어요. 다시 한 번 말씀해 주시겠어요?"

REFUSALS = {
    "option": "다시 한 번 찾아볼게요.",
    "lead": "출발이 너무 가까워서 예약이 어려워요. 다른 시간으로 찾아볼까요?",
    "limits": "오늘은 예약을 더 할 수 없어요. 내일 다시 전화 주세요.",
    "duplicate": "그 기차는 이미 잡아 두셨어요.",
    "switch": "지금은 예약을 받을 수 없어요. 열차 정보만 문자로 보내드릴게요.",
}
