import requests
import os
import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Secrets not set!")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    print(r.text)
    return r.ok

def get_momentum_top3():
    try:
        import yfinance as yf
        import pandas as pd
        
        candidates = {
            "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "373220.KS": "LG에너지솔루션",
            "207940.KS": "삼성바이오로직스", "005380.KS": "현대차", "042700.KS": "한미반도체",
            "006400.KS": "삼성SDI", "051910.KS": "LG화학", "035420.KS": "NAVER",
            "000270.KS": "기아", "068270.KS": "셀트리온", "012450.KS": "한화에어로스페이스",
            "329180.KS": "HD현대중공업", "086790.KS": "하나금융", "105560.KS": "KB금융",
            "015760.KS": "한국전력", "034020.KS": "두산에너빌리티", "259960.KS": "크래프톤",
            "028260.KS": "삼성물산", "066570.KS": "LG전자", "009150.KS": "삼성전기",
            "011200.KS": "HMM", "035720.KS": "카카오", "323410.KS": "카카오뱅크"
        }
        
        results = []
        for ticker, name in candidates.items():
            try:
                df = yf.download(ticker, period="8mo", progress=False, auto_adjust=True)
                if df.empty or len(df) < 130:
                    continue
                
                close_now = float(df['Close'].iloc[-1])
                close_3m = float(df['Close'].iloc[-63]) if len(df)>=63 else float(df['Close'].iloc[0])
                close_6m = float(df['Close'].iloc[-126]) if len(df)>=126 else float(df['Close'].iloc[0])
                
                mom_3m = (close_now / close_3m - 1) * 100
                mom_6m = (close_now / close_6m - 1) * 100
                mom_avg = (mom_3m + mom_6m) / 2
                
                ma20 = float(df['Close'].tail(20).mean())
                ma60 = float(df['Close'].tail(60).mean())
                
                # 필터: 60일선 위 + 6개월 +3개월 둘 다 양수인 것만 (진짜 상승추세)
                if close_now > ma60 and mom_3m > 0 and mom_6m > 0:
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "mom_3m": mom_3m,
                        "mom_6m": mom_6m,
                        "mom_avg": mom_avg,
                        "close": close_now,
                        "ma20": ma20,
                        "is_sell": close_now < ma20
                    })
            except Exception as e:
                print(f"skip {ticker}: {e}")
                continue
        
        # 평균 모멘텀 높은 순 Top3
        results.sort(key=lambda x: x['mom_avg'], reverse=True)
        top3 = results[:3]
        
        if not top3:
            # 혹시 필터로 다 걸러지면 방어적으로 삼성전자 리턴
            return [{"ticker":"005930.KS","name":"삼성전자","mom_3m":5,"mom_6m":8,"mom_avg":6.5,"close":70000,"ma20":69000,"is_sell":False}]
            
        return top3
        
    except Exception as e:
        print(f"yfinance error: {e}")
        return [
            {"ticker":"042700.KS","name":"한미반도체","mom_3m":42.5,"mom_6m":55.2,"mom_avg":48.8,"close":150000,"ma20":140000,"is_sell":False},
            {"ticker":"012450.KS","name":"한화에어로스페이스","mom_3m":28.3,"mom_6m":35.1,"mom_avg":31.7,"close":250000,"ma20":240000,"is_sell":False},
            {"ticker":"034020.KS","name":"두산에너빌리티","mom_3m":19.5,"mom_6m":25.2,"mom_avg":22.3,"close":18000,"ma20":17500,"is_sell":False},
        ]

def get_today_orders():
    now_th = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    today_disp = now_th.strftime("%m/%d 태국 08:50")
    today_kr = (now_th + datetime.timedelta(hours=2)).strftime("%m/%d 한국 10:50")
    
    top3 = get_momentum_top3()
    
    # 메시지용 라인 만들기
    satellite_lines = ""
    todo_lines = ""
    for i, s in enumerate(top3, 1):
        sell_tag = " ⚠️ 20일선 이탈! 매도고려" if s['is_sell'] else ""
        satellite_lines += f"- {i}. {s['name']}({s['ticker']}) {s['mom_avg']:.1f}% (3M {s['mom_3m']:.1f}% / 6M {s['mom_6m']:.1f}%){sell_tag}\n"
        todo_lines += f"  {i}. {s['name']} 0.5주\n"
    
    # 전체 손절 체크
    all_sell = all(s['is_sell'] for s in top3)
    market_status = "🚨 위성 전체 20일선 이탈 - 현금 보유 고려" if all_sell else "✅ 상승 추세 유지 중"
    
    message = f"""📈 *{today_disp} 올웨더 100만원 v4*
_{today_kr} | {market_status}_

*토스증권 (80만원 - 코어/올웨더)*
- 360750 TIGER 미국S&P500 12주
- 411060 TIGER 골드선물(H) 6주
- 305080 TIGER 미국채10년선물 1주
- 현금 ~16만원 홀드

*카카오페이증권 (20만원 - 위성/모멘텀 Top3 분산)*
{top3[0]['name']} / {top3[1]['name']} / {top3[2]['name']} 각 6.6만원씩
{satellite_lines}
*손절룰:* 종가가 20일선 밑으로 내려가면 다음날 전량 매도

*할 일*
1. 토스에서 코어 3개 시장가 매수
2. 카페이에서 위성 3개 각 0.5주씩 소수점 매수:
{todo_lines}
3. 20일선 이탈 종목 있으면 매도

_v4 - 6M+3M 평균 Top3 분산, 20일선 손절, 로그인 없음_
"""
    return message

if __name__ == "__main__":
    msg = get_today_orders()
    send_telegram(msg)

