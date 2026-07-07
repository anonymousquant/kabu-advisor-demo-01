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
    fig = go.Figure(data=[go.Candlestick(
        x=hist.index,
        open=hist["Open"],
        high=hist["High"],
        low=hist["Low"],
        close=hist["Close"],
