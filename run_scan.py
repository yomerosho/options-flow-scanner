"""
run_scan.py — Headless CLI runner for scheduled use
====================================================
Usage:
    python run_scan.py                    # prints results to terminal
    python run_scan.py --output scan.csv  # saves to CSV
    python run_scan.py --notify           # sends desktop notification (if plyer installed)
"""

import argparse
import sys
from datetime import datetime

from scanner import MeanReversionScanner, ScannerConfig


def main():
    parser = argparse.ArgumentParser(description="Mean Reversion Scanner CLI")
    parser.add_argument("--output",  "-o", help="Save results to CSV path")
    parser.add_argument("--notify",  "-n", action="store_true",
                        help="Send desktop notification with result count")
    parser.add_argument("--min-vol",    type=int,   default=2_000_000)
    parser.add_argument("--min-price",  type=float, default=30.0)
    parser.add_argument("--min-atr",    type=float, default=1.0)
    parser.add_argument("--min-beta",   type=float, default=1.0)
    parser.add_argument("--sma-buf",    type=float, default=0.5,
                        help="SMA touch buffer in percent (default 0.5)")
    parser.add_argument("--wick-ratio", type=float, default=2.0)
    parser.add_argument("--close-pct",  type=float, default=40.0,
                        help="Close must be in top X pct of range (default 40)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  MEAN REVERSION SCANNER  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    cfg = ScannerConfig(
        min_avg_volume       = args.min_vol,
        min_price            = args.min_price,
        min_atr              = args.min_atr,
        min_beta             = args.min_beta,
        sma_touch_buffer_pct = args.sma_buf / 100,
        rejection_wick_ratio = args.wick_ratio,
        close_upper_pct      = args.close_pct / 100,
    )

    scanner = MeanReversionScanner(cfg)

    def cb(idx, total, ticker):
        bar_len = 30
        filled  = int(bar_len * idx / total)
        bar     = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {idx}/{total} — {ticker:<8}", end="", flush=True)

    df = scanner.run(progress_cb=cb)
    print()  # newline after progress bar

    if df.empty:
        print("\n  ⚠️  No setups found with current parameters.\n")
        sys.exit(0)

    print(f"\n  ✅  {len(df)} setup(s) found\n")
    print(df.to_string(index=False))
    print()

    if args.output:
        df.to_csv(args.output, index=False)
        print(f"  💾  Saved to {args.output}\n")

    if args.notify:
        try:
            from plyer import notification
            notification.notify(
                title="Mean Reversion Scanner",
                message=f"{len(df)} setup(s) found — {datetime.now().strftime('%H:%M')}",
                timeout=10,
            )
        except ImportError:
            print("  ℹ️  Install 'plyer' for desktop notifications: pip install plyer")


if __name__ == "__main__":
    main()
