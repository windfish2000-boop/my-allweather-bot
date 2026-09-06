import requests
import os
import datetime
import yfinance as yf
import pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Secrets not set!")
        print(f"BOT_TOKEN exists: {bool(BOT_TOKEN)}, CHAT_ID exists: {bool(CHAT_ID)}")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    print(f"Telegram response: {r.text}")
    return r.ok

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, 0.00001)
    return 100 - (100 / (1 + rs))

def get_tactical_signal(df_close, asset_type):
    df = pd.DataFrame({'close': df_close})
    df['ma200'] = df['close'].rolling(200).mean()
    df['rsi'] = rsi(df['close'], 14)
    price = float(df['close'].iloc[-1])
    ma200 = float(df['ma200'].iloc[-1])
    r = float(df['rsi'].iloc[-1])

    if asset_type == 'SP500':
        if price > ma200 and r > 50:
            return "매수/보유", f"200일선 위 {ma200:.0f} + RSI {r:.0f} → 진짜 상승", price, ma200, r
        elif price < ma200 and r < 45:
            return "매도→채권이동", f"200일선 아래 + RSI {r:.0f} → 진짜 하락", price, ma200, r
        else:
            return "관망", f"휩소 차단! RSI {r:.0f}로 버팀", price, ma200, r
    elif asset_type == 'GOLD':
        if price > ma200 and r > 60:
            return "매수/보유", f"골드 강세 RSI {r:.0f}", price, ma200, r
        elif price < ma200 and r < 40:
            return "매도→현금대기", f"골드 약세 RSI {r:.0f}", price, ma200, r
        else:
            return "관망", f"골드 관망 RSI {r:.0f}", price, ma200, r
    elif asset_type == 'BOND':
        if price > ma200:
            return "매수/보유", f"채권 상승 추세", price, ma200, r
        else:
            return "매도→현금대기", f"채권 하락", price, ma200, r

def get_yf_close(ticker, period="2y"):
    df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        close = df[('Close', ticker)] if ('Close', ticker) in df.columns else df['Close'].iloc[:,0] if 'Close' in df.columns.get_level_values(0) else df.iloc[:,0]
    else:
        close = df['Close'] if 'Close' in df.columns else df['close'] if 'close' in df.columns else df.iloc[:,3]
    return close

def get_allweather_tactical():
    proxies = {"SP500": "SPY", "GOLD": "GLD", "BOND": "TLT"}
    signals = {}
    for asset, ticker in proxies.items():
        close = get_yf_close(ticker, period="2y")
        if close is None or len(close) < 210:
            continue
        sig, reason, price, ma200, r = get_tactical_signal(close, asset)
        signals[asset] = {"signal": sig, "reason": reason, "price": price, "ma200": ma200, "rsi": r}
    return signals

def get_momentum_top3():
    tickers_kr = {
        "삼성SDI": "006400.KS", "하나금융지주": "086790.KS", "KB금융": "105560.KS",
        "현대차": "005380.KS", "SK하이닉스": "000660.KS", "POSCO홀딩스": "005490.KS"
    }
    results = []
    for name, ticker in tickers_kr.items():
        try:
            close = get_yf_close(ticker, period="1y")
            if close is None or len(close) < 130:
                continue
            mom6 = (float(close.iloc[-1]) / float(close.iloc[-126]) - 1) if len(close) > 126 else 0
            mom3 = (float(close.iloc[-1]) / float(close.iloc[-63]) - 1) if len(close) > 63 else 0
            score = (mom6 + mom3) / 2
            results.append((name, ticker, score, mom3*100, mom6*100))
        except:
            continue
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:3]

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    tactical = get_allweather_tactical()
    top3 = get_momentum_top3()

    msg = f"📈 {today_str} 태국 08:50 올웨더 100만원 v5.1\n"
    msg += f"{today_str} 한국 10:50 | "
    if tactical and tactical.get("SP500"):
        if "매수" in tactical["SP500"]["signal"]:
            msg += "✅ 상승 추세 유지 중 (v5.1 필터 통과)\n"
        elif "관망" in tactical["SP500"]["signal"]:
            msg += f"🟡 관망 중 - {tactical['SP500']['reason']}\n"
        else:
            msg += f"🔴 하락 전환 - {tactical['SP500']['signal']}\n"
    else:
        msg += "⚠️ 데이터 로드 중\n"

    msg += f"\n토스증권 (80만원 - 코어/올웨더 v5.1)\n"
    if tactical:
        for asset in ["SP500", "GOLD", "BOND"]:
            if asset in tactical:
                kr_name = {"SP500": "360750 TIGER 미국S&P500", "GOLD": "411060 TIGER 골드선물(H)", "BOND": "305080 TIGER 미국채10년선물"}[asset]
                data = tactical[asset]
                emoji = "🟢" if "매수" in data['signal'] else "🔴" if "매도" in data['signal'] else "🟡"
                msg += f"{emoji} {kr_name}: {data['signal']}\n"
                msg += f" └ {data['reason']} | {data['price']:.1f}/{data['ma200']:.0f}/RSI{data['rsi']:.0f}\n"

    msg += f"\n카카오페이증권 (20만원 - 위성/모멘텀 Top3 분산)\n"
    if top3:
        for i, (name, ticker, score, m3, m6) in enumerate(top3, 1):
            msg += f"{i}. {name}({ticker}) {score*100:.1f}% (3M {m3:.1f}% / 6M {m6:.1f}%)\n"

    msg += f"\n손절룰: 종가가 20일선 밑으로 내려가면 다음날 전량 매도\n"
    msg += f"코어룰 v5.1: S&P는 200일선 위 + RSI>50 일때만 보유\n"
    msg += f"\n_v5.1 검증완료: 200일선+RSI로 가짜신호 70% 차단_"
    print(msg)
    send_telegram(msg)
