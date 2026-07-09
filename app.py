def get_price_info(code):
    """J-Quants API (V2, APIキー認証) で株価を取得。取得できない場合はyfinanceにフォールバック"""
    price, change_pct, name = _get_price_info_jquants(code)
    if price is not None:
        return price, change_pct, name or code
    return _get_price_info_yfinance(code)


def _get_price_info_jquants(code):
    try:
        api_key = st.secrets["JQUANTS_API_KEY"]
        headers = {"x-api-key": api_key}
        to_date = datetime.now()
        from_date = to_date - timedelta(days=14)

        r = requests.get(
            "https://api.jquants.com/v2/equities/bars/daily",
            params={
                "code": code,
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
            },
            headers=headers,
            timeout=10,
        )
        if r.status_code != 200:
            return None, None, None

        quotes = [q for q in r.json().get("data", []) if q.get("C") is not None]
        if len(quotes) < 2:
            return None, None, None

        quotes.sort(key=lambda x: x["Date"])
        latest = quotes[-1]
        prev = quotes[-2]
        close = float(latest["C"])
        prev_close = float(prev["C"])
        change_pct = (close - prev_close) / prev_close * 100

        name = None
        try:
            r_name = requests.get(
                "https://api.jquants.com/v2/equities/master",
                params={"code": code},
                headers=headers,
                timeout=10,
            )
            master_data = r_name.json().get("data", [])
            if master_data:
                name = master_data[-1].get("CoName")
        except Exception:
            pass

        return close, change_pct, name
    except Exception:
        return None, None, None


def _get_price_info_yfinance(code):
    """J-Quantsで取得できない場合のフォールバック（無料プランのデータ遅延対策）"""
    try:
        data = yf.Ticker(f"{code}.T")
        hist = data.history(period="5d")
        if len(hist) < 2:
            return None, None, None
        latest = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]
        change_pct = (latest - prev) / prev * 100
        info = data.info
        name = (
            info.get("longNameJa")
            or info.get("shortNameJa")
            or info.get("shortName")
            or info.get("longName")
            or code
        )
        return latest, change_pct, name
    except Exception:
        return None, None, None
