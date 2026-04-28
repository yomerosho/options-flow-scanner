"""
github_scanner.py
=================
Standalone scanner for GitHub Actions.
Reads Alpaca + Gmail credentials from environment variables.
Runs the appropriate scanner based on current session.
Emails results automatically.
"""

import os
import sys
import smtplib
import pytz
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Inject env vars into scanner config ───────────────────────────────────────
ALPACA_KEY    = os.environ.get("ALPACA_KEY",    "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")
GMAIL_USER    = os.environ.get("GMAIL_USER",    "")
GMAIL_PASS    = os.environ.get("GMAIL_PASS",    "")
GMAIL_TO      = os.environ.get("GMAIL_TO",      "")

from scanner import (
    IntradayScanner, HourlyScanner, PremarketScanner,
    ScannerConfig
)

ET = pytz.timezone("America/New_York")

def current_session():
    now = datetime.now(ET)
    h   = now.hour + now.minute / 60
    wd  = now.weekday()
    if wd >= 5:         return "WEEKEND"
    if 4.0  <= h < 9.5: return "PRE-MARKET"
    if 9.5  <= h < 16:  return "MARKET"
    if 16.0 <= h < 20:  return "AFTER-HOURS"
    return "CLOSED"

def build_email_html(results: dict, session: str, scan_time: str) -> str:
    """Build formatted HTML email from scan results."""

    def signal_rows(df, direction):
        if df is None or df.empty:
            return f'<p style="color:#5a7a90;font-family:monospace;">No {direction} setups.</p>'
        # Filter 4★+
        if "Confidence" in df.columns:
            df = df[df["Confidence"].str.len() >= 4]
        if df.empty:
            return f'<p style="color:#5a7a90;font-family:monospace;">No 4★+ {direction} setups.</p>'

        rows = ""
        for _, r in df.iterrows():
            col    = "#4af0c4" if direction == "CALL" else "#f04a6a"
            bg     = "#0a1f18" if direction == "CALL" else "#1f0a10"
            border = col
            icon   = "▲" if direction == "CALL" else "▼"
            is_conf = bool(r.get("Confluence", False))
            conf_tag = '<span style="background:#1a4a38;color:#4af0c4;font-size:0.7rem;padding:2px 8px;border-radius:10px;font-weight:700;margin-left:4px;">⚡ CONFLUENCE</span>' if is_conf else ""
            expiry  = str(r.get("Expiry",""))
            iv      = str(r.get("IV Note","") or r.get("Notes",""))
            iv_col  = "#f04a6a" if "High" in iv else ("#4af0c4" if "Low" in iv else "#f5c842")
            vwap    = str(r.get("VWAP","—"))
            sma     = str(r.get("SMA Level","—"))

            rows += f"""
            <div style="border-left:4px solid {border};background:{bg};
                        padding:12px 16px;border-radius:0 8px 8px 0;margin:6px 0;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;flex-wrap:wrap;">
                <span style="font-family:monospace;font-size:1rem;font-weight:700;color:#e0e8f0;">{r["Ticker"]}</span>
                <span style="background:{"#0d3d28" if direction=="CALL" else "#3d0d1a"};color:{col};
                             font-size:0.72rem;font-weight:700;padding:2px 10px;border-radius:20px;">{icon} {direction}</span>
                {conf_tag}
                <span style="color:#8090a0;font-size:0.82rem;">${r["Price"]}</span>
                <span style="margin-left:auto;">{r["Confidence"]}</span>
              </div>
              <div style="font-size:0.88rem;color:#c0d0e0;font-weight:600;margin-bottom:4px;">
                {r["Signal"]} → <span style="color:{col};">Strike ${r["Strike"]}</span>
                {"&nbsp;<span style='color:#8090a0;font-size:0.78rem;'>(" + expiry + ")</span>" if expiry else ""}
              </div>
              <div style="font-size:0.74rem;color:#5a7a90;">
                {"VWAP $" + vwap + " | " if vwap not in ["—",""] else ""}RSI {r["RSI"]} | Vol {r["Vol Ratio"]}x
              </div>
              <div style="font-size:0.72rem;color:{iv_col};margin-top:3px;">{iv}</div>
            </div>"""
        return rows

    # Build sections per scanner
    sections = ""
    scanner_icons = {
        "PRE-MARKET":  "🌅",
        "MARKET":      "⚡",
        "AFTER-HOURS": "🌙",
    }
    icon = scanner_icons.get(session, "📡")

    for scanner_name, df in results.items():
        if df is None or df.empty:
            continue
        calls = df[df["Direction"] == "CALL"] if "Direction" in df.columns else df
        puts  = df[df["Direction"] == "PUT"]  if "Direction" in df.columns else df

        total_4star = len(df[df["Confidence"].str.len() >= 4]) if "Confidence" in df.columns else 0
        if total_4star == 0:
            continue

        sections += f"""
        <div style="margin-bottom:24px;">
          <h3 style="color:#4af0c4;font-family:monospace;font-size:1rem;
                     border-bottom:1px solid #1a2535;padding-bottom:8px;">
            {icon} {scanner_name}
          </h3>
          <table width="100%" cellspacing="0" cellpadding="0"><tr valign="top">
            <td width="50%" style="padding-right:8px;">
              <div style="color:#4af0c4;font-weight:700;margin-bottom:8px;">🟢 CALLS</div>
              {signal_rows(calls, "CALL")}
            </td>
            <td width="50%" style="padding-left:8px;">
              <div style="color:#f04a6a;font-weight:700;margin-bottom:8px;">🔴 PUTS</div>
              {signal_rows(puts, "PUT")}
            </td>
          </tr></table>
        </div>"""

    if not sections:
        sections = '<p style="color:#5a7a90;font-family:monospace;">No 4★+ setups found this scan.</p>'

    return f"""<!DOCTYPE html><html>
    <body style="background:#080b10;color:#d4dce8;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:0;">
    <div style="max-width:900px;margin:0 auto;padding:24px;">
      <div style="border-bottom:1px solid #1a2535;padding-bottom:16px;margin-bottom:20px;">
        <h1 style="margin:0;font-size:1.5rem;font-weight:800;color:#4af0c4;">
          {icon} Options Flow — {session}
        </h1>
        <p style="color:#5a7a90;font-family:monospace;font-size:0.8rem;margin:6px 0 0 0;">
          Auto-scan · {scan_time} · 4★+ setups only · GitHub Actions
        </p>
      </div>
      {sections}
      <div style="border-top:1px solid #1a2535;margin-top:20px;padding-top:12px;
                  font-size:0.68rem;color:#2a3a50;text-align:center;">
        Options Flow Dashboard · Auto-generated · Not financial advice
      </div>
    </div></body></html>"""


def load_subscribers() -> list:
    """Load subscriber list from subscribers.txt"""
    subscribers = []
    try:
        with open("subscribers.txt", "r") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",", 1)
                email = parts[0].strip()
                name  = parts[1].strip() if len(parts) > 1 else email.split("@")[0]
                if "@" in email:
                    subscribers.append({"email": email, "name": name})
    except FileNotFoundError:
        print("⚠️ subscribers.txt not found — using GMAIL_TO only")
        if GMAIL_TO:
            subscribers.append({"email": GMAIL_TO, "name": "Trader"})
    return subscribers


def build_personalized_html(html_template: str, name: str) -> str:
    """Add personal greeting to email."""
    greeting = (
        "<div style='background:#0a1f18;border-left:3px solid #4af0c4;"
        "padding:10px 16px;margin-bottom:16px;font-family:monospace;"
        "font-size:0.85rem;color:#4af0c4;border-radius:0 6px 6px 0;'>"
        f"Hey {name}! Here are your options flow alerts 👋"
        "</div>"
    )
    anchor = '<div style="max-width:900px;margin:0 auto;padding:24px;">'
    return html_template.replace(anchor, anchor + greeting, 1)


def send_email(html: str, subject: str):
    if not all([GMAIL_USER, GMAIL_PASS]):
        print("⚠️ Gmail credentials missing — skipping email")
        return

    subscribers = load_subscribers()
    if not subscribers:
        print("⚠️ No subscribers found")
        return

    print(f"📧 Sending to {len(subscribers)} subscriber(s)...")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        for sub in subscribers:
            try:
                personalized = build_personalized_html(html, sub["name"])
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"]    = GMAIL_USER
                msg["To"]      = sub["email"]
                msg.attach(MIMEText(personalized, "html"))
                s.sendmail(GMAIL_USER, sub["email"], msg.as_string())
                print(f"  ✅ Sent to {sub['name']} <{sub['email']}>")
            except Exception as e:
                print(f"  ❌ Failed for {sub['email']}: {e}")


def main():
    session   = current_session()
    scan_time = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

    print(f"\n{'='*60}")
    print(f"  OPTIONS FLOW AUTO-SCANNER")
    print(f"  Session: {session} | {scan_time}")
    print(f"{'='*60}\n")

    if session in ("CLOSED", "WEEKEND"):
        print(f"Market is {session} — skipping scan")
        sys.exit(0)

    cfg = ScannerConfig(
        alpaca_key    = ALPACA_KEY,
        alpaca_secret = ALPACA_SECRET,
    )

    results   = {}
    all_found = 0

    # ── Run appropriate scanners based on session ──────────────────────────────

    if session == "PRE-MARKET":
        print("🌅 Running Pre-Market scanner...")
        pm  = PremarketScanner(cfg)
        df  = pm.run()
        results["Pre-Market Intelligence"] = df
        if not df.empty:
            all_found += len(df)
            print(f"   Found {len(df)} tickers with moves")

    elif session == "MARKET":
        print("⚡ Running 15-min Intraday scanner...")
        intra = IntradayScanner(cfg)
        df    = intra.run()
        results["15-min Intraday"] = df
        if not df.empty:
            strong = df[df["Confidence"].str.len() >= 4]
            all_found += len(strong)
            print(f"   Found {len(df)} signals ({len(strong)} are 4★+)")

    elif session == "AFTER-HOURS":
        print("🌙 Running After-Hours 1-hr scanner...")
        hourly = HourlyScanner(cfg)
        df     = hourly.run()
        results["After-Hours 1-hr"] = df
        if not df.empty:
            strong = df[df["Confidence"].str.len() >= 4]
            all_found += len(strong)
            print(f"   Found {len(df)} setups ({len(strong)} are 4★+)")

    # ── Email results ──────────────────────────────────────────────────────────

    if all_found == 0:
        print("\nNo 4★+ setups found — skipping email")
        sys.exit(0)

    html    = build_email_html(results, session, scan_time)
    icons   = {"PRE-MARKET": "🌅", "MARKET": "⚡", "AFTER-HOURS": "🌙"}
    icon    = icons.get(session, "📡")
    subject = f"{icon} Options Flow — {session} · {all_found} setup(s) · {datetime.now(ET).strftime('%b %d %H:%M ET')}"

    send_email(html, subject)
    print(f"\n✅ Scan complete — {all_found} high-confidence setup(s) found")


if __name__ == "__main__":
    main()
