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
        end = dt.datetime.now().strftime("%Y%m%d")
        start = (dt.datetime.now() - dt.timedelta(days=10)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, end, kr_code)
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

CORE_EACH = 800000 // 3
SAT_TOTAL = 200000

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    # 고거래량 버전: KODEX/TIGER 위주로 재구성
    # 114800 KODEX 인버스 - 일 2억주 거래, TIGER 인버스 123310 - 일 3000만주
    # 채권은 미국채 인버스 대신 거래량 많은 KODEX 국고채10년선물인버스 157450 사용 (또는 현금대기)
    assets = {"SP500": ("360750","SPY","114800"), "GOLD": ("411060","GLD",None), "BOND": ("305080","TLT","157450")}
    names = {"SP500":"360750 TIGER S&P500","GOLD":"411060 TIGER 골드","BOND":"305080 TIGER 미국채10년"}
    inv_names = {
        "SP500":"114800 KODEX 인버스 [거래량 2억주]",
        "BOND":"157450 KODEX 국고채10년선물인버스 [거래량 50만주] - 미국채 하락시 국고채도 하락동조"
    }

    msg = f"📈 {today_str} 올웨더 100만원 v6.8 고거래량 최종\n"
    msg += f"🇹🇭08:50 🇰🇷10:50 | KODEX/TIGER 고유동성\n"
    msg += f"\n[코어 80만원 - 26.6만원씩]\n"
    
    cash_core = 0
    for asset in ["SP500","GOLD","BOND"]:
        kr, proxy, inv = assets[asset]
        close, _ = get_close(kr, proxy)
        if close is None: continue
        sig, reason, price, ma200, rsi, is_buy, is_inv = core_signal(close, asset)
        if is_buy:
            cur_price = get_price_pykrx(kr) or price
            shares = CORE_EACH / cur_price
            msg += f"🟢 {names[asset]}: {sig}\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 매수\n"
            msg += f" └ {reason}\n"
        elif is_inv:
            inv_name = inv_names[asset]
            cur_price = get_price_pykrx(inv) or 4000
            shares = CORE_EACH / cur_price
            msg += f"🔵 {names[asset]} → {inv_name}: {sig}\n"
            msg += f" └ 🔴 보유중이면 {names[asset]} 전량 매도!\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 인버스 매수\n"
            msg += f" └ {reason}\n"
        else:
            msg += f"🟡 {names[asset]}: {sig} → 보유중이면 전량 매도!\n"
            msg += f" └ ⛔ 진입금지 / 현금 {CORE_EACH//10000}만원 대기\n"
            msg += f" └ 🔴 매도 후 현금 보유!\n"
            msg += f" └ {reason}\n"
            cash_core += CORE_EACH

    msg += f"\n💰 코어 현금대기: {cash_core//10000}만원\n"
    msg += f"\n[위성 20만원 - Top3 고거래량 종목만]\n"
    tickers = {"SK하이닉스":("000660","000660.KS"),"삼성전자":("005930","005930.KS"),"KB금융":("105560","105560.KS"),"현대차":("005380","005380.KS"),"삼성SDI":("006400","006400.KS")}
    results=[]
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
        for i,(name,score,price_now) in enumerate(top3,1):
            shares = each / price_now
            msg += f"{i}. {name} Score{score*100:.1f}%\n"
            msg += f" └ 👉 {each//10000}만원 → {price_now:.0f}원 x {shares:.4f}주\n"
    else:
        msg += "Top3 없음 → ⛔ 위성 현금 대기\n"

    msg += f"\n룰: 🟢매수 🔴매도 🟡현금대기 | KODEX/TIGER 고거래량으로 체결 잘됨\n"
    print(msg)
    send_telegram(msg)
