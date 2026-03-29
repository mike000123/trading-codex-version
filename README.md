# Historical Trade Outcome Simulator

A small Streamlit app for testing historical leveraged trades from daily OHLC data.

## Features


- Upload CSV with OHLC/date columns in **any order**. Common names are accepted (e.g. `Date`, `Close/Last`, `Open`, `High`, `Low`).
=======
- Upload CSV with columns: `date, open, high, low, close`.

- Choose a historical trade date, direction (long/short), and leverage.
- **Mode 1:** Enter take-profit and stop-loss prices and get the first date one of them is hit.
- **Mode 2:** Enter desired leveraged profit (%) and get suggested take-profit/stop-loss levels based on historical path.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- The app uses **daily** candles only. If high and low touch both thresholds on the same day, intraday order is unknown and results are marked ambiguous.
- In mode 2, suggested stop-loss is set just beyond the worst adverse move seen before the first target-hit day in historical data.
