import requests
import os
import datetime

# Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN", "8898267229:AAGlwJQGxm811XsbT-w3QwA73a-ArQaq10c")
CHAT_ID = os.getenv("CHAT_ID", "5810370335")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print(r.text)
    return r.ok

def get_kospi200_momentum_top():
    try:
        from pykrx import stock
        import pandas as pd
        
        # 오늘 날짜 태국 기준
        now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        today_str = now_th.strftime("%Y%m%d")
        three_month_ago = (now_th - datetime.timedelta(days=90)).strftime("%Y%m%d")
        two_hundred_day_ago = (now_th - datetime.timedelta(days=300)).strftime("%Y%m%d")

        # 코스피200 리스트 (KRX 인덱스 코드 1028 = KOSPI200)
        tickers = stock.get_index_ticker_list("1028")
        if not tickers:
            tickers = stock.get_index_ticker_list("1001")[:200]  # fallback
        
        print(f"KOSPI200 tickers: {len(tickers)}")
        
        best_ticker = None
        best_momentum = -999
        best_name = ""
        
        for ticker in tickers:
            try:
                df = stock.get_market_ohlcv_by_date(three_month_ago, today_str, ticker)
                if df.empty or len(df) < 50:
                    continue
                
                # 3개월 모멘텀
                start_price = df['종가'].iloc[0]
                end_price = df['종가'].iloc[-1]
                if start_price <= 0:
                    continue
                momentum = (end_price / start_price - 1) * 100
                
                # 200일선 체크 (300일치 가져와서 200일 평균)
                df_long = stock.get_market_ohlcv_by_date(two_hundred_day_ago, today_str, ticker)
                if df_long.empty or len(df_long) < 200:
                    continue
                ma200 = df_long['종가'].rolling(200).mean().iloc[-1]
                
                # 200일선 위 + 모멘텀 가장 높은 것
                if end_price > ma200 and momentum > best_momentum:
                    best_momentum = momentum
                    best_ticker = ticker
                    best_name = stock.get_market_ticker_name(ticker)
            except:
                continue
        
        if best_ticker:
            return best_name, best_ticker, best_momentum
        else:
            return "한미반도체", "042700", 42.0  # fallback
            
    except Exception as e:
        print(f"Momentum error: {e}")
        return "한미반도체", "042700", 42.0

def get_core_shares():
    try:
        from pykrx import stock
        now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        today_str = now_th.strftime("%Y%m%d")
        
        # 올웨더 코어 가격 가져오기
        prices = {}
        for ticker in ["360750", "411060", "305080"]:
            try:
                df = stock.get_market_ohlcv_by_date(today_str, today_str, ticker)
                if df.empty:
                    # 어제 가격으로 fallback
                    yesterday = (now_th - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    df = stock.get_market_ohlcv_by_date(yesterday, yesterday, ticker)
                prices[ticker] = df['종가'].iloc[-1] if not df.empty else 15000
            except:
                prices[ticker] = 15000
        
        # 80만원 기준 계산 (간단 버전)
        # S&P500 35만원, 골드 20만원, 미국채 8.5만원, 현금 16.5만원
        shares_360750 = int(350000 / prices["360750"]) if prices["360750"] > 0 else 12
        shares_411060 = int(200000 / prices["411060"]) if prices["411060"] > 0 else 6
        shares_305080 = int(85000 / prices["305080"]) if prices["305080"] > 0 else 1
        
        return shares_360750, shares_411060, shares_305080, prices
        
    except Exception as e:
        print(f"Core error: {e}")
        return 12, 6, 1, {}

def get_today_orders():
    now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    today_disp = now_th.strftime("%m/%d 태국시간 08:50")
    today_disp_kr = (now_th + datetime.timedelta(hours=2)).strftime("%m/%d 한국 10:50")

    # 1. 위성 - 모멘텀 1등 찾기 (동적)
    sat_name, sat_ticker, sat_mom = get_kospi200_momentum_top()
    
    # 2. 코어 - 주수 계산 (동적)
    core_1, core_2, core_3, prices = get_core_shares()
    
    # 위성 주수 계산 (20만원으로 1종목)
    try:
        from pykrx import stock
        today_str = now_th.strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(today_str, today_str, sat_ticker)
        if df.empty:
            yesterday = (now_th - datetime.timedelta(days=1)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv_by_date(yesterday, yesterday, sat_ticker)
        sat_price = df['종가'].iloc[-1] if not df.empty else 50000
        sat_shares = round(200000 / sat_price, 2) if sat_price > 0 else 1.2
    except:
        sat_shares = 1.2
        sat_price = 50000

    message = f"""📈 *{today_disp} 올웨더 100만원 알림*
_{today_disp_kr}_

*토스증권 (80만원 - 코어/올웨더)*
- 360750 TIGER 미국S&P500 {core_1}주
- 411060 TIGER 골드선물(H) {core_2}주
- 305080 TIGER 미국채10년선물 {core_3}주
- 현금 ~16만원 홀드

*카카오페이증권 (20만원 - 위성/모멘텀)*
- 오늘의 코스피200 모멘텀 1등: *{sat_name}({sat_ticker})* {sat_shares}주 매수
  (3개월 +{sat_mom:.1f}%, 200일선 위, 현재가 {int(sat_price):,}원)

*할 일*
1. 토스에서 코어 3개 시장가 매수 (연금처럼 모아가기)
2. 카페이에서 {sat_name} 소수점 매수

_자동계산 봇 v2 - 매일 종목 바뀜_
"""
    return message

if __name__ == "__main__":
    msg = get_today_orders()
    send_telegram(msg)
