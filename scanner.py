"""
Options Flow Scanner — Intraday Engine (15-min candles)
========================================================
Signals: VWAP, ORB, Double Bottom/Top, EMA Reclaim, RSI Reset, Volume Surge
CONFLUENCE DETECTOR: 2+ signals on same bar = 5★ priority alert
"""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import logging
import time
from datetime import datetime
import pytz

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Strike snapper ────────────────────────────────────────────────────────────

def snap_strike(price: float, direction: str) -> float:
    if price < 25:     interval = 0.50
    elif price < 200:  interval = 2.50
    elif price < 500:  interval = 5.0
    else:              interval = 10.0
    if direction == "CALL":
        return round(np.ceil(price  / interval) * interval, 2)
    else:
        return round(np.floor(price / interval) * interval, 2)


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class ScannerConfig:
    index_tickers:      list  = None
    stock_tickers:      list  = None
    min_price:          float = 20.0
    min_avg_volume:     int   = 1_000_000
    vwap_buffer_pct:    float = 0.003
    rsi_oversold:       float = 30.0
    rsi_overbought:     float = 70.0
    orb_bars:           int   = 2        # 2 × 15-min = 30-min ORB
    dbl_bottom_pct:     float = 0.006    # lows within 0.6%
    vol_surge_ratio:    float = 2.0
    gap_filter_pct:     float = 0.04
    confluence_min:     int   = 2        # signals needed for confluence alert
    rate_limit_sleep:   float = 0.2
    alpaca_key:         str   = ""
    alpaca_secret:      str   = ""

    def __post_init__(self):
        if self.index_tickers is None:
            self.index_tickers = ["SPY","QQQ","IWM","DIA","TQQQ","SQQQ","XLF","EEM"]
        if self.stock_tickers is None:
            self.stock_tickers = [
                # Mega-cap tech
                "AAPL","AMZN","GOOGL","NVDA","TSLA","AMD","ARM","INTC","ORCL",
                # High-vol momentum
                "COIN","HOOD","PLTR","PYPL","NFLX","SOFI","RKLB","IONQ","IREN",
                # China / ADRs
                "BABA","JD",
                # Finance / Insurance / Misc
                "UNH","LMND","HIMS","PINS","OKLO","RBLX","RDDT",
                # Consumer / Retail
                "WMT","OXY",
                # Leveraged ETF
                "TSLL",
                # Sector ETFs
                "XLF","XLK","XLE","SOXX",
                # Additional
                "V","XOM",
                # Leveraged / Inverse ETFs
                "TQQQ","SQQQ",
                # International
                "EEM",
            ]


# ── Signal result ─────────────────────────────────────────────────────────────

@dataclass
class Signal:
    ticker:            str
    ticker_type:       str       # "index" | "stock"
    direction:         str       # CALL | PUT
    price:             float
    signal_type:       str       # primary signal name
    confluence:        bool      # True if 2+ signals stacked
    stacked_signals:   List[str] # all signals that fired
    confidence:        int       # 1-5
    suggested_strike:  float
    vwap:              float
    rsi:               float
    volume_ratio:      float
    body_above_ema9:   bool      # key candle quality filter
    notes:             str
    timestamp:         str


# ── Indicators ────────────────────────────────────────────────────────────────

class Indicators:
    @staticmethod
    def sma(s, n):   return s.rolling(n).mean()
    @staticmethod
    def ema(s, n):   return s.ewm(span=n, adjust=False).mean()
    @staticmethod
    def rsi(s, n=14):
        d = s.diff()
        g = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
        return 100 - (100 / (1 + g / l.replace(0, np.nan)))
    @staticmethod
    def vwap(h, l, c, v):
        tp = (h + l + c) / 3
        return (tp * v).cumsum() / v.cumsum()
    @staticmethod
    def atr(h, l, c, n=14):
        prev = c.shift(1)
        tr   = pd.concat([h-l,(h-prev).abs(),(l-prev).abs()],axis=1).max(axis=1)
        return tr.ewm(alpha=1/n, adjust=False).mean()
    @staticmethod
    def vol_ratio(v, n=20): return v / v.rolling(n).mean()


# ── Scanner ───────────────────────────────────────────────────────────────────

class IntradayScanner:

    def __init__(self, cfg: ScannerConfig = None):
        self.cfg = cfg or ScannerConfig()
        self.ind = Indicators()

    # ── fetch ─────────────────────────────────────────────────────────────────

    def _fetch_alpaca(self, ticker: str) -> Optional[pd.DataFrame]:
        """Real-time 15-min bars via Alpaca Markets API."""
        try:
            import requests
            from datetime import datetime, timedelta
            import pytz

            ET      = pytz.timezone("America/New_York")
            now     = datetime.now(ET)
            start   = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
            end     = now.strftime("%Y-%m-%dT%H:%M:%SZ")

            url     = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
            headers = {
                "APCA-API-KEY-ID":     self.cfg.alpaca_key,
                "APCA-API-SECRET-KEY": self.cfg.alpaca_secret,
            }
            params  = {
                "timeframe": "15Min",
                "start":     start,
                "end":       end,
                "limit":     100,
                "feed":      "iex",   # free real-time feed
            }

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                logger.debug(f"{ticker}: Alpaca {resp.status_code} — {resp.text[:100]}")
                return None

            bars = resp.json().get("bars", [])
            if not bars:
                return None

            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"], utc=True)
            df = df.set_index("t")
            df.index = df.index.tz_convert("America/New_York")
            df = df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"})

            # Keep today only
            today = df.index.date[-1]
            df    = df[df.index.date == today]
            return df if len(df) >= 8 else None

        except Exception as e:
            logger.debug(f"{ticker}: Alpaca fetch error — {e}")
            return None

    def _fetch_yfinance(self, ticker: str) -> Optional[pd.DataFrame]:
        """15-min bars via yfinance (15-min delayed fallback)."""
        try:
            t  = yf.Ticker(ticker)
            df = t.history(period="5d", interval="15m", auto_adjust=True)
            if df.empty or len(df) < 15:
                return None
            today = df.index.tz_convert("America/New_York").date[-1]
            df    = df[df.index.tz_convert("America/New_York").date == today]
            return df if len(df) >= 8 else None
        except Exception as e:
            logger.debug(f"{ticker}: yfinance error — {e}")
            return None

    def _fetch(self, ticker: str) -> Optional[pd.DataFrame]:
        """Use Alpaca if keys provided, else fallback to yfinance."""
        if self.cfg.alpaca_key and self.cfg.alpaca_secret:
            df = self._fetch_alpaca(ticker)
            if df is not None:
                return df
            logger.debug(f"{ticker}: Alpaca failed, falling back to yfinance")
        return self._fetch_yfinance(ticker)

    # ── compute ───────────────────────────────────────────────────────────────

    def _compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c, h, l, o, v = df["Close"], df["High"], df["Low"], df["Open"], df["Volume"]

        df["vwap"]   = self.ind.vwap(h, l, c, v)
        df["rsi"]    = self.ind.rsi(c, 14)
        df["ema9"]   = self.ind.ema(c, 9)
        df["ema20"]  = self.ind.ema(c, 20)
        df["sma50"]  = self.ind.sma(c, 50)
        df["vol_r"]  = self.ind.vol_ratio(v, 20)
        df["atr"]    = self.ind.atr(h, l, c, 14)
        df["body"]   = (c - o).abs()
        df["lo_wick"]= pd.concat([o,c],axis=1).min(axis=1) - l
        df["hi_wick"]= h - pd.concat([o,c],axis=1).max(axis=1)
        df["cl_pct"] = (c - l) / (h - l).replace(0, np.nan)

        # Candle body position relative to EMAs
        # Body close above EMA9: candle CLOSE AND OPEN both above ema9, or close > ema9 and body is bullish
        df["body_above_ema9"]  = (c > df["ema9"]) & (c > o)   # green candle closing above EMA9
        df["body_below_ema9"]  = (c < df["ema9"]) & (c < o)   # red candle closing below EMA9
        df["body_above_ema20"] = (c > df["ema20"]) & (c > o)
        df["body_below_ema20"] = (c < df["ema20"]) & (c < o)

        return df

    # ── gap filter ────────────────────────────────────────────────────────────

    def _today_gapped(self, df: pd.DataFrame) -> bool:
        if len(df) < 4: return False
        ema_early = float(df["ema9"].iloc[3]) if not np.isnan(df["ema9"].iloc[3]) else float(df["Open"].iloc[0])
        first_open= float(df["Open"].iloc[0])
        gap_pct   = abs(first_open - ema_early) / ema_early if ema_early > 0 else 0
        return gap_pct > self.cfg.gap_filter_pct

    # ── individual signal checkers ────────────────────────────────────────────

    def _check_vwap_reclaim(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """Price crossed above VWAP with volume confirmation."""
        was_below = float(prev["Close"]) < float(prev["vwap"])
        now_above = float(last["Close"]) > float(last["vwap"])
        vol_ok    = float(last["vol_r"]) > 1.3 if not np.isnan(last["vol_r"]) else False
        if was_below and now_above and vol_ok:
            return ("CALL", f"VWAP Reclaim ${last['vwap']:.2f}")
        return None

    def _check_vwap_rejection(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """Price crossed below VWAP with volume confirmation."""
        was_above = float(prev["Close"]) > float(prev["vwap"])
        now_below = float(last["Close"]) < float(last["vwap"])
        vol_ok    = float(last["vol_r"]) > 1.3 if not np.isnan(last["vol_r"]) else False
        if was_above and now_below and vol_ok:
            return ("PUT", f"VWAP Rejection ${last['vwap']:.2f}")
        return None

    def _check_ema9_body_reclaim(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """
        TSLA-style signal: candle BODY closes above EMA9 (not just a wick pierce).
        Previous candle must have been below EMA9.
        """
        prev_body_below = float(prev["Close"]) < float(prev["ema9"])
        now_body_above  = bool(last["body_above_ema9"])
        if prev_body_below and now_body_above:
            return ("CALL", f"EMA9 Body Reclaim ${last['ema9']:.2f}")
        return None

    def _check_ema9_body_rejection(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """Candle BODY closes below EMA9 — bearish."""
        prev_body_above = float(prev["Close"]) > float(prev["ema9"])
        now_body_below  = bool(last["body_below_ema9"])
        if prev_body_above and now_body_below:
            return ("PUT", f"EMA9 Body Rejection ${last['ema9']:.2f}")
        return None

    def _check_ema20_reclaim(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """Body close above EMA20 — stronger trend reclaim."""
        was_below = float(prev["Close"]) < float(prev["ema20"])
        now_above = bool(last["body_above_ema20"])
        above_vwap= float(last["Close"]) > float(last["vwap"])
        if was_below and now_above and above_vwap:
            return ("CALL", f"EMA20 Body Reclaim ${last['ema20']:.2f}")
        return None

    def _check_ema20_rejection(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """Body close below EMA20 — bearish trend rejection."""
        was_above = float(prev["Close"]) > float(prev["ema20"])
        now_below = bool(last["body_below_ema20"])
        below_vwap= float(last["Close"]) < float(last["vwap"])
        if was_above and now_below and below_vwap:
            return ("PUT", f"EMA20 Body Rejection ${last['ema20']:.2f}")
        return None

    def _check_double_bottom(self, df, last) -> Optional[Tuple[str,str]]:
        """Two lows within dbl_bottom_pct%, followed by a bounce above EMA9."""
        if len(df) < 10: return None
        lows       = df["Low"].values
        recent     = lows[-8:]
        first_low  = np.min(recent[:4])
        second_low = np.min(recent[4:])
        pct_diff   = abs(first_low - second_low) / first_low if first_low > 0 else 1
        bouncing   = float(last["Close"]) > float(df["Close"].iloc[-3])
        above_ema9 = float(last["Close"]) > float(last["ema9"])
        if pct_diff < self.cfg.dbl_bottom_pct and bouncing and above_ema9:
            return ("CALL", f"Double Bottom ~${min(first_low, second_low):.2f}")
        return None

    def _check_double_top(self, df, last) -> Optional[Tuple[str,str]]:
        """Two highs within dbl_bottom_pct%, followed by a drop below EMA9."""
        if len(df) < 10: return None
        highs       = df["High"].values
        recent      = highs[-8:]
        first_high  = np.max(recent[:4])
        second_high = np.max(recent[4:])
        pct_diff    = abs(first_high - second_high) / first_high if first_high > 0 else 1
        dropping    = float(last["Close"]) < float(df["Close"].iloc[-3])
        below_ema9  = float(last["Close"]) < float(last["ema9"])
        if pct_diff < self.cfg.dbl_bottom_pct and dropping and below_ema9:
            return ("PUT", f"Double Top ~${max(first_high, second_high):.2f}")
        return None

    def _check_orb(self, df, last) -> Optional[Tuple[str,str]]:
        """Opening range breakout/breakdown."""
        if len(df) <= self.cfg.orb_bars: return None
        orb    = df.iloc[:self.cfg.orb_bars]
        or_hi  = float(orb["High"].max())
        or_lo  = float(orb["Low"].min())
        price  = float(last["Close"])
        vol_ok = float(last["vol_r"]) > 1.5 if not np.isnan(last["vol_r"]) else False
        if price > or_hi * 1.001 and vol_ok and price > float(last["vwap"]):
            return ("CALL", f"ORB Breakout ${or_hi:.2f}")
        if price < or_lo * 0.999 and vol_ok and price < float(last["vwap"]):
            return ("PUT", f"ORB Breakdown ${or_lo:.2f}")
        return None

    def _check_rsi(self, df, last, prev) -> Optional[Tuple[str,str]]:
        """RSI extreme reset."""
        rsi      = float(last["rsi"])  if not np.isnan(last["rsi"])  else 50
        prev_rsi = float(prev["rsi"])  if not np.isnan(prev["rsi"])  else 50
        cl_pct   = float(last["cl_pct"]) if not np.isnan(last["cl_pct"]) else 0.5
        vol_ok   = float(last["vol_r"]) > 1.2 if not np.isnan(last["vol_r"]) else False
        if rsi < self.cfg.rsi_oversold and rsi > prev_rsi and cl_pct > 0.5 and vol_ok:
            return ("CALL", f"RSI Oversold Reset {rsi:.1f}")
        bearish_trend = float(last["Close"]) < float(last["ema20"])
        if rsi > self.cfg.rsi_overbought and rsi < prev_rsi and cl_pct < 0.5 and vol_ok and bearish_trend:
            return ("PUT", f"RSI Overbought Reset {rsi:.1f}")
        return None

    def _check_vol_surge(self, df, last) -> Optional[Tuple[str,str]]:
        """Abnormal volume with clear directional close."""
        vol_r  = float(last["vol_r"])  if not np.isnan(last["vol_r"])  else 1.0
        cl_pct = float(last["cl_pct"]) if not np.isnan(last["cl_pct"]) else 0.5
        price  = float(last["Close"])
        vwap   = float(last["vwap"])
        if vol_r > self.cfg.vol_surge_ratio * 1.5:
            if cl_pct > 0.65 and price > vwap:
                return ("CALL", f"Volume Surge {vol_r:.1f}x")
            if cl_pct < 0.35 and price < vwap:
                return ("PUT", f"Volume Surge {vol_r:.1f}x")
        return None

    # ── confluence detector ───────────────────────────────────────────────────

    def _detect(self, ticker: str, df: pd.DataFrame, ticker_type: str) -> Optional[Signal]:
        cfg  = self.cfg
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        price = float(last["Close"])
        vwap  = float(last["vwap"])
        rsi   = float(last["rsi"])  if not np.isnan(last["rsi"])  else 50.0
        vol_r = float(last["vol_r"]) if not np.isnan(last["vol_r"]) else 1.0
        body_above_ema9 = bool(last["body_above_ema9"])

        # Run all individual signal checks
        checkers = [
            self._check_vwap_reclaim(df, last, prev),
            self._check_vwap_rejection(df, last, prev),
            self._check_ema9_body_reclaim(df, last, prev),
            self._check_ema9_body_rejection(df, last, prev),
            self._check_ema20_reclaim(df, last, prev),
            self._check_ema20_rejection(df, last, prev),
            self._check_double_bottom(df, last),
            self._check_double_top(df, last),
            self._check_orb(df, last),
            self._check_rsi(df, last, prev),
            self._check_vol_surge(df, last),
        ]

        fired = [s for s in checkers if s is not None]
        if not fired:
            return None

        # Separate by direction
        calls = [s for s in fired if s[0] == "CALL"]
        puts  = [s for s in fired if s[0] == "PUT"]

        # Pick dominant direction (most signals)
        if len(calls) >= len(puts):
            direction  = "CALL"
            group      = calls
        else:
            direction  = "PUT"
            group      = puts

        if not group:
            return None

        stacked       = [s[1] for s in group]
        is_confluence = len(group) >= cfg.confluence_min
        n_signals     = len(group)

        # ── Confidence scoring ────────────────────────────────────────────────
        # Base: number of stacked signals (max 3 base points)
        base_conf = min(3, n_signals)

        # Bonus: body close confirms direction (key TSLA filter)
        body_bonus = 0
        if direction == "CALL" and body_above_ema9:
            body_bonus = 1
        elif direction == "PUT" and bool(last["body_below_ema9"]):
            body_bonus = 1

        # Bonus: VWAP alignment
        vwap_bonus = 0
        if direction == "CALL" and price > vwap:
            vwap_bonus = 1
        elif direction == "PUT" and price < vwap:
            vwap_bonus = 1

        confidence = min(5, base_conf + body_bonus + vwap_bonus)

        # Confluence gets minimum 4 stars if body + VWAP confirm
        if is_confluence and body_bonus and vwap_bonus:
            confidence = max(confidence, 4)

        # ── Primary signal label ──────────────────────────────────────────────
        # Priority order for label: Confluence > Double > EMA9 > VWAP > ORB > RSI > Vol
        priority = ["Double Bottom","Double Top","EMA9 Body","EMA20 Body","VWAP","ORB","RSI","Volume"]
        primary  = stacked[0]
        for p in priority:
            match = [s for s in stacked if p in s]
            if match:
                primary = match[0]
                break

        if is_confluence:
            sig_type = f"⚡ Confluence ({n_signals} signals)"
            notes    = " + ".join(stacked)
        else:
            sig_type = primary
            notes    = stacked[0]

        return Signal(
            ticker           = ticker,
            ticker_type      = ticker_type,
            direction        = direction,
            price            = round(price, 2),
            signal_type      = sig_type,
            confluence       = is_confluence,
            stacked_signals  = stacked,
            confidence       = confidence,
            suggested_strike = snap_strike(price, direction),
            vwap             = round(vwap, 2),
            rsi              = round(rsi, 1),
            volume_ratio     = round(vol_r, 2),
            body_above_ema9  = body_above_ema9,
            notes            = notes,
            timestamp        = str(df.index[-1]),
        )

    # ── public run ────────────────────────────────────────────────────────────

    def run(self, progress_cb=None) -> pd.DataFrame:
        cfg     = self.cfg
        all_t   = ([(t,"index") for t in cfg.index_tickers] +
                   [(t,"stock") for t in cfg.stock_tickers])
        results = []
        total   = len(all_t)

        for idx, (ticker, ttype) in enumerate(all_t, 1):
            if progress_cb:
                progress_cb(idx, total, ticker)

            df = self._fetch(ticker)
            time.sleep(cfg.rate_limit_sleep)

            if df is None or df.empty:
                continue

            df = self._compute(df)

            if self._today_gapped(df):
                logger.debug(f"{ticker}: skipped — gap filter")
                continue

            sig = self._detect(ticker, df, ttype)
            if sig:
                results.append(sig)
                flag = "⚡ CONFLUENCE" if sig.confluence else "✅"
                logger.info(f"{flag} {ticker} [{ttype}] {sig.direction} {sig.confidence}★ — {sig.signal_type}")

        return self._to_df(results)

    # ── dataframe output ──────────────────────────────────────────────────────

    @staticmethod
    def _to_df(results: list) -> pd.DataFrame:
        if not results:
            return pd.DataFrame()

        rows = [{
            "Ticker":      r.ticker,
            "Type":        r.ticker_type.upper(),
            "Direction":   r.direction,
            "Price":       r.price,
            "Signal":      r.signal_type,
            "Confluence":  r.confluence,
            "Signals":     " · ".join(r.stacked_signals),
            "Confidence":  "⭐" * r.confidence,
            "Strike":      r.suggested_strike,
            "VWAP":        r.vwap,
            "RSI":         r.rsi,
            "Vol Ratio":   r.volume_ratio,
            "Body✓EMA9":  "✅" if r.body_above_ema9 and r.direction=="CALL" else (
                           "✅" if not r.body_above_ema9 and r.direction=="PUT" else "—"),
            "Notes":       r.notes,
            "Time":        r.timestamp,
        } for r in results]

        df = pd.DataFrame(rows)
        # Sort: confluence first, then by confidence desc
        df["_conf"]   = df["Confidence"].str.len()
        df["_cfluence"] = df["Confluence"].astype(int)
        df.sort_values(["_cfluence","_conf"], ascending=[False,False], inplace=True)
        df.drop(columns=["_conf","_cfluence"], inplace=True)
        return df.reset_index(drop=True)



# ═══════════════════════════════════════════════════════════════════════════════
#  HOURLY SCANNER — After-hours / next-day setup finder (1-hr candles)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HourlySignal:
    ticker:           str
    ticker_type:      str
    direction:        str
    price:            float
    signal_type:      str
    confluence:       bool
    stacked_signals:  list
    confidence:       int
    suggested_strike: float
    suggested_expiry: str
    sma_level:        str
    rsi:              float
    volume_ratio:     float
    vwap:             float
    atr:              float
    iv_note:          str
    candle_date:      str
    notes:            str


class HourlyScanner:
    """
    After-hours / weekend scanner on 1-hour candles.
    Looks back 5 days (~30-40 bars) for high-quality next-day setups.
    Signals: VWAP, EMA reclaims, Double Bottom/Top, SMA touches,
             RSI extremes, Inside bars, Volume accumulation.
    """

    def __init__(self, cfg: ScannerConfig = None):
        self.cfg = cfg or ScannerConfig()
        self.ind = Indicators()

    # ── fetch ─────────────────────────────────────────────────────────────────

    def _fetch(self, ticker: str):
        try:
            t    = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1h", auto_adjust=True)
            info = t.info
            if hist.empty or len(hist) < 10:
                return None, None
            return info, hist
        except Exception as e:
            logger.debug(f"{ticker} hourly: {e}")
            return None, None

    # ── compute ───────────────────────────────────────────────────────────────

    def _compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        c, h, l, o, v = df["Close"], df["High"], df["Low"], df["Open"], df["Volume"]

        # EMAs & SMAs
        df["ema9"]   = self.ind.ema(c, 9)
        df["ema20"]  = self.ind.ema(c, 20)
        df["sma50"]  = self.ind.sma(c, 50)
        df["sma100"] = self.ind.sma(c, 100)
        df["sma200"] = self.ind.sma(c, 200)

        # VWAP — reset each day
        df["date"]   = df.index.tz_convert("America/New_York").date
        df["vwap"]   = np.nan
        for date, grp in df.groupby("date"):
            tp   = (grp["High"] + grp["Low"] + grp["Close"]) / 3
            vwap = (tp * grp["Volume"]).cumsum() / grp["Volume"].cumsum()
            df.loc[grp.index, "vwap"] = vwap

        df["rsi"]      = self.ind.rsi(c, 14)
        df["atr"]      = self.ind.atr(h, l, c, 14)
        df["vol_r"]    = self.ind.vol_ratio(v, 20)
        df["body"]     = (c - o).abs()
        df["lo_wick"]  = pd.concat([o,c],axis=1).min(axis=1) - l
        df["hi_wick"]  = h - pd.concat([o,c],axis=1).max(axis=1)
        df["cl_pct"]   = (c - l) / (h - l).replace(0, np.nan)

        # Body close confirmations
        df["body_above_ema9"]  = (c > df["ema9"])  & (c > o)
        df["body_below_ema9"]  = (c < df["ema9"])  & (c < o)
        df["body_above_ema20"] = (c > df["ema20"]) & (c > o)
        df["body_below_ema20"] = (c < df["ema20"]) & (c < o)

        # Inside bar
        df["inside_bar"] = (h < h.shift(1)) & (l > l.shift(1))

        # Gap detection (>3% open vs prior close)
        df["gap_pct"]    = (o - c.shift(1)) / c.shift(1)
        df["recent_gap"] = df["gap_pct"].abs().rolling(2).max() > 0.06  # only block same-day massive gaps

        return df.dropna(subset=["ema20", "rsi"])

    # ── individual signal checkers ────────────────────────────────────────────

    def _check_vwap_reclaim(self, last, prev) -> Optional[tuple]:
        was_below = float(prev["Close"]) < float(prev["vwap"])
        now_above = float(last["Close"]) > float(last["vwap"])
        vol_ok    = float(last["vol_r"]) > 1.2 if not np.isnan(last["vol_r"]) else False
        if was_below and now_above and vol_ok:
            return ("CALL", f"VWAP Reclaim ${last['vwap']:.2f}")
        return None

    def _check_vwap_rejection(self, last, prev) -> Optional[tuple]:
        was_above = float(prev["Close"]) > float(prev["vwap"])
        now_below = float(last["Close"]) < float(last["vwap"])
        vol_ok    = float(last["vol_r"]) > 1.2 if not np.isnan(last["vol_r"]) else False
        if was_above and now_below and vol_ok:
            return ("PUT", f"VWAP Rejection ${last['vwap']:.2f}")
        return None

    def _check_ema9_reclaim(self, last, prev) -> Optional[tuple]:
        """Candle BODY closes above EMA9 — TSLA-style signal."""
        was_below = float(prev["Close"]) < float(prev["ema9"])
        now_above = bool(last["body_above_ema9"])
        above_vwap= float(last["Close"]) > float(last["vwap"])
        if was_below and now_above and above_vwap:
            return ("CALL", f"EMA9 Body Reclaim ${last['ema9']:.2f}")
        return None

    def _check_ema9_rejection(self, last, prev) -> Optional[tuple]:
        was_above = float(prev["Close"]) > float(prev["ema9"])
        now_below = bool(last["body_below_ema9"])
        below_vwap= float(last["Close"]) < float(last["vwap"])
        if was_above and now_below and below_vwap:
            return ("PUT", f"EMA9 Body Rejection ${last['ema9']:.2f}")
        return None

    def _check_ema20_reclaim(self, last, prev) -> Optional[tuple]:
        was_below = float(prev["Close"]) < float(prev["ema20"])
        now_above = bool(last["body_above_ema20"])
        above_vwap= float(last["Close"]) > float(last["vwap"])
        if was_below and now_above and above_vwap:
            return ("CALL", f"EMA20 Body Reclaim ${last['ema20']:.2f}")
        return None

    def _check_ema20_rejection(self, last, prev) -> Optional[tuple]:
        was_above = float(prev["Close"]) > float(prev["ema20"])
        now_below = bool(last["body_below_ema20"])
        below_vwap= float(last["Close"]) < float(last["vwap"])
        if was_above and now_below and below_vwap:
            return ("PUT", f"EMA20 Body Rejection ${last['ema20']:.2f}")
        return None

    def _check_sma_touch(self, df, last) -> Optional[tuple]:
        """Hammer/rejection candle touching key SMA on 1-hr."""
        c       = float(last["Close"])
        body    = max(float(last["body"]), 0.01)
        lo_wick = float(last["lo_wick"])
        hi_wick = float(last["hi_wick"])
        cl_pct  = float(last["cl_pct"]) if not np.isnan(last["cl_pct"]) else 0.5
        ema20   = float(last["ema20"])
        vwap    = float(last["vwap"])

        for sma_name, sma_col in [("SMA50","sma50"),("SMA100","sma100"),("SMA200","sma200")]:
            if sma_col not in last or np.isnan(last[sma_col]):
                continue
            sma_val = float(last[sma_col])
            buf     = 0.008  # 0.8% buffer on 1-hr
            touched_lo = sma_val*(1-buf) <= float(last["Low"])  <= sma_val*(1+buf)
            touched_hi = sma_val*(1-buf) <= float(last["High"]) <= sma_val*(1+buf)

            # Bullish bounce
            if touched_lo and lo_wick >= 1.5*body and cl_pct >= 0.55 and c > sma_val:
                return ("CALL", f"{sma_name} Hammer Bounce ${sma_val:.2f}")

            # Bearish rejection
            if touched_hi and hi_wick >= 1.5*body and cl_pct <= 0.45 and c < sma_val and c < ema20:
                return ("PUT", f"{sma_name} Shooting Star ${sma_val:.2f}")

        return None

    def _check_double_bottom(self, df, last) -> Optional[tuple]:
        """Two lows within 0.8% over last 10 bars — bounce confirmed."""
        if len(df) < 12: return None
        recent     = df.tail(12)
        lows       = recent["Low"].values
        first_low  = np.min(lows[:6])
        second_low = np.min(lows[6:])
        pct_diff   = abs(first_low - second_low) / first_low if first_low > 0 else 1
        bouncing   = float(last["Close"]) > float(df["Close"].iloc[-3])
        above_ema9 = float(last["Close"]) > float(last["ema9"])
        above_vwap = float(last["Close"]) > float(last["vwap"])
        if pct_diff < 0.008 and bouncing and above_ema9:
            return ("CALL", f"Double Bottom ~${min(first_low,second_low):.2f}")
        return None

    def _check_double_top(self, df, last) -> Optional[tuple]:
        """Two highs within 0.8% over last 10 bars — drop confirmed."""
        if len(df) < 12: return None
        recent      = df.tail(12)
        highs       = recent["High"].values
        first_high  = np.max(highs[:6])
        second_high = np.max(highs[6:])
        pct_diff    = abs(first_high - second_high) / first_high if first_high > 0 else 1
        dropping    = float(last["Close"]) < float(df["Close"].iloc[-3])
        below_ema9  = float(last["Close"]) < float(last["ema9"])
        below_vwap  = float(last["Close"]) < float(last["vwap"])
        if pct_diff < 0.008 and dropping and below_ema9:
            return ("PUT", f"Double Top ~${max(first_high,second_high):.2f}")
        return None

    def _check_rsi(self, last, prev) -> Optional[tuple]:
        rsi      = float(last["rsi"])  if not np.isnan(last["rsi"])  else 50
        prev_rsi = float(prev["rsi"])  if not np.isnan(prev["rsi"])  else 50
        cl_pct   = float(last["cl_pct"]) if not np.isnan(last["cl_pct"]) else 0.5
        vol_ok   = float(last["vol_r"]) > 1.1 if not np.isnan(last["vol_r"]) else False
        c        = float(last["Close"])
        ema20    = float(last["ema20"])

        if rsi < 30 and rsi > prev_rsi and cl_pct > 0.5 and vol_ok:
            return ("CALL", f"RSI Oversold Reset {rsi:.1f}")
        if rsi > 70 and rsi < prev_rsi and cl_pct < 0.5 and vol_ok and c < ema20:
            return ("PUT", f"RSI Overbought Reset {rsi:.1f}")
        return None

    def _check_inside_bar(self, last, prev) -> Optional[tuple]:
        if not bool(last["inside_bar"]): return None
        c     = float(last["Close"])
        ema20 = float(last["ema20"])
        ema9  = float(last["ema9"])
        vwap  = float(last["vwap"])
        rsi   = float(last["rsi"]) if not np.isnan(last["rsi"]) else 50
        if c > ema20 and c > ema9 and c > vwap and rsi < 60:
            return ("CALL", "Inside Bar — bullish breakout setup")
        if c < ema20 and c < ema9 and c < vwap and rsi > 40:
            return ("PUT",  "Inside Bar — bearish breakdown setup")
        return None

    def _check_volume_surge(self, last) -> Optional[tuple]:
        vol_r  = float(last["vol_r"])  if not np.isnan(last["vol_r"])  else 1.0
        cl_pct = float(last["cl_pct"]) if not np.isnan(last["cl_pct"]) else 0.5
        c      = float(last["Close"])
        vwap   = float(last["vwap"])
        if vol_r > 2.5:
            if cl_pct > 0.65 and c > vwap:
                return ("CALL", f"Volume Surge {vol_r:.1f}x — buying")
            if cl_pct < 0.35 and c < vwap:
                return ("PUT",  f"Volume Surge {vol_r:.1f}x — selling")
        return None

    # ── confluence detector ───────────────────────────────────────────────────

    def _detect(self, ticker: str, df: pd.DataFrame,
                info: dict, ticker_type: str) -> Optional[HourlySignal]:
        cfg  = self.cfg
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else last

        c       = float(last["Close"])
        price   = info.get("regularMarketPrice") or info.get("currentPrice") or c
        avg_vol = info.get("averageVolume") or 0

        if price < cfg.min_price or avg_vol < cfg.min_avg_volume:
            return None

        # Skip only if today had a massive gap (>6%) — less aggressive than intraday
        if bool(last.get("recent_gap", False)):
            logger.debug(f"{ticker}: hourly skipped — large gap today")
            # Don't return None — just reduce confidence instead
            pass

        # Run all signal checkers
        checks = [
            self._check_vwap_reclaim(last, prev),
            self._check_vwap_rejection(last, prev),
            self._check_ema9_reclaim(last, prev),
            self._check_ema9_rejection(last, prev),
            self._check_ema20_reclaim(last, prev),
            self._check_ema20_rejection(last, prev),
            self._check_sma_touch(df, last),
            self._check_double_bottom(df, last),
            self._check_double_top(df, last),
            self._check_rsi(last, prev),
            self._check_inside_bar(last, prev),
            self._check_volume_surge(last),
        ]

        fired = [s for s in checks if s is not None]
        if not fired: return None

        calls = [s for s in fired if s[0]=="CALL"]
        puts  = [s for s in fired if s[0]=="PUT"]
        group = calls if len(calls) >= len(puts) else puts
        if not group: return None

        direction     = group[0][0]
        stacked       = [s[1] for s in group]
        is_confluence = len(group) >= cfg.confluence_min
        n_signals     = len(group)

        # Confidence
        rsi   = float(last["rsi"])  if not np.isnan(last["rsi"])  else 50
        vol_r = float(last["vol_r"]) if not np.isnan(last["vol_r"]) else 1.0
        vwap  = float(last["vwap"])
        body_above = bool(last["body_above_ema9"]) if direction=="CALL" else bool(last["body_below_ema9"])
        vwap_aligned = (c > vwap and direction=="CALL") or (c < vwap and direction=="PUT")

        base   = min(3, n_signals)
        conf   = min(5, base +
                    (1 if body_above    else 0) +
                    (1 if vwap_aligned  else 0))
        if is_confluence and body_above and vwap_aligned:
            conf = max(conf, 4)

        # Primary label
        priority = ["Double Bottom","Double Top","EMA9","EMA20","VWAP","SMA","RSI","Inside","Volume"]
        primary  = stacked[0]
        for p in priority:
            match = [s for s in stacked if p in s]
            if match:
                primary = match[0]
                break

        sig_type = f"⚡ Confluence ({n_signals} signals)" if is_confluence else primary

        # SMA level
        sma_level = "—"
        for s in stacked:
            for sma in ["SMA50","SMA100","SMA200"]:
                if sma in s:
                    sma_level = sma
                    break

        # Expiry — 1-hr signals are strong enough for next-day 1-2 DTE
        conf_val = conf
        expiry   = "Next Day (1-2 DTE)" if conf_val >= 4 else "2-3 DTE"

        # IV approximation
        atr     = float(last["atr"]) if not np.isnan(last["atr"]) else 0
        atr_pct = atr / c * 100 if c > 0 else 0
        if atr_pct > 3:
            iv_note = "⚠️ High IV — consider smaller size"
        elif atr_pct < 1.5:
            iv_note = "✅ Low IV — options relatively cheap"
        else:
            iv_note = "🟡 Moderate IV — normal sizing"

        return HourlySignal(
            ticker           = ticker,
            ticker_type      = ticker_type,
            direction        = direction,
            price            = round(float(c), 2),
            signal_type      = sig_type,
            confluence       = is_confluence,
            stacked_signals  = stacked,
            confidence       = conf,
            suggested_strike = snap_strike(float(c), direction),
            suggested_expiry = expiry,
            sma_level        = sma_level,
            rsi              = round(rsi, 1),
            volume_ratio     = round(vol_r, 2),
            vwap             = round(float(vwap), 2),
            atr              = round(atr, 2),
            iv_note          = iv_note,
            candle_date      = str(df.index[-1]),
            notes            = " + ".join(stacked) if is_confluence else stacked[0],
        )

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self, progress_cb=None) -> pd.DataFrame:
        cfg   = self.cfg
        all_t = ([(t,"index") for t in cfg.index_tickers] +
                 [(t,"stock") for t in cfg.stock_tickers])
        results = []
        total   = len(all_t)

        for idx, (ticker, ttype) in enumerate(all_t, 1):
            if progress_cb:
                progress_cb(idx, total, ticker)
            info, hist = self._fetch(ticker)
            time.sleep(cfg.rate_limit_sleep)
            if info is None: continue
            df = self._compute(hist)
            if df.empty: continue
            sig = self._detect(ticker, df, info, ttype)
            if sig:
                results.append(sig)
                flag = "⚡" if sig.confluence else "✅"
                logger.info(f"{flag} HOURLY {ticker} {sig.direction} {sig.confidence}★ — {sig.signal_type}")

        return self._to_df(results)

    @staticmethod
    def _to_df(results: list) -> pd.DataFrame:
        if not results: return pd.DataFrame()
        rows = [{
            "Ticker":      r.ticker,
            "Type":        r.ticker_type.upper(),
            "Direction":   r.direction,
            "Price":       r.price,
            "Signal":      r.signal_type,
            "Confluence":  r.confluence,
            "Signals":     " · ".join(r.stacked_signals),
            "Confidence":  "⭐" * r.confidence,
            "Strike":      r.suggested_strike,
            "Expiry":      r.suggested_expiry,
            "SMA Level":   r.sma_level,
            "RSI":         r.rsi,
            "Vol Ratio":   r.volume_ratio,
            "VWAP":        r.vwap,
            "ATR":         r.atr,
            "IV Note":     r.iv_note,
            "Date":        r.candle_date,
            "Notes":       r.notes,
        } for r in results]
        df = pd.DataFrame(rows)
        df["_c"] = df["Confidence"].str.len()
        df["_f"] = df["Confluence"].astype(int)
        df.sort_values(["_f","_c"], ascending=[False,False], inplace=True)
        df.drop(columns=["_c","_f"], inplace=True)
        return df.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  PREMARKET / AFTER-HOURS SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PremarketSignal:
    ticker:          str
    ticker_type:     str
    prev_close:      float
    current_price:   float
    gap_pct:         float
    gap_direction:   str    # UP / DOWN / FLAT
    pm_high:         float
    pm_low:          float
    pm_volume:       int
    pm_vol_ratio:    float  # vs avg daily volume
    bias:            str    # CALL / PUT / WAIT
    conviction:      str    # HIGH / MEDIUM / LOW
    confidence:      int    # 1-5
    key_level:       float  # level to watch at open
    notes:           str
    session:         str    # PRE-MARKET / AFTER-HOURS
    timestamp:       str


class PremarketScanner:
    """
    Scans pre-market (4AM-9:30AM ET) and after-hours (4PM-8PM ET) data.
    Uses Alpaca for real-time if keys provided, else yfinance fallback.
    Identifies gap direction, key levels, and opening bias for next session.
    """

    def __init__(self, cfg: ScannerConfig = None):
        self.cfg = cfg or ScannerConfig()
        self.ind = Indicators()

    # ── session detector ──────────────────────────────────────────────────────

    @staticmethod
    def current_session() -> str:
        """Returns PRE-MARKET, AFTER-HOURS, MARKET, or CLOSED."""
        ET  = pytz.timezone("America/New_York")
        now = datetime.now(ET)
        h   = now.hour + now.minute / 60
        wd  = now.weekday()

        if wd >= 5:
            return "WEEKEND"
        if 4.0 <= h < 9.5:
            return "PRE-MARKET"
        if 9.5 <= h < 16.0:
            return "MARKET"
        if 16.0 <= h < 20.0:
            return "AFTER-HOURS"
        return "CLOSED"

    # ── fetch via Alpaca ──────────────────────────────────────────────────────

    def _fetch_alpaca_extended(self, ticker: str) -> Optional[pd.DataFrame]:
        """Fetch extended hours bars from Alpaca."""
        try:
            from datetime import timedelta

            ET    = pytz.timezone("America/New_York")
            now   = datetime.now(ET)
            start = (now - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
            end   = now.strftime("%Y-%m-%dT%H:%M:%SZ")

            url     = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
            headers = {
                "APCA-API-KEY-ID":     self.cfg.alpaca_key,
                "APCA-API-SECRET-KEY": self.cfg.alpaca_secret,
            }
            params = {
                "timeframe":      "5Min",
                "start":          start,
                "end":            end,
                "limit":          200,
                "feed":           "iex",
                "extended_hours": "true",   # KEY: include pre/AH data
            }

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                return None

            bars = resp.json().get("bars", [])
            if not bars:
                return None

            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"], utc=True)
            df = df.set_index("t").tz_convert("America/New_York")
            df = df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"})
            return df

        except Exception as e:
            logger.debug(f"{ticker}: Alpaca extended hours error — {e}")
            return None

    # ── fetch via yfinance ────────────────────────────────────────────────────

    def _fetch_yfinance_extended(self, ticker: str) -> Optional[pd.DataFrame]:
        """Fetch extended hours data via yfinance."""
        try:
            t  = yf.Ticker(ticker)
            # 5-min bars with prepost=True includes extended hours
            df = t.history(period="2d", interval="5m",
                          auto_adjust=True, prepost=True)
            if df.empty:
                return None
            if df.index.tz is None:
                df.index = df.index.tz_localize("America/New_York")
            else:
                df.index = df.index.tz_convert("America/New_York")
            return df
        except Exception as e:
            logger.debug(f"{ticker}: yfinance extended error — {e}")
            return None

    def _fetch(self, ticker: str) -> Optional[pd.DataFrame]:
        if self.cfg.alpaca_key and self.cfg.alpaca_secret:
            df = self._fetch_alpaca_extended(ticker)
            if df is not None and not df.empty:
                return df
        return self._fetch_yfinance_extended(ticker)

    def _fetch_prev_close(self, ticker: str) -> float:
        """Get previous regular session close."""
        try:
            t    = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d", auto_adjust=True)
            if len(hist) >= 2:
                return float(hist["Close"].iloc[-2])
            return float(hist["Close"].iloc[-1])
        except:
            return 0.0

    def _fetch_avg_volume(self, ticker: str) -> int:
        try:
            info = yf.Ticker(ticker).info
            return info.get("averageVolume") or info.get("averageDailyVolume10Day") or 1_000_000
        except:
            return 1_000_000

    # ── analysis ──────────────────────────────────────────────────────────────

    def _analyse(self, ticker: str, df: pd.DataFrame,
                 prev_close: float, avg_vol: int,
                 session: str, ticker_type: str) -> Optional[PremarketSignal]:

        ET  = pytz.timezone("America/New_York")
        now = datetime.now(ET)

        # Filter to current session bars only
        if session == "PRE-MARKET":
            # Today's pre-market: 4AM to 9:30AM
            session_df = df[
                (df.index.date == now.date()) &
                (df.index.hour >= 4) &
                ((df.index.hour < 9) | ((df.index.hour == 9) & (df.index.minute < 30)))
            ]
        elif session == "AFTER-HOURS":
            # Today's after-hours: 4PM to 8PM
            session_df = df[
                (df.index.date == now.date()) &
                (df.index.hour >= 16) &
                (df.index.hour < 20)
            ]
        else:
            # Weekend — use most recent available extended hours
            session_df = df.tail(30)

        if session_df.empty or len(session_df) < 2:
            return None

        # Key metrics
        pm_high    = float(session_df["High"].max())
        pm_low     = float(session_df["Low"].min())
        pm_volume  = int(session_df["Volume"].sum())
        current    = float(session_df["Close"].iloc[-1])
        pm_open    = float(session_df["Open"].iloc[0])

        if prev_close <= 0:
            return None

        gap_pct    = (current - prev_close) / prev_close * 100
        vol_ratio  = pm_volume / (avg_vol * 0.15) if avg_vol > 0 else 1.0
        # Pre-market typically ~15% of regular volume — normalize against that

        # Gap direction
        if gap_pct > 0.5:
            gap_dir = "UP"
        elif gap_pct < -0.5:
            gap_dir = "DOWN"
        else:
            gap_dir = "FLAT"

        # Conviction based on volume
        if vol_ratio > 2.0:
            conviction = "HIGH"
        elif vol_ratio > 1.0:
            conviction = "MEDIUM"
        else:
            conviction = "LOW"

        # Bias determination
        # Key level = most important price to watch at open
        if gap_dir == "UP":
            bias      = "CALL"
            key_level = pm_high   # watch for breakout above PM high
            notes     = f"Gapped up {gap_pct:.1f}% · Watch for hold above PM high ${pm_high:.2f} at open"
            if vol_ratio < 0.5:
                bias  = "WAIT"
                notes = f"Gapped up {gap_pct:.1f}% but THIN volume ({vol_ratio:.1f}x) · Likely to fade at open"
        elif gap_dir == "DOWN":
            bias      = "PUT"
            key_level = pm_low    # watch for breakdown below PM low
            notes     = f"Gapped down {gap_pct:.1f}% · Watch for break below PM low ${pm_low:.2f} at open"
            if vol_ratio < 0.5:
                bias  = "WAIT"
                notes = f"Gapped down {gap_pct:.1f}% but THIN volume ({vol_ratio:.1f}x) · May recover at open"
        else:
            bias      = "WAIT"
            key_level = prev_close
            notes     = f"Flat overnight · Watch for direction break at open near ${prev_close:.2f}"

        # Adjust bias for large gaps — fade potential
        if abs(gap_pct) > 4.0 and conviction == "LOW":
            bias  = "WAIT"
            notes = f"Large gap {gap_pct:.1f}% on thin volume · High fade risk · Wait for open confirmation"

        # Mean reversion signal — if gap is extreme, opposite trade may set up
        if abs(gap_pct) > 5.0 and conviction == "HIGH":
            notes += f" · EXTREME gap — watch for mean reversion after first 15 min"

        # Confidence
        conf = 2
        if conviction == "HIGH":   conf += 2
        if conviction == "MEDIUM": conf += 1
        if abs(gap_pct) > 2.0:    conf += 1
        conf = min(5, conf)

        return PremarketSignal(
            ticker        = ticker,
            ticker_type   = ticker_type,
            prev_close    = round(prev_close, 2),
            current_price = round(current, 2),
            gap_pct       = round(gap_pct, 2),
            gap_direction = gap_dir,
            pm_high       = round(pm_high, 2),
            pm_low        = round(pm_low, 2),
            pm_volume     = pm_volume,
            pm_vol_ratio  = round(vol_ratio, 2),
            bias          = bias,
            conviction    = conviction,
            confidence    = conf,
            key_level     = round(key_level, 2),
            notes         = notes,
            session       = session,
            timestamp     = str(session_df.index[-1]),
        )

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self, progress_cb=None) -> pd.DataFrame:
        cfg     = self.cfg
        session = self.current_session()
        all_t   = ([(t,"index") for t in cfg.index_tickers] +
                   [(t,"stock") for t in cfg.stock_tickers])
        results = []
        total   = len(all_t)

        for idx, (ticker, ttype) in enumerate(all_t, 1):
            if progress_cb:
                progress_cb(idx, total, ticker)

            df = self._fetch(ticker)
            time.sleep(cfg.rate_limit_sleep)

            if df is None or df.empty:
                continue

            prev_close = self._fetch_prev_close(ticker)
            avg_vol    = self._fetch_avg_volume(ticker)

            sig = self._analyse(ticker, df, prev_close, avg_vol, session, ttype)
            if sig:
                results.append(sig)
                logger.info(f"🌅 {ticker} {sig.gap_direction} {sig.gap_pct:+.1f}% — {sig.bias} ({sig.conviction})")

        return self._to_df(results, session)

    @staticmethod
    def _to_df(results: list, session: str) -> pd.DataFrame:
        if not results:
            return pd.DataFrame()
        rows = [{
            "Ticker":      r.ticker,
            "Type":        r.ticker_type.upper(),
            "Session":     r.session,
            "Prev Close":  r.prev_close,
            "Current":     r.current_price,
            "Gap %":       r.gap_pct,
            "Direction":   r.gap_direction,
            "Bias":        r.bias,
            "Conviction":  r.conviction,
            "Confidence":  "⭐" * r.confidence,
            "PM High":     r.pm_high,
            "PM Low":      r.pm_low,
            "Key Level":   r.key_level,
            "Vol Ratio":   r.pm_vol_ratio,
            "Notes":       r.notes,
            "Time":        r.timestamp,
        } for r in results]

        df = pd.DataFrame(rows)
        # Sort: biggest absolute gap first, then by conviction
        df["_gap_abs"]  = df["Gap %"].abs()
        df["_conv_ord"] = df["Conviction"].map({"HIGH":3,"MEDIUM":2,"LOW":1})
        df.sort_values(["_conv_ord","_gap_abs"], ascending=[False,False], inplace=True)
        df.drop(columns=["_gap_abs","_conv_ord"], inplace=True)
        return df.reset_index(drop=True)
