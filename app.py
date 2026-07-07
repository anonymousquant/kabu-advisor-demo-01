import streamlit as st
from google import genai
from google.genai import types
import yfinance as yf
import plotly.graph_objects as go
import csv
import re
from datetime import datetime

api_key = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)


def log_usage(name, action):
    with open("usage_log.csv", "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), name, action])


def get_price_info(ticker):
    try:
        data = yf.Ticker(ticker)
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
            or ticker
        )
        return latest, change_pct, name
    except Exception:
        return None, None, None


def get_chart_data(ticker):
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="1mo")
        if hist.empty:
            return None
        return hist
    except Exception:
        return None


def draw_chart(hist, ticker_label):
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=hist.index,
                open=hist["Open"],
                high=hist["High"],
                low=hist["Low"],
                close=hist["Close"],
                increasing_line_color="red",
                decreasing_line_color="blue",
            )
        ]
    )
    fig.update_layout(
        title=f"{ticker_label} 過去1ヶ月",
        xaxis_title="日付",
        yaxis_title="株価（円）",
        xaxis_rangeslider_visible=False,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


st.title("株アドバイスツール")
name = st.text_input("お名前を入力してください")

if name:
    st.write(f"こんにちは、{name}さん！")

    if "logged_in" not in st.session_state:
        log_usage(name, "ログイン")
        st.session_state.logged_in = True

    if st.button("Xで話題の銘柄を見る"):
        prompt = """
        今日のX（旧Twitter）で話題になっている日本株を5銘柄挙げてください。
        特に本日急騰・急落・出来高急増している銘柄を優先してください。
        言及されているという客観的事実のみで紹介し、
        「おすすめ」「買い時」「上昇が期待できる」など
        投資判断を示す表現は使わないでください。
        出力形式（厳守）：
        銘柄名（証券コード4桁）｜話題になっている理由
        例：レーザーテック（6920）｜半導体関連として～
        銘柄名は必ず日本語で記載してください。
        区切り文字は必ず｜（全角パイプ）を使ってください。
        """
        try:
            with st.spinner("Xの話題銘柄を取得中..."):
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[
                            types.Tool(
                                google_search=types.GoogleSearchRetrieval()
                            )
                        ]
                    ),
                )
        except Exception as e:
            st.error(
                f"Geminiへの接続に失敗しました。しばらく待ってから再試行してください。\n\n({e})"
            )
            st.stop()

        log_usage(name, "銘柄照会")

        lines = [l.strip() for l in response.text.strip().split("\n") if "｜" in l]
        matches = []
        for line in lines:
            parts = line.split("｜", 1)
            if len(parts) == 2:
                header, description = parts
                m = re.search(r"(.+?)[（(](\d{4})[）)]", header)
                if m:
                    jp_name = m.group(1).strip()
                    code = m.group(2)
                    matches.append((jp_name, code, description.strip()))

        st.session_state.matches = matches

    if "matches" in st.session_state and st.session_state.matches:
        matches = st.session_state.matches

        for jp_name, code, description in matches:
            st.markdown(f"**{jp_name}（{code}）：** {description}")
            st.write("")

        st.subheader("現在の株価")
        thead = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='border-bottom:2px solid #ddd;'>"
            "<th style='text-align:left; padding:8px;'>銘柄名</th>"
            "<th style='text-align:left; padding:8px;'>コード</th>"
            "<th style='text-align:right; padding:8px;'>現在値（円）</th>"
            "<th style='text-align:right; padding:8px;'>前日比</th>"
            "</tr></thead><tbody>"
        )
        tbody = ""
        for jp_name, code, _ in matches:
            ticker = code + ".T"
            price, change_pct, _ = get_price_info(ticker)
            if price is not None:
                sign = "+" if change_pct >= 0 else ""
                tbody += (
                    "<tr style='border-bottom:1px solid #eee;'>"
                    f"<td style='padding:8px;'><b>{jp_name}</b></td>"
                    f"<td style='padding:8px;'><b>{code}</b></td>"
                    f"<td style='text-align:right; padding:8px;'>{price:,.0f}</td>"
                    f"<td style='text-align:right; padding:8px;'>{sign}{change_pct:.2f}%</td>"
                    "</tr>"
                )
            else:
                tbody += (
                    "<tr style='border-bottom:1px solid #eee;'>"
                    f"<td style='padding:8px;'><b>{jp_name}</b></td>"
                    f"<td style='padding:8px;'><b>{code}</b></td>"
                    "<td style='text-align:right; padding:8px;'>取得不可</td>"
                    "<td style='text-align:right; padding:8px;'>-</td>"
                    "</tr>"
                )
        html = thead + tbody + "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)

    st.divider()
    st.subheader("個別銘柄を調べる")
    ticker_input = st.text_input("銘柄コードを入力（例: 7203）")
    if ticker_input:
        if "." not in ticker_input:
            ticker_input = ticker_input + ".T"
        price, change_pct, stock_name = get_price_info(ticker_input)
        if price is not None:
            sign = "+" if change_pct >= 0 else ""
            st.write(
                f"**{stock_name}（{ticker_input}）**：{price:,.0f}円　（前日比 {sign}{change_pct:.2f}%）"
            )
            hist = get_chart_data(ticker_input)
            if hist is not None:
                draw_chart(hist, f"{stock_name}（{ticker_input}）")
            else:
                st.write("チャートデータを取得できませんでした")
        else:
            st.write("株価データを取得できませんでした（コードが正しいか確認してください）")
        log_usage(name, f"銘柄閲覧: {ticker_input}")
