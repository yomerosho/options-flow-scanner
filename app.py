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

from scanner import IntradayScanner, HourlyScanner, PremarketScanner, ScannerConfig, Indicators

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
html, body, [class*="css"] { font-family:'Syne',sans-serif; background:#080b10; color:#d4dce8; }

section[data-testid="stSidebar"] { background:#0c1018; border-right:1px solid #1a2030; }
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
section[data-testid="stSidebar"] .stTextArea textarea {
  color:#e0e8f0 !important;
  background:#131922 !important;
  border:1px solid #2a3a50 !important;
}

section[data-testid="stSidebar"] .stTextInput input::placeholder,
section[data-testid="stSidebar"] .stTextArea textarea::placeholder {
  color:#4a6a80 !important;
}

section[data-testid="stSidebar"] .stSelectbox div,
section[data-testid="stSidebar"] .stExpander summary p,
section[data-testid="stSidebar"] .stExpander p { color:#e0e8f0 !important; }

section[data-testid="stSidebar"] .stCheckbox label p { color:#e0e8f0 !important; }

section[data-testid="stSidebar"] [data-testid="stSliderLabel"] { color:#e0e8f0 !important; }

[data-testid="metric-container"] { background:#0e1520; border:1px solid #1a2535; border-radius:10px; padding:16px 20px; }
[data-testid="metric-container"] label { color:#4a5a70 !important; font-size:0.7rem; letter-spacing:.1em; text-transform:uppercase; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-family:'JetBrains Mono',monospace; font-size:1.8rem; font-weight:600; color:#4af0c4; }

.stButton > button { font-family:'JetBrains Mono',monospace; font-size:0.82rem; border-radius:6px; padding:10px 0; width:100%; border:none; background:linear-gradient(135deg,#1a6b50,#0d4a38); color:#4af0c4; transition:all .2s; }
.stButton > button:hover { background:linear-gradient(135deg,#22876a,#125240); }

.signal-call { border-left:3px solid #4af0c4; background:#0a1f18; padding:14px 18px; border-radius:0 8px 8px 0; margin:6px 0; }
.signal-put  { border-left:3px solid #f04a6a; background:#1f0a10; padding:14px 18px; border-radius:0 8px 8px 0; margin:6px 0; }
.badge-call  { display:inline-block; background:#0d3d28; color:#4af0c4; font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:20px; }
.badge-put   { display:inline-block; background:#3d0d1a; color:#f04a6a; font-family:'JetBrains Mono',monospace; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:20px; }
.badge-index { display:inline-block; background:#1a2a50; color:#6ab0f0; font-family:'JetBrains Mono',monospace; font-size:0.65rem; padding:1px 8px; border-radius:10px; }
.badge-stock { display:inline-block; background:#2a1a40; color:#c083f8; font-family:'JetBrains Mono',monospace; font-size:0.65rem; padding:1px 8px; border-radius:10px; }

.status-bar { background:#0e1520; border:1px solid #1a2535; border-radius:8px; padding:10px 18px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; margin-bottom:12px; }
.countdown  { background:#0a1520; border:1px solid #1a3040; border-radius:8px; padding:8px 16px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#4af0c4; text-align:center; margin-bottom:12px; }
.wl-section { background:#0e1520; border:1px solid #1a2535; border-radius:8px; padding:12px 14px; margin:8px 0; font-family:'JetBrains Mono',monospace; font-size:0.72rem; }
.wl-ticker  { display:inline-block; background:#131922; color:#d4dce8; border:1px solid #2a3a50; border-radius:4px; padding:2px 8px; margin:2px; font-size:0.72rem; }

/* Confluence card */
.signal-confluence-call {
  border-left: 4px solid #4af0c4;
  background: linear-gradient(135deg, #0a2a1f 0%, #0d1f30 100%);
  padding: 16px 18px;
  border-radius: 0 8px 8px 0;
  margin: 8px 0;
  box-shadow: 0 0 20px rgba(74,240,196,0.15);
}
.signal-confluence-put {
  border-left: 4px solid #f04a6a;
  background: linear-gradient(135deg, #2a0a10 0%, #1f0d20 100%);
  padding: 16px 18px;
  border-radius: 0 8px 8px 0;
  margin: 8px 0;
  box-shadow: 0 0 20px rgba(240,74,106,0.15);
}
.confluence-badge {
  display:inline-block;
  background: linear-gradient(90deg,#1a4a38,#1a3a50);
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
  background:#131922;
  color:#8090a0;
  font-family:'JetBrains Mono',monospace;
  font-size:0.65rem;
  padding:1px 8px;
  border-radius:10px;
  margin:2px;
  border:1px solid #1a2535;
}
.body-confirm {
  display:inline-block;
  background:#0d3020;
  color:#4af0c4;
  font-size:0.65rem;
  padding:1px 8px;
  border-radius:10px;
  font-family:'JetBrains Mono',monospace;
}
hr { border-color:#1a2030; }
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

def next_scan_secs(interval_min=15):
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
        html = f"""<html><body style='background:#080b10;color:#d4dce8;font-family:monospace;'>
        <div style='max-width:720px;margin:0 auto;padding:24px;'>
        <h2 style='color:#4af0c4;border-bottom:1px solid #1a2535;padding-bottom:12px;'>🎯 Options Flow Alert — 15-min Scan</h2>
        <p style='color:#8090a0;font-size:0.85rem;'>{len(strong)} high-confidence setup(s) — {datetime.now(ET).strftime('%H:%M ET')}</p>
        <table style='width:100%;border-collapse:collapse;background:#0e1520;border:1px solid #1a2535;'>
        <tr style='background:#131922;color:#5a7a90;font-size:0.75rem;'>
        <th style='padding:10px;text-align:left'>TICKER</th><th style='padding:10px;text-align:left'>DIR</th>
        <th style='padding:10px;text-align:left'>PRICE</th><th style='padding:10px;text-align:left'>STRIKE</th>
        <th style='padding:10px;text-align:left'>SIGNAL</th><th style='padding:10px;text-align:left'>CONF</th>
        <th style='padding:10px;text-align:left'>NOTES</th></tr>{rows}</table>
        <p style='color:#2a3a50;font-size:0.7rem;margin-top:16px;'>15-min delayed · Not financial advice</p>
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
            return f'<p style="color:#5a7a90;font-family:monospace;padding:12px;">No {direction} setups found.</p>'
        rows = ""
        for _, r in df.iterrows():
            col     = "#4af0c4" if direction=="CALL" else "#f04a6a"
            bg      = "#0a1f18" if direction=="CALL" else "#1f0a10"
            border  = col
            icon    = "▲" if direction=="CALL" else "▼"
            dir_bg  = "#0d3d28" if direction=="CALL" else "#3d0d1a"
            is_conf = bool(r.get("Confluence", False))
            conf_tag= '<span style="background:#1a4a38;color:#4af0c4;font-size:0.7rem;padding:2px 8px;border-radius:10px;font-weight:700;margin-left:4px;">⚡ CONFLUENCE</span>' if is_conf else ""
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
                        pills += f'<span style="background:#131922;color:#8090a0;font-size:0.65rem;padding:1px 7px;border-radius:8px;margin:2px;border:1px solid #1a2535;display:inline-block;">{s.strip()}</span>'
            rows += f"""
            <div style="border-left:4px solid {border};background:{bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:8px 0;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
                <span style="font-family:monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{r["Ticker"]}</span>
                <span style="background:#2a1a40;color:#c083f8;font-size:0.65rem;padding:1px 8px;border-radius:8px;">{r.get("Type","")}</span>
                <span style="background:{dir_bg};color:{col};font-size:0.72rem;font-weight:700;padding:2px 10px;border-radius:20px;">{icon} {direction}</span>
                {conf_tag}
                <span style="color:#8090a0;font-size:0.82rem;margin-left:4px;">${r["Price"]}</span>
                <span style="margin-left:auto;">{r["Confidence"]}</span>
              </div>
              <div style="font-size:0.9rem;color:#c0d0e0;font-weight:600;margin-bottom:4px;">
                {r["Signal"]} → <span style="color:{col};">Strike ${r["Strike"]}</span>
                {"&nbsp;<span style='color:#8090a0;font-size:0.78rem;'>(" + expiry + ")</span>" if expiry else ""}
              </div>
              {"<div style='margin:5px 0;'>" + pills + "</div>" if pills else ""}
              <div style="font-size:0.75rem;color:#5a7a90;margin-top:4px;">
                {"VWAP $" + vwap + " &nbsp;|&nbsp; " if vwap not in ["—","nan",""] else ""}RSI {r["RSI"]} &nbsp;|&nbsp; Vol {r["Vol Ratio"]}x{"&nbsp;|&nbsp; SMA: " + sma if sma != "—" else ""}
              </div>
              <div style="font-size:0.74rem;margin-top:4px;color:{iv_col};">{iv}</div>
            </div>"""
        return rows

    total     = len(df_calls) + len(df_puts)
    call_rows = card_rows(df_calls, "CALL")
    put_rows  = card_rows(df_puts,  "PUT")

    return f"""<!DOCTYPE html><html>
    <body style="background:#080b10;color:#d4dce8;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0;">
    <div style="max-width:900px;margin:0 auto;padding:24px;">
      <div style="border-bottom:1px solid #1a2535;padding-bottom:16px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:1.5rem;font-weight:800;color:#4af0c4;">🎯 Options Flow — {scan_type}</h1>
        <p style="color:#5a7a90;font-family:monospace;font-size:0.8rem;margin:6px 0 0 0;">
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
      <div style="border-top:1px solid #1a2535;margin-top:24px;padding-top:12px;font-size:0.68rem;color:#2a3a50;text-align:center;">
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
            template="plotly_dark", paper_bgcolor="#0e1520", plot_bgcolor="#0e1520",
            xaxis=dict(showgrid=False, rangeslider_visible=False),
            yaxis=dict(showgrid=True, gridcolor="#1a2535", domain=[0.25,1.0]),
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
            template="plotly_dark", paper_bgcolor="#0e1520", plot_bgcolor="#0e1520",
            xaxis=dict(showgrid=False, rangeslider_visible=False),
            yaxis=dict(showgrid=True, gridcolor="#1a2535", domain=[0.25,1.0]),
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
    is_conf  = bool(row.get("Confluence", False))
    body_ok  = str(row.get("Body✓EMA9","—")) == "✅"
    stacked  = str(row.get("Signals",""))

    icon     = "▲" if d=="CALL" else "▼"
    dir_col  = "#4af0c4" if d=="CALL" else "#f04a6a"
    dir_bg   = "#0d3d28" if d=="CALL" else "#3d0d1a"
    card_bg  = "#0a1f18" if d=="CALL" else "#1f0a10"
    border   = "#4af0c4" if d=="CALL" else "#f04a6a"
    type_bg  = "#1a2a50" if t=="INDEX" else "#2a1a40"
    type_col = "#6ab0f0" if t=="INDEX" else "#c083f8"

    if is_conf:
        card_bg = "linear-gradient(135deg,#0a2a1f,#0d1f30)" if d=="CALL" else "linear-gradient(135deg,#2a0a10,#1f0d20)"

    conf_badge = '<span style="background:linear-gradient(90deg,#1a4a38,#1a3a50);color:#4af0c4;font-family:JetBrains Mono,monospace;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;border:1px solid #4af0c430;">⚡ CONFLUENCE</span>' if is_conf else ""
    body_html  = '<span style="background:#0d3020;color:#4af0c4;font-size:0.65rem;padding:1px 8px;border-radius:10px;font-family:JetBrains Mono,monospace;">✅ Body Close</span>' if body_ok else ""

    pills = ""
    if stacked and is_conf:
        for s in stacked.split(" · "):
            if s.strip():
                pills += f'<span style="background:#131922;color:#8090a0;font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;margin:2px;border:1px solid #1a2535;">{s.strip()}</span>'

    return (
        f'<div style="border-left:4px solid {border};background:{card_bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:6px 0;">' +
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;flex-wrap:wrap;">' +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{ticker}</span>' +
        f'<span style="background:{type_bg};color:{type_col};font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;">{t}</span>' +
        f'<span style="background:{dir_bg};color:{dir_col};font-family:JetBrains Mono,monospace;font-size:0.72rem;font-weight:600;padding:2px 10px;border-radius:20px;">{icon} {d}</span>' +
        conf_badge + body_html +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.82rem;color:#8090a0;margin-left:4px;">${price}</span>' +
        f'<span style="margin-left:auto;font-size:0.82rem;">{conf}</span>' +
        f'</div>' +
        f'<div style="font-size:0.88rem;color:#c0d0e0;margin-bottom:5px;font-weight:600;">{signal} → <span style="color:{dir_col};">Strike ${strike}</span></div>' +
        (f'<div style="margin:5px 0;">{pills}</div>' if pills else "") +
        f'<div style="font-size:0.75rem;color:#5a7a90;margin-top:4px;">VWAP ${vwap} | RSI {rsi} | Vol {vol}x</div>' +
        f'<div style="font-size:0.74rem;color:#4a6a80;margin-top:3px;">{notes}</div>' +
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
    is_conf  = bool(row.get("Confluence", False))
    stacked  = str(row.get("Signals",""))

    icon     = "▲" if d=="CALL" else "▼"
    dir_col  = "#4af0c4" if d=="CALL" else "#f04a6a"
    dir_bg   = "#0d3d28" if d=="CALL" else "#3d0d1a"
    card_bg  = "#0a1f18" if d=="CALL" else "#1f0a10"
    border   = "#4af0c4" if d=="CALL" else "#f04a6a"
    type_bg  = "#1a2a50" if t=="INDEX" else "#2a1a40"
    type_col = "#6ab0f0" if t=="INDEX" else "#c083f8"
    iv_color = "#f04a6a" if "High" in iv_note else ("#4af0c4" if "Low" in iv_note else "#f5c842")

    conf_badge = ""
    if is_conf:
        card_bg = "linear-gradient(135deg,#0a2a1f,#0d1f30)" if d=="CALL" else "linear-gradient(135deg,#2a0a10,#1f0d20)"
        conf_badge = '<span style="background:linear-gradient(90deg,#1a4a38,#1a3a50);color:#4af0c4;font-family:JetBrains Mono,monospace;font-size:0.7rem;font-weight:700;padding:2px 10px;border-radius:20px;border:1px solid #4af0c430;">⚡ CONFLUENCE</span>'

    pills = ""
    if stacked and is_conf:
        for s in stacked.split(" · "):
            if s.strip():
                pills += f'<span style="background:#131922;color:#8090a0;font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;margin:2px;border:1px solid #1a2535;">{s.strip()}</span>'

    return (
        f'<div style="border-left:4px solid {border};background:{card_bg};padding:14px 18px;border-radius:0 8px 8px 0;margin:6px 0;">' +
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;flex-wrap:wrap;">' +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;">{ticker}</span>' +
        f'<span style="background:{type_bg};color:{type_col};font-family:JetBrains Mono,monospace;font-size:0.65rem;padding:1px 8px;border-radius:10px;">{t}</span>' +
        f'<span style="background:{dir_bg};color:{dir_col};font-family:JetBrains Mono,monospace;font-size:0.72rem;font-weight:600;padding:2px 10px;border-radius:20px;">{icon} {d}</span>' +
        conf_badge +
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.82rem;color:#8090a0;margin-left:4px;">${price}</span>' +
        f'<span style="margin-left:auto;font-size:0.82rem;">{conf}</span>' +
        f'</div>' +
        f'<div style="font-size:0.88rem;color:#c0d0e0;margin-bottom:5px;font-weight:600;">{signal} → <span style="color:{dir_col};">Strike ${strike}</span> <span style="color:#8090a0;font-size:0.78rem;">({expiry})</span></div>' +
        (f'<div style="margin:5px 0;">{pills}</div>' if pills else "") +
        f'<div style="font-size:0.75rem;color:#5a7a90;margin-top:4px;">SMA: {sma_lv} | RSI {rsi} | Vol {vol}x | ATR ${atr}</div>' +
        f'<div style="font-size:0.74rem;margin-top:4px;color:{iv_color};">{iv_note}</div>' +
        f'</div>'
    )

# ── Session state ─────────────────────────────────────────────────────────────

DEFAULTS = {
    "scan_results":    None,
    "last_scan_time":  None,
    "scan_timestamp":  None,
    "auto_enabled":    False,
    "last_alert":      "—",
    "email_error":     None,
    "daily_results":   None,
    "daily_timestamp": None,
    "pm_results":      None,
    "pm_timestamp":    None,
    "pm_session":      "—",
    "last_pm_scan":    None,
    "alpaca_key_val":    "",
    "alpaca_secret_val": "",
    "use_alpaca_val":    False,
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
        "XLF","XLK","XLE","SOXX",
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

    # ── Email alerts ──────────────────────────────────────────────────────────
    st.markdown("### 📧 Email Alerts (4★+)")
    gmail_user  = st.text_input("Gmail address",     placeholder="you@gmail.com")
    gmail_pass  = st.text_input("App password",      type="password", placeholder="xxxx xxxx xxxx xxxx")
    alert_email = st.text_input("Send alerts to",    placeholder="you@gmail.com")
    send_alerts = st.checkbox("Enable email alerts", value=False)

    if st.session_state.email_error:
        st.error(f"Email error: {st.session_state.email_error}")

    st.markdown("---")

    # ── Scan buttons ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🦙 Alpaca API (Real-Time)")
    with st.expander("Configure Alpaca Keys", expanded=False):
        ak = st.text_input("API Key ID",  type="password",
                           placeholder="PKXXXXXXXXXXXXXXXXXX", key="ak_input")
        sk = st.text_input("Secret Key",  type="password",
                           placeholder="XXXXXXXXXXXXXXXXXXXXXXXX", key="sk_input")
        ua = st.checkbox("Use Alpaca real-time data", value=False, key="ua_input")
        if st.button("Save Alpaca Keys", key="save_alpaca"):
            st.session_state.alpaca_key_val    = ak
            st.session_state.alpaca_secret_val = sk
            st.session_state.use_alpaca_val    = ua
            st.success("✅ Alpaca keys saved!")
        if st.session_state.use_alpaca_val and st.session_state.alpaca_key_val:
            st.success("✅ Real-time data active")
        elif st.session_state.use_alpaca_val:
            st.warning("⚠️ Enter keys above and save")
        else:
            st.caption("Using yfinance (15-min delayed)")

    st.markdown("---")
    scan_btn       = st.button("🔍 Scan Now (15-min)")
    daily_scan_btn = st.button("🌙 After-Hours Scan (1-hr)")
    pm_scan_btn    = st.button("🌅 Pre-Market / AH Scan")

    st.markdown(f"""
    <div style='margin-top:12px;font-size:0.7rem;color:#c0ccd8;line-height:1.9;'>
    <b style='color:#e0e8f0'>15-min signals</b><br>
    • VWAP Reclaim / Rejection<br>
    • Opening Range Breakout<br>
    • Double Bottom / Top<br>
    • EMA20 Reclaim / Rejection<br>
    • RSI Oversold / Overbought<br>
    • Volume Surge<br><br>
    <b style='color:#e0e8f0'>Last alert:</b> {st.session_state.last_alert}<br>
    <b style='color:#e0e8f0'>Watchlist:</b> {len(st.session_state.index_list)} indices · {len(st.session_state.stock_list)} stocks<br><br>
    <i style='color:#8090a0'>Pre-market: every 5 min · Market: every 15 min · After-hours: every 10 min</i><br><i style='color:#8090a0'>yfinance · 15-min delay · Not financial advice</i>
    </div>""", unsafe_allow_html=True)

# ── Config object ─────────────────────────────────────────────────────────────

# Alpaca keys — read from session state (initialized in DEFAULTS above)
alpaca_key    = st.session_state.alpaca_key_val
alpaca_secret = st.session_state.alpaca_secret_val
use_alpaca    = st.session_state.use_alpaca_val

cfg = ScannerConfig(
    index_tickers   = st.session_state.index_list,
    stock_tickers   = st.session_state.stock_list,
    vol_surge_ratio = vol_surge,
    rsi_oversold    = float(rsi_lo),
    rsi_overbought  = float(rsi_hi),
    gap_filter_pct  = gap_filt / 100,
    alpaca_key      = alpaca_key,
    alpaca_secret   = alpaca_secret,
)

# ── Header ────────────────────────────────────────────────────────────────────

st.markdown("""
<div style='padding:8px 0 12px 0;'>
  <h1 style='font-family:"Syne",sans-serif;font-size:2rem;font-weight:800;
             background:linear-gradient(90deg,#4af0c4,#4a9cf0);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             margin:0;letter-spacing:-0.02em;'>Options Flow Dashboard</h1>
  <p style='color:#3a5070;font-family:"JetBrains Mono",monospace;font-size:0.78rem;margin:4px 0 0 0;'>
    15-min intraday scanner · indices + stocks · calls & puts · auto-scan · email alerts
  </p>
</div>""", unsafe_allow_html=True)

# ── Market status bar ─────────────────────────────────────────────────────────

is_open, status_lbl, mins_open, mins_close = market_status()
now_et = datetime.now(ET).strftime("%H:%M ET")

colors = {"open":"#4af0c4","pre-market":"#f5c842","closed":"#f04a6a","weekend":"#f04a6a"}
icons  = {"open":"●","pre-market":"◐","closed":"●","weekend":"●"}
col    = colors.get(status_lbl,"#8090a0")
icon   = icons.get(status_lbl,"●")
extra  = (f" | Closes in {mins_close} min" if is_open else
          f" | Opens in {mins_open} min" if status_lbl=="pre-market" else "")
auto_badge = " | 🔄 Auto-scan ON" if auto_on else ""

st.markdown(f"""
<div class="status-bar">
  <span style="color:{col}">{icon} {status_lbl.upper()}</span>
  <span style="color:#3a5070"> | </span>
  <span style="color:#d4dce8">{now_et}</span>
  <span style="color:#3a5070">{extra}</span>
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
        secs = next_scan_secs(15)
        m, s = secs // 60, secs % 60
        last_lbl = st.session_state.scan_timestamp or "pending first scan"
        st.markdown(f"""
        <div class="countdown">
          ⚡ Market hours — auto-scan every 15 min
          &nbsp;·&nbsp; Next in <b>{m:02d}:{s:02d}</b>
          &nbsp;·&nbsp; Last: <b>{last_lbl}</b>
          &nbsp;·&nbsp; {len(st.session_state.index_list) + len(st.session_state.stock_list)} tickers
        </div>""", unsafe_allow_html=True)

# ── Run scan ──────────────────────────────────────────────────────────────────

def do_scan():
    scanner = IntradayScanner(cfg)
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
    with st.status("🌙 Running after-hours 1-hr scan...", expanded=True) as status:
        pb  = st.progress(0)
        stx = st.empty()
        def dcb(idx, total, ticker):
            pb.progress(idx / total)
            stx.markdown(f"`[{idx}/{total}]` → **{ticker}**")
        scanner  = HourlyScanner(cfg)
        df_daily = scanner.run(progress_cb=dcb)
        pb.empty(); stx.empty()
        st.session_state.daily_results   = df_daily
        st.session_state.daily_timestamp = datetime.now().strftime("%H:%M:%S")
        if send_alerts and gmail_user and gmail_pass and alert_email:
            sent = send_alert(df_daily, gmail_user, gmail_pass, alert_email)
            if sent:
                st.session_state.last_alert = datetime.now().strftime("%H:%M:%S")
        status.update(label="✅ 1-hr scan complete!", state="complete")

# Pre-market / AH scan trigger
if pm_scan_btn:
    with st.status("🌅 Scanning pre-market / after-hours data...", expanded=True) as status:
        pb  = st.progress(0)
        stx = st.empty()
        def pmcb(idx, total, ticker):
            pb.progress(idx / total)
            stx.markdown(f"`[{idx}/{total}]` → **{ticker}**")
        pm_scanner = PremarketScanner(cfg)
        df_pm      = pm_scanner.run(progress_cb=pmcb)
        pb.empty(); stx.empty()
        st.session_state.pm_results   = df_pm
        st.session_state.pm_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pm_session   = PremarketScanner.current_session()
        status.update(label="✅ Pre-market scan complete!", state="complete")

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
    st.rerun()

# After-hours auto-scan (every 10 min, 4PM-8PM ET)
if auto_on and _session_now == "AFTER-HOURS" and next_pm_scan_secs("AFTER-HOURS") == 0:
    with st.spinner("🌙 Auto-scanning after-hours..."):
        _pm_s  = PremarketScanner(cfg)
        _df_pm = _pm_s.run()
        st.session_state.pm_results   = _df_pm
        st.session_state.pm_timestamp = datetime.now().strftime("%H:%M:%S")
        st.session_state.pm_session   = "AFTER-HOURS"
        st.session_state.last_pm_scan = datetime.now()
    st.rerun()

# 15-min intraday auto-scan (market hours only)
if auto_on and is_open and next_scan_secs(15) == 0:
    with st.spinner("🔄 Auto-scanning..."):
        do_scan()
    st.rerun()

# ── Results tabs ─────────────────────────────────────────────────────────────

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["⚡ 15-min Intraday Scanner", "🌙 After-Hours 1-hr Scanner", "🌅 Pre-Market & After-Hours"])

# ════════════════════════════════════════════════
#  TAB 1 — 15-min Intraday
# ════════════════════════════════════════════════
with tab1:
    if st.session_state.scan_results is not None:
        df    = st.session_state.scan_results
        # Exclude 1★ and 2★ setups
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
            st.markdown("### 📊 Chart Explorer (15-min)")
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
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("🟡 VWAP · 🟢 EMA9 · 🟣 EMA20 · 🔴 SMA50")
                d      = row["Direction"]
                border = "#4af0c4" if d=="CALL" else "#f04a6a"
                st.markdown(f"""
                <div style='background:#0e1520;border-left:3px solid {border};border-radius:0 8px 8px 0;padding:16px 20px;margin-top:8px;'>
                  <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:0.85rem;'>
                    <div><span style='color:#5a7a90'>Signal:</span> <b>{row['Signal']}</b></div>
                    <div><span style='color:#5a7a90'>RSI:</span> <b>{row['RSI']}</b></div>
                    <div><span style='color:#5a7a90'>Volume:</span> <b>{row['Vol Ratio']}x</b></div>
                    <div><span style='color:#5a7a90'>VWAP:</span> <b>${row['VWAP']}</b></div>
                    <div><span style='color:#5a7a90'>Strike:</span> <b>${row['Strike']}</b></div>
                    <div><span style='color:#5a7a90'>Confidence:</span> <b>{row['Confidence']}</b></div>
                  </div>
                  <div style='margin-top:10px;padding-top:10px;border-top:1px solid #1a2535;font-size:0.82rem;color:#8090a0;'>{row['Notes']}</div>
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
        <div style='text-align:center;padding:60px 0;color:#2a3a50;'>
          <div style='font-size:3rem;'>⚡</div>
          <div style='font-family:"JetBrains Mono",monospace;font-size:0.95rem;margin-top:12px;color:#3a5070;'>
            Click <b style='color:#4af0c4'>Scan Now (15-min)</b> in the sidebar
          </div>
          <div style='font-size:0.78rem;margin-top:6px;'>Best between 9:45 AM – 3:45 PM ET</div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
#  TAB 2 — After-Hours Daily Scanner
# ════════════════════════════════════════════════
with tab2:
    st.markdown("""
    <div style='background:#0e1520;border:1px solid #1a2535;border-radius:8px;padding:14px 18px;margin-bottom:16px;font-family:"JetBrains Mono",monospace;font-size:0.78rem;color:#8090a0;'>
      🌙 <b style='color:#e0e8f0'>After-Hours 1-hr Scanner</b> — finds next-day setups on 1-hour candles.<br>
      Run after 4:00 PM ET or on weekends · looks back 5 days (~30-40 bars).<br>
      Signals: VWAP · EMA9/20 reclaims · Double Bottom/Top · SMA touches · RSI extremes · Inside bars · Volume
    </div>""", unsafe_allow_html=True)

    if st.session_state.daily_results is not None:
        df    = st.session_state.daily_results
        # Exclude 1★ and 2★ setups
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
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("🟢 EMA9 · 🟣 EMA20 · 🟡 SMA50 · 🟠 SMA100 · 🔴 SMA200 · 🟡 VWAP")
                d      = row["Direction"]
                border = "#4af0c4" if d=="CALL" else "#f04a6a"
                iv_color = "#f04a6a" if "High" in row.get("IV Note","") else (
                           "#4af0c4" if "Low"  in row.get("IV Note","") else "#f5c842")
                st.markdown(f"""
                <div style='background:#0e1520;border-left:3px solid {border};border-radius:0 8px 8px 0;padding:16px 20px;margin-top:8px;'>
                  <div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;font-size:0.85rem;margin-bottom:10px;'>
                    <div><span style='color:#5a7a90'>Signal:</span> <b>{row['Signal']}</b></div>
                    <div><span style='color:#5a7a90'>SMA Level:</span> <b>{row['SMA Level']}</b></div>
                    <div><span style='color:#5a7a90'>RSI:</span> <b>{row['RSI']}</b></div>
                    <div><span style='color:#5a7a90'>Volume:</span> <b>{row['Vol Ratio']}x avg</b></div>
                    <div><span style='color:#5a7a90'>ATR:</span> <b>${row['ATR']}</b></div>
                    <div><span style='color:#5a7a90'>VWAP:</span> <b>${row.get('VWAP','—')}</b></div>
                    <div><span style='color:#5a7a90'>Confidence:</span> <b>{row['Confidence']}</b></div>
                  </div>
                  <div style='padding-top:10px;border-top:1px solid #1a2535;font-size:0.82rem;color:{iv_color};'>{row.get('IV Note','')}</div>
                  <div style='margin-top:6px;font-size:0.78rem;color:#8090a0;'>{row['Notes']}</div>
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
        <div style='text-align:center;padding:60px 0;color:#2a3a50;'>
          <div style='font-size:3rem;'>🌙</div>
          <div style='font-family:"JetBrains Mono",monospace;font-size:0.95rem;margin-top:12px;color:#3a5070;'>
            Click <b style='color:#4af0c4'>After-Hours Scan (1-hr)</b> in the sidebar
          </div>
          <div style='font-size:0.78rem;margin-top:6px;'>
            1-hr candles · 5-day lookback · best for next-day trade planning
          </div>
        </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════
#  TAB 3 — Pre-Market & After-Hours Intelligence
# ════════════════════════════════════════════════
with tab3:
    session_now = PremarketScanner.current_session()

    # Session banner
    session_colors = {
        "PRE-MARKET":  ("#f5c842", "🌅 PRE-MARKET SESSION"),
        "AFTER-HOURS": ("#c087f8", "🌙 AFTER-HOURS SESSION"),
        "MARKET":      ("#4af0c4", "⚡ MARKET OPEN"),
        "WEEKEND":     ("#8090a0", "💤 WEEKEND"),
        "CLOSED":      ("#f04a6a", "● CLOSED"),
    }
    s_color, s_label = session_colors.get(session_now, ("#8090a0","● UNKNOWN"))

    st.markdown(f"""
    <div style='background:#0e1520;border:1px solid #1a2535;border-radius:8px;
                padding:12px 18px;margin-bottom:16px;font-family:"JetBrains Mono",monospace;'>
      <span style='color:{s_color};font-weight:700;'>{s_label}</span>
      <span style='color:#3a5070;margin:0 12px;'>|</span>
      <span style='color:#8090a0;font-size:0.8rem;'>
        Pre-market: 4:00–9:30 AM ET &nbsp;·&nbsp; After-hours: 4:00–8:00 PM ET
      </span>
    </div>""", unsafe_allow_html=True)

    # Info box
    st.markdown("""
    <div style='background:#0a1520;border:1px solid #1a2535;border-radius:8px;
                padding:14px 18px;margin-bottom:16px;font-family:"JetBrains Mono",monospace;font-size:0.78rem;color:#8090a0;'>
      🌅 <b style='color:#e0e8f0'>Pre-Market & After-Hours Intelligence</b><br>
      Identifies gap direction, key price levels, volume conviction, and opening bias (CALL/PUT/WAIT).<br>
      Uses Alpaca real-time if connected · yfinance fallback (15-min delayed) · Works any time of day.
    </div>""", unsafe_allow_html=True)

    if st.session_state.pm_results is not None:
        df_pm = st.session_state.pm_results

        if not df_pm.empty:
            # Filter by conviction
            calls_pm = df_pm[df_pm["Bias"]=="CALL"]
            puts_pm  = df_pm[df_pm["Bias"]=="PUT"]
            waits_pm = df_pm[df_pm["Bias"]=="WAIT"]

            st.caption(f"⏱ {st.session_state.pm_timestamp} · Session: {st.session_state.pm_session} · {len(df_pm)} tickers scanned")

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Scanned", len(df_pm))
            c2.metric("🟢 CALL Bias",  len(calls_pm))
            c3.metric("🔴 PUT Bias",   len(puts_pm))
            c4.metric("⏳ WAIT",       len(waits_pm))

            st.markdown("---")

            # High conviction only first
            high_conv = df_pm[df_pm["Conviction"]=="HIGH"]
            if not high_conv.empty:
                st.markdown("### 🔥 High Conviction Moves")
                for _, r in high_conv.iterrows():
                    gap    = float(r["Gap %"])
                    bias   = str(r["Bias"])
                    ticker = str(r["Ticker"])
                    gap_col= "#4af0c4" if gap > 0 else "#f04a6a"
                    bias_col= "#4af0c4" if bias=="CALL" else ("#f04a6a" if bias=="PUT" else "#f5c842")
                    bias_icon= "▲" if bias=="CALL" else ("▼" if bias=="PUT" else "⏳")
                    t_bg   = "#1a2a50" if r["Type"]=="INDEX" else "#2a1a40"
                    t_col  = "#6ab0f0" if r["Type"]=="INDEX" else "#c083f8"
                    st.markdown(f"""
                    <div style='border-left:4px solid {gap_col};background:#0e1520;padding:14px 18px;border-radius:0 8px 8px 0;margin:6px 0;'>
                      <div style='display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;'>
                        <span style='font-family:"JetBrains Mono",monospace;font-size:1.05rem;font-weight:700;color:#e0e8f0;'>{ticker}</span>
                        <span style='background:{t_bg};color:{t_col};font-size:0.65rem;padding:1px 8px;border-radius:8px;'>{r["Type"]}</span>
                        <span style='background:#1a3a50;color:{gap_col};font-family:"JetBrains Mono",monospace;font-size:0.8rem;font-weight:700;padding:2px 12px;border-radius:20px;'>
                          {"+" if gap>0 else ""}{gap:.2f}% {r["Direction"]}
                        </span>
                        <span style='background:{"#0d3d28" if bias=="CALL" else ("#3d0d1a" if bias=="PUT" else "#2a2a10")};color:{bias_col};font-size:0.72rem;font-weight:700;padding:2px 10px;border-radius:20px;'>
                          {bias_icon} {bias}
                        </span>
                        <span style='margin-left:auto;font-size:0.72rem;color:#f5c842;font-weight:700;'>🔥 {r["Conviction"]}</span>
                      </div>
                      <div style='display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;font-size:0.78rem;color:#8090a0;margin-bottom:6px;'>
                        <div>Prev Close: <b style='color:#d4dce8;'>${r["Prev Close"]}</b></div>
                        <div>Current: <b style='color:{gap_col};'>${r["Current"]}</b></div>
                        <div>PM High: <b style='color:#d4dce8;'>${r["PM High"]}</b></div>
                        <div>PM Low: <b style='color:#d4dce8;'>${r["PM Low"]}</b></div>
                      </div>
                      <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.78rem;color:#8090a0;margin-bottom:6px;'>
                        <div>Key Level: <b style='color:#f5c842;'>${r["Key Level"]}</b></div>
                        <div>PM Volume: <b style='color:#d4dce8;'>{r["Vol Ratio"]:.1f}x avg</b></div>
                      </div>
                      <div style='font-size:0.78rem;color:#a0b0c0;margin-top:4px;'>{r["Notes"]}</div>
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # Full table
            st.markdown("### 📋 All Tickers")
            display_cols = ["Ticker","Type","Gap %","Direction","Bias","Conviction","Confidence","PM High","PM Low","Key Level","Vol Ratio","Notes"]
            available = [c for c in display_cols if c in df_pm.columns]

            styled = df_pm[available].style.applymap(
                lambda v: "color:#4af0c4" if v=="CALL" else ("color:#f04a6a" if v=="PUT" else "color:#f5c842"),
                subset=["Bias"] if "Bias" in available else []
            ).format({"Gap %": "{:+.2f}%"} if "Gap %" in available else {})
            st.dataframe(styled, use_container_width=True)

            # Export
            st.markdown("---")
            st.markdown("### 📤 Export")
            ex1, ex2 = st.columns(2)
            with ex1:
                csv_pm = df_pm[available].to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv_pm,
                    file_name=f"premarket_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", key="csv_pm")
            with ex2:
                if st.button("📧 Email Pre-Market Report", key="email_pm"):
                    if gmail_user and gmail_pass and alert_email:
                        # Build simple HTML email for pre-market
                        pm_html = f"""<html><body style='background:#080b10;color:#d4dce8;font-family:monospace;'>
                        <div style='max-width:800px;margin:0 auto;padding:24px;'>
                        <h2 style='color:#f5c842;'>🌅 Pre-Market Intelligence — {st.session_state.pm_timestamp}</h2>
                        <p style='color:#5a7a90;'>Session: {st.session_state.pm_session} · {len(calls_pm)} CALL bias · {len(puts_pm)} PUT bias · {len(waits_pm)} WAIT</p>
                        <table style='width:100%;border-collapse:collapse;background:#0e1520;border:1px solid #1a2535;'>
                        <tr style='background:#131922;color:#5a7a90;font-size:0.75rem;'>
                          <th style='padding:8px;text-align:left;'>TICKER</th><th style='padding:8px;'>GAP%</th>
                          <th style='padding:8px;'>BIAS</th><th style='padding:8px;'>CONVICTION</th>
                          <th style='padding:8px;'>KEY LEVEL</th><th style='padding:8px;'>VOL</th>
                          <th style='padding:8px;text-align:left;'>NOTES</th></tr>"""
                        for _, r in df_pm.iterrows():
                            gap   = float(r["Gap %"])
                            gcol  = "#4af0c4" if gap > 0 else "#f04a6a"
                            bcol  = "#4af0c4" if r["Bias"]=="CALL" else ("#f04a6a" if r["Bias"]=="PUT" else "#f5c842")
                            pm_html += f"""<tr>
                              <td style='padding:8px;font-weight:bold;color:#e0e8f0;'>{r["Ticker"]}</td>
                              <td style='padding:8px;color:{gcol};text-align:center;'>{"+" if gap>0 else ""}{gap:.2f}%</td>
                              <td style='padding:8px;color:{bcol};text-align:center;font-weight:bold;'>{r["Bias"]}</td>
                              <td style='padding:8px;text-align:center;'>{r["Conviction"]}</td>
                              <td style='padding:8px;text-align:center;'>${r["Key Level"]}</td>
                              <td style='padding:8px;text-align:center;'>{r["Vol Ratio"]:.1f}x</td>
                              <td style='padding:8px;font-size:0.75rem;'>{r["Notes"]}</td></tr>"""
                        pm_html += """</table>
                        <p style='color:#2a3a50;font-size:0.7rem;margin-top:16px;'>Not financial advice · Educational use only</p>
                        </div></body></html>"""
                        sent = send_export_email(pm_html,
                            f"🌅 Pre-Market Report — {len(calls_pm)} CALL · {len(puts_pm)} PUT · {datetime.now(ET).strftime('%b %d %H:%M ET')}",
                            gmail_user, gmail_pass, alert_email)
                        if sent: st.success("✅ Email sent!")
                        else:    st.error("❌ Check Gmail settings")
                    else:
                        st.warning("⚠️ Enter Gmail details in sidebar")
        else:
            st.info("No pre-market data found. Try again after 4:00 AM ET or check your Alpaca connection.")
    else:
        st.markdown("""
        <div style='text-align:center;padding:60px 0;color:#2a3a50;'>
          <div style='font-size:3rem;'>🌅</div>
          <div style='font-family:"JetBrains Mono",monospace;font-size:0.95rem;margin-top:12px;color:#3a5070;'>
            Click <b style='color:#f5c842;'>Pre-Market / AH Scan</b> in the sidebar
          </div>
          <div style='font-size:0.78rem;margin-top:6px;'>
            Best times: 8:00–9:30 AM ET (pre-market) · 4:00–8:00 PM ET (after-hours)
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
