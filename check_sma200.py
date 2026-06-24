import os
import sys
import requests
import pandas as pd
import yfinance as yf

# Secrets
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
if not TOKEN or not CHAT_ID:
    print("Fehler: TELEGRAM_BOT_TOKEN oder TELEGRAM_CHAT_ID nicht gesetzt (Secrets prüfen).")
    sys.exit(1)

# Standard: Ticker aus Env; Fallback hier ist ^GSPC (Index) – ändere bei Bedarf auf 'SPY'
TICKER = os.environ.get("TICKER", "^GSPC")

# Trend-Schwelle (in % über 10 Handelstage) für "seitwärts"
TREND_EPS_PCT = float(os.environ.get("TREND_EPS_PCT", "0.05"))

def send_telegram(text):
    try:
        # HTML für fette Überschrift
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as e:
        print("Telegram-Fehler:", e)

def main():
    # 3 Jahre Tagesdaten, flaches Spaltenlayout
    df = yf.Ticker(TICKER).history(period="3y", interval="1d", auto_adjust=True)
    if df is None or df.empty:
        print("Keine Daten geladen.")
        sys.exit(1)

    if "Close" not in df.columns:
        print(f"'Close'-Spalte nicht gefunden. Spalten: {list(df.columns)}")
        sys.exit(1)

    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    sma = close.rolling(200, min_periods=200).mean()
    aligned = pd.DataFrame({"Close": close, "SMA200": sma}).dropna()

    if len(aligned) < 12:
        print("Nicht genug Datenpunkte für Trend/Cross.")
        sys.exit(1)

    # Heute / gestern
    close_today = float(aligned["Close"].iloc[-1])
    sma_today   = float(aligned["SMA200"].iloc[-1])
    close_yday  = float(aligned["Close"].iloc[-2])
    sma_yday    = float(aligned["SMA200"].iloc[-2])

    # Abweichung in %
    delta_pct = (close_today - sma_today) / sma_today * 100 if sma_today else 0.0

    # 10-Tage-Trend
    sma_prev10  = float(aligned["SMA200"].iloc[-11])
    trend_pct = (sma_today - sma_prev10) / sma_prev10 * 100 if sma_prev10 else 0.0
    trend = "seitwärts" if abs(trend_pct) < TREND_EPS_PCT else ("aufwärts" if sma_today > sma_prev10 else "abwärts")

    status = "Risk ON" if close_today >= sma_today else "Risk OFF"
    circle = "🟢" if status == "Risk ON" else "🔴"

    # Optionales Cross-Signal (seit gestern)
    cross_up = (close_yday < sma_yday) and (close_today >= sma_today)
    cross_dn = (close_yday > sma_yday) and (close_today <= sma_today)
    signal_line = ""
    if cross_up:
        signal_line = "\n<b>Signal:</b> ⬆️ Cross UP"
    elif cross_dn:
        signal_line = "\n<b>Signal:</b> ⬇️ Cross DOWN"

    date_str = aligned.index[-1].date().isoformat()

    # Überschrift fett, zweite Zeile mit Ticker+Datum, danach Leerzeile
    title = "<b>S&amp;P500 Update</b>"
    msg = (
        f"{title}\n\n"
        f"{TICKER} - {date_str}\n\n"
        f"Kurs (Close): {close_today:.2f}\n"
        f"SMA200: {sma_today:.2f}\n"
        f"Abweichung: {delta_pct:.2f}%\n"
        f"SMA-Trend (10 Tage): {trend}\n"
        f"\n"
        f"<b>Status:</b> {circle} {status}"
        f"{signal_line}"
    )

    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()
