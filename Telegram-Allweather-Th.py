import requests
import os
import datetime

# 깃허브 Secrets에서 가져옴 (안전)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8898267229:AAGlwJQGxm811XsbT-w3QwA73a-ArQaq10c")
CHAT_ID = os.getenv("CHAT_ID", "5810370335")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print(r.text)
    return r.ok

def get_today_orders():
    # 태국시간 기준
    now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    today = now_th.strftime("%m/%d 태국시간 08:50")
    
    message = f"""📈 *{today} 올웨더 100만원 알림*

*토스증권 (80만원 - 코어)*
- 360750 TIGER 미국S&P500 12주
- 411060 TIGER 골드선물(H) 6주
- 305080 TIGER 미국채10년선물 1주
- 현금 28만원 홀드

*카카오페이증권 (20만원 - 위성)*
- 오늘의 코스피200 모멘텀 1등: *한미반도체* 1.2주 매수
  (3개월 +42%, 200일선 위)

*할 일*
1. 토스에서 위 3개 시장가 매수
2. 카페이에서 한미반도체 소수점 매수

폭락 체크: OFF
"""
    return message

if __name__ == "__main__":
    msg = get_today_orders()
    send_telegram(msg)
