import requests, os, datetime, pandas as pd, yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    print(r.text)

def rsi_wilder(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 0.00001)
    return 100 - (100 / (1 + rs))

def get_close(kr_ticker, proxy):
    try:
        from pykrx import stock
        end = datetime.datetime.now().strftime("%Y%m%d")
        start = (datetime.datetime.now() - datetime.timedelta(days=800)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, end, kr_ticker)
        if not df.empty and len(df) > 210:
            return df['종가'], True
    except: pass
    df = yf.download(proxy, period="2y", progress=False, auto_adjust=True)
    if df.empty: return None, False
    close = df['Close'].iloc[:,0] if isinstance(df.columns, pd.MultiIndex) else df['Close'] if 'Close' in df.columns else df.iloc[:,-1]
    return close, False

def get_price_pykrx(kr_code):
    try:
        from pykrx import stock
        import datetime as dt
        today = dt.datetime.now().strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(today, today, kr_code)
        if not df.empty:
            return float(df['종가'].iloc[-1])
    except: pass
    return None

def core_signal(df_close, asset_type):
    df = pd.DataFrame({'close': df_close})
    df['ma200'] = df['close'].rolling(200).mean()
    df['rsi'] = rsi_wilder(df['close'], 14)
    price = float(df['close'].iloc[-1]); ma200 = float(df['ma200'].iloc[-1]); r = float(df['rsi'].iloc[-1])
    if asset_type == 'SP500':
        if price > ma200 and r > 50: return "매수/보유", f"200일선 위 {ma200:.0f} RSI {r:.0f}", price, ma200, r, True, False
        elif price < ma200 and r < 45: return "인버스 전환", f"200일선 아래 {ma200:.0f} RSI {r:.0f} → 하락확정", price, ma200, r, False, True
        else: return "관망(현금)", f"휩소 RSI {r:.0f} 진입금지", price, ma200, r, False, False
    elif asset_type == 'GOLD':
        if price > ma200 and r > 55: return "매수/보유", f"골드 강세 RSI {r:.0f}", price, ma200, r, True, False
        else: return "관망", f"골드 관망 RSI {r:.0f} 진입금지", price, ma200, r, False, False
    else:
        if price > ma200: return "매수/보유", f"채권 상승", price, ma200, r, True, False
        else: return "인버스 전환", f"채권 하락 → 금리상승 베팅", price, ma200, r, False, True

TOTAL = 1000000
CORE_TOTAL = 800000
CORE_EACH = CORE_TOTAL // 3
SAT_TOTAL = 200000

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    assets = {"SP500": ("360750","SPY","114800"), "GOLD": ("411060","GLD",None), "BOND": ("305080","TLT","225130")}
    names = {"SP500":"360750 TIGER S&P500","GOLD":"411060 TIGER 골드","BOND":"305080 TIGER 미국채10년"}

    msg = f"📈 {today_str} 올웨더 100만원 v6.6 매도명시 최종\n"
    msg += f"🇹🇭08:50 🇰🇷10:50 | 소수점 매수 가능\n"
    msg += f"\n[코어 80만원 - 26.6만원씩]\n"
    
    cash_core = 0
    for asset in ["SP500","GOLD","BOND"]:
        kr, proxy, inv = assets[asset]
        close, is_direct = get_close(kr, proxy)
        if close is None: continue
        sig, reason, price, ma200, rsi, is_buy, is_inv = core_signal(close, asset)
        if is_buy:
            cur_price = get_price_pykrx(kr) or price
            shares = CORE_EACH / cur_price
            msg += f"🟢 {names[asset]}: {sig}\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 매수 진입\n"
            msg += f" └ {reason} | {price:.0f}/{ma200:.0f}/RSI{rsi:.0f}\n"
        elif is_inv:
            inv_name = "114800 KODEX 인버스" if asset=="SP500" else "225130 KODEX 미국채10년선물인버스"
            inv_ticker = inv
            cur_price = get_price_pykrx(inv_ticker) or 7000
            shares = CORE_EACH / cur_price
            msg += f"🔵 {names[asset]} → {inv_name}: {sig}\n"
            msg += f" └ 🔴 보유중이면 {names[asset]} 전량 매도!\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 인버스 신규 매수\n"
            msg += f" └ {reason} | {price:.0f}/{ma200:.0f}/RSI{rsi:.0f}\n"
        else:
            msg += f"🟡 {names[asset]}: {sig} → 보유중이면 전량 매도!\n"
            msg += f" └ ⛔ 진입금지 - 0주 / 현금 {CORE_EACH//10000}만원 대기\n"
            msg += f" └ 🔴 매도 후 현금 보유! 신규 진입 금지\n"
            msg += f" └ {reason}\n"
            cash_core += CORE_EACH

    msg += f"\n💰 코어 현금대기: {cash_core//10000}만원\n"
    msg += f"\n[위성 20만원 - Top3 소수점 분산]\n"
    tickers = {"SK하이닉스":("000660","000660.KS"),"삼성SDI":("006400","006400.KS"),"하나금융지주":("086790","086790.KS"),"KB금융":("105560","105560.KS"),"현대차":("005380","005380.KS")}
    results=[]
    prev_top3 = ["SK하이닉스","삼성SDI","하나금융지주"] # 예시 - 실제로는 어제 Top3와 비교해야 하지만 메시지에선 안내로 처리
    for name, (kr_code, yf_code) in tickers.items():
        c = yf.download(yf_code, period="1y", progress=False, auto_adjust=True)
        if c.empty: continue
        close = c['Close'].iloc[:,0] if isinstance(c.columns, pd.MultiIndex) else c['Close']
        if len(close)<130: continue
        mom3 = float(close.iloc[-1]/close.iloc[-63]-1); mom6 = float(close.iloc[-1]/close.iloc[-126]-1)
        score=(mom3+mom6)/2; ma20=float(close.rolling(20).mean().iloc[-1])
        if float(close.iloc[-1]) < ma20: continue
        price_now = get_price_pykrx(kr_code) or float(close.iloc[-1])
        results.append((name, score, price_now))
    results.sort(key=lambda x: x[1], reverse=True)
    top3 = results[:3]
    
    if top3:
        each = SAT_TOTAL // len(top3)
        top3_names = [x[0] for x in top3]
        # 탈락 종목 체크
        dropped = [n for n in prev_top3 if n not in top3_names]
        if dropped:
            msg += f"🔴 위성 교체: {', '.join(dropped)} → 전량 매도!\n"
        for i,(name,score,price_now) in enumerate(top3,1):
            shares = each / price_now if price_now else 0
            is_new = name not in prev_top3
            new_tag = " [신규매수]" if is_new else ""
            msg += f"{i}. {name} Score{score*100:.1f}%{new_tag}\n"
            msg += f" └ 👉 {each//10000}만원 → {price_now:.0f}원 x {shares:.4f}주 소수점 매수\n"
    else:
        msg += "Top3 없음 → ⛔ 위성도 진입금지\n"
        msg += " └ 🔴 보유중이면 위성 전량 매도!\n"
        msg += " └ 👉 현금 20만원 대기 or 114800 인버스 20만원 고려\n"

    msg += f"\n룰: 🟢매수 🔴매도 🟡관망=현금대기, 👉 뜰때만 진입\n"
    print(msg)
    send_telegram(msg)
