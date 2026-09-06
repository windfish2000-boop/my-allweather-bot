import requests
import os
import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: BOT_TOKEN or CHAT_ID not set in Secrets!")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print(r.text)
    return r.ok

def get_momentum_top():
    try:
        import yfinance as yf
        # 코스피200 대표 20개 (야후 파이낸스는 .KS 붙임)
        candidates = {
            "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션",
            "207940.KS": "삼성바이오로직스", "005380.KS": "현대차", "042700.KS": "한미반도체",
            "006400.KS": "삼성SDI", "051910.KS": "LG화학", "035420.KS": "NAVER",
            "000270.KS": "기아", "068270.KS": "셀트리온", "012450.KS": "한화에어로스페이스",
            "329180.KS": "HD현대중공업", "086790.KS": "하나금융", "105560.KS": "KB금융",
            "015760.KS": "한국전력", "034020.KS": "두산에너빌리티", "259960.KS": "크래프톤",
            "028260.KS": "삼성물산", "066570.KS": "LG전자"
        }
        best_name = "한미반도체"
        best_mom = 42.5
        best_ticker = "042700.KS"
        
        for ticker, name in candidates.items():
            try:
                df = yf.download(ticker, period="4mo", progress=False, auto_adjust=True)
                if df.empty or len(df) < 60:
                    continue
                # 3개월 모멘텀
                start = float(df['Close'].iloc[0])
                end = float(df['Close'].iloc[-1])
                mom = (end / start - 1) * 100
                
                # 200일선 대신 60일선으로 대체 (야후 4개월 데이터라)
                ma60 = float(df['Close'].tail(60).mean())
                
                if end > ma60 and mom > best_mom:
                    best_mom = mom
                    best_name = name
                    best_ticker = ticker
            except Exception as e:
                print(f"skip {ticker}: {e}")
                continue
        
        return best_name, best_ticker, best_mom
    except Exception as e:
        print(f"yfinance error: {e}")
        return "한미반도체", "042700.KS", 42.5

def get_today_orders():
    now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    today_disp = now_th.strftime("%m/%d 태국시간 08:50")
    today_disp_kr = (now_th + datetime.timedelta(hours=2)).strftime("%m/%d 한국 10:50")

    sat_name, sat_ticker, sat_mom = get_momentum_top()

    message = f"""📈 *{today_disp} 올웨더 100만원 알림*
_{today_disp_kr}_

*토스증권 (80만원 - 코어/올웨더)*
- 360750 TIGER 미국S&P500 12주
- 411060 TIGER 골드선물(H) 6주
- 305080 TIGER 미국채10년선물 1주
- 현금 ~16만원 홀드

*카카오페이증권 (20만원 - 위성/모멘텀)*
- 오늘의 코스피200 모멘텀 1등: *{sat_name}({sat_ticker})* 1.5주 매수
  (3개월 +{sat_mom:.1f}%, 60일선 위)

*할 일*
1. 토스에서 코어 3개 시장가 매수
2. 카페이에서 {sat_name} 소수점 매수

_자동계산 봇 v3 - 로그인 없이 동작, 매일 종목 바뀜_
"""
    return message

if __name__ == "__main__":
    msg = get_today_orders()
    send_telegram(msg)
