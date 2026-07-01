"""
Fleet-Scorecard — FastAPI backend
Read-only against external APIs and Supabase.
"""
import asyncio
import os
import pathlib
import time
from datetime import datetime, date, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# ─────────────────────────── config ───────────────────────────
ET = ZoneInfo("America/New_York")

SCORECARD_PASSWORD = os.environ.get("SCORECARD_PASSWORD", "")
SCORECARD_SECRET   = os.environ.get("SCORECARD_SECRET") or SCORECARD_PASSWORD
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY       = os.environ.get("SUPABASE_KEY", "")
PORT               = int(os.environ.get("PORT", "8000"))

HL_STATE_URL   = "https://bounce-scanner-deux-production-88de.up.railway.app/api/state"
MEXC_STATE_URL = "https://web-production-d03dd.up.railway.app/api/state"

COOKIE_NAME     = "aria_session"
SESSION_MAX_AGE = 30 * 24 * 3600  # 30 days

# ─────────────────────────── live-state cache ───────────────────────────
_live: dict[str, Any] = {
    "hl": None, "mexc": None,
    "hl_ok": False, "mexc_ok": False,
    "updated_at": 0.0,
}

# ─────────────────────────── app & signer ───────────────────────────
app = FastAPI(docs_url=None, redoc_url=None)
signer = URLSafeTimedSerializer(SCORECARD_SECRET or "no-secret-set")

STATIC_DIR = pathlib.Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─────────────────────────── auth ───────────────────────────
def _is_authed(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        signer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False

def _require_auth(request: Request) -> None:
    if not _is_authed(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

# ─────────────────────────── live-state poller ───────────────────────────
async def _poll_live() -> None:
    while True:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for key, url in [("hl", HL_STATE_URL), ("mexc", MEXC_STATE_URL)]:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    data = r.json()
                    _live[key] = data
                    _live[f"{key}_ok"] = True
                    ps = data.get("pair_states", [])
                    ot = data.get("open_trades", {})
                    n_ps = len(ps) if isinstance(ps, list) else f"type={type(ps).__name__}"
                    n_ot = len(ot) if isinstance(ot, (dict, list)) else f"type={type(ot).__name__}"
                    print(
                        f"[LIVE] {key.upper()} OK — pair_states={n_ps} items, "
                        f"open_trades={n_ot}, daily_pnl={data.get('daily', {}).get('pnl')}",
                        flush=True,
                    )
                    if isinstance(ps, list) and ps:
                        sample = ps[0]
                        print(
                            f"[LIVE] {key.upper()} sample pair: symbol={sample.get('symbol')} "
                            f"j15m={sample.get('j15m')} j1h={sample.get('j1h')} in_trade={sample.get('in_trade')}",
                            flush=True,
                        )
                    else:
                        print(f"[LIVE] {key.upper()} WARNING — pair_states is empty or wrong type: {type(ps).__name__}", flush=True)
                except Exception as exc:
                    _live[f"{key}_ok"] = False
                    print(f"[LIVE] {key.upper()} ERROR — {exc}", flush=True)
        _live["updated_at"] = time.time()
        await asyncio.sleep(30)

@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(_poll_live())

# ─────────────────────────── Supabase helper ───────────────────────────
async def _sb_fetch(table: str, extra_params: Optional[dict] = None) -> list:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=none",
    }
    params: dict = {"select": "*"}
    if extra_params:
        params.update(extra_params)
    async with httpx.AsyncClient(timeout=25.0) as client:
        try:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                params=params,
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception:
            return []

# ─────────────────────────── type helpers ───────────────────────────
def _f(val: Any) -> Optional[float]:
    """Safe float cast."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

def _to_et(val: Any) -> Optional[datetime]:
    if not val:
        return None
    try:
        s = str(val).strip()
        if not s.endswith(("Z", "+00:00")) and "+" not in s[10:] and "-" not in s[10:]:
            s += "+00:00"
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s).astimezone(ET)
    except Exception:
        return None

def _et_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=ET)

def _range_start(range_key: str) -> Optional[datetime]:
    now = datetime.now(ET)
    if range_key == "today":
        return _et_midnight(now.date())
    if range_key == "week":
        return _et_midnight((now - timedelta(days=6)).date())
    return None

# ─────────────────────────── analytics computation ───────────────────────────
def _filter_by_range(rows: list, start: Optional[datetime]) -> list:
    if start is None:
        return list(rows)
    out = []
    for r in rows:
        ct = _to_et(r.get("close_time"))
        if ct and ct >= start:
            out.append(r)
    return out

TERMINAL_REASONS: frozenset = frozenset({"TRAILBLAZER", "TRAIL", "SL", "MANUAL", "PEAK_DECAY_20", "RUNNER_DECAY_10", "ADVERSE_CUT"})


def _group_logical_trades(rows: list) -> tuple[list, list]:
    """Return (terminal_rows, all_pnl_rows).

    Groups rows by (pair, direction, open_time).  For each group the
    *terminal* row is whichever one has an exit_reason in TERMINAL_REASONS
    (i.e. the final close, not a TP1 partial).  If no terminal row is found
    the last row by close_time is used as fallback.  Single-row groups pass
    through unchanged.

    terminal_rows -- one per logical trade, used for trade_count / win_rate.
    all_pnl_rows  -- every row with non-null pnl_dollars, used for PnL sums.
    """
    groups: dict[tuple, list] = {}
    for r in rows:
        pair = r.get("pair") or r.get("symbol") or ""
        dr   = str(r.get("direction") or "").upper()
        ot   = str(r.get("open_time") or "")
        groups.setdefault((pair, dr, ot), []).append(r)

    terminal_rows: list = []
    for grp in groups.values():
        if len(grp) == 1:
            if _f(grp[0].get("pnl_dollars")) is not None:
                terminal_rows.append(grp[0])
        else:
            terminal = [r for r in grp
                        if str(r.get("exit_reason") or "").upper() in TERMINAL_REASONS]
            if terminal:
                terminal.sort(key=lambda r: str(r.get("close_time") or ""))
                chosen = terminal[-1]
            else:
                chosen = sorted(grp, key=lambda r: str(r.get("close_time") or ""))[-1]
            if _f(chosen.get("pnl_dollars")) is not None:
                terminal_rows.append(chosen)

    all_pnl_rows = [r for r in rows if _f(r.get("pnl_dollars")) is not None]
    return terminal_rows, all_pnl_rows


def _venue_metrics(rows: list) -> dict:
    # Group by logical trade (pair+direction+open_time) so TP1 partial-close
    # rows are NOT counted as separate trades.  PnL sum still uses all rows.
    terminal_rows, all_pnl_rows = _group_logical_trades(rows)

    # Dollar totals -- include TP1 partials + final closes
    all_pnls     = [_f(r.get("pnl_dollars")) for r in all_pnl_rows]
    gross_profit = sum(p for p in all_pnls if p > 0)
    gross_loss   = abs(sum(p for p in all_pnls if p <= 0))
    pf = gross_profit / gross_loss if gross_loss else (999.0 if gross_profit else 0.0)

    # Trade counts / win-rate -- one entry per logical trade (terminal row)
    t_pnls = [_f(r.get("pnl_dollars")) for r in terminal_rows]
    wins   = [p for p in t_pnls if p > 0]
    losses = [p for p in t_pnls if p <= 0]
    wr     = len(wins) / len(t_pnls) if t_pnls else 0.0

    r_vals  = [v for v in (_f(r.get("r_value")) for r in rows) if v is not None]
    avg_r   = sum(r_vals) / len(r_vals) if r_vals else 0.0

    pair_pnl: dict[str, float] = {}
    for r in rows:
        pair = r.get("pair") or r.get("symbol") or "UNKNOWN"
        p = _f(r.get("pnl_dollars"))
        if p is not None:
            pair_pnl[pair] = pair_pnl.get(pair, 0.0) + p
    best_pair  = max(pair_pnl, key=pair_pnl.__getitem__) if pair_pnl else None
    worst_pair = min(pair_pnl, key=pair_pnl.__getitem__) if pair_pnl else None

    holds = [ds / 3600 for r in rows if (ds := _f(r.get("duration_seconds"))) is not None]
    avg_hold = sum(holds) / len(holds) if holds else 0.0

    runner_r = [v for r in rows
                if str(r.get("exit_reason", "")).upper() in ("TRAILBLAZER", "TRAIL", "RUNNER_DECAY_10")
                if (v := _f(r.get("r_value"))) is not None]
    avg_runner_r = sum(runner_r) / len(runner_r) if runner_r else None

    return {
        "pnl": round(sum(all_pnls), 2),
        "trade_count": len(t_pnls),
        "win_rate": round(wr, 4),
        "profit_factor": round(min(pf, 999.0), 2),
        "avg_r": round(avg_r, 3),
        "best_pair": best_pair,
        "worst_pair": worst_pair,
        "avg_hold_hours": round(avg_hold, 2),
        "avg_runner_r": round(avg_runner_r, 3) if avg_runner_r is not None else None,
        "open_count": None,
        "unrealized_pnl": None,
    }

def _base_pair(pair: str) -> str:
    return str(pair or "").upper().replace("_USDT", "").replace("USDT", "").replace("/USDT", "")

def _compute_twins(hl_rows: list, mexc_rows: list) -> tuple[list, float]:
    hl_map: dict[tuple, list]   = {}
    mx_map: dict[tuple, list]   = {}
    for r in hl_rows:
        bp  = _base_pair(r.get("pair") or r.get("symbol", ""))
        dr  = str(r.get("direction", "")).upper()
        ot  = _to_et(r.get("open_time"))
        if bp and dr and ot:
            hl_map.setdefault((bp, dr), []).append((ot, r))
    for r in mexc_rows:
        bp  = _base_pair(r.get("pair") or r.get("symbol", ""))
        dr  = str(r.get("direction", "")).upper()
        ot  = _to_et(r.get("open_time"))
        if bp and dr and ot:
            mx_map.setdefault((bp, dr), []).append((ot, r))

    twins: list[dict] = []
    for key in set(hl_map) & set(mx_map):
        bp, direction = key
        for hl_ot, hl_r in hl_map[key]:
            for mx_ot, mx_r in mx_map[key]:
                if abs((hl_ot - mx_ot).total_seconds()) <= 1800:
                    hl_pnl = _f(hl_r.get("pnl_dollars")) or 0.0
                    mx_pnl = _f(mx_r.get("pnl_dollars")) or 0.0
                    hl_rv  = _f(hl_r.get("r_value"))  or 0.0
                    mx_rv  = _f(mx_r.get("r_value"))  or 0.0
                    edge   = (f"HL +{round(hl_rv - mx_rv, 1)}" if hl_rv >= mx_rv
                              else f"MEXC +{round(mx_rv - hl_rv, 1)}")
                    twins.append({
                        "base_pair": bp,
                        "direction": direction,
                        "hl_pnl":  round(hl_pnl, 2),
                        "mexc_pnl": round(mx_pnl, 2),
                        "hl_r":    round(hl_rv, 2),
                        "mexc_r":  round(mx_rv, 2),
                        "edge":    edge,
                    })
    twins.sort(key=lambda t: t["base_pair"])
    venue_edge = round(sum(t["hl_pnl"] - t["mexc_pnl"] for t in twins), 2)
    return twins, venue_edge

def _compute_sessions(all_rows: list) -> list:
    SESSIONS = ["ASIA", "EU", "US", "OFF"]
    SESSION_MAP = {
        "ASIA_EARLY": "ASIA", "ASIA_LATE": "ASIA",
        "LONDON": "EU", "NY": "US", "NEW_YORK": "US", "NEWYORK": "US",
    }
    data: dict[str, dict] = {s: {"lp": 0.0, "sp": 0.0, "lt": 0, "st": 0, "lw": 0, "sw": 0}
                              for s in SESSIONS}
    terminal_rows, all_pnl_rows = _group_logical_trades(all_rows)
    # PnL sums -- include all rows (TP1 partials + final closes)
    for r in all_pnl_rows:
        sess = str(r.get("session_opened") or r.get("session") or "").upper().strip()
        sess = SESSION_MAP.get(sess, sess)
        if sess not in data:
            sess = "OFF"
        dr  = str(r.get("direction", "")).upper()
        pnl = _f(r.get("pnl_dollars"))
        if pnl is None:
            continue
        if dr == "LONG":
            data[sess]["lp"] += pnl
        elif dr == "SHORT":
            data[sess]["sp"] += pnl
    # Trade counts / win-rate -- one per logical trade (terminal row only)
    for r in terminal_rows:
        sess = str(r.get("session_opened") or r.get("session") or "").upper().strip()
        sess = SESSION_MAP.get(sess, sess)
        if sess not in data:
            sess = "OFF"
        dr  = str(r.get("direction", "")).upper()
        pnl = _f(r.get("pnl_dollars"))
        if pnl is None:
            continue
        if dr == "LONG":
            data[sess]["lt"] += 1
            if pnl > 0: data[sess]["lw"] += 1
        elif dr == "SHORT":
            data[sess]["st"] += 1
            if pnl > 0: data[sess]["sw"] += 1
    return [
        {
            "session": s,
            "long_pnl":    round(data[s]["lp"], 2),
            "short_pnl":   round(data[s]["sp"], 2),
            "long_trades":  data[s]["lt"],
            "short_trades": data[s]["st"],
            "long_wr":  round(data[s]["lw"] / data[s]["lt"], 3) if data[s]["lt"] else None,
            "short_wr": round(data[s]["sw"] / data[s]["st"], 3) if data[s]["st"] else None,
        }
        for s in SESSIONS
    ]

def _compute_pair_league(all_rows: list) -> list:
    stats: dict[str, dict] = {}
    terminal_rows, all_pnl_rows = _group_logical_trades(all_rows)
    _empty = {"pnl": 0.0, "count": 0, "r_sum": 0.0, "r_n": 0,
              "dur_sum": 0.0, "dur_n": 0,
              "dur_w_sum": 0.0, "dur_w_n": 0,
              "dur_l_sum": 0.0, "dur_l_n": 0}
    # PnL sums and avg_r -- include all rows (TP1 partials + final closes)
    for r in all_pnl_rows:
        pair = r.get("pair") or r.get("symbol") or "UNKNOWN"
        pnl  = _f(r.get("pnl_dollars"))
        rv   = _f(r.get("r_value"))
        if pnl is None:
            continue
        s = stats.setdefault(pair, dict(_empty))
        s["pnl"] += pnl
        if rv is not None:
            s["r_sum"] += rv; s["r_n"] += 1
    # Trade count + duration -- one per logical trade (terminal row only)
    for r in terminal_rows:
        pair = r.get("pair") or r.get("symbol") or "UNKNOWN"
        pnl  = _f(r.get("pnl_dollars"))
        if pnl is None:
            continue
        s = stats.setdefault(pair, dict(_empty))
        s["count"] += 1
        ds = _f(r.get("duration_seconds"))
        if ds is not None:
            s["dur_sum"] += ds; s["dur_n"] += 1
            if pnl > 0:
                s["dur_w_sum"] += ds; s["dur_w_n"] += 1
            else:
                s["dur_l_sum"] += ds; s["dur_l_n"] += 1
    def _avg(sm, n): return round(sm / n) if n else None
    return sorted(
        [{"pair": p, "pnl": round(v["pnl"], 2), "trade_count": v["count"],
          "avg_r":                    round(v["r_sum"] / v["r_n"], 3) if v["r_n"] else None,
          "avg_duration_sec":         _avg(v["dur_sum"],   v["dur_n"]),
          "avg_duration_sec_winners": _avg(v["dur_w_sum"], v["dur_w_n"]),
          "avg_duration_sec_losers":  _avg(v["dur_l_sum"], v["dur_l_n"])}
         for p, v in stats.items()],
        key=lambda x: x["pnl"], reverse=True,
    )

def _compute_excursion(all_rows: list) -> dict:
    valid   = [r for r in all_rows if _f(r.get("mae_r")) is not None]
    skipped = len(all_rows) - len(valid)

    winners_mae = [_f(r["mae_r"]) for r in valid if (_f(r.get("pnl_dollars")) or 0) > 0]  # type: ignore[arg-type]
    losers_mae  = [_f(r["mae_r"]) for r in valid if (_f(r.get("pnl_dollars")) or 0) <= 0]  # type: ignore[arg-type]
    avg_win_mae = (sum(winners_mae) / len(winners_mae)) if winners_mae else None
    avg_los_mae = (sum(losers_mae)  / len(losers_mae))  if losers_mae  else None

    mfe_caps: list[float] = []
    for r in all_rows:
        rv   = _f(r.get("r_value"))
        mfev = _f(r.get("mfe_r"))
        if rv is not None and mfev and mfev > 0 and str(r.get("exit_reason", "")).upper() in ("TRAILBLAZER", "TRAIL", "RUNNER_DECAY_10"):
            mfe_caps.append(rv / mfev)
    avg_mfe = (sum(mfe_caps) / len(mfe_caps)) if mfe_caps else None

    deep_mae_winners = [r for r in valid
                        if (_f(r.get("pnl_dollars")) or 0) > 0
                        and (_f(r.get("mae_r")) or 0) <= -0.5]

    forgone_rows = deep_mae_winners
    losing_rows  = [r for r in valid if (_f(r.get("pnl_dollars")) or 0) <= 0]

    forgone = sum(_f(r.get("pnl_dollars")) or 0 for r in forgone_rows)
    saved   = 0.0
    for r in losing_rows:
        pnl = _f(r.get("pnl_dollars")) or 0.0
        rv  = _f(r.get("r_value"))
        if rv and rv != 0:
            one_r = abs(pnl / rv)
            saved += abs(pnl) - 0.5 * one_r
        else:
            saved += abs(pnl) * 0.5
    net = saved - forgone

    return {
        "winners_avg_mae":     round(avg_win_mae, 3) if avg_win_mae is not None else None,
        "losers_avg_mae":      round(avg_los_mae, 3) if avg_los_mae  is not None else None,
        "avg_mfe_capture":     round(avg_mfe, 3)     if avg_mfe      is not None else None,
        "deep_mae_winner_count": len(deep_mae_winners),
        "forgone": round(forgone, 2),
        "saved":   round(saved, 2),
        "net":     round(net, 2),
        "verdict": "HOLD" if net <= 0 else "SHIP",
        "skipped": skipped,
    }



# ─────────────────────────── sentinel coverage ───────────────────────────

SENTINEL_RETIRED_PAIRS: dict[str, list[str]] = {
    "hl":   ["HYPE", "LINK", "ZEC"],
    "mexc": ["ZEC_USDT", "XAUT_USDT"],
}
SENTINEL_LIVE_ACTION: dict[str, list[str]] = {
    "hl":   ["NEAR"],
    "mexc": ["NEAR_USDT"],
}


def _compute_sentinel_coverage(hl_rows: list, mexc_rows: list) -> dict:
    """
    Classify non-retired pairs by sentinel eligibility tier.
    Gate: mfe_r >= 0.5 (trade showed meaningful upside).
    Banked  = terminal pnl > 0
    Bleeder = terminal pnl <= 0

    T1: bleeder_n >= 2 AND bleeder_pnl <= -100 AND avg_dur_bleeder <= avg_dur_banked
    T2: bleeder_n >= 1 AND avg_dur_bleeder > avg_dur_banked
    T3: everything else
    """
    venue_pair_rows: dict[tuple, list] = {}
    for venue, rows in [("hl", hl_rows), ("mexc", mexc_rows)]:
        retired  = set(SENTINEL_RETIRED_PAIRS.get(venue, []))
        tagged   = [{**r, "_venue": venue} for r in rows]
        terminal_rows, _ = _group_logical_trades(tagged)
        for r in terminal_rows:
            pair = r.get("pair") or r.get("symbol") or "UNKNOWN"
            if pair in retired:
                continue
            venue_pair_rows.setdefault((venue, pair), []).append(r)

    results: list[dict] = []
    for (venue, pair), rows in sorted(venue_pair_rows.items()):
        qualifying = [r for r in rows if (_f(r.get("mfe_r")) or 0.0) >= 0.5]
        q_n = len(qualifying)
        if q_n == 0:
            results.append({
                "venue": venue, "pair": pair,
                "qualifying_trades": 0,
                "banked_n": 0, "bleeder_n": 0,
                "banked_pnl": 0.0, "bleeder_pnl": 0.0,
                "avg_duration_min_banked": None,
                "avg_duration_min_bleeder": None,
                "tier": 3,
                "live_action": pair in SENTINEL_LIVE_ACTION.get(venue, []),
            })
            continue

        banked  = [r for r in qualifying if (_f(r.get("pnl_dollars")) or 0) > 0]
        bleeder = [r for r in qualifying if (_f(r.get("pnl_dollars")) or 0) <= 0]

        def _avg_dur_min(rr: list) -> Optional[float]:
            durs = [_f(r.get("duration_seconds")) for r in rr]
            durs = [d for d in durs if d is not None]
            if not durs:
                return None
            return round(sum(durs) / len(durs) / 60.0, 1)

        avg_dur_b   = _avg_dur_min(banked)
        avg_dur_l   = _avg_dur_min(bleeder)
        banked_pnl  = round(sum(_f(r.get("pnl_dollars")) or 0 for r in banked),  2)
        bleeder_pnl = round(sum(_f(r.get("pnl_dollars")) or 0 for r in bleeder), 2)

        if (len(bleeder) >= 2 and bleeder_pnl <= -100
                and avg_dur_l is not None and avg_dur_b is not None
                and avg_dur_l <= avg_dur_b):
            tier = 1
        elif (len(bleeder) >= 1
              and avg_dur_l is not None and avg_dur_b is not None
              and avg_dur_l > avg_dur_b):
            tier = 2
        else:
            tier = 3

        results.append({
            "venue": venue, "pair": pair,
            "qualifying_trades": q_n,
            "banked_n": len(banked), "bleeder_n": len(bleeder),
            "banked_pnl": banked_pnl, "bleeder_pnl": bleeder_pnl,
            "avg_duration_min_banked":  avg_dur_b,
            "avg_duration_min_bleeder": avg_dur_l,
            "tier": tier,
            "live_action": pair in SENTINEL_LIVE_ACTION.get(venue, []),
        })

    t1 = [r for r in results if r["tier"] == 1]
    t2 = [r for r in results if r["tier"] == 2]
    t3 = [r for r in results if r["tier"] == 3]
    return {
        "tier1_count": len(t1),
        "tier2_count": len(t2),
        "tier3_count": len(t3),
        "pairs": results,
    }


def _live_open(state: Any) -> Optional[int]:
    if not state or not isinstance(state, dict):
        return None
    ot = state.get("open_trades")
    if isinstance(ot, dict):
        return len(ot)
    if isinstance(ot, list):
        return len(ot)
    ps = state.get("pair_states")
    if isinstance(ps, list):
        return sum(1 for p in ps if isinstance(p, dict) and p.get("in_trade"))
    return 0

def _live_unrealized(state: Any) -> Optional[float]:
    if not state or not isinstance(state, dict):
        return None
    for key in ("unrealized_pnl", "unrealizedPnl", "open_pnl", "unrealized"):
        v = _f(state.get(key))
        if v is not None:
            return v
    return None

def _compute_analytics(hl_rows: list, mexc_rows: list, range_key: str) -> dict:
    start = _range_start(range_key)
    hl    = _filter_by_range(hl_rows,   start)
    mexc  = _filter_by_range(mexc_rows, start)
    all_r = [{"_venue": "hl",   **r} for r in hl] + \
            [{"_venue": "mexc", **r} for r in mexc]

    fleet_m = _venue_metrics(all_r)
    hl_m    = _venue_metrics(hl)
    mexc_m  = _venue_metrics(mexc)

    def _distinct(rows: list, direction: str) -> int:
        return len({r.get("pair") or r.get("symbol") or ""
                    for r in rows if str(r.get("direction", "")).upper() == direction})

    twins, venue_edge = _compute_twins(hl, mexc)

    fleet_m["long_count"]    = sum(1 for r in all_r if str(r.get("direction", "")).upper() == "LONG")
    fleet_m["short_count"]   = sum(1 for r in all_r if str(r.get("direction", "")).upper() == "SHORT")
    fleet_m["long_distinct"] = _distinct(all_r, "LONG")
    fleet_m["short_distinct"]= _distinct(all_r, "SHORT")
    fleet_m["daily_target"]  = 1000

    # MTD and YTD P&L from all unfiltered rows
    _now_et = datetime.now(ET)
    _mtd_start = _et_midnight(_now_et.date().replace(day=1))
    _ytd_start = _et_midnight(_now_et.date().replace(month=1, day=1))
    _all_raw = list(hl_rows) + list(mexc_rows)
    _mtd_pnl = 0.0
    _ytd_pnl = 0.0
    for _r in _all_raw:
        _ct = _to_et(_r.get("close_time"))
        if _ct is None:
            continue
        _pnl = _f(_r.get("pnl_dollars"))
        if _pnl is None:
            continue
        if _ct >= _mtd_start:
            _mtd_pnl += _pnl
        if _ct >= _ytd_start:
            _ytd_pnl += _pnl
    mtd_pnl = round(_mtd_pnl, 2)
    ytd_pnl = round(_ytd_pnl, 2)

    return {
        "range":       range_key,
        "fleet":       fleet_m,
        "hl":          hl_m,
        "mexc":        mexc_m,
        "twins":       twins,
        "twin_count":  len(twins),
        "venue_edge":  venue_edge,
        "sessions":    _compute_sessions(all_r),
        "pair_league": _compute_pair_league(
            [{"_venue": "hl",   **r} for r in hl_rows] +
            [{"_venue": "mexc", **r} for r in mexc_rows]
        ),
        "excursion":   _compute_excursion(all_r),
        "row_counts":  {"hl": len(hl_rows), "mexc": len(mexc_rows)},
        "mtd_pnl":     mtd_pnl,
        "ytd_pnl":     ytd_pnl,
    }

# ─────────────────────────── login HTML ───────────────────────────
def _login_html(error: str = "") -> str:
    err_line = f'<p class="err">{error}</p>' if error else '<p class="err">&nbsp;</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FLEET SCORECARD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%}}
body{{background:#000;color:#fff;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;min-height:100vh;padding:16px}}
.wrap{{width:100%;max-width:320px;text-align:center}}
h1{{font-family:'Bebas Neue',sans-serif;font-size:2.8rem;letter-spacing:.12em;line-height:1}}
.sub{{font-size:.65rem;color:#444;letter-spacing:.2em;margin:.4em 0 2.5rem;text-transform:uppercase}}
input[type=password]{{width:100%;background:#050505;border:1px solid #1c1c1c;color:#fff;padding:.85em 1em;font-family:'JetBrains Mono',monospace;font-size:.95rem;text-align:center;outline:none;letter-spacing:.2em;-webkit-appearance:none;border-radius:0}}
input[type=password]:focus{{border-color:#b388ff44}}
button{{margin-top:.6em;width:100%;background:#0a0a0a;border:1px solid #222;color:#fff;padding:.85em;font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.2em;cursor:pointer;border-radius:0;-webkit-appearance:none}}
button:active{{background:#141414}}
.err{{font-size:.72rem;color:#ff4d4d;margin-top:.8em;min-height:1.1em;letter-spacing:.05em}}
</style>
</head>
<body>
<div class="wrap">
  <h1>FLEET SCORECARD</h1>
  <div class="sub">Scorecard Access</div>
  <form method="POST" action="/login" autocomplete="off">
    <input type="password" name="password" placeholder="PASSWORD" autofocus autocomplete="current-password">
    <button type="submit">ENTER</button>
    {err_line}
  </form>
</div>
</body>
</html>"""

# ─────────────────────────── routes ───────────────────────────
@app.get("/")
async def root(request: Request) -> HTMLResponse:
    if not _is_authed(request):
        return HTMLResponse(_login_html())
    html = (STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)

@app.post("/login", response_model=None)
async def login(request: Request):
    form = await request.form()
    pw   = str(form.get("password", ""))
    if not SCORECARD_PASSWORD or pw != SCORECARD_PASSWORD:
        return HTMLResponse(_login_html("Invalid password"))
    token = signer.dumps("ok")
    resp  = RedirectResponse(url="/", status_code=303)
    resp.set_cookie(
        COOKIE_NAME, token,
        httponly=True, max_age=SESSION_MAX_AGE, samesite="lax", secure=False,
    )
    return resp

@app.post("/logout")
async def logout() -> RedirectResponse:
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp

@app.get("/api/live")
async def api_live(request: Request) -> JSONResponse:
    _require_auth(request)
    return JSONResponse({
        "hl":         _live["hl"],
        "mexc":       _live["mexc"],
        "hl_ok":      _live["hl_ok"],
        "mexc_ok":    _live["mexc_ok"],
        "updated_at": _live["updated_at"],
    })

@app.get("/api/analytics")
async def api_analytics(request: Request, range: str = "today") -> JSONResponse:
    _require_auth(request)
    if range not in ("today", "week", "all"):
        raise HTTPException(400, "range must be: today | week | all")
    hl_rows, mexc_rows = await asyncio.gather(
        _sb_fetch("hl_trade_log"),
        _sb_fetch("mexc_trade_log"),
    )
    data = _compute_analytics(hl_rows, mexc_rows, range)
    data["hl"]["open_count"]       = _live_open(_live["hl"])
    data["hl"]["unrealized_pnl"]   = _live_unrealized(_live["hl"])
    data["mexc"]["open_count"]     = _live_open(_live["mexc"])
    data["mexc"]["unrealized_pnl"] = _live_unrealized(_live["mexc"])
    return JSONResponse(data)

@app.get("/api/log")
async def api_log(
    request: Request,
    range: str = "all",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> JSONResponse:
    _require_auth(request)
    hl_rows, mexc_rows = await asyncio.gather(
        _sb_fetch("hl_trade_log",   {"order": "close_time.desc", "limit": "2000"}),
        _sb_fetch("mexc_trade_log", {"order": "close_time.desc", "limit": "2000"}),
    )
    if from_date and to_date:
        try:
            start = _et_midnight(date.fromisoformat(from_date))
            end   = _et_midnight(date.fromisoformat(to_date)) + timedelta(days=1)
        except ValueError:
            raise HTTPException(400, "Invalid date format; use YYYY-MM-DD")
        def _in_range(r: dict) -> bool:
            ct = _to_et(r.get("close_time"))
            return bool(ct and start <= ct < end)
        hl_f   = [r for r in hl_rows   if _in_range(r)]
        mexc_f = [r for r in mexc_rows if _in_range(r)]
    else:
        if range not in ("today", "week", "all"):
            raise HTTPException(400, "range must be: today | week | all")
        start_r = _range_start(range)
        hl_f    = _filter_by_range(hl_rows,   start_r)
        mexc_f  = _filter_by_range(mexc_rows, start_r)
    all_rows = (
        [{"_venue": "hl",   **r} for r in hl_f   if r.get("close_time")]
      + [{"_venue": "mexc", **r} for r in mexc_f if r.get("close_time")]
    )
    all_rows.sort(key=lambda r: str(r.get("close_time") or ""), reverse=True)
    return JSONResponse(all_rows)

@app.get("/api/schema")
async def api_schema(request: Request) -> JSONResponse:
    _require_auth(request)
    hl_s, mx_s = await asyncio.gather(
        _sb_fetch("hl_trade_log",  {"limit": "1"}),
        _sb_fetch("mexc_trade_log", {"limit": "1"}),
    )
    return JSONResponse({
        "hl_columns":   sorted(hl_s[0].keys())  if hl_s  else [],
        "mexc_columns": sorted(mx_s[0].keys())  if mx_s  else [],
    })


# ─────────────────────────── reconstruct helpers ───────────────────────────

HL_API_URL      = "https://api.hyperliquid.xyz/info"
MEXC_KLINE_BASE = "https://contract.mexc.com/api/v1/contract/kline"

# HL internal-symbol -> API coin name (add new pairs here as discovered)
HL_COIN_MAP: dict[str, str] = {
    "@107": "HYPE",
}


def _hl_coin(pair: str) -> str:
    return HL_COIN_MAP.get(pair, pair)


def _rl_price(entry: float, sl: float, r: float, direction: str) -> float:
    if direction.upper() == "LONG":
        return entry + r * (entry - sl)
    return entry - r * (sl - entry)


async def _fetch_hl_candles_1m(coin: str, start_ms: int, end_ms: int) -> list[dict]:
    payload = {"type": "candleSnapshot", "req": {"coin": coin, "interval": "1m",
               "startTime": start_ms, "endTime": end_ms}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(HL_API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                return []
            candles: list[dict] = []
            for c in data:
                if isinstance(c, (list, tuple)) and len(c) >= 5:
                    candles.append({"time_ms": int(c[0]),
                                    "high": float(c[2]), "low": float(c[3])})
                elif isinstance(c, dict):
                    t = c.get("t") or c.get("T") or c.get("time") or 0
                    candles.append({"time_ms": int(t),
                                    "high": float(c.get("h") or c.get("high") or 0),
                                    "low":  float(c.get("l") or c.get("low")  or 0)})
            return sorted(candles, key=lambda x: x["time_ms"])
        except Exception as exc:
            print(f"[RECONSTRUCT] HL candle error: {exc}")
            return []


async def _fetch_mexc_candles_1m(symbol: str, start_s: int, end_s: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(f"{MEXC_KLINE_BASE}/{symbol}",
                                    params={"interval": "Min1", "start": start_s, "end": end_s})
            resp.raise_for_status()
            d = resp.json().get("data") or {}
            times = d.get("time", []);  highs = d.get("high", []);  lows = d.get("low", [])
            candles = [{"time_ms": int(times[i]) * 1000,
                        "high": float(highs[i]), "low": float(lows[i])}
                       for i in range(min(len(times), len(highs), len(lows)))]
            return sorted(candles, key=lambda x: x["time_ms"])
        except Exception as exc:
            print(f"[RECONSTRUCT] MEXC candle error: {exc}")
            return []


def _find_crossing(candles: list[dict], target: float, up: bool,
                   sl_dist: float, after_ms: int = 0) -> Optional[dict]:
    """Find first candle after after_ms where price comes within 0.15R of target.
    up=True  -> looking for HIGH >= target - gap  (adverse SHORT / favorable LONG).
    up=False -> looking for LOW  <= target + gap  (adverse LONG  / favorable SHORT).
    Returns dict with time_ms, gap_r, tag (confirmed | near-miss), or None.
    """
    gap_price = 0.15 * sl_dist
    for c in candles:
        if c["time_ms"] < after_ms:
            continue
        if up:
            boundary = c["high"]
            dist = target - boundary           # <= 0 if crossed
        else:
            boundary = c["low"]
            dist = boundary - target           # <= 0 if crossed
        if dist <= gap_price:
            gap_r = max(dist, 0.0) / sl_dist if sl_dist > 0 else 0.0
            return {
                "time_ms":  c["time_ms"],
                "boundary": round(boundary, 8),
                "gap_r":    round(gap_r, 4),
                "tag":      "confirmed" if dist <= 0 else "near-miss",
            }
    return None


def _parse_open_utc(ts_str: str) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        s = str(ts_str).strip().replace("Z", "+00:00")
        if "+" not in s[10:] and "-" not in s[10:]:
            s += "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None


# ─────────────────────────── reconstruct endpoints ───────────────────────────

@app.get("/api/reconstruct/shortlist")
async def api_reconstruct_shortlist(
    request: Request,
    venue:       str   = "all",
    exit_reason: str   = "all",
    from_date:   Optional[str]   = Query(None, alias="from"),
    to:          Optional[str]   = None,
    min_mae:     float = 0.0,
    min_mfe:     float = 0.0,
) -> JSONResponse:
    _require_auth(request)

    hl_rows   = await _sb_fetch("hl_trade_log",   {"order": "close_time.desc", "limit": "1000"}) if venue in ("all", "hl")   else []
    mexc_rows = await _sb_fetch("mexc_trade_log", {"order": "close_time.desc", "limit": "1000"}) if venue in ("all", "mexc") else []
    rows = ([{"_venue": "hl",   **r} for r in hl_rows   if r.get("close_time")] +
            [{"_venue": "mexc", **r} for r in mexc_rows if r.get("close_time")])

    if exit_reason != "all":
        er = exit_reason.upper()
        rows = [r for r in rows if (r.get("exit_reason") or "").upper() == er]

    if from_date:
        from_dt = _parse_open_utc(from_date + "T00:00:00")
        if from_dt:
            rows = [r for r in rows
                    if (_parse_open_utc(r.get("close_time")) or datetime.min.replace(tzinfo=timezone.utc)) >= from_dt]
    if to:
        to_dt = _parse_open_utc(to + "T23:59:59")
        if to_dt:
            rows = [r for r in rows
                    if (_parse_open_utc(r.get("close_time")) or datetime.max.replace(tzinfo=timezone.utc)) <= to_dt]

    if min_mae > 0:
        rows = [r for r in rows if (_f(r.get("mae_r")) or 0) <= -min_mae]
    if min_mfe > 0:
        rows = [r for r in rows if (_f(r.get("mfe_r")) or 0) >= min_mfe]

    rows.sort(key=lambda r: str(r.get("close_time") or ""), reverse=True)

    return JSONResponse([{
        "id":          r.get("id"),
        "venue":       r["_venue"],
        "pair":        r.get("pair"),
        "direction":   r.get("direction"),
        "exit_reason": r.get("exit_reason"),
        "mae_r":       _f(r.get("mae_r")),
        "mfe_r":       _f(r.get("mfe_r")),
        "open_time":   r.get("open_time"),
        "close_time":  r.get("close_time"),
        "entry_price": _f(r.get("entry_price")),
        "sl":          _f(r.get("sl")),
    } for r in rows])


@app.get("/api/reconstruct/{venue}/{trade_id}")
async def api_reconstruct(
    request: Request,
    venue:    str,
    trade_id: int,
) -> JSONResponse:
    _require_auth(request)

    if venue not in ("hl", "mexc"):
        raise HTTPException(400, "venue must be hl or mexc")

    table = "hl_trade_log" if venue == "hl" else "mexc_trade_log"
    rows  = await _sb_fetch(table, {"id": f"eq.{trade_id}"})
    if not rows:
        raise HTTPException(404, "trade not found")
    row = rows[0]

    entry     = _f(row.get("entry_price"))
    sl_val    = _f(row.get("sl"))
    mae_r_val = _f(row.get("mae_r"))
    mfe_r_val = _f(row.get("mfe_r"))
    direction = str(row.get("direction") or "").upper()
    exit_rsn  = str(row.get("exit_reason") or "").upper()
    open_ts   = row.get("open_time")
    close_ts  = row.get("close_time")
    pair      = str(row.get("pair") or "")

    if not all([entry is not None, sl_val is not None,
                mae_r_val is not None, mfe_r_val is not None,
                direction, open_ts, close_ts]):
        return JSONResponse({"status": "error", "msg": "missing required fields in DB row"})

    if exit_rsn not in ("TRAILBLAZER", "SL"):
        return JSONResponse({"status": "unsupported",
                             "msg": f"reconstruction not yet supported for exit_reason={row.get('exit_reason')}"})

    open_utc  = _parse_open_utc(open_ts)
    close_utc = _parse_open_utc(close_ts)
    if not open_utc or not close_utc:
        return JSONResponse({"status": "error", "msg": "could not parse timestamps"})

    open_ms   = int(open_utc.timestamp()  * 1000)
    close_ms  = int(close_utc.timestamp() * 1000)
    open_s    = int(open_utc.timestamp())
    close_s   = int(close_utc.timestamp())
    total_sec = (close_utc - open_utc).total_seconds()

    # HL 5-day retention check
    if venue == "hl":
        age_days = (datetime.now(timezone.utc) - open_utc).total_seconds() / 86400
        if age_days > 5:
            return JSONResponse({
                "status": "outside_retention",
                "msg": f"HL candleSnapshot retains ~5 days of 1m history; trade is {age_days:.1f} days old",
            })

    # SL distance and R-level prices
    if direction == "LONG":
        sl_dist = entry - sl_val
    else:
        sl_dist = sl_val - entry

    if sl_dist <= 0:
        return JSONResponse({"status": "error", "msg": f"invalid sl_dist={sl_dist} (entry={entry} sl={sl_val})"})

    mae_price = _rl_price(entry, sl_val, mae_r_val, direction)
    mfe_price = _rl_price(entry, sl_val, mfe_r_val, direction)

    # Fetch 1-minute candles
    if venue == "hl":
        candles = await _fetch_hl_candles_1m(_hl_coin(pair), open_ms - 60000, close_ms + 60000)
    else:
        sym = pair if "_USDT" in pair else pair + "_USDT"
        candles = await _fetch_mexc_candles_1m(sym, open_s - 60, close_s + 60)

    if not candles:
        return JSONResponse({"status": "error", "msg": "no candles returned from exchange API"})

    # Direction of crossing for each R-level
    # SHORT adverse = price UP (H >= mae_price); SHORT favorable = price DOWN (L <= mfe_price)
    # LONG  adverse = price DOWN (L <= mae_price); LONG  favorable = price UP (H >= mfe_price)
    mae_up = direction == "SHORT"
    mfe_up = direction == "LONG"

    def _ts_iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

    def _pct(secs: float) -> float:
        return round(secs / total_sec * 100, 1) if total_sec > 0 else 0.0

    if exit_rsn == "TRAILBLAZER":
        # Group a: entry -> MAE -> MFE -> close
        mae_hit = _find_crossing(candles, mae_price, mae_up,  sl_dist, after_ms=open_ms)
        if not mae_hit:
            # mae_r=0 means no adverse move; set MAE to entry time
            if mae_r_val == 0:
                mae_hit = {"time_ms": open_ms, "boundary": round(entry, 8), "gap_r": 0.0, "tag": "confirmed"}
            else:
                return JSONResponse({"status": "no_crossing", "msg": "MAE crossing not found in 1m candles",
                                     "mae_price": round(mae_price, 6), "mfe_price": round(mfe_price, 6)})
        mfe_hit = _find_crossing(candles, mfe_price, mfe_up, sl_dist, after_ms=mae_hit["time_ms"] + 1)
        if not mfe_hit:
            return JSONResponse({"status": "no_crossing", "msg": "MFE crossing not found after MAE in 1m candles",
                                 "mae_timestamp": _ts_iso(mae_hit["time_ms"]),
                                 "mae_price": round(mae_price, 6), "mfe_price": round(mfe_price, 6)})

        # Breakeven crossing: after MAE adverse, before MFE (price recovers through entry)
        bev_candles_a = [c for c in candles if c["time_ms"] < mfe_hit["time_ms"]]
        bev_hit_a = _find_crossing(bev_candles_a, entry, mfe_up, sl_dist,
                                   after_ms=mae_hit["time_ms"] + 1)

        adverse_s  = (mae_hit["time_ms"] - open_ms) / 1000
        recovery_s = (mfe_hit["time_ms"] - mae_hit["time_ms"]) / 1000

        return JSONResponse({
            "status": "ok", "group": "a",
            "exit_reason": exit_rsn, "direction": direction, "pair": pair, "venue": venue,
            "entry_price": round(entry, 6), "sl": round(sl_val, 6), "sl_dist": round(sl_dist, 6),
            "mae_r": mae_r_val, "mfe_r": mfe_r_val,
            "mae_price": round(mae_price, 6), "mfe_price": round(mfe_price, 6),
            "open_time": open_ts, "close_time": close_ts,
            "total_seconds": round(total_sec),
            "mae_timestamp":          _ts_iso(mae_hit["time_ms"]),
            "mfe_timestamp":          _ts_iso(mfe_hit["time_ms"]),
            "mae_candle_boundary":    mae_hit["boundary"],
            "mfe_candle_boundary":    mfe_hit["boundary"],
            "mae_tag":                mae_hit["tag"],
            "mfe_tag":                mfe_hit["tag"],
            "mae_gap_r":              mae_hit["gap_r"],
            "mfe_gap_r":              mfe_hit["gap_r"],
            "time_to_mae_seconds":    round(adverse_s),
            "mae_to_mfe_seconds":     round(recovery_s),
            "pct_of_duration_adverse":  _pct(adverse_s),
            "pct_of_duration_recovery": _pct(recovery_s),
            "window_start_pct":  _pct(adverse_s),
            "window_end_pct":    _pct(adverse_s + recovery_s),
            "breakeven_timestamp":       _ts_iso(bev_hit_a["time_ms"]) if bev_hit_a else None,
            "breakeven_tag":             bev_hit_a["tag"] if bev_hit_a else "not_found",
            "breakeven_gap_r":           bev_hit_a["gap_r"] if bev_hit_a else None,
            "breakeven_pct_of_duration": _pct((bev_hit_a["time_ms"] - open_ms) / 1000) if bev_hit_a else None,
        })

    else:  # SL — group b: entry -> MFE -> MAE/SL -> close
        mfe_hit = _find_crossing(candles, mfe_price, mfe_up, sl_dist, after_ms=open_ms)
        if not mfe_hit:
            if mfe_r_val == 0:
                mfe_hit = {"time_ms": open_ms, "boundary": round(entry, 8), "gap_r": 0.0, "tag": "confirmed"}
            else:
                return JSONResponse({"status": "no_crossing", "msg": "MFE crossing not found in 1m candles",
                                     "mfe_price": round(mfe_price, 6), "mae_price": round(mae_price, 6)})
        mae_hit = _find_crossing(candles, mae_price, mae_up, sl_dist, after_ms=mfe_hit["time_ms"] + 1)
        if not mae_hit:
            return JSONResponse({"status": "no_crossing", "msg": "MAE/SL crossing not found after MFE peak in 1m candles",
                                 "mfe_timestamp": _ts_iso(mfe_hit["time_ms"]),
                                 "mae_price": round(mae_price, 6)})

        # Breakeven crossing: after MFE peak, before SL/MAE (price falls back through entry)
        bev_candles_b = [c for c in candles if c["time_ms"] < mae_hit["time_ms"]]
        bev_hit_b = _find_crossing(bev_candles_b, entry, mae_up, sl_dist,
                                   after_ms=mfe_hit["time_ms"] + 1)

        favorable_s  = (mfe_hit["time_ms"] - open_ms) / 1000
        roundtrip_s  = (mae_hit["time_ms"] - mfe_hit["time_ms"]) / 1000

        return JSONResponse({
            "status": "ok", "group": "b",
            "exit_reason": exit_rsn, "direction": direction, "pair": pair, "venue": venue,
            "entry_price": round(entry, 6), "sl": round(sl_val, 6), "sl_dist": round(sl_dist, 6),
            "mae_r": mae_r_val, "mfe_r": mfe_r_val,
            "mae_price": round(mae_price, 6), "mfe_price": round(mfe_price, 6),
            "open_time": open_ts, "close_time": close_ts,
            "total_seconds": round(total_sec),
            "mfe_timestamp":         _ts_iso(mfe_hit["time_ms"]),
            "sl_timestamp":          _ts_iso(mae_hit["time_ms"]),
            "mfe_candle_boundary":   mfe_hit["boundary"],
            "sl_candle_boundary":    mae_hit["boundary"],
            "mfe_tag":               mfe_hit["tag"],
            "sl_tag":                mae_hit["tag"],
            "mfe_gap_r":             mfe_hit["gap_r"],
            "sl_gap_r":              mae_hit["gap_r"],
            "time_to_mfe_seconds":   round(favorable_s),
            "mfe_to_sl_seconds":     round(roundtrip_s),
            "pct_of_duration_favorable":  _pct(favorable_s),
            "pct_of_duration_roundtrip":  _pct(roundtrip_s),
            "window_start_pct": _pct(favorable_s),
            "window_end_pct":   _pct(favorable_s + roundtrip_s),
            "breakeven_timestamp":       _ts_iso(bev_hit_b["time_ms"]) if bev_hit_b else None,
            "breakeven_tag":             bev_hit_b["tag"] if bev_hit_b else "not_found",
            "breakeven_gap_r":           bev_hit_b["gap_r"] if bev_hit_b else None,
            "breakeven_pct_of_duration": _pct((bev_hit_b["time_ms"] - open_ms) / 1000) if bev_hit_b else None,
        })


# ─────────────────────────── timeline endpoint ───────────────────────────

def _session_for_utc(dt: datetime) -> str:
    h = dt.hour + dt.minute / 60.0
    if h < 8:   return "ASIA"
    if h < 14:  return "EU"
    if h < 22:  return "US"
    return "OFF"


def _tl_finalise(cur: dict, clusters: list) -> None:
    dirs = sorted(cur["directions"] - {""})
    clusters.append({
        "start_ms":       cur["start_ms"],
        "end_ms":         cur["end_ms"],
        "start_time":     datetime.fromtimestamp(cur["start_ms"] / 1000, tz=timezone.utc).isoformat(),
        "end_time":       datetime.fromtimestamp(cur["end_ms"]   / 1000, tz=timezone.utc).isoformat(),
        "peak_count":     cur["peak_count"],
        "same_direction": len(dirs) == 1,
        "directions":     dirs,
        "trade_ids":      sorted(cur["trade_ids"]),
    })


@app.get("/api/timeline")
async def api_timeline(
    request: Request,
    date:   str   = Query(default=""),
    venue:  str   = Query(default="all"),
    margin: float = Query(default=2000.0),
) -> JSONResponse:
    _require_auth(request)

    if venue not in ("all", "hl", "mexc"):
        raise HTTPException(400, "venue must be all | hl | mexc")

    try:
        target_date = datetime.fromisoformat(date).date() if date else datetime.now(timezone.utc).date()
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")

    date_str = target_date.isoformat()
    next_str = (target_date + timedelta(days=1)).isoformat()
    filt     = {"open_time": f"lt.{next_str}T00:00:00", "close_time": f"gte.{date_str}T00:00:00"}

    if venue == "hl":
        hl_r = await _sb_fetch("hl_trade_log", filt)
        mx_r: list = []
    elif venue == "mexc":
        hl_r = []
        mx_r = await _sb_fetch("mexc_trade_log", filt)
    else:
        hl_r, mx_r = await asyncio.gather(
            _sb_fetch("hl_trade_log",   filt),
            _sb_fetch("mexc_trade_log", filt),
        )

    raw = [{"_venue": "hl",   **r} for r in hl_r] + \
          [{"_venue": "mexc", **r} for r in mx_r]

    trades: list[dict] = []
    for r in raw:
        ot = _parse_open_utc(r.get("open_time"))
        ct = _parse_open_utc(r.get("close_time"))
        if not ot or not ct:
            continue
        pnl      = _f(r.get("pnl_dollars")) or 0.0
        exit_rsn = str(r.get("exit_reason") or "").upper()
        is_win   = exit_rsn in ("TRAILBLAZER", "TP1") or (exit_rsn == "MANUAL" and pnl > 0)
        is_win   = is_win or (exit_rsn in ("PEAK_DECAY_20", "RUNNER_DECAY_10") and pnl > 0)
        trades.append({
            "id":             r.get("id"),
            "venue":          r["_venue"],
            "pair":           str(r.get("pair") or r.get("symbol") or ""),
            "direction":      str(r.get("direction") or "").upper(),
            "exit_reason":    exit_rsn,
            "result":         "win" if is_win else "loss",
            "open_time":      ot.isoformat(),
            "close_time":     ct.isoformat(),
            "open_ms":        int(ot.timestamp() * 1000),
            "close_ms":       int(ct.timestamp() * 1000),
            "session_opened": _session_for_utc(ot),
            "pnl_dollars":    pnl,
        })
    trades.sort(key=lambda t: t["open_ms"])

    # Concurrency series at every open/close event
    event_ms = sorted({ms for t in trades for ms in (t["open_ms"], t["close_ms"])})
    series: list[dict] = []
    for ev in event_ms:
        c = sum(1 for t in trades if t["open_ms"] <= ev < t["close_ms"])
        series.append({"t_ms": ev, "count": c, "margin_deployed": round(c * margin, 2)})

    # Cluster zones (count >= 3)
    clusters: list[dict] = []
    cur: Optional[dict] = None
    for i, pt in enumerate(series):
        nxt = series[i + 1]["t_ms"] if i + 1 < len(series) else pt["t_ms"]
        if pt["count"] >= 3:
            active = [t for t in trades if t["open_ms"] <= pt["t_ms"] < t["close_ms"]]
            if cur is None:
                cur = {"start_ms": pt["t_ms"], "end_ms": nxt,
                       "peak_count": pt["count"],
                       "trade_ids":  {t["id"] for t in active},
                       "directions": {t["direction"] for t in active}}
            else:
                cur["end_ms"]     = nxt
                cur["peak_count"] = max(cur["peak_count"], pt["count"])
                cur["trade_ids"].update(t["id"] for t in active)
                cur["directions"].update(t["direction"] for t in active)
        else:
            if cur is not None:
                _tl_finalise(cur, clusters)
                cur = None
    if cur is not None:
        _tl_finalise(cur, clusters)

    # Drain annotations: margin drops >30 % from a local peak
    drains: list[dict] = []
    local_peak = 0.0
    for pt in series:
        m = pt["margin_deployed"]
        if m > local_peak:
            local_peak = m
        elif local_peak > 0 and m < local_peak * 0.70:
            drains.append({
                "t_ms":            pt["t_ms"],
                "time":            datetime.fromtimestamp(pt["t_ms"] / 1000, tz=timezone.utc).isoformat(),
                "margin_deployed": m,
                "drained_from":    local_peak,
            })
            local_peak = m

    peak_pt = max(series, key=lambda x: x["margin_deployed"]) if series else None

    return JSONResponse({
        "date":               date_str,
        "venue_filter":       venue,
        "margin_per_trade":   margin,
        "trade_count":        len(trades),
        "trades":             trades,
        "concurrency_series": series,
        "peak_concurrent":    peak_pt["count"]             if peak_pt else 0,
        "peak_margin":        peak_pt["margin_deployed"]   if peak_pt else 0.0,
        "peak_margin_time":   datetime.fromtimestamp(peak_pt["t_ms"] / 1000, tz=timezone.utc).isoformat()
                              if peak_pt else None,
        "clusters":           clusters,
        "cluster_count":      len(clusters),
        "drains":             drains,
    })


# ─────────────────────────────── peak protection ───────────────────────────────
@app.get("/api/peak-protection")
async def api_peak_protection(request: Request) -> JSONResponse:
    _require_auth(request)
    rows = await _sb_fetch("peak_protection_shadow")

    # Dedup: group by (venue, pair, direction, open_time).
    # Any group with count > 1 is a resurrection duplicate — exclude entirely.
    group_counts: dict = {}
    for r in rows:
        key = (r.get("venue"), r.get("pair"), r.get("direction"), r.get("open_time"))
        group_counts[key] = group_counts.get(key, 0) + 1

    clean = [
        r for r in rows
        if group_counts[(r.get("venue"), r.get("pair"), r.get("direction"), r.get("open_time"))] == 1
    ]
    excluded_contaminated_count = sum(1 for v in group_counts.values() if v > 1)

    def _threshold(at_key: str, pnl_key: str) -> dict:
        triggered = [r for r in clean if r.get(at_key) is not None]
        gb_vals = [
            (r["peak_pnl_usd"] - r[pnl_key]) / r["peak_pnl_usd"] * 100
            for r in triggered
            if (r.get("peak_pnl_usd") or 0) > 0
        ]
        fg_vals = [
            (r["pnl_dollars"] - r[pnl_key])
            for r in triggered
            if r.get("pnl_dollars") is not None
        ]
        return {
            "triggered_count":  len(triggered),
            "avg_giveback_pct": round(sum(gb_vals) / len(gb_vals), 1) if gb_vals else None,
            "forgone_dollars":  round(sum(fg_vals), 2) if fg_vals else None,
        }

    saved_side_count = sum(
        1 for r in clean
        if (r.get("peak_pnl_usd") or 0) >= 20 and (r.get("pnl_dollars") or 0) < 0
    )

    return JSONResponse({
        "clean_sample_count":          len(clean),
        "excluded_contaminated_count": excluded_contaminated_count,
        "thresholds": {
            "20": _threshold("decay20_triggered_at", "decay20_pnl_at_trigger"),
            "30": _threshold("decay30_triggered_at", "decay30_pnl_at_trigger"),
            "40": _threshold("decay40_triggered_at", "decay40_pnl_at_trigger"),
        },
        "saved_side_count": saved_side_count,
    })



# ─────────────────────────── sentinel coverage endpoint ───────────────────────────
@app.get("/api/sentinel-coverage")
async def api_sentinel_coverage(request: Request) -> JSONResponse:
    _require_auth(request)
    hl_r, mx_r = await asyncio.gather(
        _sb_fetch("hl_trade_log"),
        _sb_fetch("mexc_trade_log"),
    )
    return JSONResponse(_compute_sentinel_coverage(hl_r, mx_r))




# ─────────────────────────── ops caches ───────────────────────────
_ops_hourly_cache: dict = {"data": None, "updated_at": 0.0}
_ops_exit_cache:   dict = {"data": None, "updated_at": 0.0}
_OPS_CACHE_TTL = 60.0  # seconds

async def _compute_hourly_activity() -> list:
    """Signal count per ET hour for today, from both trade log tables."""
    today_et = datetime.now(ET).date()
    today_iso = today_et.isoformat()
    hl_rows, mexc_rows = await asyncio.gather(
        _sb_fetch("hl_trade_log",   {"open_time": f"gte.{today_iso}T00:00:00+00:00", "select": "open_time"}),
        _sb_fetch("mexc_trade_log", {"open_time": f"gte.{today_iso}T00:00:00+00:00", "select": "open_time"}),
    )
    buckets: dict[int, dict] = {h: {"hour": h, "hl": 0, "mexc": 0} for h in range(24)}
    for row in hl_rows:
        dt = _to_et(row.get("open_time"))
        if dt and dt.date() == today_et:
            buckets[dt.hour]["hl"] += 1
    for row in mexc_rows:
        dt = _to_et(row.get("open_time"))
        if dt and dt.date() == today_et:
            buckets[dt.hour]["mexc"] += 1
    return [buckets[h] for h in range(24)]

async def _compute_exit_breakdown() -> list:
    """Exit reasons grouped with win/loss + P&L for today ET."""
    today_et = datetime.now(ET).date()
    et_midnight = _et_midnight(today_et)
    utc_midnight = et_midnight.astimezone(timezone.utc)
    utc_iso = utc_midnight.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    hl_rows, mexc_rows = await asyncio.gather(
        _sb_fetch("hl_trade_log",   {"close_time": f"gte.{utc_iso}"}),
        _sb_fetch("mexc_trade_log", {"close_time": f"gte.{utc_iso}"}),
    )
    buckets: dict[str, dict] = {}
    for row in list(hl_rows) + list(mexc_rows):
        reason = str(row.get("exit_reason") or "UNKNOWN")
        pnl    = float(row.get("pnl_dollars") or 0)
        if reason not in buckets:
            buckets[reason] = {"exit_reason": reason, "trades": 0, "wins": 0, "net_pnl": 0.0}
        buckets[reason]["trades"] += 1
        if pnl > 0:
            buckets[reason]["wins"] += 1
        buckets[reason]["net_pnl"] = round(buckets[reason]["net_pnl"] + pnl, 2)
    ORDER = ["PEAK_DECAY_20", "TP1", "RUNNER_DECAY_10", "ADVERSE_CUT", "SL"]
    for v in buckets.values():
        v["avg_pnl"] = round(v["net_pnl"] / v["trades"], 2) if v["trades"] else 0.0
    result = sorted(buckets.values(),
                    key=lambda x: ORDER.index(x["exit_reason"]) if x["exit_reason"] in ORDER else 99)
    return result


# ─────────────────────────── operations endpoints ───────────────────────────
@app.get("/api/hourly_activity")
async def api_hourly_activity(request: Request) -> JSONResponse:
    _require_auth(request)
    now = time.time()
    if _ops_hourly_cache["data"] is None or now - _ops_hourly_cache["updated_at"] > _OPS_CACHE_TTL:
        _ops_hourly_cache["data"]       = await _compute_hourly_activity()
        _ops_hourly_cache["updated_at"] = now
    return JSONResponse(_ops_hourly_cache["data"])

@app.get("/api/exit_breakdown")
async def api_exit_breakdown(request: Request) -> JSONResponse:
    _require_auth(request)
    now = time.time()
    if _ops_exit_cache["data"] is None or now - _ops_exit_cache["updated_at"] > _OPS_CACHE_TTL:
        _ops_exit_cache["data"]       = await _compute_exit_breakdown()
        _ops_exit_cache["updated_at"] = now
    return JSONResponse(_ops_exit_cache["data"])

@app.get("/api/gate_activity")
async def api_gate_activity(request: Request) -> JSONResponse:
    _require_auth(request)
    today_iso = datetime.now(ET).date().isoformat()
    rows = await _sb_fetch("gate_activity_log", {
        "fired_at": f"gte.{today_iso}T00:00:00+00:00",
        "order":    "fired_at.desc",
        "limit":    "50",
    })
    return JSONResponse(rows)

# ─────────────────────────── entry point ───────────────────────────
@app.get("/api/alert-log")
async def api_alert_log(request: Request) -> JSONResponse:
    _require_auth(request)
    rows = await _sb_fetch("alert_log", {
        "order": "created_at.desc",
        "limit": "500",
    })
    return JSONResponse(rows)

if __name__ == "__main__":
  import uvicorn
  uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
