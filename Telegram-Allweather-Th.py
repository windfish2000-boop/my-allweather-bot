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
        if price > ma200: return "매수/보유", f"채권 상승 → 금리하락", price, ma200, r, True, False
        else: return "인버스 전환", f"채권 하락 → 금리상승 베팅", price, ma200, r, False, True

CORE_EACH = 800000 // 3

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    assets = {"SP500": ("360750","SPY","114800"), "GOLD": ("411060","GLD",None), "BOND": ("305080","TLT","176950")}
    names = {"SP500":"360750 TIGER S&P500","GOLD":"411060 TIGER 골드","BOND":"305080 TIGER 미국채10년"}
    inv_names = {"SP500":"114800 KODEX 인버스", "BOND":"176950 KODEX 국채선물10년인버스"}

    msg = f"📈 {today_str} 올웨더 100만원 v7.0 쌍방향 청산\n"
    msg += f"🇹🇭08:50 🇰🇷10:50 | 인버스 매도 로직 추가\n"
    msg += f"\n[코어 80만원]\n"
    
    cash_core = 0
    for asset in ["SP500","GOLD","BOND"]:
        kr, proxy, inv = assets[asset]
        close, _ = get_close(kr, proxy)
        if close is None: continue
        sig, reason, price, ma200, rsi, is_buy, is_inv = core_signal(close, asset)
        inv_name = inv_names.get(asset, "")
        
        if is_buy:
            # 추세가 바뀌면 인버스 매도 문구 표시!
            cur_price = get_price_pykrx(kr) or price
            shares = CORE_EACH / cur_price
            msg += f"🟢 {names[asset]}: {sig} (인버스 → 원본 복귀)\n"
            if inv:
                msg += f" └ 🔴 보유중이면 {inv_name} {inv} 전량 매도! (인버스 청산)\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 원본 신규 매수\n"
            msg += f" └ {reason}\n"
        elif is_inv:
            cur_price = get_price_pykrx(inv) or 50000
            shares = CORE_EACH / cur_price
            msg += f"🔵 {names[asset]} → {inv_name}: {sig}\n"
            msg += f" └ 🔴 보유중이면 {names[asset]} 전량 매도! (원본 청산)\n"
            msg += f" └ 👉 {CORE_EACH//10000}만원 → {cur_price:.0f}원 x {shares:.3f}주 인버스 신규 매수\n"
            msg += f" └ {reason}\n"
        else:
            msg += f"🟡 {names[asset]}: {sig}\n"
            msg += f" └ 🔴 보유중이면 {names[asset]} + {inv_name} 모두 전량 매도!\n"
            msg += f" └ ⛔ 현금 {CORE_EACH//10000}만원 대기\n"
            msg += f" └ {reason}\n"
            cash_core += CORE_EACH

    msg += f"\n💰 코어 현금대기: {cash_core//10000}만원\n"
    msg += f"\n룰: 추세반전시 원본↔인버스 자동 교체, 휩소시 모두 매도 후 현금\n"
    print(msg)
    send_telegram(msg)
