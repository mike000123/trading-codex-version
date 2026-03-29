import io
from dataclasses import dataclass
from typing import Optional, Tuple

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="Historical Trade Outcome Simulator", layout="wide")


@dataclass
class TradeResult:
    outcome: str
    outcome_date: Optional[pd.Timestamp]
    exit_price: Optional[float]
    leveraged_return_pct: Optional[float]
    notes: str = ""


def portfolio_value_after_trade(capital: float, leveraged_return_pct: Optional[float]) -> Optional[float]:
    if leveraged_return_pct is None:
        return None
    return capital * (1 + leveraged_return_pct / 100)


def render_price_chart_with_markers(
    data: pd.DataFrame, entry_date: Optional[pd.Timestamp], exit_date: Optional[pd.Timestamp]
) -> alt.Chart:
    base = alt.Chart(data).mark_line().encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("close:Q", title="Close"),
        tooltip=["date:T", "close:Q"],
    )

    layers = [base]

    marker_rows = []
    if entry_date is not None:
        marker_rows.append({"date": entry_date, "label": "Entry"})
    if exit_date is not None:
        marker_rows.append({"date": exit_date, "label": "Exit"})

    if marker_rows:
        marker_df = pd.DataFrame(marker_rows)
        marker_rules = (
            alt.Chart(marker_df)
            .mark_rule(strokeWidth=2)
            .encode(
                x="date:T",
                color=alt.Color("label:N", scale=alt.Scale(domain=["Entry", "Exit"], range=["#2ca02c", "#d62728"])),
                tooltip=["date:T", "label:N"],
            )
        )
        marker_points = (
            alt.Chart(marker_df)
            .mark_point(filled=True, size=200)
            .encode(
                x="date:T",
                y=alt.Y("close:Q"),
                color=alt.Color("label:N", scale=alt.Scale(domain=["Entry", "Exit"], range=["#2ca02c", "#d62728"])),
                tooltip=["date:T", "label:N", "close:Q"],
            )
            .transform_lookup(
                lookup="date",
                from_=alt.LookupData(data, "date", ["close"]),
            )
        )
        marker_labels = (
            alt.Chart(marker_df)
            .mark_text(dy=-12, fontWeight="bold")
            .encode(
                x="date:T",
                y=alt.Y("close:Q"),
                text="label:N",
                color=alt.Color("label:N", scale=alt.Scale(domain=["Entry", "Exit"], range=["#2ca02c", "#d62728"])),
            )
            .transform_lookup(
                lookup="date",
                from_=alt.LookupData(data, "date", ["close"]),
            )
        )
        layers.extend([marker_rules, marker_points, marker_labels])

    return alt.layer(*layers).properties(height=300)


def _canonicalize_column(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


def _to_numeric(series: pd.Series) -> pd.Series:
    # Handles common CSV formats such as "$4,321.50" and "1,234".
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def load_price_data(file_buffer) -> pd.DataFrame:
    raw = file_buffer.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")

    df = pd.read_csv(io.BytesIO(raw))
    canonical_to_original = {_canonicalize_column(c): c for c in df.columns}

    aliases = {
        "date": ["date", "datetime", "time", "timestamp"],
        "open": ["open", "openingprice"],
        "high": ["high", "max"],
        "low": ["low", "min"],
        "close": ["close", "closelast", "closeprice", "last"],
    }

    resolved = {}
    missing = []
    for target, candidates in aliases.items():
        matched = next((canonical_to_original[c] for c in candidates if c in canonical_to_original), None)
        if matched is None:
            missing.append(target)
        else:
            resolved[target] = matched

    if missing:
        raise ValueError(
            "CSV is missing required price columns: "
            + ", ".join(sorted(missing))
            + ". Accepted names include: Date/Datetime, Open, High/Max, Low/Min, Close/Close/Last."
        )

    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(df[resolved["date"]], errors="coerce", utc=True).dt.tz_localize(None),
            "open": _to_numeric(df[resolved["open"]]),
            "high": _to_numeric(df[resolved["high"]]),
            "low": _to_numeric(df[resolved["low"]]),
            "close": _to_numeric(df[resolved["close"]]),
        }
    ).dropna()

    normalized = normalized.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if normalized.empty:
        raise ValueError("No valid rows after parsing data.")
    return normalized


def fetch_price_data_from_ticker(
    ticker: str, interval: str, start_date: pd.Timestamp, end_date: pd.Timestamp
) -> pd.DataFrame:
    if not ticker.strip():
        raise ValueError("Ticker cannot be empty.")
    if end_date < start_date:
        raise ValueError("End date must be on or after start date.")

    data = yf.download(
        ticker.strip(),
        start=start_date.strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval=interval,
        auto_adjust=False,
        progress=False,
    )

    if data is None or data.empty:
        raise ValueError("No data returned for this ticker/interval/date range.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required_cols = ["Open", "High", "Low", "Close"]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Fetched data missing required column: {col}")

    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(data.index, errors="coerce", utc=True).tz_localize(None),
            "open": pd.to_numeric(data["Open"], errors="coerce"),
            "high": pd.to_numeric(data["High"], errors="coerce"),
            "low": pd.to_numeric(data["Low"], errors="coerce"),
            "close": pd.to_numeric(data["Close"], errors="coerce"),
        }
    ).dropna()

    normalized = normalized.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if normalized.empty:
        raise ValueError("No valid rows after fetching data.")
    return normalized


def leveraged_return(entry_price: float, exit_price: float, leverage: float, direction: str) -> float:
    raw_move = (exit_price - entry_price) / entry_price
    if direction == "Short":
        raw_move = -raw_move
    return raw_move * leverage * 100


def apply_max_loss_cap_to_stop(
    entry_price: float,
    stop_price: float,
    leverage: float,
    direction: str,
    max_loss_pct_of_capital: float,
) -> Tuple[float, bool]:
    """
    Enforce a maximum loss threshold (% of capital) by clamping stop-loss.
    """
    loss_move = max_loss_pct_of_capital / 100 / leverage
    if direction == "Long":
        min_allowed_stop = entry_price * (1 - loss_move)
        adjusted = max(stop_price, min_allowed_stop)
    else:
        max_allowed_stop = entry_price * (1 + loss_move)
        adjusted = min(stop_price, max_allowed_stop)
    was_adjusted = abs(adjusted - stop_price) > 1e-12
    return adjusted, was_adjusted


def simulate_trade(
    data: pd.DataFrame,
    entry_date: pd.Timestamp,
    direction: str,
    leverage: float,
    take_price: float,
    stop_price: float,
) -> TradeResult:
    subset = data[data["date"] >= entry_date].copy()
    if subset.empty:
        return TradeResult("No data", None, None, None, "No rows from selected entry date onward.")

    entry_row = subset.iloc[0]
    entry_price = float(entry_row["close"])

    for _, row in subset.iterrows():
        day = row["date"]
        high = float(row["high"])
        low = float(row["low"])

        if direction == "Long":
            hit_tp = high >= take_price
            hit_sl = low <= stop_price
        else:
            hit_tp = low <= take_price
            hit_sl = high >= stop_price

        if hit_tp and hit_sl:
            return TradeResult(
                outcome="Ambiguous candle",
                outcome_date=day,
                exit_price=None,
                leveraged_return_pct=None,
                notes=(
                    "Take-profit and stop-loss were both touched within the same candle. "
                    "Intraday order is unknown from daily OHLC data."
                ),
            )

        if hit_tp:
            pnl = leveraged_return(entry_price, take_price, leverage, direction)
            return TradeResult("Take-profit hit", day, take_price, pnl)

        if hit_sl:
            pnl = leveraged_return(entry_price, stop_price, leverage, direction)
            return TradeResult("Stop-loss hit", day, stop_price, pnl)

    return TradeResult("Open", None, None, None, "Neither threshold was hit in available data.")


def suggest_levels_for_desired_profit(
    data: pd.DataFrame,
    entry_date: pd.Timestamp,
    direction: str,
    leverage: float,
    desired_profit_pct: float,
) -> Tuple[Optional[float], Optional[float], Optional[pd.Timestamp], str]:
    subset = data[data["date"] >= entry_date].copy()
    if subset.empty:
        return None, None, None, "No rows from selected entry date onward."

    entry_price = float(subset.iloc[0]["close"])
    underlying_move = desired_profit_pct / 100 / leverage

    if direction == "Long":
        take_price = entry_price * (1 + underlying_move)
        target_hits = subset[subset["high"] >= take_price]
    else:
        take_price = entry_price * (1 - underlying_move)
        target_hits = subset[subset["low"] <= take_price]

    if target_hits.empty:
        return None, None, None, (
            "Desired profit target was never reached in the historical window with this leverage."
        )

    first_hit_date = target_hits.iloc[0]["date"]
    pre_target = subset[subset["date"] < first_hit_date]

    if direction == "Long":
        if pre_target.empty:
            stop_price = entry_price * 0.99
        else:
            stop_price = float(pre_target["low"].min()) * 0.999
    else:
        if pre_target.empty:
            stop_price = entry_price * 1.01
        else:
            stop_price = float(pre_target["high"].max()) * 1.001

    note = (
        "Suggested stop is set just beyond the worst adverse move before the first target-hit day. "
        "If both thresholds can occur within one day, sequence remains ambiguous with daily bars."
    )

    return take_price, stop_price, first_hit_date, note


st.title("Historical Trade Outcome Simulator")
st.write(
    "Load OHLC data from file or ticker, then test leveraged long/short scenarios from any historical date."
)

data_mode = st.radio("Data source", ["Ticker (auto-fetch)", "CSV upload"])

if data_mode == "Ticker (auto-fetch)":
    c_ticker, c_interval = st.columns(2)
    with c_ticker:
        ticker = st.text_input("Ticker symbol", value="AAPL")
    with c_interval:
        interval = st.selectbox(
            "Frequency",
            ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1d", "5d", "1wk", "1mo"],
            index=7,
        )

    c_start, c_end = st.columns(2)
    with c_start:
        start_fetch = st.date_input(
            "Start date", value=(pd.Timestamp.today() - pd.Timedelta(days=365)).date()
        )
    with c_end:
        end_fetch = st.date_input("End date", value=pd.Timestamp.today().date())

    fetch_now = st.button("Fetch data", type="primary")
    request_key = f"{ticker}|{interval}|{start_fetch}|{end_fetch}"

    if "fetched_prices" not in st.session_state:
        st.session_state["fetched_prices"] = None
    if "fetched_request_key" not in st.session_state:
        st.session_state["fetched_request_key"] = None

    if fetch_now:
        try:
            fetched = fetch_price_data_from_ticker(
                ticker=ticker,
                interval=interval,
                start_date=pd.Timestamp(start_fetch),
                end_date=pd.Timestamp(end_fetch),
            )
            st.session_state["fetched_prices"] = fetched
            st.session_state["fetched_request_key"] = request_key
        except Exception as exc:
            st.error(f"Failed to fetch ticker data: {exc}")
            st.stop()

    if st.session_state["fetched_prices"] is None:
        st.info("Select ticker/frequency/date range, then click Fetch data.")
        st.stop()

    if st.session_state["fetched_request_key"] != request_key:
        st.warning("Inputs changed. Click 'Fetch data' to refresh data for the new settings.")

    prices = st.session_state["fetched_prices"].copy()
else:
    st.session_state["fetched_prices"] = None
    st.session_state["fetched_request_key"] = None
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded is None:
        st.info("Upload a CSV to begin.")
        st.stop()

    try:
        prices = load_price_data(uploaded)
    except Exception as exc:
        st.error(f"Failed to parse file: {exc}")
        st.stop()

st.success(f"Loaded {len(prices)} rows from {prices['date'].min().date()} to {prices['date'].max().date()}.")

if "entry_marker" not in st.session_state:
    st.session_state["entry_marker"] = None
if "exit_marker" not in st.session_state:
    st.session_state["exit_marker"] = None

left, right = st.columns(2)
with left:
    st.subheader("Data preview")
    st.dataframe(prices, use_container_width=True)
with right:
    st.subheader("Price chart (close)")
    chart_placeholder = st.empty()
    chart = render_price_chart_with_markers(
        prices,
        st.session_state["entry_marker"],
        st.session_state["exit_marker"],
    )
    chart_placeholder.altair_chart(chart, use_container_width=True)

st.divider()

controls_col, results_col = st.columns([1.05, 0.95])

mode = controls_col.radio(
    "Select workflow",
    [
        "1) Given take/stop levels, find outcome date",
        "2) Given desired profit, suggest take/stop levels",
    ],
)

entry_date = controls_col.date_input(
    "Trade entry date",
    value=prices["date"].min().date(),
    min_value=prices["date"].min().date(),
    max_value=prices["date"].max().date(),
)

direction = controls_col.selectbox("Direction", ["Long", "Short"])
leverage = controls_col.number_input("Leverage", min_value=1.0, max_value=500.0, value=10.0, step=1.0)
capital = controls_col.number_input("Capital", min_value=0.0, value=1000.0, step=100.0)
max_loss_pct = 50.0
controls_col.write(f"Max allowed stop-loss (% of capital): **{max_loss_pct:.2f}%**")
controls_col.caption(
    "Stop-loss is automatically capped so loss cannot exceed 50% of your capital."
)

entry_ts = pd.Timestamp(entry_date)
entry_slice = prices[prices["date"] >= entry_ts]
entry_close = float(entry_slice.iloc[0]["close"]) if not entry_slice.empty else None
if entry_close:
    controls_col.caption(f"Entry close price used for calculations: {entry_close:.4f}")
    max_underlying_move_pct = max_loss_pct / leverage
    if direction == "Long":
        implied_stop_limit = entry_close * (1 - max_underlying_move_pct / 100)
        controls_col.caption(
            f"With leverage {leverage:.2f}, a max portfolio loss of {max_loss_pct:.2f}% "
            f"means max underlying move is {max_underlying_move_pct:.2f}%, "
            f"so lowest allowed stop-loss is {implied_stop_limit:.4f}."
        )
    else:
        implied_stop_limit = entry_close * (1 + max_underlying_move_pct / 100)
        controls_col.caption(
            f"With leverage {leverage:.2f}, a max portfolio loss of {max_loss_pct:.2f}% "
            f"means max underlying move is {max_underlying_move_pct:.2f}%, "
            f"so highest allowed stop-loss is {implied_stop_limit:.4f}."
        )

if mode.startswith("1"):
    c1, c2 = controls_col.columns(2)
    with c1:
        take_price = st.number_input("Take-profit price", min_value=0.0, value=entry_close * 1.02)
    with c2:
        stop_price = st.number_input("Stop-loss price", min_value=0.0, value=entry_close * 0.98)

    run = controls_col.button("Run simulation", type="primary")
    if run:
        st.session_state["entry_marker"] = entry_slice.iloc[0]["date"] if not entry_slice.empty else entry_ts
        stop_price_capped, was_capped = apply_max_loss_cap_to_stop(
            entry_close, stop_price, leverage, direction, max_loss_pct
        )
        result = simulate_trade(prices, entry_ts, direction, leverage, take_price, stop_price_capped)
        st.session_state["exit_marker"] = result.outcome_date if result.outcome_date is not None else None
        chart_placeholder.altair_chart(
            render_price_chart_with_markers(
                prices, st.session_state["entry_marker"], st.session_state["exit_marker"]
            ),
            use_container_width=True,
        )
        results_col.subheader("Result")
        results_col.write(f"**Outcome:** {result.outcome}")
        results_col.write(f"**Date:** {result.outcome_date.date() if result.outcome_date is not None else 'N/A'}")
        results_col.write(f"**Exit price:** {result.exit_price if result.exit_price is not None else 'N/A'}")
        results_col.write(f"**Stop-loss used after max-loss cap:** {stop_price_capped:.4f}")
        results_col.write(
            f"**Leveraged return (%):** "
            f"{result.leveraged_return_pct:.2f}%"
            if result.leveraged_return_pct is not None
            else "**Leveraged return (%):** N/A"
        )
        stop_loss_activated = result.outcome == "Stop-loss hit"
        if result.outcome in {"Take-profit hit", "Stop-loss hit"}:
            final_portfolio_value = portfolio_value_after_trade(capital, result.leveraged_return_pct)
            results_col.write(
                f"**Stop-loss activated:** {'Yes' if stop_loss_activated else 'No'}"
            )
            results_col.write(
                f"**Final portfolio value at trade close:** {final_portfolio_value:.2f}"
            )
        elif result.outcome == "Ambiguous candle":
            results_col.write("**Stop-loss activated:** Unknown (TP and SL touched in the same daily candle).")
            results_col.write("**Final portfolio value at trade close:** N/A (intraday order unknown).")
        else:
            results_col.write("**Stop-loss activated:** No (trade did not close via stop-loss).")
            results_col.write("**Final portfolio value at trade close:** N/A")
        if was_capped:
            results_col.warning(
                "Your input stop-loss exceeded the max-loss cap (50% of capital), "
                "so it was adjusted automatically."
            )
        if result.notes:
            results_col.warning(result.notes)

else:
    desired_profit = controls_col.number_input(
        "Desired profit (%) on your capital",
        min_value=0.1,
        max_value=10000.0,
        value=20.0,
        step=0.1,
    )

    run2 = controls_col.button("Suggest levels", type="primary")
    if run2:
        st.session_state["entry_marker"] = entry_slice.iloc[0]["date"] if not entry_slice.empty else entry_ts
        take, stop, hit_date, note = suggest_levels_for_desired_profit(
            prices, entry_ts, direction, leverage, desired_profit
        )

        results_col.subheader("Suggested levels")
        if take is None or stop is None or hit_date is None:
            results_col.error(note)
        else:
            stop_capped, stop_was_capped = apply_max_loss_cap_to_stop(
                entry_close, stop, leverage, direction, max_loss_pct
            )
            capped_result = simulate_trade(prices, entry_ts, direction, leverage, take, stop_capped)
            st.session_state["exit_marker"] = (
                capped_result.outcome_date if capped_result.outcome_date is not None else None
            )
            chart_placeholder.altair_chart(
                render_price_chart_with_markers(
                    prices, st.session_state["entry_marker"], st.session_state["exit_marker"]
                ),
                use_container_width=True,
            )

            results_col.write(f"**Suggested take-profit price:** {take:.4f}")
            tp_price_change_pct = ((take - entry_close) / entry_close) * 100
            if direction == "Short":
                tp_price_change_pct = -tp_price_change_pct
            tp_leveraged_return = leveraged_return(entry_close, take, leverage, direction)
            tp_money = capital * (tp_leveraged_return / 100)
            results_col.write(f"↳ Price change from entry: {tp_price_change_pct:.2f}%")
            results_col.write(f"↳ Estimated P/L on capital: {tp_money:+.2f}")

            results_col.write(f"**Suggested stop-loss price (after max-loss cap):** {stop_capped:.4f}")
            sl_price_change_pct = ((stop_capped - entry_close) / entry_close) * 100
            if direction == "Short":
                sl_price_change_pct = -sl_price_change_pct
            sl_leveraged_return = leveraged_return(entry_close, stop_capped, leverage, direction)
            sl_money = capital * (sl_leveraged_return / 100)
            results_col.write(f"↳ Price change from entry: {sl_price_change_pct:.2f}%")
            results_col.write(f"↳ Estimated P/L on capital: {sl_money:+.2f}")

            if stop_was_capped:
                results_col.warning(
                    "Stop-loss was tightened to respect the max-loss cap (50% of capital)."
                )

            results_col.write(
                f"**Outcome using capped levels (TP + capped SL):** {capped_result.outcome}"
            )
            results_col.write(
                f"**First date TP or capped SL was touched:** "
                f"{capped_result.outcome_date.date() if capped_result.outcome_date is not None else 'N/A'}"
            )
            if capped_result.outcome == "Take-profit hit":
                results_col.caption(
                    "This date is when take-profit was reached first. "
                    "Stop-loss level does not need to be touched on that day."
                )
            elif capped_result.outcome == "Stop-loss hit":
                results_col.caption(
                    "This date is when capped stop-loss was reached first."
                )
            stop_loss_activated_mode2 = capped_result.outcome == "Stop-loss hit"
            if capped_result.outcome in {"Take-profit hit", "Stop-loss hit"}:
                final_portfolio_value_mode2 = portfolio_value_after_trade(
                    capital, capped_result.leveraged_return_pct
                )
                results_col.write(
                    f"**Stop-loss activated (capped simulation):** "
                    f"{'Yes' if stop_loss_activated_mode2 else 'No'}"
                )
                results_col.write(
                    f"**Final portfolio value at trade close (capped simulation):** "
                    f"{final_portfolio_value_mode2:.2f}"
                )
            elif capped_result.outcome == "Ambiguous candle":
                results_col.write(
                    "**Stop-loss activated (capped simulation):** Unknown "
                    "(TP and SL touched in the same daily candle)."
                )
                results_col.write(
                    "**Final portfolio value at trade close (capped simulation):** "
                    "N/A (intraday order unknown)."
                )
            else:
                results_col.write("**Stop-loss activated (capped simulation):** No")
                results_col.write("**Final portfolio value at trade close (capped simulation):** N/A")
            results_col.info(note)
