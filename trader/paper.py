"""Daily paper-trading run (GitHub Actions, weekdays 10:00 New York).

  uv run python -m trader.paper [--dry-run]

1. Fetch fresh daily data and this month's point-in-time universe (trader.live.data).
2. Momentum 12-1, top 20 (the owner's pick for the paper account): rebalance the $200 paper account
   on the first run of each month, or right away if it holds nothing. Every other run only reports.
3. Forward-track all five baseline strategies as simulated $200 portfolios from TRACK_START on the
   same fresh data, so each one is judged on days after it was chosen, not on history.
4. Write a summary (printed, and to the GitHub run page).
Paper only: refuses to run in any other mode; the rebalancer also refuses any host but paper.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from trader.alpaca.client import client_from_settings
from trader.backtest import strategies as st
from trader.backtest.engine import Window, build_context, run
from trader.config import Mode, get_settings
from trader.data.universe import load_etfs
from trader.live.data import live_inputs
from trader.live.rebalance import already_ran_today, execute, plan

NY = ZoneInfo("America/New_York")
TAG = "mom"                       # client_order_id prefix for the momentum paper account
TRACK_START = date(2026, 11, 23)  # forward tracking decides at this day's close, trades from Nov 24
log = logging.getLogger("paper")


def momentum_weights(ctx, etfs: set[str], fractionable: set[str]) -> dict[str, float]:
    """Today's momentum picks, among stocks Alpaca allows as fractional shares. Dollar-amount
    orders are rejected on the others, and $10 positions need fractions (42% of tradable stocks
    aren't fractionable)."""
    i = len(ctx.days) - 1
    w = Window(ctx.days[i], ctx.days, ctx.symbols, ctx.close, ctx.open, ctx.volume,
               ctx.allowed(i) & fractionable, ctx._index)
    return st.momentum(etfs, force=True)(w) or {}


def rebalance_due(orders: list[dict], positions: list[dict], today: date) -> tuple[bool, str]:
    if not positions:
        return True, "the account holds nothing"
    ours = [o for o in orders if (o.get("client_order_id") or "").startswith(f"{TAG}-") and o.get("status") == "filled"]
    if not ours:
        return True, "no momentum rebalance on record"
    last = max(datetime.fromisoformat(o["filled_at"].replace("Z", "+00:00")).astimezone(NY).date()
               for o in ours if o.get("filled_at"))
    if (last.year, last.month) < (today.year, today.month):
        return True, f"first run of {today:%B} (last rebalance {last})"
    return False, f"already rebalanced this month ({last})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="plan orders but don't send them")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    s = get_settings()
    if s.mode is not Mode.PAPER:
        raise SystemExit("trader.paper only runs with MODE=paper")
    today = datetime.now(NY).date()
    etfs = load_etfs(s.etfs_file)
    lines = [f"# Paper run {today} ({'dry run' if args.dry_run else 'live paper orders'})", ""]

    with client_from_settings(s, allow_orders=True) as client:
        clock = client.clock()
        history, universe, assets = live_inputs(client, today, etfs, feed=s.data_feed, size=s.universe_size,
                                           min_price=s.universe_min_price, lookback=s.universe_lookback_days)
        ctx = build_context(history, universe, today - timedelta(days=400), today - timedelta(days=1))
        acct = client.account()
        positions = client.positions()
        orders = client.orders(status="all", limit=500)
        equity, cash = float(acct["equity"]), float(acct["cash"])
        lines += [f"**Paper account:** equity ${equity:.2f}, cash ${cash:.2f}, {len(positions)} positions. "
                  f"Market {'open' if clock.get('is_open') else 'closed'}.", ""]

        # ---- momentum paper account ----
        due, why = rebalance_due(orders, positions, today)
        if not clock.get("is_open") and not args.dry_run:  # a dry run still shows the plan
            lines.append(f"Momentum: market closed now, no orders ({why}).")
        elif not due:
            lines.append(f"Momentum: no rebalance today; {why}.")
        elif already_ran_today(client, TAG, today):
            lines.append("Momentum: already traded today (a second trigger), nothing sent.")
        else:
            fractionable = set(assets.filter(assets["fractionable"])["symbol"].to_list())
            weights = momentum_weights(ctx, set(etfs), fractionable)
            held = {p["symbol"]: (float(p["qty"]), float(p["current_price"])) for p in positions}
            p = plan(equity, cash, held, weights)
            lines += [f"Momentum: rebalancing ({why}). Target: {len(weights)} stocks, about "
                      f"${(equity * 0.98) / max(1, len(weights)):.2f} each.", "",
                      "| side | symbol | amount | reason |", "|---|---|---|---|"]
            lines += [f"| {o.side} | {o.symbol} | {'all' if o.close_all else (o.qty if o.qty else f'${o.notional:.2f}')} | {o.reason} |"
                      for o in p.sells + p.buys]
            lines += [f"- skipped: {x}" for x in p.skipped]
            sent = execute(client, p, tag=TAG, day=today, dry_run=args.dry_run, log=log.info)
            lines.append(f"\n{'Planned' if args.dry_run else 'Sent'} {len(p.sells) + len(p.buys) if args.dry_run else len(sent)} orders.")

    # ---- forward tracking of every baseline from TRACK_START ----
    first = next((k for k, d in enumerate(ctx.days) if d >= TRACK_START), None)
    lines += ["", f"## Simulated forward tracking since {TRACK_START} ($200 each, 5 bps costs)", ""]
    if first is None or first >= len(ctx.days) - 1:
        lines.append("Not enough trading days since the start yet.")
    else:
        e = set(etfs)
        plans = {"SPY (benchmark)": st.buy_hold("SPY", also_on=TRACK_START),
                 "momentum 12-1 (paper account)": st.momentum(e, also_on=TRACK_START),
                 "reversal 5d": st.reversal(e, also_on=TRACK_START),
                 "low vol 60d": st.low_vol(e, also_on=TRACK_START),
                 "trend ETFs 200d": st.trend_etfs(e, also_on=TRACK_START)}
        lines += ["| strategy | value | return |", "|---|---|---|"]
        for name, f in plans.items():
            r = run(ctx, f, name, capital=200.0, cost_bps=5.0, start_index=first)
            v = float(r.equity[-1])
            lines.append(f"| {name} | ${v:.2f} | {v / 200 - 1:+.1%} |")
        lines.append(f"\nThrough the close of {ctx.days[-1]}. Simulated fills at the next open; the paper account's "
                     "real fills differ slightly.")

    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    main()
