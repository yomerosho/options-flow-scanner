# 📡 Mean Reversion Scanner

A Python stock screener that identifies **hammer / rejection candle setups** at key SMA levels (100-day & 200-day), with both a Streamlit web dashboard and a CLI runner for automated scheduling.

---

## 🗂️ Project Structure

```
stock_scanner/
├── scanner.py        ← Core engine (universe, filters, setup detector)
├── app.py            ← Streamlit dashboard
├── run_scan.py       ← Headless CLI runner (for schedulers)
├── requirements.txt  ← Python dependencies
└── README.md
```

---

## ⚙️ Installation

```bash
# 1. Clone / copy this folder
cd stock_scanner

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

> **Python 3.10+** required.

---

## 🚀 Running the Streamlit Dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.  
Adjust parameters in the sidebar and click **Run Scan**.

---

## 🖥️ Running the CLI (headless)

```bash
# Basic run — prints table to terminal
python run_scan.py

# Save results to CSV
python run_scan.py --output results.csv

# Custom parameters
python run_scan.py --min-vol 3000000 --min-beta 1.2 --wick-ratio 2.5

# With desktop notification (requires plyer)
python run_scan.py --notify
```

All CLI flags:
| Flag | Default | Description |
|---|---|---|
| `--output` | — | Save CSV to this path |
| `--notify` | false | Desktop notification on completion |
| `--min-vol` | 2,000,000 | Minimum average daily volume |
| `--min-price` | 30.0 | Minimum stock price ($) |
| `--min-atr` | 1.0 | Minimum 14-day ATR |
| `--min-beta` | 1.0 | Minimum beta |
| `--sma-buf` | 0.5 | SMA touch buffer (%) |
| `--wick-ratio` | 2.0 | Minimum wick-to-body ratio |
| `--close-pct` | 40.0 | Close must be in top X% of range |

---

## ⏰ Scheduling — Run Daily 30 Minutes Before Market Close

US market closes at **4:00 PM ET** → schedule at **3:30 PM ET** on weekdays.

### macOS / Linux — cron

```bash
crontab -e
```

Add this line (adjust paths):
```cron
30 15 * * 1-5 /path/to/.venv/bin/python /path/to/stock_scanner/run_scan.py --output /path/to/results/scan_$(date +\%Y\%m\%d).csv
```

### Windows — Task Scheduler

1. Open **Task Scheduler** → Create Basic Task
2. Trigger: **Daily**, 3:30 PM
3. Action: **Start a program**
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `C:\path\to\stock_scanner\run_scan.py --output C:\scans\scan.csv`
4. Set to repeat only on **weekdays** in the advanced settings.

### macOS — launchd (alternative to cron)

Create `~/Library/LaunchAgents/com.scanner.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
<dict>
  <key>Label</key><string>com.scanner</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/python</string>
    <string>/path/to/stock_scanner/run_scan.py</string>
    <string>--output</string>
    <string>/tmp/scan.csv</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>15</integer>
    <key>Minute</key><integer>30</integer>
  </dict>
</dict>
</plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.scanner.plist`

---

## 📊 Scanner Logic

### Part 1 — Universe & Fundamental Filter
| Criterion | Default |
|---|---|
| Optionable | ✅ curated universe |
| Avg Volume | > 2,000,000 |
| Price | > $30 |
| ATR (14-day) | > 1.0 |
| Beta | > 1.0 |
| Price above 20 SMA | ✅ |
| Price above 50 SMA | ✅ |

### Part 2 — Setup Detection (Rejection Candle)
| Criterion | Default |
|---|---|
| Daily Low within X% of SMA-100 or SMA-200 | 0.5% |
| Lower shadow ≥ N × body | 2.0× |
| Close in upper 40% of day's range | top 40% |
| Close above the SMA tested | ✅ |

### Output Columns
| Column | Description |
|---|---|
| Ticker | Symbol |
| Date | Candle date |
| Price | Last close |
| SMA Tested | 100 or 200 |
| SMA Value | SMA price level |
| Rejection Strength | Lower wick ÷ body (higher = stronger) |
| Lower Wick ($) | Shadow size in dollars |
| Body Size ($) | Candle body size in dollars |
| Close % of Range | How high in the day's range did it close |
| Volume | Day's volume |
| ATR | 14-day ATR |
| Beta | Stock beta |

---

## 🔧 Upgrading to a Pro Data Source

`yfinance` is great for free use. For production where **data accuracy is critical**, swap in:

- **[Polygon.io](https://polygon.io)** — `pip install polygon-api-client`
- **[Financial Modeling Prep](https://financialmodelingprep.com)** — REST API
- **[Alpaca](https://alpaca.markets)** — `pip install alpaca-trade-api`

Replace the `_fetch()` method in `MeanReversionScanner` with your preferred provider.

---

## ⚠️ Disclaimer

This tool is for **educational and research purposes only**. It does not constitute financial advice. Always do your own due diligence before trading.
