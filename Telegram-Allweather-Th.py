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

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_tactical_signal(df, asset_type):
    """
    v5.1 200일선 + RSI 필터 - 종목별 맞춤
    """
    df['ma200'] = df['close'].rolling(200).mean()
    df['rsi'] = rsi(df['close'], 14)
    
    price = df['close'].iloc[-1]
    ma200 = df['ma200'].iloc[-1]
    r = df['rsi'].iloc[-1]
    
    if asset_type == 'SP500':  # 360750 TIGER 미국S&P500 / SPY
        if price > ma200 and r > 50:
            return "매수/보유", f"200일선 위 {ma200:.0f} + RSI {r:.0f} → 진짜 상승", price, ma200, r
        elif price < ma200 and r < 45:
            return "매도→채권이동", f"200일선 아래 + RSI {r:.0f} → 진짜 하락", price, ma200, r
        else:
            return "관망", f"휩소 차단! (가 200일선 아래지만 RSI {r:.0f}로 버팀)", price, ma200, r
            
    elif asset_type == 'GOLD':  # 411060 / GLD
        if price > ma200 and r > 60:
            return "매수/보유", f"골드 강세 RSI {r:.0f}", price, ma200, r
        elif price < ma200 and r < 40:
            return "매도→현금대기", f"골드 약세 RSI {r:.0f}", price, ma200, r
        else:
            return "관망", f"골드 관망 RSI {r:.0f}", price, ma200, r
            
    elif asset_type == 'BOND':  # 305080 / TLT
        if price > ma200:
            return "매수/보유", f"채권 상승 추세", price, ma200, r
        else:
            return "매도→현금대기", f"채권 하락", price, ma200, r

def get_momentum_top3():
    try:
        import yfinance as yf
        import pandas as pd
        
        # 한국 Top3 모멘텀 (기존 로직 유지)
        tickers_kr = {
            "삼성SDI": "006400.KS",
            "하나금융지주": "086790.KS",
            "KB금융": "105560.KS",
            "현대차": "005380.KS",
            "SK하이닉스": "000660.KS",
            "POSCO홀딩스": "005490.KS"
        }
        
        results = []
        for name, ticker in tickers_kr.items():
            try:
                df = yf.download(ticker, period="1y", progress=False)
                if len(df) < 200:
                    continue
                close = df['Close']
                # 6M + 3M 모멘텀 (v4 기존)
                mom6 = (close.iloc[-1] / close.iloc[-126] - 1) if len(close) > 126 else 0
                mom3 = (close.iloc[-1] / close.iloc[-63] - 1) if len(close) > 63 else 0
                score = (mom6 + mom3) / 2
                results.append((name, ticker, score, close.iloc[-1]))
            except Exception as e:
                print(f"Error {name}: {e}")
                continue
        
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:3]
    except Exception as e:
        print(f"Momentum error: {e}")
        return []

def get_allweather_tactical():
    """코어 올웨더 v5.1 필터"""
    try:
        import yfinance as yf
        
        # 해외 ETF로 200일선 체크 (한국 ETF는 yfinance 데이터 짧아서 SPY/GLD/TLT로 프록시)
        proxies = {
            "SP500": "SPY",   # -> 360750 매핑
            "GOLD": "GLD",    # -> 411060
            "BOND": "TLT"     # -> 305080
        }
        
        signals = {}
        for asset, ticker in proxies.items():
            df = yf.download(ticker, period="2y", progress=False)
            df = df.rename(columns={"Close": "close"})
            # yfinance multi-index 대응
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                if 'close' not in df.columns and 'Close' in df.columns:
                    df = df.rename(columns={"Close": "close"})
            
            sig, reason, price, ma200, r = get_tactical_signal(df, asset)
            signals[asset] = {
                "signal": sig,
                "reason": reason,
                "price": price,
                "ma200": ma200,
                "rsi": r
            }
        return signals
    except Exception as e:
        print(f"Tactical error: {e}")
        import traceback
        traceback.print_exc()
        return {}

if __name__ == "__main__":
    import pandas as pd
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 1. 코어 올웨더 v5.1 신호
    tactical = get_allweather_tactical()
    
    # 2. 위성 Top3
    top3 = get_momentum_top3()
    
    # 메시지 조립
    msg = f"📊 *v5.1 올웨더 (200일선+RSI) {today}*\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"*[코어 80만원 - Tactical 필터]*\n"
    
    action_needed = []
    
    if tactical:
        for asset, data in tactical.items():
            kr_name = {"SP500": "S&P500(360750)", "GOLD": "골드(411060)", "BOND": "채권(305080)"}[asset]
            emoji = "🟢" if "매수" in data['signal'] else "🔴" if "매도" in data['signal'] else "🟡"
            msg += f"{emoji} {kr_name}: *{data['signal']}*\n"
            msg += f"   └ {data['reason']}\n"
            msg += f"   └ 현재가 {data['price']:.1f} / 200일선 {data['ma200']:.1f} / RSI {data['rsi']:.0f}\n"
            if "매도" in data['signal']:
                action_needed.append(f"{kr_name} 매도")
    else:
        msg += "⚠️ 코어 데이터 로드 실패\n"
    
    msg += f"\n*[위성 20만원 - Top3 모멘텀]*\n"
    if top3:
        for i, (name, ticker, score, price) in enumerate(top3, 1):
            msg += f"{i}. {name} (점수 {score*100:.1f}%)\n"
    else:
        msg += "Top3 로드 실패 - 기존 홀딩 유지\n"
    
    msg += f"\n━━━━━━━━━━━━━━━━━━\n"
    if action_needed:
        msg += f"🚨 *오늘 액션:* {', '.join(action_needed)}\n"
        msg += f"→ 매도 자금은 채권/현금으로 이동 대기\n"
    else:
        msg += f"✅ 오늘 액션 없음 - 전량 보유\n"
    
    msg += f"\n_v5.1 공식: S&P(200일+RSI50) / 골드(200일+RSI60/40) / 채권(200일)_"
    
    send_telegram(msg)


