# SCORECARD_AUDIT.md
**Repo:** krishnanrvijay-afk/fleet-scorecard  
**HEAD at audit time:** d65150ef0465057a42302a74a1eda262257fcd0c  
**Files audited:** index.html (6425 lines, blob SHA fbc69205), main.py (2007 lines, blob SHA 3c24b612)  
**Audit date:** 2025-07-17  
**Method:** read-only; no code changes made.

---

## A — LANDING PAGE PILL ROW

### A1 — Full HTML of the header pill/status row (DOM order, verbatim)

```html
<!-- index.html L1415–1430 -->
  <div class="header">
    <div class="logo"><span class="logo-dot"></span>KRV FLEET SCORECARD</div>
    <div class="header-right">
      <button id="btc-regime-pill" class="rg-exempt" onclick="openBtcRegimeOverlay()" title="BTC Regime — click for detail"><span style="font-family:'Bebas Neue',sans-serif;font-size:13px;letter-spacing:0.14em;line-height:1.1;display:block">BTC REGIME</span><span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;letter-spacing:0.08em;opacity:0.7;display:block;line-height:1.2;margin-top:1px">BTC&nbsp;J1H&nbsp;&middot;&nbsp;&mdash;</span></button>
      <div id="sentinel-gate-pill" title="SENTINEL Gate — auto HALT/LIVE based on daily PnL + BTC Regime">SENTINEL GATE</div>
      <div class="range-btns">
        <button id="btn-today" onclick="setRange('today')" class="active">TODAY</button>
        <button id="btn-week"  onclick="setRange('week')">WEEK</button>
        <button id="btn-all"   onclick="setRange('all')">ALL</button>
      </div>
      <div id="analytics-status" class="fetch-status"></div>
        <div class="badge-paper">PAPER</div>
      <div id="fleet-halt-wrap" style="display:flex;align-items:center;margin-left:auto;margin-right:12px;">
        <button id="fleet-halt-btn" onclick="fleetHaltToggle()" style="font-family:'Bebas Neue',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px;padding:8px 24px;border-radius:6px;border:none;cursor:pointer;color:#ffffff;background:#22c55e;min-width:120px;">◎ LIVE</button>
      </div>
    </div>
  </div>
```

### A2 — CSS for each pill class used in that row

```css
/* index.html L1335–1358 — BTC regime pill */
#btc-regime-pill {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 13px;
  letter-spacing: 0.14em;
  padding: 5px 18px 6px;
  border-radius: 999px;
  border: 2px solid rgba(34,211,238,0.4);
  background: rgba(34,211,238,0.06);
  color: #22d3ee;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  line-height: 1;
}
#btc-regime-pill:hover { transform: scale(1.03); }
#btc-regime-pill.rg-confirmed { border-color: rgba(0,230,118,0.70); color: #00e676; background: rgba(0,230,118,0.12); box-shadow: 0 0 20px rgba(0,230,118,0.65), 0 0 50px rgba(0,230,118,0.28), inset 0 0 3px rgba(0,230,118,0.18); }
#btc-regime-pill.rg-caution   { border-color: rgba(255,179,0,0.70); color: #ffb300; background: rgba(255,179,0,0.11); box-shadow: 0 0 20px rgba(255,179,0,0.60), 0 0 50px rgba(255,179,0,0.25), inset 0 0 3px rgba(255,179,0,0.16); }
#btc-regime-pill.rg-stop      { border-color: rgba(255,70,70,0.75); color: #ff4646; background: rgba(255,70,70,0.12); animation: rgStopPulse 1.8s ease-in-out infinite; }
#btc-regime-pill.rg-exempt    { border-color: #2e2e2e; color: #555; background: transparent; box-shadow: none; }
@keyframes rgStopPulse { 0%,100%{box-shadow:0 0 12px rgba(255,70,70,0.40),0 0 0px rgba(255,70,70,0)} 50%{box-shadow:0 0 28px rgba(255,70,70,0.80),0 0 55px rgba(255,70,70,0.35)} }

/* index.html L1388–1407 — sentinel gate pill */
#sentinel-gate-pill {
  font-family: 'Bebas Neue', sans-serif;
  font-size: 13px;
  letter-spacing: 0.08em;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1.5px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.04);
  color: #888;
  white-space: nowrap;
  transition: all 0.3s;
  cursor: default;
  user-select: none;
}
#sentinel-gate-pill.sg-earn    { border-color:rgba(34,197,94,0.55);  color:#22c55e; background:rgba(34,197,94,0.07); }
#sentinel-gate-pill.sg-protect { border-color:rgba(251,191,36,0.55); color:#fbbf24; background:rgba(251,191,36,0.07); animation:sgProtectPulse 2.5s ease-in-out infinite; }
#sentinel-gate-pill.sg-halt    { border-color:rgba(239,68,68,0.60);  color:#ef4444; background:rgba(239,68,68,0.08);  animation:sgHaltPulse 1.8s ease-in-out infinite; }
@keyframes sgProtectPulse { 0%,100%{box-shadow:0 0 6px rgba(251,191,36,0.15)} 50%{box-shadow:0 0 18px rgba(251,191,36,0.38)} }
@keyframes sgHaltPulse    { 0%,100%{box-shadow:0 0 8px rgba(239,68,68,0.18)}  50%{box-shadow:0 0 24px rgba(239,68,68,0.48)} }

/* index.html L1427–1428 — fleet halt button (inline style, no named class) */
/* style="font-family:'Bebas Neue',sans-serif;font-size:18px;font-weight:700;
          letter-spacing:1px;padding:8px 24px;border-radius:6px;border:none;
          cursor:pointer;color:#ffffff;background:#22c55e;min-width:120px;" */
/* background toggled in JS: #22c55e (LIVE) / #ef4444 (HALTED) */
```

### A3 — Every pill by ID and what drives it

| ID | Element | Data source |
|----|---------|-------------|
| `btc-regime-pill` | `<button>` | `live.hl.pair_states` BTC entry → `j1h` field. HL primary; MEXC fallback if HL BTC entry absent. Driven by `_getBtcState()` called from `_refreshBtcRegimePill()` after every `loadLive()` (5 s). |
| `sentinel-gate-pill` | `<div>` | Combination of BTC regime state (from above) and `_sentinelDailyPnl` (from `/api/analytics?range=today` → `fleet.pnl`, polled every 30 s). |
| `btn-today` / `btn-week` / `btn-all` | `<button>` | UI range selector; toggles `active` CSS class on click. No external data. |
| `analytics-status` | `<div>` | Fetch status indicator populated by `_setFetchStatus('live-status', ...)` inside `loadLive()`. |
| `.badge-paper` | `<div>` | Static — always reads "PAPER". Not data-driven. |
| `fleet-halt-btn` | `<button>` | `_fleetHalted` JS bool. Initialised from `/api/fleet/status` on page load; toggled by `fleetHaltToggle()` click. Background: `#22c55e` (LIVE) or `#ef4444` (HALTED). |

---

## B — BTC REGIME PILL

### B4 — BTC regime pill HTML verbatim with element ID

```html
<!-- index.html L1418 -->
<button id="btc-regime-pill" class="rg-exempt" onclick="openBtcRegimeOverlay()" title="BTC Regime — click for detail"><span style="font-family:'Bebas Neue',sans-serif;font-size:13px;letter-spacing:0.14em;line-height:1.1;display:block">BTC REGIME</span><span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;letter-spacing:0.08em;opacity:0.7;display:block;line-height:1.2;margin-top:1px">BTC&nbsp;J1H&nbsp;&middot;&nbsp;&mdash;</span></button>
```

### B5 — JS that populates it — full functions

```js
/* index.html L6215–6228 — data source */
function _getBtcState() {
  /* BTC pair_state: both scanners track BTC in pair_states.
     HL primary, MEXC fallback. Normalize symbol variants. */
  function normBtc(arr) {
    if (!Array.isArray(arr)) return null;
    return arr.find(function(p) {
      var s = (p.symbol || '').replace(/_?USDT$/i,'').replace(/-?USDT$/i,'').toUpperCase();
      return s === 'BTC';
    }) || null;
  }
  var hlPairs   = (typeof live !== 'undefined' && live && live.hl   && live.hl.pair_states)   || [];
  var mexcPairs = (typeof live !== 'undefined' && live && live.mexc && live.mexc.pair_states) || [];
  return normBtc(hlPairs) || normBtc(mexcPairs) || null;
}

/* index.html L6252–6282 — pill renderer */
function _refreshBtcRegimePill() {
  var pill = document.getElementById('btc-regime-pill');
  if (!pill) return;
  var btc = _getBtcState();
  var rg  = _btcRegime(btc);
  pill.className = rg.cls === 'confirmed'
    ? (rg.state === 'CONFIRMED_LONG' ? 'rg-confirmed' : 'rg-confirmed')
    : rg.cls === 'caution' ? 'rg-caution'
    : rg.cls === 'stop'    ? 'rg-stop'
    :                        'rg-exempt';
  var labelLine = rg.state === 'CONFIRMED_LONG'  ? 'CONFIRMED'
               : rg.state === 'CAUTION_LONG'    ? 'CAUTION'
               : rg.state === 'STOP'            ? 'STOP'
               : rg.state === 'CAUTION_SHORT'   ? 'CAUTION'
               : rg.state === 'CONFIRMED_SHORT' ? 'SHORT SAFE'
               :                                  'BTC REGIME';
  var j1hScore = (btc && btc.j1h != null) ? Math.round(btc.j1h) : '\u2014';
  var scoreLine = 'BTC\u00a0J1H\u00a0\u00b7\u00a0' + j1hScore;
  pill.innerHTML = '<span style="font-family:\'Bebas Neue\',sans-serif;font-size:13px;letter-spacing:0.14em;line-height:1.1;display:block">' + labelLine + '</span>'
    + '<span style="font-family:\'JetBrains Mono\',monospace;font-size:9px;font-weight:700;letter-spacing:0.08em;opacity:0.7;display:block;line-height:1.2;margin-top:1px">' + scoreLine + '</span>';
  /* If overlay is open, refresh its content too */
  var bd = document.getElementById('btc-ov-bd');
  if (bd && bd.style.display !== 'none') {
    var pn = document.getElementById('btc-ov-pn');
    if (pn) {
      pn.className = rg.cls;
      pn.innerHTML = _btcRegimeCardHtml('FLEET', btc, rg, 1.0);
    }
  }
  _sentinelGateCheck();
}
```

Endpoint read: `_refreshBtcRegimePill()` calls `_getBtcState()`, which reads from the global `live` object. `live` is populated by `loadLive()` (index.html L2261–2300), which fetches `/api/live` (L2263). No separate regime endpoint exists; the pill reads `live.hl.pair_states` (HL primary) then `live.mexc.pair_states` (MEXC fallback). The specific field consumed is `btc.j1h`.

### B6 — Every regime state with exact colour and label

```js
/* index.html L6074–6082 */
function _btcRegime(btc) {
  if (!btc) return { state:'EXEMPT', cls:'exempt', color:'#fff', label:' EXEMPT' };
  var j1h = btc.j1h || 0;
  if (j1h < 20)  return { state:'CONFIRMED_LONG',  cls:'confirmed', color:'#00e676', label:' CONFIRMED' };
  if (j1h < 40)  return { state:'CAUTION_LONG',    cls:'caution',   color:'#ffb300', label:' CAUTION'   };
  if (j1h <= 60) return { state:'STOP',            cls:'stop',      color:'#ff4646', label:' STOP'      };
  if (j1h < 80)  return { state:'CAUTION_SHORT',   cls:'caution',   color:'#ffb300', label:' CAUTION'   };
  return           { state:'CONFIRMED_SHORT',  cls:'confirmed', color:'#ff4646', label:' SHORT SAFE' };
}
```

Full state table:

| btc.j1h range | state | cls | color | pill label |
|---|---|---|---|---|
| btc is null/undefined | EXEMPT | exempt | #fff | BTC REGIME (static) |
| < 20 | CONFIRMED_LONG | confirmed | #00e676 | CONFIRMED |
| 20–39 | CAUTION_LONG | caution | #ffb300 | CAUTION |
| 40–60 | STOP | stop | #ff4646 | STOP |
| 61–79 | CAUTION_SHORT | caution | #ffb300 | CAUTION |
| ≥ 80 | CONFIRMED_SHORT | confirmed | #ff4646 | SHORT SAFE |

CSS pill class → colour mapping (index.html L1355–1358):

```css
#btc-regime-pill.rg-confirmed { border-color: rgba(0,230,118,0.70); color: #00e676; ... }
#btc-regime-pill.rg-caution   { border-color: rgba(255,179,0,0.70); color: #ffb300; ... }
#btc-regime-pill.rg-stop      { border-color: rgba(255,70,70,0.75); color: #ff4646; ... animation: rgStopPulse 1.8s ... }
#btc-regime-pill.rg-exempt    { border-color: #2e2e2e; color: #555; background: transparent; box-shadow: none; }
```

Note: both CONFIRMED_LONG and CONFIRMED_SHORT map to CSS class `rg-confirmed` (L6257–6258), but their colors differ: CONFIRMED_LONG renders green (#00e676) from the regime object; CONFIRMED_SHORT renders red (#ff4646). The CSS class alone does not distinguish them — only the innerHTML label does.

### B7 — Endpoint that serves BTC regime — full handler verbatim

There is no dedicated `/api/btc-regime` endpoint. The regime is computed entirely in the browser from the `/api/live` response.

```python
# main.py L740–749
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
```

`_live["hl"]` and `_live["mexc"]` are populated by the server-side background poller `_poll_live()`:

```python
# main.py L67–100
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
        await asyncio.sleep(5)   # scorecard live-state cache: 5s poll
```

Value origin: the BTC `j1h` value originates from the scanner's `/api/state` response (`pair_states` list), polled server-side from each scanner. It is not computed in the scorecard; it is forwarded verbatim.

### B8 — HL only, MEXC only, or both? How is a disagreement resolved?

```js
/* index.html L6215–6228 */
function _getBtcState() {
  /* BTC pair_state: both scanners track BTC in pair_states.
     HL primary, MEXC fallback. Normalize symbol variants. */
  function normBtc(arr) {
    if (!Array.isArray(arr)) return null;
    return arr.find(function(p) {
      var s = (p.symbol || '').replace(/_?USDT$/i,'').replace(/-?USDT$/i,'').toUpperCase();
      return s === 'BTC';
    }) || null;
  }
  var hlPairs   = (typeof live !== 'undefined' && live && live.hl   && live.hl.pair_states)   || [];
  var mexcPairs = (typeof live !== 'undefined' && live && live.mexc && live.mexc.pair_states) || [];
  return normBtc(hlPairs) || normBtc(mexcPairs) || null;
}
```

**HL is primary. MEXC is used only as a fallback when HL's BTC entry is absent.** There is no disagreement-resolution logic. If HL returns a BTC entry, its `j1h` is used exclusively and MEXC's is ignored regardless of what MEXC reports. If HL has no BTC entry (e.g. scanner down or BTC absent from pair_states), MEXC's BTC entry is used. If both are absent, `_getBtcState()` returns `null` and `_btcRegime()` returns `{ state:'EXEMPT' }`.

### B9 — Refresh interval

```js
/* index.html L3848 */
setInterval(loadLive,       5_000);   /* positions: 5s refresh */

/* index.html L2286 — inside loadLive() */
    _refreshBtcRegimePill();
```

The BTC regime pill refreshes every **5,000 ms** (5 seconds), driven by the `loadLive` polling loop. `_refreshBtcRegimePill()` is called synchronously inside `loadLive()` after each successful `/api/live` response.

---

## C — HALT / LIVE TOGGLE PILL

### C10 — Toggle pill HTML verbatim with element ID

```html
<!-- index.html L1427–1429 -->
      <div id="fleet-halt-wrap" style="display:flex;align-items:center;margin-left:auto;margin-right:12px;">
        <button id="fleet-halt-btn" onclick="fleetHaltToggle()" style="font-family:'Bebas Neue',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px;padding:8px 24px;border-radius:6px;border:none;cursor:pointer;color:#ffffff;background:#22c55e;min-width:120px;">◎ LIVE</button>
      </div>
```

### C11 — Every JS function that touches it

```js
/* index.html L6025 */
var _fleetHalted = false;

/* index.html L6027–6036 — page-load init */
async function fleetHaltInit() {
  try {
    var r = await fetch('/api/fleet/status');
    var d = await r.json();
    _fleetHalted = d.fleet_halt || false;
    _updateHaltBtn();
  } catch(e) {
    console.error('Fleet status error:', e);
  }
}

/* index.html L6038–6053 — click handler */
async function fleetHaltToggle() {
  _btcAutoHalted = false;
  _fleetHalted = !_fleetHalted;
  _updateHaltBtn();
  try {
    await fetch('/api/fleet/halt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({halt: _fleetHalted})
    });
  } catch(e) {
    _fleetHalted = !_fleetHalted;
    _updateHaltBtn();
    console.error('Fleet halt error:', e);
  }
}

/* index.html L6055–6065 — state setter */
function _updateHaltBtn() {
  var btn = document.getElementById('fleet-halt-btn');
  if (!btn) return;
  if (_fleetHalted) {
    btn.textContent = '◎ HALTED';
    btn.style.background = '#ef4444';
  } else {
    btn.textContent = '◎ LIVE';
    btn.style.background = '#22c55e';
  }
}

/* index.html L6067 — boot call */
fleetHaltInit();
```

Sentinel auto-halt also touches the button via `_applyAutoHalt()`:

```js
/* index.html L6354–6366 */
async function _applyAutoHalt(halt, posture, rgState, dailyPnl) {
  _fleetHalted = halt;
  _updateHaltBtn();

  try {
    await fetch('/api/fleet/halt', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({halt: halt})
    });
  } catch(e) {
    console.error('[SENTINEL] halt write error:', e);
  }
  ...
}
```

Note: `_applyAutoHalt()` optimistically updates the button and then fires the POST. It does **not** revert the button on error — the `catch` only logs the error.

### C12 — /api/fleet/halt handler verbatim

```python
# main.py L1913–1922
@app.post("/api/fleet/halt")
async def fleet_halt_toggle(
    request: Request,
) -> JSONResponse:
    _require_auth(request)
    body = await request.json()
    halt = bool(body.get("halt", False))
    await _sb_patch("hl_scanner_state",   "id=eq.1", {"fleet_halt": halt})
    await _sb_patch("mexc_scanner_state", "id=eq.1", {"fleet_halt": halt})
    return JSONResponse({"fleet_halt": halt, "status": "ok"})
```

### C13 — /api/fleet/status handler verbatim

```python
# main.py L1935–1942
@app.get("/api/fleet/status")
async def fleet_status(
    request: Request,
) -> JSONResponse:
    _require_auth(request)
    rows = await _sb_fetch("hl_scanner_state", {"id": "eq.1", "select": "fleet_halt"})
    halt = rows[0].get("fleet_halt", False) if rows else False
    return JSONResponse({"fleet_halt": halt})
```

### C14 — Every table the halt POST writes to

```python
# main.py L1920–1921
    await _sb_patch("hl_scanner_state",   "id=eq.1", {"fleet_halt": halt})
    await _sb_patch("mexc_scanner_state", "id=eq.1", {"fleet_halt": halt})
```

Two writes: `hl_scanner_state` row id=1 field `fleet_halt`, and `mexc_scanner_state` row id=1 field `fleet_halt`.

The `_sb_patch` helper (main.py L131–150):

```python
async def _sb_patch(table: str, row_filter: str, payload: dict) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.patch(
                f"{SUPABASE_URL}/rest/v1/{table}?{row_filter}",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            return True
        except Exception:
            return False
```

**Critical: `_sb_patch` swallows all exceptions and returns `False` silently.** The `/api/fleet/halt` handler does not check the return values of either `_sb_patch` call. If either or both PATCH requests fail (network error, Supabase timeout, etc.), the handler still returns `{"fleet_halt": halt, "status": "ok"}` with HTTP 200.

### C15 — Which table does the status GET read from?

```python
# main.py L1940
    rows = await _sb_fetch("hl_scanner_state", {"id": "eq.1", "select": "fleet_halt"})
```

**The status GET reads from `hl_scanner_state` only.** `mexc_scanner_state` is not queried.

**Consequence of per-venue divergence:** If `hl_scanner_state.fleet_halt = false` but `mexc_scanner_state.fleet_halt = true` (achievable by a partial write failure or direct Supabase edit), `/api/fleet/status` returns `{"fleet_halt": false}`, `_fleetHalted` is set to `false`, the pill reads "◎ LIVE" with a green background — while MEXC scanner is actually halted. The pill lies.

### C16 — Optimistic UI update and error revert

**fleetHaltToggle() — optimistic update with revert:**

```js
/* index.html L6038–6053 */
async function fleetHaltToggle() {
  _btcAutoHalted = false;
  _fleetHalted = !_fleetHalted;   // ← optimistic flip
  _updateHaltBtn();                // ← UI updated immediately
  try {
    await fetch('/api/fleet/halt', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({halt: _fleetHalted})
    });
  } catch(e) {
    _fleetHalted = !_fleetHalted;  // ← revert on fetch() network error
    _updateHaltBtn();
    console.error('Fleet halt error:', e);
  }
}
```

The revert fires only on a `fetch()` network exception (i.e., the request never left the browser). It does **not** revert if the server returns a non-2xx HTTP status — the `catch` block is not reached for HTTP error responses. If the server returns 500 or 401, `_fleetHalted` and the button remain in the optimistically-flipped state.

**_applyAutoHalt() — optimistic update, no revert:**

```js
/* index.html L6354–6366 */
async function _applyAutoHalt(halt, posture, rgState, dailyPnl) {
  _fleetHalted = halt;
  _updateHaltBtn();
  try {
    await fetch('/api/fleet/halt', { ... });
  } catch(e) {
    console.error('[SENTINEL] halt write error:', e);
    // ← no revert
  }
  ...
}
```

`_applyAutoHalt()` has no revert path at all.

### C17 — Auth guard on both endpoints

```python
# main.py L63–65 — the guard function
def _require_auth(request: Request) -> None:
    if not _is_authed(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

# main.py L52–61 — the check
def _is_authed(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        signer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False

# main.py L1917 — /api/fleet/halt guard
    _require_auth(request)

# main.py L1939 — /api/fleet/status guard
    _require_auth(request)
```

Both `/api/fleet/halt` (POST) and `/api/fleet/status` (GET) call `_require_auth(request)` as their first statement. Auth is cookie-based: `URLSafeTimedSerializer` with `SCORECARD_SECRET`, cookie name `aria_session`, max age 30 days (main.py L34–35, L46).

**INCONSISTENCY — /api/fleet/halt-long and /api/fleet/halt-short lack auth guards:**

```python
# main.py L1891–1899
@app.post("/api/fleet/halt-long")
async def fleet_halt_long_toggle(
    request: Request,
    body: dict = Body(...),
) -> JSONResponse:
    halt = bool(body.get("halt", False))                         # ← no _require_auth call
    await _sb_patch("hl_scanner_state",   "id=eq.1", {"halt_long": halt})
    await _sb_patch("mexc_scanner_state", "id=eq.1", {"halt_long": halt})
    return JSONResponse({"halt_long": halt, "status": "ok"})

# main.py L1902–1910
@app.post("/api/fleet/halt-short")
async def fleet_halt_short_toggle(
    request: Request,
    body: dict = Body(...),
) -> JSONResponse:
    halt = bool(body.get("halt", False))                         # ← no _require_auth call
    await _sb_patch("hl_scanner_state",   "id=eq.1", {"halt_short": halt})
    await _sb_patch("mexc_scanner_state", "id=eq.1", {"halt_short": halt})
    return JSONResponse({"halt_short": halt, "status": "ok"})
```

`/api/fleet/halt-long` and `/api/fleet/halt-short` have **no authentication guard**. Any unauthenticated caller can halt or resume long/short trading on both venues by POSTing `{"halt": true}` or `{"halt": false}` to these endpoints.

---

## D — VENUE COVERAGE

### D18 — Every venue the scorecard knows about

**Scanner base URLs (main.py L31–32):**
```python
HL_STATE_URL   = "https://bounce-scanner-deux-production-88de.up.railway.app/api/state"
MEXC_STATE_URL = "https://web-production-d03dd.up.railway.app/api/state"
```

**Supabase table names (main.py, selected):**
- `hl_scanner_state` — L1920, L1897, L1908, L1940
- `mexc_scanner_state` — L1921, L1898, L1909
- `hl_trade_log` — L757, L797, L828, L1065, L1118, L1530
- `mexc_trade_log` — L758, L798, L830, L1066, L1119, L1531

**Venue literal strings (main.py, selected):**
- `"hl"` — L514, L615, L797, L828, L1065, L1067, L1094, L1115, L1118, L1155, L1176, L1345, L1357, L1631, L1680, L1964
- `"mexc"` — L514, L616, L798, L830, L1066, L1068, L1115, L1118, L1348, L1358, L1631, L1680, L1964
- `venue not in ("hl", "mexc")` — L1115, L1333, L1646, L1850 (hard validation gates)

**Venue literal strings (index.html, selected):**
- `'hl'` and `'mexc'` — L460–462, L566–567, L1020–1022, L1742–1744, L2276, L2851–2854, L2864, L2940–2941, L3660–3662, L4368, L4524–4526, L4559–4561, L5212–5214, L5293–5295, L5486–5487, L5533–5534, L5565
- venue chip buttons hardcode: `id="vchip-all"`, `id="vchip-hl"`, `id="vchip-mexc"` (L1742–1744)
- venue filter buttons hardcode: `'ALL','HL','MEXC'` (index.html L5565)

The venue list is **hardcoded** throughout. It is not derived from config, environment variables, or a data structure — every venue-aware function enumerates "hl" and "mexc" explicitly.

### D19 — Is Kraken referenced anywhere?

**No.** grep for `kraken` and `Kraken` across both index.html and main.py returns zero matches.

### D20 — Files and lines that would need editing to add a third venue

**main.py — every hardcoded venue location:**

| Line | Code |
|------|------|
| L31–32 | `HL_STATE_URL` / `MEXC_STATE_URL` — add new URL constant |
| L39–40 | `_live` dict — add new key |
| L71 | `for key, url in [("hl", HL_STATE_URL), ("mexc", MEXC_STATE_URL)]` — add tuple |
| L514 | `for venue, rows in [("hl", hl_rows), ("mexc", mexc_rows)]` — add tuple |
| L615–616 | list comprehensions building `all_r` — add entry |
| L618–620 | `fleet_m`, `hl_m`, `mexc_m` — add venue metric call |
| L756–759 | `asyncio.gather(_sb_fetch("hl_trade_log"), _sb_fetch("mexc_trade_log"))` — add gather |
| L797–798 | log endpoint list comprehensions — add entry |
| L827–834 | `venue.lower() == "hl"` / `elif venue.lower() == "mexc"` conditionals — add elif |
| L885–886 | performance endpoint list comprehensions — add entry |
| L1065–1068 | reconstruct shortlist fetches and list comprehensions — add branch |
| L1115–1118 | `if venue not in ("hl", "mexc")` / `table = ... if venue == "hl" else ...` — extend |
| L1333–1334 | `if venue not in ("all", "hl", "mexc")` — extend |
| L1345–1358 | timeline fetch conditionals and list comprehensions — add branch |
| L1530–1531 | hourly activity `asyncio.gather` — add gather |
| L1646–1647 | `if venue not in ("all", "hl", "mexc")` — extend |
| L1680 | `trade_logs_by_venue = {"hl": hl_trades, "mexc": mexc_trades}` — add key |
| L1850–1851 | `if venue not in ("hl", "mexc")` — extend |
| L1867 | `if venue == "hl"` close URL — add branch |
| L1897–1898, L1908–1909, L1920–1921 | `_sb_patch("hl_scanner_state", ...)` + `_sb_patch("mexc_scanner_state", ...)` pairs — add third patch |
| L1940 | status GET reads `hl_scanner_state` — add logic or pick new source of truth |
| L1964 | `if venue not in ("hl", "mexc") or ...` — extend |

**index.html — every hardcoded venue location:**

| Lines | Code |
|-------|------|
| L460–462 | `.active-all/.active-hl/.active-mexc` CSS classes |
| L566–567 | `.venue-tag.hl` / `.venue-tag.mexc` CSS |
| L1020–1022 | `.ops-feed-venue-hl` / `.ops-feed-venue-mexc` CSS |
| L1741–1744 | venue chip buttons `id="vchip-all"`, `id="vchip-hl"`, `id="vchip-mexc"` |
| L2276 | `[hlFlash ? "HL" : "", mxFlash ? "MEXC" : ""]` flash banner |
| L2401 | `live[venue]` keyed access |
| L2851–2854 | radar tag arrays `venue:'hl'` / `venue:'mexc'` |
| L2940–2941 | `includes('hl')` / `includes('mexc')` |
| L3660–3662 | venue tag render conditional |
| L3936–3938 | reconstruct venue tag render |
| L4368 | `if (r.venue === 'hl')` MEXC kline fetch conditional |
| L4524–4526, L4559–4561 | sentinel coverage venue tag renders |
| L5212–5214, L5293–5295 | venue chip button triplets |
| L5486–5487, L5533–5534 | alert-log / performance filter buttons |
| L5565 | `{venue:['ALL','HL','MEXC'],...}` filter group |
| L6072 | comment: "Data: live.hl.pair_states" |
| L6216–6227 | `_getBtcState()` — reads `live.hl` and `live.mexc` by name |

The venue list is hardcoded in both files. There is no config-driven enumeration. Adding a third venue requires editing at minimum 20+ distinct locations across both files.

---

## E — POLLING & REFRESH

### E21 — Every setInterval / polling loop with its interval

```js
/* index.html L3848 */
setInterval(loadLive,       5_000);   /* positions: 5s refresh */

/* index.html L3849 */
setInterval(htcFetchGate, 30000);

/* index.html L3851 */
setInterval(loadAnalytics, 300_000);

/* index.html L6413 */
setInterval(_fetchSentinelPnl, 30000);

/* index.html L4749 — ops panel (conditional, fires only when ops panel active) */
    _opsGateTmr  = setInterval(_opsRefreshGate, 10000);

/* index.html L5830 — alert-log panel (conditional, fires only when alert-log active) */
    _alTimer=setInterval(function(){if(_alActive)_alFetch();},30000);

/* index.html L2233 (line 2768 area) — additional log refresh loop (found at L2768) */
setInterval(function() { ... }, ...)
```

Full table of unconditional intervals:

| Interval (ms) | Function | What it fetches |
|---|---|---|
| 5,000 | `loadLive` | `/api/live` — scanner pair_states, open_trades, btc_flash |
| 30,000 | `htcFetchGate` | `/api/gate_activity` — position gate data |
| 300,000 | `loadAnalytics` | `/api/analytics?range=<range>` — trade analytics |
| 30,000 | `_fetchSentinelPnl` | `/api/analytics?range=today` — fleet daily PnL for sentinel |

Server-side poll (main.py L100):
```python
        await asyncio.sleep(5)   # scorecard live-state cache: 5s poll
```

### E22 — /api/live handler verbatim — every field it returns

```python
# main.py L740–749
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
```

Fields returned:

| Field | Type | Description |
|---|---|---|
| `hl` | object or null | Full `/api/state` response from HL scanner |
| `mexc` | object or null | Full `/api/state` response from MEXC scanner |
| `hl_ok` | bool | Whether the last HL poll succeeded |
| `mexc_ok` | bool | Whether the last MEXC poll succeeded |
| `updated_at` | float | Unix timestamp of last successful poll cycle |

`_live["hl"]` and `_live["mexc"]` contain whatever the scanner's `/api/state` returns (pair_states, open_trades, daily, btc_flash_active, etc.) — no field stripping or transformation is applied before forwarding.

### E23 — Does /api/live return fleet_halt or btc regime?

- **fleet_halt:** No. `/api/live` does not include `fleet_halt`. The halt state comes from a separate `/api/fleet/status` call at page load only, not from the polling loop.
- **btc regime:** No. `/api/live` does not compute or return a `btc_regime` field. The raw scanner state (including `j1h` inside `pair_states`) is forwarded verbatim; the browser computes the regime class from `j1h`.

### E24 — How the scorecard reaches each scanner

```python
# main.py L31–32 — base URLs
HL_STATE_URL   = "https://bounce-scanner-deux-production-88de.up.railway.app/api/state"
MEXC_STATE_URL = "https://web-production-d03dd.up.railway.app/api/state"
```

Both URLs are hardcoded string constants. There is no environment variable fallback or config file for them.

```python
# main.py L67–100 — poller
async def _poll_live() -> None:
    while True:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for key, url in [("hl", HL_STATE_URL), ("mexc", MEXC_STATE_URL)]:
                try:
                    r = await client.get(url)
                    r.raise_for_status()
                    ...
                except Exception as exc:
                    _live[f"{key}_ok"] = False
                    print(f"[LIVE] {key.upper()} ERROR — {exc}", flush=True)
        _live["updated_at"] = time.time()
        await asyncio.sleep(5)
```

- **Timeout:** 10.0 seconds per request (`httpx.AsyncClient(timeout=10.0)`)
- **Retry:** None. A failed poll sets `{key}_ok = False` and logs the error; the loop continues to the next scanner and waits 5 seconds before retrying.
- **Auth on scanner calls:** None. The scorecard calls the scanner `/api/state` as a plain unauthenticated GET.
- **Error propagation:** Silent. `_live[key]` retains its last successful value on failure; `_live[f"{key}_ok"]` is set False.

---

## F — REPORT

### Does the HALT pill write to ALL venue tables but read from only one?

**Yes.**

- POST `/api/fleet/halt` writes to **both** `hl_scanner_state` (L1920) **and** `mexc_scanner_state` (L1921).
- GET `/api/fleet/status` reads from **`hl_scanner_state` only** (L1940). `mexc_scanner_state` is never read.

### Can the pill show LIVE while a venue is actually halted?

**Yes, in at least two scenarios:**

1. **Silent write failure:** `_sb_patch` swallows all exceptions (main.py L148–150: `except Exception: return False`). The `/api/fleet/halt` handler ignores the return value of both patch calls and always returns `{"fleet_halt": halt, "status": "ok"}`. If the MEXC patch fails silently, `mexc_scanner_state.fleet_halt` stays at its previous value. The status GET, reading only HL, returns the HL value. Pill and HL agree; MEXC is diverged.

2. **Table divergence by any means:** If `hl_scanner_state.fleet_halt = false` and `mexc_scanner_state.fleet_halt = true` (achievable via direct Supabase edit, infrastructure failure, or past silent patch failure), the status GET at L1940 returns `false`, `_fleetHalted = false`, the pill shows "◎ LIVE" in green — while MEXC scanner is halted.

3. **Unauthenticated `/api/fleet/halt-long` or `/api/fleet/halt-short`:** These endpoints (L1891, L1902) have no auth guard and can write `halt_long` or `halt_short` to both scanner tables without a login. A halt on these sub-fields is not reflected anywhere in the fleet-halt pill.

### Does the BTC regime pill reflect one venue or the fleet?

**HL primary; MEXC is a silent fallback only.** The pill reflects HL's BTC `j1h` in all cases where HL returns a BTC entry in `pair_states`. There is no averaging, comparison, or consensus logic. A divergence between HL and MEXC BTC j1h is silently discarded — HL wins.

### Any endpoint that returns 500 or references an undefined name?

No endpoint explicitly raises 500 or references an obviously undefined name. However:

- **`_sb_patch` silent swallow:** As noted, both halt-related PATCH calls can fail silently. The caller receives `{"status": "ok"}` regardless. This is not a 500 but it is a false success response.
- **`signer` fallback:** `signer = URLSafeTimedSerializer(SCORECARD_SECRET or "no-secret-set")` (main.py L46). If `SCORECARD_SECRET` is not set, the signer uses the literal string `"no-secret-set"` as the secret key. Auth tokens signed with this key are valid but trivially forgeable by anyone who reads the source code.
- **`_btcRegime(btc)` note:** If `btc.j1h` is exactly 60, the function returns `STOP` (L6079: `if (j1h <= 60)`). If `j1h` is exactly 80, the function returns `CONFIRMED_SHORT` (L6081: final `return`). Both are boundary cases that may surprise — they are not bugs but the thresholds are inclusive/exclusive in non-obvious ways.

### Any pill whose displayed state can drift from the underlying data?

1. **`fleet-halt-btn`:** Drifts from `mexc_scanner_state` perpetually (status reads HL only). Drifts from `hl_scanner_state` on the next page load after a `fleetHaltToggle()` fetch error that returned a non-network HTTP error (e.g., 401, 500) — the button stays flipped but the DB was not written.

2. **`sentinel-gate-pill`:** Derives from `_sentinelDailyPnl` (updated every 30 s from `/api/analytics`) and BTC regime (updated every 5 s from `/api/live`). Max drift window: 30 seconds on the PnL dimension. If `/api/analytics` returns stale or cached data, the posture (EARN/PROTECT) and `shouldHalt` decision lag by up to 5 minutes (the analytics cache TTL at main.py L1577–1579 is `_OPS_CACHE_TTL`, which is separate from the 30 s sentinel poll).

3. **`btc-regime-pill`:** Drifts from actual MEXC BTC j1h always (MEXC is never used when HL has a BTC entry). If HL scanner goes down mid-session, `_live["hl"]` retains the last good value — the pill shows a stale HL regime for the duration of the outage, while the fleet may be operating under different conditions.

4. **`fleet-halt-btn` with `_applyAutoHalt` (sentinel):** No revert on error — if the sentinel fires an auto-halt but the POST fails, the button shows HALTED and `_fleetHalted = true`, but neither scanner table was updated. The scanners remain live; the pill shows HALTED.

---

*End of audit. Read-only. No code changes made.*
