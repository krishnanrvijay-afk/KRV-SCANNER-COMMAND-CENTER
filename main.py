"""
Fleet-Scorecard — FastAPI backend
Read-only against external APIs and Supabase.
"""
import asyncio
import os
import pathlib
import time
from datetime import datetime, date, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, Request, HTTPException
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

def _venue_metrics(rows: list) -> dict:
    pnls   = [_f(r.get("pnl_dollars")) for r in rows]
    pnls   = [p for p in pnls if p is not None]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins)   if wins   else 0.0
    gross_loss   = abs(sum(losses)) if losses else 0.0
    pf = gross_profit / gross_loss if gross_loss else (999.0 if gross_profit else 0.0)
    wr = len(wins) / len(pnls) if pnls else 0.0

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
                if str(r.get("exit_reason", "")).upper() in ("TRAILBLAZER", "TRAIL")
                if (v := _f(r.get("r_value"))) is not None]
    avg_runner_r = sum(runner_r) / len(runner_r) if runner_r else None

    return {
        "pnl": round(sum(pnls), 2),
        "trade_count": len(pnls),
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
    for r in all_rows:
        sess = str(r.get("session_opened") or r.get("session") or "").upper().strip()
        sess = SESSION_MAP.get(sess, sess)
        if sess not in data:
            sess = "OFF"
        dr  = str(r.get("direction", "")).upper()
        pnl = _f(r.get("pnl_dollars"))
        if pnl is None:
            continue
        if dr == "LONG":
            data[sess]["lp"] += pnl; data[sess]["lt"] += 1
            if pnl > 0: data[sess]["lw"] += 1
        elif dr == "SHORT":
            data[sess]["sp"] += pnl; data[sess]["st"] += 1
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
    for r in all_rows:
        pair = r.get("pair") or r.get("symbol") or "UNKNOWN"
        pnl  = _f(r.get("pnl_dollars"))
        rv   = _f(r.get("r_value"))
        if pnl is None:
            continue
        s = stats.setdefault(pair, {"pnl": 0.0, "count": 0, "r_sum": 0.0, "r_n": 0})
        s["pnl"] += pnl; s["count"] += 1
        if rv is not None:
            s["r_sum"] += rv; s["r_n"] += 1
    return sorted(
        [{"pair": p, "pnl": round(v["pnl"], 2), "trade_count": v["count"],
          "avg_r": round(v["r_sum"] / v["r_n"], 3) if v["r_n"] else None}
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
        if rv is not None and mfev and mfev > 0 and str(r.get("exit_reason", "")).upper() in ("TRAILBLAZER", "TRAIL"):
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

    return {
        "range":       range_key,
        "fleet":       fleet_m,
        "hl":          hl_m,
        "mexc":        mexc_m,
        "twins":       twins,
        "twin_count":  len(twins),
        "venue_edge":  venue_edge,
        "sessions":    _compute_sessions(all_r),
        "pair_league": _compute_pair_league(all_r),
        "excursion":   _compute_excursion(all_r),
        "row_counts":  {"hl": len(hl_rows), "mexc": len(mexc_rows)},
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
async def api_log(request: Request, range: str = "all") -> JSONResponse:
    _require_auth(request)
    if range not in ("today", "week", "all"):
        raise HTTPException(400, "range must be: today | week | all")
    hl_rows, mexc_rows = await asyncio.gather(
        _sb_fetch("hl_trade_log",   {"order": "close_time.desc", "limit": "2000"}),
        _sb_fetch("mexc_trade_log", {"order": "close_time.desc", "limit": "2000"}),
    )
    start    = _range_start(range)
    hl_f     = _filter_by_range(hl_rows,   start)
    mexc_f   = _filter_by_range(mexc_rows, start)
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

# ─────────────────────────── entry point ───────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
