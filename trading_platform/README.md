 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index f7c764bd723837d8a7ed58ccaaa59088561b4a09..c8447c839c78c8990581d249432239092532082e 100644
--- a/README.md
+++ b/README.md
@@ -1,28 +1,63 @@
-# Historical Trade Outcome Simulator
-
-A small Streamlit app for testing historical leveraged trades from daily OHLC data.
-
-## Features
-
-
-- Upload CSV with OHLC/date columns in **any order**. Common names are accepted (e.g. `Date`, `Close/Last`, `Open`, `High`, `Low`).
-=======
-- Upload CSV with columns: `date, open, high, low, close`.
-
-- Choose a historical trade date, direction (long/short), and leverage.
-- **Mode 1:** Enter take-profit and stop-loss prices and get the first date one of them is hit.
-- **Mode 2:** Enter desired leveraged profit (%) and get suggested take-profit/stop-loss levels based on historical path.
+# Modular Streamlit Algo Trading Platform
+
+This repository now contains a modular architecture for progressing from historical simulation to paper/live algorithmic trading with Alpaca.
+
+## What is included
+
+- Streamlit control console with **paper/live mode** separation and live safeguards.
+- Data ingestion from **Yahoo Finance** and **CSV upload**.
+- Strategy abstraction with a pluggable interface and a built-in **RSI Mean Reversion** strategy.
+- Global risk layer (position sizing, daily loss cap, drawdown cap, leverage cap, SL/TP validation).
+- Order router that supports:
+  - simulated paper routing
+  - Alpaca live routing (`alpaca-py`) when explicitly armed
+- Persistent logs for signals/orders/events/config snapshots in `/storage`.
+- Theme system with predefined presets (Dark Pro, Bright Clean, Emerald).
+- Portfolio overview panel based on persisted order history.
+
+## Project structure
+
+```text
+app.py
+trading_platform/
+  config.py
+  engine.py
+  data/sources.py
+  strategies/base.py
+  strategies/rsi_strategy.py
+  risk/controls.py
+  execution/router.py
+  state/storage.py
+  ui/themes.py
+storage/   # auto-created on first run
+```
 
 ## Run locally
 
 ```bash
 python -m venv .venv
 source .venv/bin/activate
 pip install -r requirements.txt
 streamlit run app.py
 ```
 
-## Notes
+## Live mode safeguards
+
+Live order submission requires all of the following:
 
-- The app uses **daily** candles only. If high and low touch both thresholds on the same day, intraday order is unknown and results are marked ambiguous.
-- In mode 2, suggested stop-loss is set just beyond the worst adverse move seen before the first target-hit day in historical data.
+1. Execution mode set to `live`.
+2. UI checkbox confirming arm intent.
+3. Exact phrase `ARM LIVE TRADING`.
+4. Alpaca credentials in environment variables:
+   - `ALPACA_API_KEY`
+   - `ALPACA_SECRET_KEY`
+
+`ALPACA_PAPER=true|false` can be set to control Alpaca environment endpoint.
+
+## Packaging
+
+To produce a distributable zip:
+
+```bash
+zip -r forward_simulation_platform.zip . -x ".git/*" "__pycache__/*" ".venv/*"
+```
 
EOF
)
