import requests
import os
import datetime
import pandas as pd
import yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    print(r.text)
    return r.ok

def rsi_wilder(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 0.00001)
    return 100 - (100 / (1 + rs))

def get_yf_close(ticker, period="2y"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'].iloc[:,0] if 'Close' in df.columns.get_level_values(0) else df.iloc[:,0]
        else:
            close = df['Close'] if 'Close' in df.columns else df.iloc[:, -1]
        return close
    except: return None

def get_kr_close_fallback(kr_ticker, proxy_ticker):
    try:
        from pykrx import stock
        import datetime as dt
        end = dt.datetime.now().strftime("%Y%m%d")
        start = (dt.datetime.now() - dt.timedelta(days=800)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, end, kr_ticker)
        if not df.empty and len(df) > 210:
            return df['종가'], True
    except: pass
    close = get_yf_close(proxy_ticker, period="2y")
    return close, False

# --- B 옵션: 코어는 200일 + RSI만! 20일선 제거 ---
def get_core_signal(df_close, asset_type):
    df = pd.DataFrame({'close': df_close})
    df['ma200'] = df['close'].rolling(200).mean()
    df['rsi'] = rsi_wilder(df['close'], 14)
    price = float(df['close'].iloc[-1])
    ma200 = float(df['ma200'].iloc[-1])
    r = float(df['rsi'].iloc[-1])

    if asset_type == 'SP500':
        if price > ma200 and r > 50:
            return "매수/보유", f"200일선 위 {ma200:.0f} + RSI {r:.0f} → 상승 추세 유지", price, ma200, r, False
        elif price < ma200 and r < 45:
            return "인버스 전환", f"200일선 아래 {ma200:.0f} + RSI {r:.0f} → 진짜 하락 → 인버스", price, ma200, r, True
        else:
            return "관망(현금)", f"휩소 구간 - RSI {r:.0f}로 버팀 (20일선 무시)", price, ma200, r, False
    elif asset_type == 'GOLD':
        if price > ma200 and r > 55:
            return "매수/보유", f"골드 강세 RSI {r:.0f}", price, ma200, r, False
        elif price < ma200 and r < 45:
            return "현금 대기", f"골드 약세 RSI {r:.0f}", price, ma200, r, False
        else:
            return "관망", f"골드 관망 RSI {r:.0f}", price, ma200, r, False
    elif asset_type == 'BOND':
        if price > ma200:
            return "매수/보유", f"채권 상승", price, ma200, r, False
        else:
            return "인버스 전환(채권하락 베팅)", f"채권 하락 → 금리 상승 베팅", price, ma200, r, True

def get_allweather_core():
    assets = {"SP500": ("360750", "SPY"), "GOLD": ("411060", "GLD"), "BOND": ("305080", "TLT")}
    inverse_map = {"SP500": "114800 KODEX 인버스", "BOND": "225130 KODEX 미국채10년선물인버스"}
    signals = {}
    for asset, (kr, proxy) in assets.items():
        close, is_direct = get_kr_close_fallback(kr, proxy)
        if close is None or len(close) < 210: continue
        sig, reason, price, ma200, rsi, use_inv = get_core_signal(close, asset)
        signals[asset] = {"signal": sig, "reason": reason, "price": price, "ma200": ma200, "rsi": rsi, "use_inverse": use_inv, "is_direct": is_direct, "inv_name": inverse_map.get(asset)}
    return signals

# --- 위성은 20일선 필터 유지 ---
def get_satellite_top3():
    try:
        kospi = get_yf_close("^KS11", period="2y")
        is_bear = False
        if kospi is not None and len(kospi) > 200:
            is_bear = float(kospi.iloc[-1]) < float(kospi.rolling(200).mean().iloc[-1])
    except: is_bear = False
    if is_bear: return [], True

    universe = {
        "삼성SDI": "006400.KS", "하나금융지주": "086790.KS", "KB금융": "105560.KS",
        "현대차": "005380.KS", "SK하이닉스": "000660.KS", "POSCO홀딩스": "005490.KS",
        "삼성전자": "005930.KS", "LG에너지솔루션": "373220.KS"
    }
    results = []
    for name, ticker in universe.items():
        close = get_yf_close(ticker, period="1y")
        if close is None or len(close) < 130: continue
        # 공식 설명용 변수
        price_now = float(close.iloc[-1])
        price_63 = float(close.iloc[-63])
        price_126 = float(close.iloc[-126])
        mom3 = price_now / price_63 - 1
        mom6 = price_now / price_126 - 1
        score = (mom3 + mom6) / 2
        
        ma20 = float(close.rolling(20).mean().iloc[-1])
        # 위성은 20일선 필터 적용
        if price_now < ma20: continue
        
        results.append((name, ticker, score, mom3*100, mom6*100, price_now, ma20))
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:3], False

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    core = get_allweather_core()
    top3, bear = get_satellite_top3()

    msg = f"📈 {today_str} 올웨더 100만원 v6.2 (B옵션)\n"
    msg += f"{today_str} 한국 10:50 | "
    if core.get("SP500"):
        if "매수" in core["SP500"]["signal"]: msg += "✅ 코어 상승 유지 (20일선 무시)\n"
        elif "인버스" in core["SP500"]["signal"]: msg += "🔴 코어 인버스 전환\n"
        else: msg += f"🟡 {core['SP500']['reason']}\n"

    msg += f"\n[코어 80만원 - 공식: 200일선 + Wilder RSI만]\n"
    msg += f"└ 20일선 손절 제거 → 덜 흔들림\n"
    for asset in ["SP500", "GOLD", "BOND"]:
        if asset in core:
            d = core[asset]
            kr = {"SP500":"360750 S&P500","GOLD":"411060 골드","BOND":"305080 미국채10년"}[asset]
            mark = "(직접)" if d['is_direct'] else "(프록시)"
            if d['use_inverse']:
                msg += f"🔵 {kr} → {d['inv_name']} 매수\n"
                msg += f" └ {d['reason']} | {d['price']:.0f}/{d['ma200']:.0f}/RSI{d['rsi']:.0f}\n"
            else:
                emoji = "🟢" if "매수" in d['signal'] else "🟡"
                msg += f"{emoji} {kr}{mark}: {d['signal']}\n"
                msg += f" └ {d['reason']} | {d['price']:.0f}/{d['ma200']:.0f}/RSI{d['rsi']:.0f}\n"

    msg += f"\n[위성 20만원 - 공식: Score=(3M+6M)/2 + 20일선 필터]\n"
    msg += f"└ 3M=오늘/63일전-1, 6M=오늘/126일전-1, Score 평균\n"
    msg += f"└ 오늘종가 < 20일선이면 제외\n"
    if bear:
        msg += "🐻 KOSPI 200일선 아래 → 위성 현금/인버스 대기\n"
    elif top3:
        for i, (name, ticker, score, m3, m6, price, ma20) in enumerate(top3, 1):
            msg += f"{i}. {name} Score{score*100:.1f}% (3M{m3:.1f}%/6M{m6:.1f}%) 20일선 위\n"
    else:
        msg += "조건 충족 없음 → 20일선 밑이라 제외됨\n"

    print(msg)
    send_telegram(msg)
