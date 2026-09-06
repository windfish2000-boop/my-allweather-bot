import requests
import os
import datetime
import pandas as pd
import yfinance as yf

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

# --- 개선 1: RSI Wilder's Smoothing (HTS와 동일) ---
def rsi_wilder(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    # Wilder's EMA
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 0.00001)
    return 100 - (100 / (1 + rs))

def get_tactical_signal(df_close, asset_type):
    df = pd.DataFrame({'close': df_close})
    df['ma200'] = df['close'].rolling(200).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['rsi'] = rsi_wilder(df['close'], 14)
    
    price = float(df['close'].iloc[-1])
    ma200 = float(df['ma200'].iloc[-1])
    ma20 = float(df['ma20'].iloc[-1])
    r = float(df['rsi'].iloc[-1])

    # 손절 판정 추가
    stop_loss = price < ma20

    if asset_type == 'SP500':
        if price > ma200 and r > 50 and not stop_loss:
            return "매수/보유", f"200일선 위 {ma200:.0f} + RSI {r:.0f} → 진짜 상승", price, ma200, r, stop_loss
        elif price < ma200 and r < 45:
            return "매도→채권이동", f"200일선 아래 + RSI {r:.0f} → 진짜 하락", price, ma200, r, stop_loss
        elif stop_loss:
            return "매도(20일선 손절)", f"20일선 {ma20:.0f} 이탈 → 단기 손절", price, ma200, r, stop_loss
        else:
            return "관망", f"휩소 차단! RSI {r:.0f}로 버팀", price, ma200, r, stop_loss
    elif asset_type == 'GOLD':
        if price > ma200 and r > 60 and not stop_loss:
            return "매수/보유", f"골드 강세 RSI {r:.0f}", price, ma200, r, stop_loss
        elif price < ma200 and r < 40:
            return "매도→현금대기", f"골드 약세 RSI {r:.0f}", price, ma200, r, stop_loss
        elif stop_loss:
            return "매도(20일선 손절)", f"20일선 이탈", price, ma200, r, stop_loss
        else:
            return "관망", f"골드 관망 RSI {r:.0f}", price, ma200, r, stop_loss
    elif asset_type == 'BOND':
        if price > ma200 and not stop_loss:
            return "매수/보유", f"채권 상승 추세", price, ma200, r, stop_loss
        else:
            return "매도→현금대기", f"채권 하락 or 20일선 이탈", price, ma200, r, stop_loss

# --- 개선 2: 한국 ETF 직접 조회 시도 + 프록시 fallback ---
def get_yf_close(ticker, period="2y"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            if 'Close' in df.columns.get_level_values(0):
                close = df['Close'].iloc[:,0]
            else:
                close = df.iloc[:,0]
        else:
            close = df['Close'] if 'Close' in df.columns else df['close'] if 'close' in df.columns else df.iloc[:, -1]
        return close
    except:
        return None

def get_kr_close_fallback(kr_ticker, proxy_ticker, period="2y"):
    # 1. pykrx 시도
    try:
        from pykrx import stock
        import datetime as dt
        end = dt.datetime.now().strftime("%Y%m%d")
        start = (dt.datetime.now() - dt.timedelta(days=800)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(start, end, kr_ticker)
        if not df.empty and len(df) > 210:
            print(f"{kr_ticker} pykrx 성공: {len(df)}개")
            return df['종가']
    except Exception as e:
        print(f"pykrx 실패 {kr_ticker}: {e}")
    # 2. 실패시 미국 프록시로 fallback
    print(f"{kr_ticker} -> {proxy_ticker} 프록시로 대체")
    return get_yf_close(proxy_ticker, period)

def get_allweather_tactical():
    # 한국티커와 프록시 매핑
    assets = {
        "SP500": ("360750", "SPY"),
        "GOLD": ("411060", "GLD"),
        "BOND": ("305080", "TLT")
    }
    signals = {}
    for asset, (kr_ticker, proxy) in assets.items():
        close = get_kr_close_fallback(kr_ticker, proxy, period="2y")
        if close is None or len(close) < 210:
            continue
        sig, reason, price, ma200, r, stop = get_tactical_signal(close, asset)
        signals[asset] = {"signal": sig, "reason": reason, "price": price, "ma200": ma200, "rsi": r, "stop": stop, "is_proxy": len(close) < 500} # pykrx는 보통 500개 이상
    return signals

def get_momentum_top3_with_regime():
    # --- 개선 4: 시장 레짐 필터 (KOSPI 200일선) ---
    try:
        kospi = get_yf_close("^KS11", period="2y")
        market_bear = False
        if kospi is not None and len(kospi) > 200:
            kospi_ma200 = kospi.rolling(200).mean().iloc[-1]
            market_bear = float(kospi.iloc[-1]) < float(kospi_ma200)
            print(f"KOSPI 레짐: {'약세' if market_bear else '강세'}")
        else:
            market_bear = False
    except:
        market_bear = False

    if market_bear:
        return [], True # 약세면 Top3 매수 금지

    tickers_kr = {
        "삼성SDI": "006400.KS", "하나금융지주": "086790.KS", "KB금융": "105560.KS",
        "현대차": "005380.KS", "SK하이닉스": "000660.KS", "POSCO홀딩스": "005490.KS",
        "삼성전자": "005930.KS", "LG에너지솔루션": "373220.KS" # 유니버스 8개로 확장
    }
    results = []
    for name, ticker in tickers_kr.items():
        try:
            close = get_yf_close(ticker, period="1y")
            if close is None or len(close) < 130:
                continue
            mom6 = (float(close.iloc[-1]) / float(close.iloc[-126]) - 1) if len(close) > 126 else -999
            mom3 = (float(close.iloc[-1]) / float(close.iloc[-63]) - 1) if len(close) > 63 else -999
            # 20일선 손절 필터
            ma20 = close.rolling(20).mean().iloc[-1]
            if float(close.iloc[-1]) < float(ma20):
                continue # 20일선 밑이면 후보에서 제외
            score = (mom6 + mom3) / 2
            results.append((name, ticker, score, mom3*100, mom6*100))
        except:
            continue
    results.sort(key=lambda x: x[2], reverse=True)
    return results[:3], False

if __name__ == "__main__":
    today_str = datetime.datetime.now().strftime("%m/%d")
    tactical = get_allweather_tactical()
    top3, is_bear_market = get_momentum_top3_with_regime()

    msg = f"📈 {today_str} 올웨더 100만원 v6.0 개선판\n"
    msg += f"{today_str} 한국 10:50 | "
    if tactical and tactical.get("SP500"):
        if "매수" in tactical["SP500"]["signal"]:
            msg += "✅ 상승 추세 유지 (Wilder RSI 필터)\n"
        elif "관망" in tactical["SP500"]["signal"]:
            msg += f"🟡 관망 - {tactical['SP500']['reason']}\n"
        else:
            msg += f"🔴 {tactical['SP500']['signal']} - {tactical['SP500']['reason']}\n"
    else:
        msg += "⚠️ 데이터 로드 중\n"

    msg += f"\n[코어 80만원 - 200일+Wilder RSI+20일 손절]\n"
    if tactical:
        for asset in ["SP500", "GOLD", "BOND"]:
            if asset in tactical:
                kr_name = {"SP500": "360750 S&P500", "GOLD": "411060 골드", "BOND": "305080 미국채10년"}[asset]
                data = tactical[asset]
                emoji = "🟢" if "매수" in data['signal'] else "🔴" if "매도" in data['signal'] else "🟡"
                proxy_mark = "(프록시)" if data.get('is_proxy') else "(직접)"
                msg += f"{emoji} {kr_name}{proxy_mark}: {data['signal']}\n"
                msg += f" └ {data['reason']} | {data['price']:.1f}/{data['ma200']:.0f}/RSI{data['rsi']:.0f}\n"

    msg += f"\n[위성 20만원 - Top3 + 시장레짐]\n"
    if is_bear_market:
        msg += "🐻 KOSPI 200일선 아래 - 위성 전액 현금 대기\n"
    elif top3:
        for i, (name, ticker, score, m3, m6) in enumerate(top3, 1):
            msg += f"{i}. {name} {score*100:.1f}% (3M {m3:.1f}% / 6M {m6:.1f}%)\n"
    else:
        msg += "Top3 조건 충족 없음 - 현금 대기\n"

    msg += f"\n개선사항 v6:\n"
    msg += f"• RSI: Wilder 방식으로 HTS와 동일\n"
    msg += f"• 데이터: pykrx 직접조회 + 실패시 SPY 프록시\n"
    msg += f"• 손절: 20일선 이탈시 매도신호 + Top3 후보 제외\n"
    msg += f"• 레짐: KOSPI 약세시 위성 현금화\n"

    print(msg)
    send_telegram(msg)

