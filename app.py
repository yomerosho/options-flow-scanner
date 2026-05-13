"""
Options Flow Dashboard — Unified 15-min Intraday Scanner
=========================================================
One unified scanner for indices + stocks on 15-min bars.
Watchlist editor in sidebar — add/remove tickers without touching code.
Auto-scan every 15 min + email alerts for 4★+ setups.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import numpy as np
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz

from scanner import IntradayScanner, HourlyScanner, DailyScanner, PremarketScanner, ScannerConfig, Indicators

# ── Load secrets from Streamlit Cloud if available ────────────────────────────
def get_secret(section, key, default=""):
    try:
        return st.secrets[section][key]
    except:
        return default

_alpaca_key_default    = get_secret("alpaca", "key",      "")
_alpaca_secret_default = get_secret("alpaca", "secret",   "")
_gmail_user_default    = get_secret("gmail",  "user",     "")
_gmail_pass_default    = get_secret("gmail",  "password", "")
_gmail_alert_default   = get_secret("gmail",  "alert_to", "")

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Options Flow — 15min Scanner",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=JetBrains+Mono:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family:'Syne',sans-serif; background:#2a2f3d; color:#f0f4fb; }
.stApp { background:#2a2f3d; }

section[data-testid="stSidebar"] { background:#22273a; border-right:1px solid #454b62; }
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#e0e8f0 !important; font-size:0.85rem; }

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color:#ffffff !important; }

section[data-testid="stSidebar"] .stTextInput input,
section[data-testid="stSidebar"] .stTextArea textarea,
section[data-testid="stSidebar"] .stNumberInput input {
  color:#f0f4fb !important;
  background:#2f3548 !important;
  border:1px solid #525a72 !important;
}

section[data-testid="stSidebar"] .stTextInput input::placeholder,
section[data-testid="stSidebar"] .stTextArea textarea::placeholder {
  color:#8a92a8 !important;
}

/* Selectbox / Multiselect dropdown — dark bg, light text */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background-color:#2f3548 !important;
  border:1px solid #525a72 !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] * { color:#f0f4fb !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"] {
  background-color:#6a5a90 !important;
  color:#f0f4fb !important;
}

section[data-testid="stSidebar"] .stExpander summary p,
section[data-testid="stSidebar"] .stExpander p { color:#f0f4fb !important; }

section[data-testid="stSidebar"] .stCheckbox label p { color:#f0f4fb !important; }

section[data-testid="stSidebar"] [data-testid="stSliderLabel"],
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] { color:#f0f4fb !important; }

/* Tab styling — matching GexMetrics */
.stTabs [data-baseweb="tab-list"] { background: #22273a; border-bottom: 1px solid #525a72; }
.stTabs [data-baseweb="tab"] { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; padding: 12px 24px; color: #a0a8c0; }
.stTabs [aria-selected="true"] { background: #363b4f !important; color: #bc8cff !important; border-bottom: 2px solid #bc8cff !important; }

[data-testid="metric-container"] { background:#363b4f; border:1px solid #525a72; border-radius:10px; padding:16px 20px; }
[data-testid="metric-container"] label { color:#a0a8c0 !important; font-size:0.7rem; letter-spacing:.1em; text-transform:uppercase; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family:'JetBrains Mono',monospace; font-size:1.8rem; font-weight:600; color:#bc8cff; }

.stButton > button { font-family:'JetBrains Mono',monospace; font-size:0.82rem; border-radius:6px; padding:10px 0; width:100%; border:none; background:linear-gradient(135deg,#4a2a80,#2a1560); color:#d4b8ff; transition:all .2s; }
.stButton > button:hover { background:linear-gradient(135deg,#5a3a98,#3a2070); }

.signal-call { border-left:3px solid #4af0c4; background:#1a3d2a; padding:14px 18px; border-radius:0 8px 8px 0; margin:6px 0; }
.signal-put  { border-left:3px solid #f04a6a; background:#3d1a25; padding:14px 18px; border-radius:0 8px 8px 0; margin:6px 0; }
.badge-call  { display:inline-block; background:#2a5a48; color:#4af0c4; font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:20px; }
.badge-put   { display:inline-block; background:#4a1f2a; color:#f04a6a; font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:20px; }
.badge-index { display:inline-block; background:#3a4870; color:#6ab0f0; font-family:'JetBrains Mono',monospace; font-size:0.65rem; padding:1px 8px; border-radius:10px; }
.badge-stock { display:inline-block; background:#4a3a70; color:#bc8cff; font-family:'JetBrains Mono',monospace; font-size:0.65rem; padding:1px 8px; border-radius:10px; }

.status-bar { background:#363b4f; border:1px solid #525a72; border-radius:8px; padding:10px 18px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; margin-bottom:12px; }
.countdown  { background:#363b4f; border:1px solid #525a72; border-radius:8px; padding:8px 16px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#4af0c4; text-align:center; margin-bottom:12px; }
.wl-section { background:#363b4f; border:1px solid #525a72; border-radius:8px; padding:12px 14px; margin:8px 0; font-family:'JetBrains Mono',monospace; font-size:0.72rem; }
.wl-ticker  { display:inline-block; background:#454b62; color:#d4dce8; border:1px solid #7a6a98; border-radius:4px; padding:2px 8px; margin:2px; font-size:0.72rem; }

/* Confluence card */
.signal-confluence-call {
  border-left: 4px solid #4af0c4;
  background: linear-gradient(135deg, #1f4a3a 0%, #3a2f55 100%);
  padding: 16px 18px;
  border-radius: 0 8px 8px 0;
  margin: 8px 0;
  box-shadow: 0 0 20px rgba(74,240,196,0.15);
}
.signal-confluence-put {
  border-left: 4px solid #f04a6a;
  background: linear-gradient(135deg, #4a1f25 0%, #1f0d20 100%);
  padding: 16px 18px;
  border-radius: 0 8px 8px 0;
  margin: 8px 0;
  box-shadow: 0 0 20px rgba(240,74,106,0.15);
}
.confluence-badge {
  display:inline-block;
  background: linear-gradient(90deg,#2a5a48,#1a3a50);
  color:#4af0c4;
  font-family:'JetBrains Mono',monospace;
  font-size:0.72rem;
  font-weight:700;
  padding:2px 12px;
  border-radius:20px;
  letter-spacing:.06em;
  border:1px solid #4af0c430;
}
.stacked-pill {
  display:inline-block;
  background:#454b62;
  color:#b8c2d2;
  font-family:'JetBrains Mono',monospace;
  font-size:0.65rem;
  padding:1px 8px;
  border-radius:10px;
  margin:2px;
  border:1px solid #525a72;
}
.body-confirm {
  display:inline-block;
  background:#1a4a38;
  color:#4af0c4;
  font-size:0.65rem;
  padding:1px 8px;
  border-radius:10px;
  font-family:'JetBrains Mono',monospace;
}
hr { border-color:#525a72; }
</style>
""", unsafe_allow_html=True)

# ── Timezone / market helpers ─────────────────────────────────────────────────

ET = pytz.timezone("America/New_York")

def market_status():
    now    = datetime.now(ET)
    wd     = now.weekday()
    open_  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_ = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    if wd >= 5:   return False, "weekend",   None, None
    if now < open_:
        return False, "pre-market", int((open_-now).total_seconds()/60), None
    if now > close_: return False, "closed", None, None
    return True, "open", None, int((close_-now).total_seconds()/60)

def next_pm_scan_secs(session):
    """Seconds until next pre-market/AH scan."""
    last = st.session_state.get("last_pm_scan")
    if last is None:
        return 0
    interval = 5 if session == "PRE-MARKET" else 10  # 5-min PM, 10-min AH
    return max(0, int(interval * 60 - (datetime.now() - last).total_seconds()))

def next_scan_secs(interval_min=30):
    last = st.session_state.get("last_scan_time")
    if last is None: return 0
    return max(0, int(interval_min*60 - (datetime.now()-last).total_seconds()))

# ── Email alert ───────────────────────────────────────────────────────────────

def send_alert(df, gmail_user, gmail_pass, to_email):
    if df.empty: return False
    strong = df[df["Confidence"].str.len() >= 4]
    if strong.empty: return False
    try:
        rows = ""
        for _, r in strong.iterrows():
            col = "#4af0c4" if r["Direction"]=="CALL" else "#f04a6a"
            rows += f"<tr><td style='padding:8px;font-weight:bold;color:{col}'>{r['Ticker']}</td><td style='padding:8px;color:{col}'>{r['Direction']}</td><td style='padding:8px'>${r['Price']}</td><td style='padding:8px'>${r['Strike']}</td><td style='padding:8px'>{r['Signal']}</td><td style='padding:8px'>{r['Confidence']}</td><td style='padding:8px'>{r['Notes']}</td></tr>"
        html = f"""<html><body style='background:#2a2f3d;color:#d4dce8;font-family:monospace;'>
        <div style='max-width:720px;margin:0 auto;padding:24px;'>
        <h2 style='color:#bc8cff;border-bottom:1px solid #525a72;padding-bottom:12px;'>🎯 Options Flow Alert — 15-min Scan</h2>
        <p style='color:#b8c2d2;font-size:0.85rem;'>{len(strong)} high-confidence setup(s) — {datetime.now(ET).strftime('%H:%M ET')}</p>
        <table style='width:100%;border-collapse:collapse;background:#363b4f;border:1px solid #525a72;'>
        <tr style='background:#454b62;color:#a8b3c8;font-size:0.75rem;'>
        <th style='padding:10px;text-align:left'>TICKER</th><th style='padding:10px;text-align:left'>DIR</th>
        <th style='padding:10px;text-align:left'>PRICE</th><th style='padding:10px;text-align:left'>STRIKE</th>
        <th style='padding:10px;text-align:left'>SIGNAL</th><th style='padding:10px;text-align:left'>CONF</th>
        <th style='padding:10px;text-align:left'>NOTES</th></tr>{rows}</table>
        <p style='color:#7a6a98;font-size:0.7rem;margin-top:16px;'>15-min delayed · Not financial advice</p>
        </div></body></html>"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎯 Options Alert: {len(strong)} setup(s) — {datetime.now(ET).strftime('%H:%M ET')}"
        msg["From"] = gmail_user
        msg["To"]   = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(gmail_user, gmail_pass)
            s.sendmail(gmail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        st.session_state["email_error"] = str(e)
        return False

# ── Export functions ──────────────────────────────────────────────────────────

def build_export_html(df_calls, df_puts, scan_type, scan_time):
    def card_rows(df, direction):
        if df.empty:
            return f'<p style="color:#a8b3c8;font-family:monospace;padding:12px;">No {direction} setups found.</p>'
        rows = ""
        for _, r in df.iterrows():
            col     = "#4af0c4" if direction=="CALL" else "#f04a6a"
            bg      = "#1a3d2a" if direction=="CALL" else "#3d1a25"
            border  = col
            icon    = "▲" if direction=="CALL" else "▼"
            dir_bg  = "#2a5a48" if direction=="CALL" else "#4a1f2a"
            is_conf = bool(r.get("Confluence", False))
            conf_tag= '<span style="background:#2a5a48;color:#4af0c4;font-size:0.7rem;padding:2px 8px;border-radius:10px;font-weight:700;margin-left:4px;">⚡ CONFLUENCE</span>' if is_conf else ""
            signals = str(r.get("Signals","") or r.get("Notes",""))
            expiry  = str(r.get("Expiry",""))
            iv      = str(r.get("IV Note",""))
            iv_col  = "#f04a6a" if "High" in iv else ("#4af0c4" if "Low" in iv else "#f5c842")
            sma     = str(r.get("SMA Level","—"))
            vwap    = str(r.get("VWAP","—"))
            pills   = ""
            if signals and is_conf:
                for s in signals.split(" · "):
                    if s.strip():
                        pills += f'<span style="background:#454b62;color:#b8c2d2;font-size:0.65rem;padding:1px 7px;border-radius:8px;margin:2px;border:1px solid #525a72;display:inline-block;">{s.strip()}</span>'
            rows += f"""
            <div style="border-left:4px solid {border};background:{bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:8px 0;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
                <span style="font-family:monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{r["Ticker"]}</span>
                <span style="background:#4a3a70;color:#bc8cff;font-size:0.65rem;padding:1px 8px;border-radius:8px;">{r.get("Type","")}</span>
                <span style="background:{dir_bg};color:{col};font-size:0.72rem;font-weight:700;padding:2px 10px;border-radius:20px;">{icon} {direction}</span>
                {conf_tag}
                <span style="color:#b8c2d2;font-size:0.82rem;margin-left:4px;">${r["Price"]}</span>
                <span style="margin-left:auto;">{r["Confidence"]}</span>
              </div>
              <div style="font-size:0.9rem;color:#e8edf5;font-weight:600;margin-bottom:4px;">
                {r["Signal"]} → <span style="color:{col};">Strike ${r["Strike"]}</span>
                {"&nbsp;<span style='color:#b8c2d2;font-size:0.78rem;'>(" + expiry + ")</span>" if expiry else ""}
              </div>
              {"<div style='margin:5px 0;'>" + pills + "</div>" if pills else ""}
              <div style="font-size:0.75rem;color:#a8b3c8;margin-top:4px;">
                {"VWAP $" + vwap + " &nbsp;|&nbsp; " if vwap not in ["—","nan",""] else ""}RSI {r["RSI"]} &nbsp;|&nbsp; Vol {r["Vol Ratio"]}x{"&nbsp;|&nbsp; SMA: " + sma if sma != "—" else ""}
              </div>
              <div style="font-size:0.74rem;margin-top:4px;color:{iv_col};">{iv}</div>
            </div>"""
        return rows

    total     = len(df_calls) + len(df_puts)
    call_rows = card_rows(df_calls, "CALL")
    put_rows  = card_rows(df_puts,  "PUT")

    return f"""<!DOCTYPE html><html>
    <body style="background:#2a2f3d;color:#d4dce8;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0;">
    <div style="max-width:900px;margin:0 auto;padding:24px;">
      <div style="border-bottom:1px solid #525a72;padding-bottom:16px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:1.5rem;font-weight:800;color:#bc8cff;">🎯 Options Flow — {scan_type}</h1>
        <p style="color:#a8b3c8;font-family:monospace;font-size:0.8rem;margin:6px 0 0 0;">
          Scanned: {scan_time} &nbsp;·&nbsp; {total} setup(s) &nbsp;·&nbsp; 3★+ only
        </p>
      </div>
      <table width="100%" cellspacing="0" cellpadding="0"><tr valign="top">
        <td width="50%" style="padding-right:10px;">
          <div style="font-size:1rem;font-weight:700;color:#4af0c4;margin-bottom:10px;">🟢 CALL Setups</div>
          {call_rows}
        </td>
        <td width="50%" style="padding-left:10px;">
          <div style="font-size:1rem;font-weight:700;color:#f04a6a;margin-bottom:10px;">🔴 PUT Setups</div>
          {put_rows}
        </td>
      </tr></table>
      <div style="border-top:1px solid #525a72;margin-top:24px;padding-top:12px;font-size:0.68rem;color:#7a6a98;text-align:center;">
        Options Flow Dashboard · yfinance · Not financial advice · Educational use only
      </div>
    </div></body></html>"""


def send_export_email(html, subject, gmail_user, gmail_pass, to_email):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = gmail_user
        msg["To"]      = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(gmail_user, gmail_pass)
            s.sendmail(gmail_user, to_email, msg.as_string())
        return True
    except Exception as e:
        st.session_state["email_error"] = str(e)
        return False


def build_csv(df):
    cols        = ["Ticker","Type","Direction","Price","Signal","Confidence",
                   "Strike","Expiry","RSI","Vol Ratio","IV Note","Notes","Date"]
    export_cols = [c for c in cols if c in df.columns]
    return df[export_cols].to_csv(index=False)


# ── Chart builder ─────────────────────────────────────────────────────────────

ind = Indicators()

def build_chart(ticker):
    try:
        t  = yf.Ticker(ticker)
        df = t.history(period="5d", interval="15m", auto_adjust=True)
        if df.empty: return None
        today = df.index.tz_convert("America/New_York").date[-1]
        df    = df[df.index.tz_convert("America/New_York").date == today]
        if len(df) < 5: return None

        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
        df["vwap"]  = ind.vwap(h, l, c, v)
        df["ema9"]  = ind.ema(c, 9)
        df["ema20"] = ind.ema(c, 20)
        df["sma50"] = ind.sma(c, 50)

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=h, low=l, close=c, name=ticker,
            increasing_line_color="#4af0c4", decreasing_line_color="#f04a6a",
            increasing_fillcolor="#4af0c4", decreasing_fillcolor="#f04a6a",
        ))
        colors = ["rgba(74,240,196,0.25)" if c_>=o else "rgba(240,74,106,0.25)"
                  for c_,o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=v, marker_color=colors, name="Vol", yaxis="y2"))
        for col_name, color, dash, label in [
            ("vwap","#f5c842","solid","VWAP"),
            ("ema9","#4af0c4","dot","EMA9"),
            ("ema20","#c87af5","dot","EMA20"),
            ("sma50","#f04a6a","dash","SMA50"),
        ]:
            fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=label,
                line=dict(color=color, width=1.4, dash=dash), hoverinfo="skip"))

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#363b4f", plot_bgcolor="#363b4f",
            xaxis=dict(showgrid=False, rangeslider_visible=False),
            yaxis=dict(showgrid=True, gridcolor="#525a72", domain=[0.25,1.0]),
            yaxis2=dict(showgrid=False, overlaying="y", side="right", domain=[0,0.2]),
            legend=dict(bgcolor="rgba(0,0,0,0)", font_color="#5a6a80", font_size=10),
            margin=dict(l=8,r=8,t=24,b=8), height=440,
            font=dict(family="JetBrains Mono", color="#5a6a80"),
        )
        return fig
    except:
        return None

# ── Daily chart builder ───────────────────────────────────────────────────────

def build_daily_chart(ticker):
    """1-hour chart for after-hours tab."""
    try:
        t  = yf.Ticker(ticker)
        df = t.history(period="5d", interval="1h", auto_adjust=True)
        if df.empty: return None
        c  = df["Close"]
        df["ema9"]   = c.ewm(span=9,  adjust=False).mean()
        df["ema20"]  = c.ewm(span=20, adjust=False).mean()
        df["sma_50"] = c.rolling(50).mean()
        df["sma_100"]= c.rolling(100).mean()
        df["sma_200"]= c.rolling(200).mean()
        # VWAP per day
        df["date"] = df.index.tz_convert("America/New_York").date
        df["vwap"] = np.nan
        for date, grp in df.groupby("date"):
            tp = (grp["High"] + grp["Low"] + grp["Close"]) / 3
            vwap = (tp * grp["Volume"]).cumsum() / grp["Volume"].cumsum()
            df.loc[grp.index, "vwap"] = vwap

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name=ticker,
            increasing_line_color="#4af0c4", decreasing_line_color="#f04a6a",
            increasing_fillcolor="#4af0c4", decreasing_fillcolor="#f04a6a",
        ))
        colors = ["rgba(74,240,196,0.25)" if c_>=o else "rgba(240,74,106,0.25)"
                  for c_,o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"],
                             marker_color=colors, name="Vol", yaxis="y2"))
        for col_name, color, dash, label in [
            ("vwap",    "#f5c842","solid", "VWAP"),
            ("ema9",    "#4af0c4","dot",   "EMA9"),
            ("ema20",   "#c87af5","dot",   "EMA20"),
            ("sma_50",  "#f08040","dash",  "SMA50"),
            ("sma_100", "#4af0c4","solid", "SMA100"),
            ("sma_200", "#f04a6a","solid", "SMA200"),
        ]:
            if col_name in df:
                fig.add_trace(go.Scatter(x=df.index, y=df[col_name], name=label,
                    line=dict(color=color, width=1.3, dash=dash), hoverinfo="skip"))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#363b4f", plot_bgcolor="#363b4f",
            xaxis=dict(showgrid=False, rangeslider_visible=False),
            yaxis=dict(showgrid=True, gridcolor="#525a72", domain=[0.25,1.0]),
            yaxis2=dict(showgrid=False, overlaying="y", side="right", domain=[0,0.2]),
            legend=dict(bgcolor="rgba(0,0,0,0)", font_color="#5a6a80", font_size=10),
            margin=dict(l=8,r=8,t=24,b=8), height=440,
            font=dict(family="JetBrains Mono", color="#5a6a80"),
        )
        return fig
    except:
        return None

# ── Signal card ───────────────────────────────────────────────────────────────

def signal_card(row):
    d        = str(row.get("Direction",""))
    t        = str(row.get("Type",""))
    ticker   = str(row.get("Ticker",""))
    price    = str(row.get("Price",""))
    signal   = str(row.get("Signal",""))
    strike   = str(row.get("Strike",""))
    conf     = str(row.get("Confidence",""))
    vwap     = str(row.get("VWAP",""))
    rsi      = str(row.get("RSI",""))
    vol      = str(row.get("Vol Ratio",""))
    notes    = str(row.get("Notes",""))
    plan     = str(row.get("Plan",""))
    is_conf  = bool(row.get("Confluence", False))
    body_ok  = str(row.get("Body✓EMA9","—")) == "✅"
    stacked  = str(row.get("Signals",""))

    icon     = "▲" if d=="CALL" else "▼"
    dir_col  = "#4af0c4" if d=="CALL" else "#f04a6a"
    dir_bg   = "#2a5a48" if d=="CALL" else "#4a1f2a"
    card_bg  = "#1a3d2a" if d=="CALL" else "#3d1a25"
    border   = "#4af0c4" if d=="CALL" else "#f04a6a"
    type_bg  = "#3a4870" if t=="INDEX" else "#4a3a70"
    type_col = "#6ab0f0" if t=="INDEX" else "#bc8cff"

    if is_conf:
        card_bg = "linear-gradient(135deg,#1f4a3a,#3a2f55)" if d=="CALL" else "linear-gradient(135deg,#4a1f25,#1f0d20)"

    conf_badge = '<span style="background:linear-gradient(90deg,#2a5a48,#1a3a50);color:#4af0c4;font-family:JetBrains Mono,monospace;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;border:1px solid #4af0c430;">⚡ CONFLUENCE</span>' if is_conf else ""
    body_html  = '<span style="background:#1a4a38;color:#4af0c4;font-size:0.65rem;padding:1px 8px;border-radius:10px;font-family:JetBrains Mono,monospace;">✅ Body Close</span>' if body_ok else ""

    pills = ""
    if stacked and is_conf:
        for s in stacked.split(" · "):
            if s.strip():
                pills += f'<span style="background:#454b62;color:#b8c2d2;font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;margin:2px;border:1px solid #525a72;">{s.strip()}</span>'

    return (
        f'<div style="border-left:4px solid {border};background:{card_bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:6px 0;">' +
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;flex-wrap:wrap;">' +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{ticker}</span>' +
        f'<span style="background:{type_bg};color:{type_col};font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;">{t}</span>' +
        f'<span style="background:{dir_bg};color:{dir_col};font-family:JetBrains Mono,monospace;font-size:0.72rem;font-weight:600;padding:2px 10px;border-radius:20px;">{icon} {d}</span>' +
        conf_badge + body_html +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.82rem;color:#b8c2d2;margin-left:4px;">${price}</span>' +
        f'<span style="margin-left:auto;font-size:0.82rem;">{conf}</span>' +
        f'</div>' +
        f'<div style="font-size:0.88rem;color:#e8edf5;margin-bottom:5px;font-weight:600;">{signal} → <span style="color:{dir_col};">Strike ${strike}</span></div>' +
        (f'<div style="margin:5px 0;">{pills}</div>' if pills else "") +
        f'<div style="font-size:0.75rem;color:#a8b3c8;margin-top:4px;">VWAP ${vwap} | RSI {rsi} | Vol {vol}x</div>' +
        (f'<div style="font-size:0.78rem;color:#f5c842;margin-top:5px;padding:4px 8px;background:#3a3a1a;border-radius:4px;">📋 {plan}</div>' if plan else "") +
        f'</div>'
    )

# ── Daily signal card ────────────────────────────────────────────────────────

def daily_signal_card(row):
    d        = str(row.get("Direction",""))
    t        = str(row.get("Type",""))
    ticker   = str(row.get("Ticker",""))
    price    = str(row.get("Price",""))
    signal   = str(row.get("Signal",""))
    strike   = str(row.get("Strike",""))
    expiry   = str(row.get("Expiry",""))
    conf     = str(row.get("Confidence",""))
    rsi      = str(row.get("RSI",""))
    vol      = str(row.get("Vol Ratio",""))
    atr      = str(row.get("ATR",""))
    sma_lv   = str(row.get("SMA Level","—"))
    iv_note  = str(row.get("IV Note",""))
    notes    = str(row.get("Notes",""))
    plan     = str(row.get("Plan",""))
    plan     = str(row.get("Plan",""))
    is_conf  = bool(row.get("Confluence", False))
    stacked  = str(row.get("Signals",""))

    icon     = "▲" if d=="CALL" else "▼"
    dir_col  = "#4af0c4" if d=="CALL" else "#f04a6a"
    dir_bg   = "#2a5a48" if d=="CALL" else "#4a1f2a"
    card_bg  = "#1a3d2a" if d=="CALL" else "#3d1a25"
    border   = "#4af0c4" if d=="CALL" else "#f04a6a"
    type_bg  = "#3a4870" if t=="INDEX" else "#4a3a70"
    type_col = "#6ab0f0" if t=="INDEX" else "#bc8cff"
    iv_color = "#f04a6a" if "High" in iv_note else ("#4af0c4" if "Low" in iv_note else "#f5c842")

    conf_badge = ""
    if is_conf:
        card_bg = "linear-gradient(135deg,#1f4a3a,#3a2f55)" if d=="CALL" else "linear-gradient(135deg,#4a1f25,#1f0d20)"
        conf_badge = '<span style="background:linear-gradient(90deg,#2a5a48,#1a3a50);color:#4af0c4;font-family:JetBrains Mono,monospace;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;border:1px solid #4af0c430;">⚡ CONFLUENCE</span>'

    pills = ""
    if stacked and is_conf:
        for s in stacked.split(" · "):
            if s.strip():
                pills += f'<span style="background:#454b62;color:#b8c2d2;font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;margin:2px;border:1px solid #525a72;">{s.strip()}</span>'

    return (
        f'<div style="border-left:4px solid {border};background:{card_bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:6px 0;">' +
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;flex-wrap:wrap;">' +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{ticker}</span>' +
        f'<span style="background:{type_bg};color:{type_col};font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;">{t}</span>' +
        f'<span style="background:{dir_bg};color:{dir_col};font-family:JetBrains Mono,monospace;font-size:0.72rem;font-weight:600;padding:2px 10px;border-radius:20px;">{icon} {d}</span>' +
        conf_badge +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.82rem;color:#b8c2d2;margin-left:4px;">${price}</span>' +
        f'<span style="margin-left:auto;font-size:0.82rem;">{conf}</span>' +
        f'</div>' +
        f'<div style="font-size:0.88rem;color:#e8edf5;margin-bottom:5px;font-weight:600;">{signal} → <span style="color:{dir_col};">Strike ${strike}</span> <span style="color:#b8c2d2;font-size:0.78rem;">({expiry})</span></div>' +
        (f'<div style="margin:5px 0;">{pills}</div>' if pills else "") +
        f'<div style="font-size:0.75rem;color:#a8b3c8;margin-top:4px;">SMA: {sma_lv} | RSI {rsi} | Vol {vol}x | ATR ${atr}</div>' +
        f'<div style="font-size:0.74rem;margin-top:4px;color:{iv_color};">{iv_note}</div>' +
        f'</div>'
    )

# ── Session state ─────────────────────────────────────────────────────────────

DEFAULTS = {
    "scan_results":    None,
    "last_scan_time":  None,
    "scan_timestamp":  None,
    "auto_enabled":    True,
    "user_name":       "",
    "user_email":      "",
    "user_tickers":    [],
    "user_setup_done": False,
    "last_alert":      "—",
    "email_error":     None,
    "daily_results":   None,
    "daily_timestamp": None,
    "pm_results":      None,
    "pm_timestamp":    None,
    "pm_session":      "—",
    "last_pm_scan":    None,
    "alpaca_key_val":    _alpaca_key_default,
    "alpaca_secret_val": _alpaca_secret_default,
    "use_alpaca_val":    True if _alpaca_key_default else False,
    # Watchlists (editable)
    "index_list": ["SPY","QQQ","IWM","DIA","TQQQ","SQQQ","XLF","EEM"],
    "stock_list": [
        # Mega-cap tech
        "AAPL","AMZN","GOOGL","NVDA","TSLA","AMD","ARM","INTC","ORCL",
        # High-vol momentum
        "COIN","HOOD","PLTR","PYPL","NFLX","SOFI","RKLB","IONQ","IREN",
        # China / ADRs
        "BABA","JD",
        # Finance / Insurance
        "UNH","LMND","HIMS","PINS","OKLO","RBLX","RDDT",
        # Consumer / Retail
        "WMT","OXY",
        # Leveraged ETFs & sector
        "TSLL",
        # Sector ETFs
        "XLK","XLE","SOXX",
        # Individual high-vol stocks from your list
        "V","XOM",
    ],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎯 Options Flow")
    st.markdown("---")

    # ── User Profile ──────────────────────────────────────────────────────────
    st.markdown("### 👤 My Settings")
    with st.expander("Set up your profile", expanded=not st.session_state.user_setup_done):
        user_name  = st.text_input("Your name",
                                   value=st.session_state.user_name,
                                   placeholder="e.g. John")
        user_email = st.text_input("Your email (for alerts)",
                                   value=st.session_state.user_email,
                                   placeholder="you@email.com")
        st.markdown("**Add your own tickers** (on top of the default list):")
        user_tickers_raw = st.text_input(
            "Extra tickers (comma separated)",
            value=",".join(st.session_state.user_tickers),
            placeholder="e.g. HOOD, RDDT, IONQ"
        )
        if st.button("💾 Save My Settings", key="save_profile"):
            st.session_state.user_name      = user_name.strip()
            st.session_state.user_email     = user_email.strip().lower()
            st.session_state.user_tickers   = [
                t.strip().upper()
                for t in user_tickers_raw.split(",")
                if t.strip()
            ]
            st.session_state.user_setup_done = True
            st.success(f"✅ Saved! Welcome {user_name or 'trader'} 👋")
            st.rerun()

    if st.session_state.user_setup_done:
        name_lbl   = st.session_state.user_name or "Trader"
        email_lbl  = st.session_state.user_email or "—"
        extras     = len(st.session_state.user_tickers)
        st.markdown(f"""
        <div style='background:#363b4f;border:1px solid #525a72;border-radius:8px;
                    padding:10px 14px;font-family:"JetBrains Mono",monospace;font-size:0.75rem;'>
          <span style='color:#4af0c4;'>👤 {name_lbl}</span><br>
          <span style='color:#b8c2d2;'>📧 {email_lbl}</span><br>
          <span style='color:#b8c2d2;'>📈 {extras} personal ticker(s) added</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Watchlist editor ──────────────────────────────────────────────────────
    st.markdown("### 📋 Watchlist Editor")

    with st.expander("🏛 Indices", expanded=False):
        idx_str = st.text_area("One ticker per line",
                               "\n".join(st.session_state.index_list),
                               height=100, key="idx_edit")
        if st.button("Save Indices", key="save_idx"):
            new = [t.strip().upper() for t in idx_str.split("\n") if t.strip()]
            st.session_state.index_list = new
            st.success(f"Saved {len(new)} index tickers")

    with st.expander("📈 Stocks & ETFs", expanded=False):
        stk_str = st.text_area("One ticker per line",
                               "\n".join(st.session_state.stock_list),
                               height=220, key="stk_edit")
        if st.button("Save Stocks & ETFs", key="save_stk"):
            new = [t.strip().upper() for t in stk_str.split("\n") if t.strip()]
            st.session_state.stock_list = new
            st.success(f"Saved {len(new)} tickers")

        # Quick-add single ticker
        st.markdown("**Quick add:**")
        col_a, col_b = st.columns([2,1])
        with col_a:
            new_ticker = st.text_input("Ticker", placeholder="e.g. HOOD", key="quick_add", label_visibility="collapsed")
        with col_b:
            if st.button("Add", key="btn_add"):
                t = new_ticker.strip().upper()
                if t and t not in st.session_state.stock_list:
                    st.session_state.stock_list.append(t)
                    st.success(f"Added {t}")
                elif t in st.session_state.stock_list:
                    st.warning(f"{t} already in list")

        # Quick-remove
        if st.session_state.stock_list:
            remove_t = st.selectbox("Remove ticker", ["—"] + sorted(st.session_state.stock_list), key="remove_sel")
            if st.button("Remove", key="btn_remove") and remove_t != "—":
                st.session_state.stock_list.remove(remove_t)
                st.success(f"Removed {remove_t}")

    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Signal Filters")
    vol_surge = st.slider("Vol surge threshold (x avg)", 1.5, 4.0, 2.0, 0.25)
    rsi_lo    = st.slider("RSI oversold threshold", 20, 40, 35, 1)
    rsi_hi    = st.slider("RSI overbought threshold", 60, 80, 65, 1)
    gap_filt  = st.slider("Gap filter (%)", 1, 10, 6, 1)

    st.markdown("---")

    # ── Auto-scan ─────────────────────────────────────────────────────────────
    st.markdown("### ⏱ Auto-Scan")
    auto_on = st.toggle("Auto-scan all sessions", value=st.session_state.auto_enabled)
    st.session_state.auto_enabled = auto_on

    st.markdown("---")

    # ── Email alerts (configured via Streamlit secrets — silent) ──────────────
    # No UI for Gmail credentials — they come from secrets.toml. We just read
    # the defaults into the variables that downstream code expects.
    gmail_user  = _gmail_user_default
    gmail_pass  = _gmail_pass_default
    alert_email = _gmail_alert_default
    send_alerts = bool(gmail_user and gmail_pass and alert_email)

    if st.session_state.email_error:
        st.error(f"Email error: {st.session_state.email_error}")

    # ── Scan buttons ──────────────────────────────────────────────────────────
    scan_all_btn   = st.button("🚀 Scan All", type="primary")
    st.markdown("---")
    scan_btn       = st.button("⚡ 1-hr Intraday Scan")
    daily_scan_btn = st.button("🌙 After-Hours Daily Scan")

    # ── Connection status (compact, informational only) ───────────────────────
    _alpaca_ready = bool(_alpaca_key_default)
    _gmail_ready  = bool(gmail_user and gmail_pass)
    st.markdown(f"""
    <div style='margin-top:14px;padding:10px 12px;background:#363b4f;border:1px solid #525a72;border-radius:8px;font-family:JetBrains Mono,monospace;font-size:0.7rem;line-height:1.7;'>
      {"🟢" if _alpaca_ready else "⚪"} Alpaca: {"connected" if _alpaca_ready else "yfinance fallback"}<br>
      {"🟢" if _gmail_ready else "⚪"} Email alerts: {"active" if _gmail_ready else "disabled"}
    </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style='margin-top:12px;font-size:0.7rem;color:#c8d2e0;line-height:1.9;'>
    <b style='color:#f0f4fb'>15-min signals</b><br>
    • VWAP Reclaim / Rejection<br>
    • Opening Range Breakout<br>
    • Double Bottom / Top<br>
    • EMA20 Reclaim / Rejection<br>
    • RSI Oversold / Overbought<br>
    • Volume Surge<br><br>
    <b style='color:#f0f4fb'>Last alert:</b> {st.session_state.last_alert}<br>
    <b style='color:#f0f4fb'>Watchlist:</b> {len(st.session_state.index_list)} indices · {len(st.session_state.stock_list)} stocks<br><br>
    <i style='color:#a8b3c8'>Pre-market: every 5 min · Market: every 15 min · After-hours: every 10 min</i><br><i style='color:#a8b3c8'>Not financial advice</i>
    </div>""", unsafe_allow_html=True)

# ── Use secrets as fallback (already loaded above, kept for explicitness) ────
if not gmail_user  and _gmail_user_default:  gmail_user  = _gmail_user_default
if not gmail_pass  and _gmail_pass_default:  gmail_pass  = _gmail_pass_default
if not alert_email and _gmail_alert_default: alert_email = _gmail_alert_default

# ── Config object ─────────────────────────────────────────────────────────────

# Alpaca keys — prefer secrets over session state
alpaca_key    = _alpaca_key_default    or st.session_state.alpaca_key_val
alpaca_secret = _alpaca_secret_default or st.session_state.alpaca_secret_val
use_alpaca    = bool(alpaca_key)  # auto-enable if keys available

# Merge user personal tickers into stock list (no duplicates)
_user_extras  = st.session_state.get("user_tickers", [])
_merged_stocks = list(dict.fromkeys(
    st.session_state.stock_list + _user_extras
))

cfg = ScannerConfig(
    index_tickers   = st.session_state.index_list,
    stock_tickers   = _merged_stocks,
    vol_surge_ratio = vol_surge,
    rsi_oversold    = float(rsi_lo),
    rsi_overbought  = float(rsi_hi),
    gap_filter_pct  = gap_filt / 100,
    alpaca_key      = alpaca_key,
    alpaca_secret   = alpaca_secret,
)

# ── Header ────────────────────────────────────────────────────────────────────

_greeting_name = st.session_state.get("user_name", "")
_greeting      = f"Welcome back, {_greeting_name} 👋" if _greeting_name else ""
_user_extras   = st.session_state.get("user_tickers", [])
_extra_count   = len(_user_extras)
_total_tickers = len(st.session_state.get("stock_list",[])) + \
                 len(st.session_state.get("index_list",[])) + _extra_count

st.markdown(f"""
<div style='padding:8px 0 12px 0;'>
  <h1 style='font-family:"Syne",sans-serif;font-size:2rem;font-weight:800;
             background:linear-gradient(90deg,#bc8cff,#4af0c4);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             margin:0;letter-spacing:-0.02em;'>Options Flow Dashboard</h1>
  <p style='color:#a896d0;font-family:"JetBrains Mono",monospace;
            font-size:0.78rem;margin:4px 0 0 0;'>
    1-hr intraday · daily swing setups · calls & puts · email alerts
    {"&nbsp;·&nbsp;<span style='color:#4af0c4;font-weight:600;'>" + _greeting + "</span>" if _greeting else ""}
  </p>
  <p style='color:#7a6a98;font-family:"JetBrains Mono",monospace;
            font-size:0.72rem;margin:2px 0 0 0;'>
    Scanning {_total_tickers} tickers
    {"&nbsp;·&nbsp;" + str(_extra_count) + " personal ticker(s) added" if _extra_count else ""}
  </p>
</div>""", unsafe_allow_html=True)

# ── Market status bar ─────────────────────────────────────────────────────────

is_open, status_lbl, mins_open, mins_close = market_status()
now_et = datetime.now(ET).strftime("%H:%M ET")

colors = {"open":"#4af0c4","pre-market":"#f5c842","closed":"#f04a6a","weekend":"#f04a6a"}
icons  = {"open":"●","pre-market":"◐","closed":"●","weekend":"●"}
col    = colors.get(status_lbl,"#b8c2d2")
icon   = icons.get(status_lbl,"●")
extra  = (f" | Closes in {mins_close} min" if is_open else
          f" | Opens in {mins_open} min" if status_lbl=="pre-market" else "")
auto_badge = " | 🔄 Auto-scan ON" if auto_on else ""

st.markdown(f"""
<div class="status-bar">
  <span style="color:{col}">{icon} {status_lbl.upper()}</span>
  <span style="color:#a896d0"> | </span>
  <span style="color:#d4dce8">{now_et}</span>
  <span style="color:#a896d0">{extra}</span>
  <span style="color:#4af0c4">{auto_badge}</span>
</div>""", unsafe_allow_html=True)

# ── Countdown ─────────────────────────────────────────────────────────────────

if auto_on:
    session_now = PremarketScanner.current_session()

    if session_now in ("PRE-MARKET", "AFTER-HOURS"):
        # Show PM/AH countdown
        if st.session_state.last_pm_scan is None:
            st.session_state.last_pm_scan = datetime.now()
        pm_secs = next_pm_scan_secs(session_now)
        pm_m, pm_s = pm_secs // 60, pm_secs % 60
        interval_lbl = "5 min" if session_now == "PRE-MARKET" else "10 min"
        last_lbl = st.session_state.pm_timestamp or "pending first scan"
        st.markdown(f"""
        <div class="countdown">
          {"🌅" if session_now == "PRE-MARKET" else "🌙"} {session_now} auto-scan every {interval_lbl}
          &nbsp;·&nbsp; Next in <b>{pm_m:02d}:{pm_s:02d}</b>
          &nbsp;·&nbsp; Last: <b>{last_lbl}</b>
        </div>""", unsafe_allow_html=True)
    else:
        # Show 15-min intraday countdown
        if st.session_state.last_scan_time is None:
            st.session_state.last_scan_time = datetime.now()
        secs = next_scan_secs(30)
        m, s = secs // 60, secs % 60
        last_lbl = st.session_state.scan_timestamp or "pending first scan"
        st.markdown(f"""
        <div class="countdown">
          ⚡ Market hours — auto-scan every 30 min
          &nbsp;·&nbsp; Next in <b>{m:02d}:{s:02d}</b>
          &nbsp;·&nbsp; Last: <b>{last_lbl}</b>
          &nbsp;·&nbsp; {len(st.session_state.index_list) + len(st.session_state.stock_list)} tickers
        </div>""", unsafe_allow_html=True)

# ── Run scan ──────────────────────────────────────────────────────────────────

def do_scan():
    scanner = HourlyScanner(cfg)   # 1-hr bars for intraday swing entries
    pb  = st.progress(0)
    stx = st.empty()

    def cb(idx, total, ticker):
        pb.progress(idx / total)
        stx.markdown(f"`[{idx}/{total}]` scanning **{ticker}**…")

    df = scanner.run(progress_cb=cb)
    pb.empty(); stx.empty()

    st.session_state.scan_results   = df
    st.session_state.last_scan_time = datetime.now()
    st.session_state.scan_timestamp = datetime.now().strftime("%H:%M:%S")

    if send_alerts and gmail_user and gmail_pass and alert_email:
        sent = send_alert(df, gmail_user, gmail_pass, alert_email)
        if sent:
            st.session_state.last_alert = datetime.now().strftime("%H:%M:%S")

if scan_btn:
    with st.status("🔍 Scanning 15-min signals...", expanded=True) as status:
        do_scan()
        status.update(label="✅ Scan complete!", state="complete")

# Daily scan trigger
if daily_scan_btn:
    with st.status("🌙 Scanning daily candles for swing setups...", expanded=True) as status:
        pb  = st.progress(0)
        stx = st.empty()
        def dcb(idx, total, ticker):
            pb.progress(idx / total)
            stx.markdown(f"`[{idx}/{total}]` → **{ticker}**")
        scanner  = DailyScanner(cfg)
        df_daily = scanner.run(progress_cb=dcb)
        pb.empty(); stx.empty()
        st.session_state.daily_results   = df_daily
        st.session_state.daily_timestamp = datetime.now().strftime("%H:%M:%S")
        if send_alerts and gmail_user and gmail_pass and alert_email:
            sent = send_alert(df_daily, gmail_user, gmail_pass, alert_email)
            if sent:
                st.session_state.last_alert = datetime.now().strftime("%H:%M:%S")
        status.update(label="✅ 1-hr scan complete!", state="complete")

# ── Scan All trigger ─────────────────────────────────────────────────────────
if scan_all_btn:
    with st.status("🚀 Running all 3 scanners...", expanded=True) as status:
        pb  = st.progress(0)
        stx = st.empty()

        # 1. 15-min Intraday
        stx.markdown("**[1/3]** ⚡ Running 15-min intraday scan...")
        pb.progress(0.1)
        def _cb1(idx, total, ticker):
            pb.progress(0.1 + 0.3 * idx/total)
            stx.markdown(f"**[1/3]** ⚡ 15-min — `{ticker}`")
        _s1 = HourlyScanner(cfg)   # 1-hr bars
        _df1 = _s1.run(progress_cb=_cb1)
        st.session_state.scan_results   = _df1
        st.session_state.scan_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.last_scan_time = datetime.now()

        # 2. After-Hours 1-hr
        stx.markdown("**[2/3]** 🌙 Running 1-hr after-hours scan...")
        pb.progress(0.4)
        def _cb2(idx, total, ticker):
            pb.progress(0.4 + 0.3 * idx/total)
            stx.markdown(f"**[2/3]** 🌙 1-hr — `{ticker}`")
        _s2 = DailyScanner(cfg)    # Daily candles for swing setups
        _df2 = _s2.run(progress_cb=_cb2)
        st.session_state.daily_results   = _df2
        st.session_state.daily_timestamp = datetime.now().strftime("%H:%M:%S")

        # 3. Pre-Market / AH
        stx.markdown("**[3/3]** 🌅 Running pre-market scan...")
        pb.progress(0.7)
        def _cb3(idx, total, ticker):
            pb.progress(0.7 + 0.3 * idx/total)
            stx.markdown(f"**[3/3]** 🌅 Pre-market — `{ticker}`")
        _s3 = PremarketScanner(cfg)
        _df3 = _s3.run(progress_cb=_cb3)
        st.session_state.pm_results   = _df3
        st.session_state.pm_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pm_session   = PremarketScanner.current_session()
        st.session_state.last_pm_scan = datetime.now()

        pb.progress(1.0)
        pb.empty(); stx.empty()

        # Email all results
        if send_alerts and gmail_user and gmail_pass and alert_email:
            send_alert(_df1, gmail_user, gmail_pass, alert_email)
            send_alert(_df2, gmail_user, gmail_pass, alert_email)

        _total = (len(_df1) if not _df1.empty else 0) +                  (len(_df2) if not _df2.empty else 0) +                  (len(_df3) if not _df3.empty else 0)
        status.update(label=f"✅ All 3 scans complete — {_total} total signals!", state="complete")

# Pre-market tab removed

# ── Auto-scan trigger — fires based on current session ────────────────────────
_session_now = PremarketScanner.current_session()

# Pre-market auto-scan (every 5 min, 4AM-9:30AM ET)
if auto_on and _session_now == "PRE-MARKET" and next_pm_scan_secs("PRE-MARKET") == 0:
    with st.spinner("🌅 Auto-scanning pre-market..."):
        _pm_s  = PremarketScanner(cfg)
        _df_pm = _pm_s.run()
        st.session_state.pm_results   = _df_pm
        st.session_state.pm_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pm_session   = "PRE-MARKET"
        st.session_state.last_pm_scan = datetime.now()
        if send_alerts and gmail_user and gmail_pass and alert_email:
            pass  # PM alerts handled separately

# After-hours auto-scan (every 10 min, 4PM-8PM ET)
if auto_on and _session_now == "AFTER-HOURS" and next_pm_scan_secs("AFTER-HOURS") == 0:
    with st.spinner("🌙 Auto-scanning after-hours..."):
        _pm_s  = PremarketScanner(cfg)
        _df_pm = _pm_s.run()
        st.session_state.pm_results   = _df_pm
        st.session_state.pm_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pm_session   = "AFTER-HOURS"
        st.session_state.last_pm_scan = datetime.now()

# 15-min intraday auto-scan (market hours only)
if auto_on and is_open and next_scan_secs(30) == 0:
    with st.spinner("🔄 Auto-scanning..."):
        do_scan()
    # Don't rerun — results are already in session state and will render below

# ── Results tabs ─────────────────────────────────────────────────────────────

st.markdown("---")
tab1, tab2 = st.tabs(["⚡ 1-hr Intraday Scanner", "🌙 After-Hours Daily Scanner"])

# ════════════════════════════════════════════════
#  TAB 1 — 15-min Intraday
# ════════════════════════════════════════════════
with tab1:
    if st.session_state.scan_results is not None:
        df    = st.session_state.scan_results
        # Show 4★+ only
        if not df.empty and "Confidence" in df.columns:
            df = df[df["Confidence"].str.len() >= 4]
        calls = df[df["Direction"]=="CALL"] if not df.empty else pd.DataFrame()
        puts  = df[df["Direction"]=="PUT"]  if not df.empty else pd.DataFrame()
        confluences = df[df["Confluence"]==True] if "Confluence" in df.columns else pd.DataFrame()

        st.caption(f"⏱ {st.session_state.scan_timestamp} · 15-min delayed · {len(df)} total signals")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Signals",   len(df))
        c2.metric("⚡ Confluence",   len(confluences))
        c3.metric("CALL Signals",    len(calls))
        c4.metric("PUT Signals",     len(puts))
        c5.metric("Tickers Scanned", len(cfg.index_tickers)+len(cfg.stock_tickers))
        st.markdown("---")

        if df.empty:
            st.info("No signals right now. Best times: 9:45–11:30 AM and 2:00–3:45 PM ET.")
        else:
            col_c, col_p = st.columns(2)
            with col_c:
                st.markdown("### 🟢 CALL Signals")
                if calls.empty: st.caption("No call signals.")
                for _, row in calls.iterrows():
                    st.markdown(signal_card(row.to_dict()), unsafe_allow_html=True)
            with col_p:
                st.markdown("### 🔴 PUT Signals")
                if puts.empty: st.caption("No put signals.")
                for _, row in puts.iterrows():
                    st.markdown(signal_card(row.to_dict()), unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📊 Chart Explorer (1-hr)")
            sel = st.selectbox("Select ticker", df["Ticker"].tolist(), key="intra_sel")
            if sel:
                row = df[df["Ticker"]==sel].iloc[0]
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("Price",     f"${row['Price']}")
                m2.metric("Direction", row["Direction"])
                m3.metric("Strike",    f"${row['Strike']}")
                m4.metric("Signal",    row["Signal"])
                with st.spinner(f"Loading {sel} 15-min chart…"):
                    fig = build_chart(sel)
                if fig:
                    st.plotly_chart(fig, width='stretch')
                    st.caption("🟡 VWAP · 🟢 EMA9 · 🟣 EMA20 · 🔴 SMA50")
                d      = row["Direction"]
                border = "#4af0c4" if d=="CALL" else "#f04a6a"
                st.markdown(f"""
                <div style='background:#363b4f;border-left:3px solid {border};border-radius:0 8px 8px 0;padding:16px 20px;margin-top:8px;'>
                  <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:0.85rem;'>
                    <div><span style='color:#a8b3c8'>Signal:</span> <b>{row['Signal']}</b></div>
                    <div><span style='color:#a8b3c8'>RSI:</span> <b>{row['RSI']}</b></div>
                    <div><span style='color:#a8b3c8'>Volume:</span> <b>{row['Vol Ratio']}x</b></div>
                    <div><span style='color:#a8b3c8'>VWAP:</span> <b>${row['VWAP']}</b></div>
                    <div><span style='color:#a8b3c8'>Strike:</span> <b>${row['Strike']}</b></div>
                    <div><span style='color:#a8b3c8'>Confidence:</span> <b>{row['Confidence']}</b></div>
                  </div>
                  <div style='margin-top:10px;padding-top:10px;border-top:1px solid #525a72;font-size:0.82rem;color:#b8c2d2;'>{row['Notes']}</div>
                </div>""", unsafe_allow_html=True)
        # ── Export section ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📤 Export Results")
        ex1, ex2, ex3 = st.columns(3)

        with ex1:
            if st.button("📧 Email Results", key="email_intra") and not df.empty:
                if gmail_user and gmail_pass and alert_email:
                    html    = build_export_html(calls, puts, "15-min Intraday",
                                                st.session_state.scan_timestamp or "—")
                    subject = f"🎯 Options Flow — 15-min Intraday · {len(calls)} Calls · {len(puts)} Puts · {datetime.now(ET).strftime('%b %d %H:%M ET')}"
                    sent    = send_export_email(html, subject, gmail_user, gmail_pass, alert_email)
                    if sent: st.success("✅ Email sent!")
                    else:    st.error("❌ Email failed — check Gmail settings in sidebar")
                else:
                    st.warning("⚠️ Enter Gmail details in sidebar first")

        with ex2:
            if not df.empty:
                csv = build_csv(df)
                st.download_button("⬇️ Download CSV", csv,
                                   file_name=f"options_flow_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                   mime="text/csv", key="csv_intra")

        with ex3:
            if not df.empty:
                html_export = build_export_html(calls, puts, "15-min Intraday",
                                                st.session_state.scan_timestamp or "—")
                st.download_button("⬇️ Download HTML", html_export,
                                   file_name=f"options_flow_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                                   mime="text/html", key="html_intra")

    else:
        st.markdown("""
        <div style='text-align:center;padding:60px 0;color:#7a6a98;'>
          <div style='font-size:3rem;'>⚡</div>
          <div style='font-family:"JetBrains Mono",monospace;font-size:0.95rem;margin-top:12px;color:#a896d0;'>
            Click <b style='color:#4af0c4'>⚡ 1-hr Intraday Scan</b> in the sidebar
          </div>
          <div style='font-size:0.78rem;margin-top:6px;'>Best between 9:30 AM – 3:45 PM ET</div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
#  TAB 2 — After-Hours Daily Scanner
# ════════════════════════════════════════════════
with tab2:
    st.markdown("""
    <div style='background:#363b4f;border:1px solid #525a72;border-radius:8px;padding:14px 18px;margin-bottom:16px;font-family:"JetBrains Mono",monospace;font-size:0.78rem;color:#b8c2d2;'>
      🌙 <b style='color:#e0e8f0'>After-Hours 1-hr Scanner</b> — finds next-day setups on 1-hour candles.<br>
      Run after 4:00 PM ET or on weekends · looks back 5 days (~30-40 bars).<br>
      Signals: VWAP · EMA9/20 reclaims · Double Bottom/Top · SMA touches · RSI extremes · Inside bars · Volume
    </div>""", unsafe_allow_html=True)

    if st.session_state.daily_results is not None:
        df    = st.session_state.daily_results
        # Show 4★+ only
        if not df.empty and "Confidence" in df.columns:
            df = df[df["Confidence"].str.len() >= 4]
        calls = df[df["Direction"]=="CALL"] if not df.empty else pd.DataFrame()
        puts  = df[df["Direction"]=="PUT"]  if not df.empty else pd.DataFrame()
        confluences = df[df["Confluence"]==True] if "Confluence" in df.columns else pd.DataFrame()

        st.caption(f"⏱ Scanned: {st.session_state.daily_timestamp} · 1-hr candles · {len(df)} setups found")
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Setups",    len(df))
        c2.metric("⚡ Confluence",   len(confluences))
        c3.metric("CALL Setups",     len(calls))
        c4.metric("PUT Setups",      len(puts))
        c5.metric("Tickers Scanned", len(cfg.index_tickers)+len(cfg.stock_tickers))
        st.markdown("---")

        if df.empty:
            st.info("No 1-hr setups found. Try running after 4 PM ET or on weekends for best results.")
        else:
            col_c, col_p = st.columns(2)
            with col_c:
                st.markdown("### 🟢 CALL Setups (Next Day)")
                if calls.empty: st.caption("No call setups.")
                for _, row in calls.iterrows():
                    st.markdown(daily_signal_card(row.to_dict()), unsafe_allow_html=True)
            with col_p:
                st.markdown("### 🔴 PUT Setups (Next Day)")
                if puts.empty: st.caption("No put setups.")
                for _, row in puts.iterrows():
                    st.markdown(daily_signal_card(row.to_dict()), unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📊 Daily Chart Explorer")
            sel = st.selectbox("Select ticker", df["Ticker"].tolist(), key="daily_sel")
            if sel:
                row = df[df["Ticker"]==sel].iloc[0]
                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("Price",     f"${row['Price']}")
                m2.metric("Direction", row["Direction"])
                m3.metric("Strike",    f"${row['Strike']}")
                m4.metric("Expiry",    row["Expiry"])
                m5.metric("RSI",       row["RSI"])
                with st.spinner(f"Loading {sel} daily chart…"):
                    fig = build_daily_chart(sel)
                if fig:
                    st.plotly_chart(fig, width='stretch')
                    st.caption("🟢 EMA9 · 🟣 EMA20 · 🟡 SMA50 · 🟠 SMA100 · 🔴 SMA200 · 🟡 VWAP")
                d      = row["Direction"]
                border = "#4af0c4" if d=="CALL" else "#f04a6a"
                iv_color = "#f04a6a" if "High" in row.get("IV Note","") else (
                           "#4af0c4" if "Low"  in row.get("IV Note","") else "#f5c842")
                st.markdown(f"""
                <div style='background:#363b4f;border-left:3px solid {border};border-radius:0 8px 8px 0;padding:16px 20px;margin-top:8px;'>
                  <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:0.85rem;margin-bottom:10px;'>
                    <div><span style='color:#a8b3c8'>Signal:</span> <b>{row['Signal']}</b></div>
                    <div><span style='color:#a8b3c8'>SMA Level:</span> <b>{row['SMA Level']}</b></div>
                    <div><span style='color:#a8b3c8'>RSI:</span> <b>{row['RSI']}</b></div>
                    <div><span style='color:#a8b3c8'>Volume:</span> <b>{row['Vol Ratio']}x avg</b></div>
                    <div><span style='color:#a8b3c8'>ATR:</span> <b>${row['ATR']}</b></div>
                    <div><span style='color:#a8b3c8'>VWAP:</span> <b>${row.get('VWAP','—')}</b></div>
                    <div><span style='color:#a8b3c8'>Confidence:</span> <b>{row['Confidence']}</b></div>
                  </div>
                  <div style='padding-top:10px;border-top:1px solid #525a72;font-size:0.82rem;color:{iv_color};'>{row.get('IV Note','')}</div>
                  <div style='margin-top:6px;font-size:0.78rem;color:#b8c2d2;'>{row['Notes']}</div>
                </div>""", unsafe_allow_html=True)
        # ── Export section ─────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 📤 Export Results")
        ex1, ex2, ex3 = st.columns(3)

        with ex1:
            if st.button("📧 Email Results", key="email_hourly") and not df.empty:
                if gmail_user and gmail_pass and alert_email:
                    html    = build_export_html(calls, puts, "After-Hours 1-hr",
                                                st.session_state.daily_timestamp or "—")
                    subject = f"🌙 Options Flow — After-Hours 1-hr · {len(calls)} Calls · {len(puts)} Puts · {datetime.now(ET).strftime('%b %d %H:%M ET')}"
                    sent    = send_export_email(html, subject, gmail_user, gmail_pass, alert_email)
                    if sent: st.success("✅ Email sent!")
                    else:    st.error("❌ Email failed — check Gmail settings in sidebar")
                else:
                    st.warning("⚠️ Enter Gmail details in sidebar first")

        with ex2:
            if not df.empty:
                csv = build_csv(df)
                st.download_button("⬇️ Download CSV", csv,
                                   file_name=f"afterhours_flow_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                   mime="text/csv", key="csv_hourly")

        with ex3:
            if not df.empty:
                html_export = build_export_html(calls, puts, "After-Hours 1-hr",
                                                st.session_state.daily_timestamp or "—")
                st.download_button("⬇️ Download HTML", html_export,
                                   file_name=f"afterhours_flow_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                                   mime="text/html", key="html_hourly")

    else:
        st.markdown("""
        <div style='text-align:center;padding:60px 0;color:#7a6a98;'>
          <div style='font-size:3rem;'>🌙</div>
          <div style='font-family:"JetBrains Mono",monospace;font-size:0.95rem;margin-top:12px;color:#a896d0;'>
            Click <b style='color:#4af0c4'>After-Hours Scan (1-hr)</b> in the sidebar
          </div>
          <div style='font-size:0.78rem;margin-top:6px;'>
            1-hr candles · 5-day lookback · best for next-day trade planning
          </div>
        </div>""", unsafe_allow_html=True)

# ── Auto-refresh ──────────────────────────────────────────────────────────────

if auto_on:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=30_000, limit=None, key="autorefresh")
    except ImportError:
        st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("""
<div style='text-align:center;font-family:"JetBrains Mono",monospace;font-size:0.68rem;color:#1a2a40;'>
  yfinance · 15-min delayed · not financial advice · educational use only
</div>""", unsafe_allow_html=True)
