#!/usr/bin/env python3
"""allocator.py - target allocation from deterministic screen output. SIMULATION ONLY.

Reads the lending screen and produces a target allocation JSON. It does NOT sign, broadcast,
or touch a chain. There is no vault. This is the arithmetic a vault WOULD use, so that the
rules can be tested before any capital is ever at risk.

THREE RULES, adapted from Kinetic's pooled money-market design to Morpho's isolated markets.

RULE 1 - BORROW DEPTH. Max allocation = 20% of the market's current borrow volume.
    Rationale: supplying more than the market borrows drives utilisation toward zero and
    compresses the supply APY to nothing. In a pooled market Kinetic caps this with protocol
    supply caps; in isolated markets the curator must impose the cap themselves.

RULE 2 - ORACLE PROVENANCE. Reject markets whose oracle is not a recognised Chainlink feed.
    Rationale: Morpho allows a custom oracle per market. An unrecognised oracle is not a
    judgement about its quality -- it is the absence of any information, and that cannot be
    underwritten. NOTE: this is weaker than the brief asked for. The brief wanted an update-
    frequency check ("minimum update threshold verified against on-chain block frequency").
    The API exposes oracle TYPE and FEED ADDRESSES but NOT heartbeat or update interval.
    A real latency check needs per-feed on-chain reads. THIS RULE DOES NOT DO THAT and should
    not be described as if it does.
    Verified live: of the top markets, cbBTC and WETH are ChainlinkOracleV2; USDe and HERMES
    report type "Unknown" with no feed addresses.

RULE 3 - VOLATILITY-WEIGHTED LLTV. Reject if (1 - LLTV) / daily_vol < SIGMA_FLOOR.
    Rationale: the liquidation window is intraday. A position dies when price falls further
    than the margin (1 - LLTV) before a liquidator can act.
        margin          = 1 - LLTV
        daily_vol       = annualised_vol / sqrt(365)
        sigma_to_breach = margin / daily_vol
    CHANGE FROM THE BRIEF: the brief said reject where "historical daily drawdowns violate the
    liquidator profitability margin" and suggested comparing LLTV to volatility directly. That
    comparison is dimensionally wrong and rejects the safest markets: cbBTC at 86% LLTV against
    109% ANNUALISED vol would be rejected, yet it is the largest and steadiest market in the
    set. Annualised vol and a margin are different units. sigma_to_breach fixes the units.

    Threshold SIGMA_FLOOR = 2.0 is a parameter, not a finding. It is set so that a market
    needs more than a 2-sigma daily move to breach. That is a policy choice and is exposed
    as configuration for that reason.

RULE 4 - RESERVE BUFFER. Deployable capital = total * (1 - RESERVE_BUFFER), default 15%.
    Rationale: a vault's deposit side is demand-driven. Depositors withdraw on their schedule,
    not the vault's, and Morpho markets can sit at 100% utilisation with no liquidity to
    redeem. A buffer is therefore NOT a fallback for when opportunities are scarce -- it is a
    structural cost of accepting deposits at all. It holds whether one market is eligible or
    fifty.
    Every downstream budget derives from the deployable figure, so the reserve cannot be
    bypassed by a later rescale.

RULE 5 - COLLATERAL CONCENTRATION. No single collateral symbol may exceed 30% of CAPITAL.
    Rationale: Morpho isolates MARKETS; it does not isolate a curator from re-pooling. Five
    cbBTC markets with different market ids are one economic position. That is precisely the
    concentration Kinetic prevents with protocol-level supply caps, and in an isolated
    landscape the curator must impose it instead.

    OBSERVED LIMIT: with 11 eligible collateral groups, budgets sum to 11 x 30% = 330% of
    deployable capital, so the total-cap rescale dominates and every group lands near 9%. The
    30% ceiling is therefore INERT at current market breadth and binds only below four groups.
    That is asserted in tests 8b and 8c so nobody assumes the cap is doing work it is not. The
    grouping still usefully re-weights WITHIN buckets by sigma-to-breach.

DEFERRED - CROSS-ASSET CORRELATION. Grouping is by collateral SYMBOL. It catches five cbBTC
    markets. It does NOT catch cbBTC and LBTC moving together, nor USDe and sUSN as the same
    delta, nor wrapped-vs-native BTC pairs. A real correlation model needs a return series per
    collateral and a covariance matrix; the price history is already cached in
    price_cache.json, so it is feasible, but it is a separate piece of work and is NOT claimed
    here. Until then, symbol grouping is strictly better than nothing and strictly worse than
    a covariance model.

Every rule is configurable. Every rejection records the number that caused it.
"""
import json, math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "allocation.json")

# --- policy parameters. change these deliberately, not incidentally. ---
BORROW_DEPTH_PCT = 0.20      # cap at 20% of the market's current borrow volume
SIGMA_FLOOR = 2.0            # reject if a <2-sigma daily move would breach the position
MIN_ALLOC_USD = 1_000        # below this the borrow-depth cap is too small to bother with
MIN_POSITION_USD = 150.0     # TRANSACTION-COST FLOOR. A position smaller than this cannot
                             # pay for its own rebalancing: a 5% trigger on $150 is $7.50, and
                             # gas is cents, so the deadband actually binds. Derived from the
                             # observed $0.02 gas cost and a ~5% APY: at $150 a rebalance costs
                             # roughly one day's yield. Below it, splitting capital across many
                             # markets manufactures dust that no trigger can economically move.
ACCEPTED_ORACLE_TYPES = ("ChainlinkOracle", "ChainlinkOracleV2")
MAX_COLLATERAL_CONCENTRATION = 0.30   # no single collateral asset may exceed 30% of capital
RESERVE_BUFFER = 0.15                 # capital NEVER deployed. see the docstring note below.
                                      # this is structural, not a fallback: a vault whose
                                      # deposit-side is demand-driven must hold exit liquidity
                                      # regardless of how attractive the lending side looks.
                                      # 100% deployment was observed once (a 30% group cap that
                                      # does not bind) and that is exactly the failure mode this
                                      # prevents: full allocation arising from arithmetic rather
                                      # than from a decision.
LOCK_UTIL = 0.95                     # utilisation at which Morpho locks withdrawals
MAX_RUNWAY_SHARE = 0.50              # a position may occupy at most half the exit runway.
                                     # NOT a finding: a policy choice. At 1.0 a position uses the
                                     # entire runway and the next depositor out freezes the market;
                                     # at 0.5 there is always somewhere for the position to go.
SIGMA_WEIGHT_CAP = 10.0               # cap the sigma weight: sUSN's sigma of 300 must not
                                      # crowd out everything else in its bucket


def _water_fill(candidates, budget, cap_key, weight_key):
    """Distribute `budget` across candidates: proportional to weight, capped per candidate.

    Iterative, because a cap that binds frees budget for the others. Returns {market_id: usd}.

    Weight is clamped to SIGMA_WEIGHT_CAP. Without the clamp a single very safe market (a
    sigma-to-breach of 300) would absorb its whole bucket and the other markets in it would
    receive nothing, which is concentration risk dressed up as prudence.
    """
    out = {c["market_id"]: 0.0 for c in candidates}
    active = [c for c in candidates if (c.get(cap_key) or 0) > 0]
    remaining = float(budget)
    guard = 0
    while remaining > 1e-6 and active and guard < 1000:
        guard += 1
        weights = {}
        for c in active:
            w = c.get(weight_key)
            weights[c["market_id"]] = min(float(w), SIGMA_WEIGHT_CAP) if w else 0.0
        wsum = sum(weights.values())
        if wsum <= 0:                      # no usable weights: equal split
            weights = {c["market_id"]: 1.0 for c in active}
            wsum = float(len(active))
        start = remaining
        distributed = 0.0
        still = []
        for c in active:
            share = start * (weights[c["market_id"]] / wsum)
            room = (c.get(cap_key) or 0) - out[c["market_id"]]
            take = min(share, room)
            if take > 0:
                out[c["market_id"]] += take
                distributed += take
            if room - take > 1e-6:
                still.append(c)
        remaining -= distributed
        active = still
        if distributed <= 1e-9:
            break
    return out


def daily_vol(pts):
    """Annualised vol from a price history, then converted to daily. Returns (ann_pct, daily_pct, n)."""
    ys = sorted(((float(p["x"]), float(p["y"])) for p in (pts or []) if p.get("y")),
                key=lambda t: t[0])
    px = [y for _, y in ys if y and y > 0]
    if len(px) < 10:
        return None, None, len(px)
    rets = [math.log(px[i] / px[i - 1]) for i in range(1, len(px)) if px[i - 1] > 0]
    if len(rets) < 8:
        return None, None, len(px)
    sd = statistics.stdev(rets)
    ann = sd * math.sqrt(365) * 100
    return ann, ann / math.sqrt(365), len(px)


def evaluate_market(m, oracle_type, price_pts, capital_usd, sigma_hint=None):
    """Return a per-market decision dict. Never raises; missing data fails CLOSED."""
    reasons, fails = [], []
    mid = m.get("market_id")
    tvl = m.get("tvl_usd") or 0.0
    borrow = m.get("borrow_usd") or 0.0
    lltv = m.get("lltv")
    coll = m.get("collateral")

    # a market must be REAL to receive anything at all
    if m.get("verdict") != "REAL":
        fails.append("NOT_REAL")
        reasons.append("screen verdict is %s: %s" % (m.get("verdict"), ", ".join(m.get("fails") or [])))

    # RULE 1: borrow depth
    cap = borrow * BORROW_DEPTH_PCT
    if cap < MIN_ALLOC_USD:
        fails.append("NO_DEPTH")
        reasons.append("20%% of borrow volume ($%s) is below the $%s floor"
                       % (format(int(borrow), ","), format(MIN_ALLOC_USD, ",")))

    # RULE 1b: RUNWAY TO THE 95% LOCK. A market freezes when utilisation reaches 95%: deposits
    # cannot be redeemed while borrows occupy the pool. The existing depth cap is `borrow * 20%`,
    # which is a BORROW-side limit and says nothing about how much can be WITHDRAWN.
    #
    # WHY THIS IS A SEPARATE RULE. Free liquidity (supply - borrow) is NOT the distance to the
    # lock. A market at 91% utilisation has 9% of supply free but only
    #   supply - borrow/0.95
    # of room before it freezes, which is far less. MEASURED on the live book: cbZEC at 91.34%
    # utilisation has $138,756 free but only $61,728 of runway -- and the allocator had assigned it
    # a $70,833 target, which is 1.15x the runway. The position could not fully exit without
    # pushing the market to the freeze. The old check passed it because free liquidity exceeded the
    # target. Every other funded position sits at 0.60 or below.
    supply = m.get("tvl_usd")
    util = m.get("utilization")
    if supply and util is not None:
        runway = supply - (supply * util) / LOCK_UTIL
        if runway <= 0:
            fails.append("NO_RUNWAY")
            reasons.append("utilisation %.1f%% is at or past the %.0f%% withdrawal lock: a "
                           "depositor cannot exit at any size"
                           % (util * 100, LOCK_UTIL * 100))
        else:
            # the largest position this market can absorb without the position itself being
            # unable to leave: it occupies at most MAX_RUNWAY_SHARE of the available runway
            max_fit = runway * MAX_RUNWAY_SHARE
            if cap > max_fit:
                cap = max_fit
                reasons.append("position capped to $%s: %.0f%% of the $%s runway to the %.0f%% "
                               "lock (utilisation %.1f%%)"
                               % (format(int(cap), ","), MAX_RUNWAY_SHARE * 100,
                                  format(int(runway), ","), LOCK_UTIL * 100, util * 100))

    # RULE 2: oracle provenance
    if oracle_type not in ACCEPTED_ORACLE_TYPES:
        fails.append("ORACLE_UNVERIFIED")
        reasons.append("oracle type %r is not a recognised Chainlink feed; feed heartbeat is not "
                       "exposed by the API, so latency cannot be checked" % oracle_type)

    # RULE 3: volatility-weighted LLTV. Prefer sigma already stored in the run: it was
    # computed at screen time from the same cache, and recomputing it here would let the two
    # paths drift apart -- the exact failure this project keeps finding.
    ann, dv, n = daily_vol(price_pts)
    if sigma_hint and sigma_hint.get(m.get("market_id")) is not None:
        sigma = sigma_hint[m.get("market_id")]
        if lltv is None or sigma < SIGMA_FLOOR:
            fails.append("LIQUIDATION_THIN")
            reasons.append("margin %.1f%% is only %.1f daily sigmas (from the run)"
                           % ((1 - lltv) * 100 if lltv else 0, sigma))
        return {
            "market_id": mid, "collateral": coll, "lltv": lltv,
            "tvl_usd": round(tvl, 2), "borrow_usd": round(borrow, 2),
            "capacity_usd": round(cap, 2), "oracle_type": oracle_type,
            "ann_vol_pct": m.get("ann_vol_pct"), "daily_vol_pct": m.get("daily_vol_pct"),
            "sigma_to_breach": sigma,
            "eligible": not fails, "fails": fails, "reasons": reasons,
            "unconstrained_usd": 0.0,
        }
    if lltv is None or dv is None or dv <= 0:
        fails.append("VOL_UNKNOWN")
        reasons.append("no usable price history (%d points); cannot compute sigma-to-breach" % n)
        sigma = None
    else:
        margin = 1.0 - lltv
        sigma = margin / (dv / 100.0)
        if sigma < SIGMA_FLOOR:
            fails.append("LIQUIDATION_THIN")
            reasons.append("margin %.1f%% is only %.1f daily sigmas (daily vol %.2f%%); "
                           "a routine move breaches the position" % (margin * 100, sigma, dv))

    ok = not fails
    alloc = 0.0
    if ok:
        alloc = round(min(cap, capital_usd * BORROW_DEPTH_PCT * 5), 2)   # provisional; normalised below
    return {
        "market_id": mid, "collateral": coll, "lltv": lltv,
        "tvl_usd": round(tvl, 2), "borrow_usd": round(borrow, 2),
        "capacity_usd": round(cap, 2), "oracle_type": oracle_type,
        "ann_vol_pct": round(ann, 2) if ann is not None else None,
        "daily_vol_pct": round(dv, 3) if dv is not None else None,
        "sigma_to_breach": round(sigma, 2) if sigma is not None else None,
        "eligible": ok, "fails": fails, "reasons": reasons,
        "unconstrained_usd": alloc,
    }


def allocate_from_run(run_dir, capital_usd=1_000_000.0):
    """Allocate from ONE immutable run directory, using only that run's artefacts.

    WHY THIS IS THE RIGHT ENTRY POINT. The flat-file path (morpho_markets.json +
    lending_screen.json) reads files that are overwritten on every cycle, so an allocation
    produced from them cannot be tied to a block. Everything else in this project is
    provenance-stamped and replay-verified; the allocator's output was the one artefact that
    was not. This reads runs/<iso>/markets.json and runs/<iso>/screen.json instead, so the
    allocation inherits the run's block, timestamp and checksums.

    sigma_to_breach now arrives INSIDE the run, so the safety ranking needs no external cache.
    """
    import json as _json
    mp = os.path.join(run_dir, "markets.json")
    sp = os.path.join(run_dir, "screen.json")
    if not (os.path.exists(mp) and os.path.exists(sp)):
        raise SystemExit("run dir %s lacks markets.json or screen.json" % run_dir)
    markets = _json.load(open(mp))
    screen = _json.load(open(sp))
    otypes = {m.get("market_id"): (m.get("oracle_type") or "Unknown") for m in markets}
    phist = {m.get("market_id"): m.get("_price_history") or [] for m in markets}
    # sigma is already in the run; pass it through so evaluate_market does not recompute it
    res = allocate(markets, screen, otypes, phist, capital_usd=capital_usd,
                   sigma_hint={m.get("market_id"): m.get("sigma_to_breach") for m in markets})
    res["run_dir"] = os.path.basename(os.path.abspath(run_dir))
    return res


def allocate(markets, screen, oracle_types, price_histories, capital_usd=1_000_000.0,
             sigma_hint=None):
    """Full pipeline: evaluate every market, then size the survivors.

    Sizing respects each market's borrow-depth cap, then distributes the remainder evenly.
    If nothing is eligible the target is 100% unallocated - which is a defined state, not an
    error. A vault that cannot find a defensible market should hold cash.
    """
    scr = {s["market_id"]: s for s in screen}
    rows = []
    for m in markets:
        s = scr.get(m.get("market_id"))
        if s is None:
            continue
        merged = dict(m)
        merged["verdict"] = s["verdict"]
        merged["fails"] = s.get("fails")
        rows.append(evaluate_market(merged, oracle_types.get(m.get("market_id")),
                                     price_histories.get(m.get("market_id")), capital_usd,
                                     sigma_hint=sigma_hint))

    elig = [r for r in rows if r["eligible"]]

    # DEPLOYABLE capital, after the structural reserve. Every downstream budget derives from
    # this, so the buffer cannot be bypassed by a later rescale.
    deployable = capital_usd * (1.0 - RESERVE_BUFFER)

    # POSITION COUNT. Spreading $85 across 13 markets produces $6.54 positions that no
    # deadband can economically move -- the rebalance trigger is smaller than the gas. So the
    # allocator first decides HOW MANY positions the capital can sustain above MIN_POSITION_USD,
    # ranks markets by safety margin, and takes only that many. The remainder stays in cash.
    # Fragmentation is not diversification when each fragment is too small to maintain.
    max_positions = int(deployable // MIN_POSITION_USD)
    capped = [r for r in elig if (r.get("capacity_usd") or 0) >= MIN_POSITION_USD]
    # rank by safety margin, tie-broken by borrow depth so the largest market wins
    capped.sort(key=lambda r: (-(min(r.get("sigma_to_breach") or 0, SIGMA_WEIGHT_CAP)),
                               -(r.get("capacity_usd") or 0)))
    selected = capped[:max_positions] if max_positions > 0 else []
    selected_ids = {r["market_id"] for r in selected}
    for r in rows:
        if r["market_id"] not in selected_ids:
            r.setdefault("target_usd", 0.0)

    # Collateral grouping, applied to the SELECTED set. Morpho isolates MARKETS; a curator
    # allocating across several markets sharing one collateral has re-created the pooled
    # exposure Morpho removed. Five cbBTC markets with different ids are ONE position.
    by_coll = {}
    for r in selected:
        by_coll.setdefault(r.get("collateral") or "(unknown)", []).append(r)

    # THE CAP YIELDS TO THE FLOOR. A 30% cap on $425 deployable is $127.50, which is BELOW the
    # $150 floor -- so every group was allocated $127.50 and then dropped as dust, leaving the
    # whole $425 (or $500) range unusable. That is a contradiction, not a policy: a cap exists
    # to stop one collateral dominating the OTHERS, and with a single position there are no
    # others. So the effective cap is the larger of the nominal cap and what it takes to fund
    # every selected position at the floor.
    n_groups = max(1, len(by_coll))
    floor_pressure = deployable / n_groups if n_groups else deployable
    effective_cap = max(deployable * MAX_COLLATERAL_CONCENTRATION,
                        min(MIN_POSITION_USD, floor_pressure, deployable))
    for coll, group in sorted(by_coll.items()):
        got = _water_fill(group, effective_cap, "capacity_usd", "sigma_to_breach")
        for r in group:
            r["target_usd"] = round(max(0.0, got[r["market_id"]]), 2)

    # enforce the floor: a position that lands below MIN_POSITION_USD is dropped entirely and
    # its budget stays in cash, rather than being trimmed to a size that cannot be maintained.
    for r in rows:
        if 0 < r.get("target_usd", 0) < MIN_POSITION_USD:
            r.setdefault("dropped_below_floor", r["target_usd"])
            r["target_usd"] = 0.0

    for r in rows:
        r.setdefault("target_usd", 0.0)

    # total cap: bucket budgets can sum above capital when there are 4+ collaterals, so scale
    # everything down proportionally. Scaling only ever reduces, so the 30% group cap holds.
    raw_total = sum(r["target_usd"] for r in rows)
    scale = 1.0
    if raw_total > deployable and raw_total > 0:
        scale = deployable / raw_total
        for r in rows:
            r["target_usd"] = round(r["target_usd"] * scale, 2)

    for r in rows:
        r["target_pct"] = round(r["target_usd"] / capital_usd * 100, 4) if capital_usd else 0.0

    # which constraints actually bound? reported so a reader can see why capital is idle.
    binding = []
    for coll, group in sorted(by_coll.items()):
        used = sum(r["target_usd"] for r in rows if (r.get("collateral") or "(unknown)") == coll)
        if scale < 1.0:
            binding.append({"collateral": coll, "reason": "total capital scaled by %.4f" % scale,
                            "group_usd": round(used, 2)})
        else:
            binding.append({"collateral": coll, "reason": "at the effective group cap" if used >= effective_cap - 1 else "capacity-bound",
                            "group_usd": round(used, 2)})

    # Per-market round(x,2) sums ABOVE the budget: six markets each rounding up by <1 cent
    # pushed the total $0.02 past the 85% limit. A cap that can be exceeded by rounding is
    # not a cap. Truncate, then give any残 remainder to the largest holding so the total is
    # exactly the budget when capacity allows.
    for r in rows:
        r["target_usd"] = math.floor(r["target_usd"] * 100) / 100.0
    allocated = sum(r["target_usd"] for r in rows)

    # if per-market flooring still left the total above the ceiling, trim the largest holdings
    if allocated > deployable:
        over = allocated - deployable
        for r in sorted(rows, key=lambda x: -x["target_usd"]):
            if over <= 0:
                break
            cut = min(r["target_usd"], over)
            r["target_usd"] = round(r["target_usd"] - cut, 2)
            over -= cut
        allocated = sum(r["target_usd"] for r in rows)
    return {
        "capital_usd": capital_usd,
        "allocated_usd": round(allocated, 2),
        "unallocated_usd": round(capital_usd - allocated, 2),
        "unallocated_pct": round((capital_usd - allocated) / capital_usd * 100, 4) if capital_usd else 0.0,
        "reserve_usd": round(capital_usd * RESERVE_BUFFER, 2),
        "reserve_pct": round(RESERVE_BUFFER * 100, 4),
        "deployable_usd": round(deployable, 2),
        "params": {"borrow_depth_pct": BORROW_DEPTH_PCT, "sigma_floor": SIGMA_FLOOR,
                   "min_alloc_usd": MIN_ALLOC_USD, "accepted_oracle_types": list(ACCEPTED_ORACLE_TYPES),
                   "max_collateral_concentration": MAX_COLLATERAL_CONCENTRATION,
                   "reserve_buffer": RESERVE_BUFFER,
                   "sigma_weight_cap": SIGMA_WEIGHT_CAP,
                   "min_position_usd": MIN_POSITION_USD},
        "n_collateral_groups": len(by_coll),
        "n_selected": len(selected),
        "max_positions_affordable": max_positions,
        "n_capacity_eligible": len(capped),
        "effective_collateral_cap_usd": round(effective_cap, 2),
        "nominal_collateral_cap_usd": round(deployable * MAX_COLLATERAL_CONCENTRATION, 2),
        "cash_due_to_floor_usd": round(deployable - allocated, 2),
        "group_utilisation": binding,
        "total_scaled_by": round(scale, 6),
        "n_evaluated": len(rows), "n_eligible": len(elig),
        "markets": sorted(rows, key=lambda r: -r["target_usd"]),
    }


def write_into_run(run_dir, capital_usd=1_000_000.0):
    """Write allocator.json INTO the run directory. Returns the path or None.

    The allocation becomes a checksummed artefact of the run, like markets.json and
    screen.json, so a target can be tied to the block it was derived from.
    """
    import json as _json
    try:
        res = allocate_from_run(run_dir, capital_usd=capital_usd)
    except Exception as e:
        print("  [allocator skipped: %s]" % str(e)[:70])
        return None
    p = os.path.join(run_dir, "allocator.json")
    with open(p, "w") as fh:
        _json.dump(res, fh, indent=1)
    return p


def main():
    import morpho_fetch as mf
    try:
        markets = json.load(open(os.path.join(HERE, "morpho_markets.json")))
        screen = json.load(open(os.path.join(HERE, "lending_screen.json")))
    except Exception as e:
        print("need morpho_markets.json and lending_screen.json: %s" % e)
        return 1

    # fetch oracle type + collateral price history per market (read-only).
    # CACHED: one GraphQL call per market dominates runtime and we rerun constantly.
    CACHE = os.path.join(HERE, "price_cache.json")
    phist = {}
    if os.path.exists(CACHE):
        try:
            phist = json.load(open(CACHE))
        except Exception:
            phist = {}
    print("fetching price histories for %d markets (%d cached)..." % (len(markets), len(phist)), flush=True)
    otypes = {m["market_id"]: (m.get("oracle_type") or "Unknown") for m in markets}
    # AN ALL-NULL SERIES IS A REFETCH TRIGGER, NOT A COVERED ONE. The old `todo` test asked only
    # "is the market_id present" -- so a market whose whole price series came back null was
    # cached once and NEVER retried: 30 of 61 entries sat all-null for over a day while the
    # rest populated. Each all-null market is now retried on a later pass (bounded, so a
    # genuinely dead feed costs one request per cycle, not a loop).
    def _all_null(v):
        return not v or all(p.get("y") is None for p in v)
    todo = [m for m in markets if m["market_id"] not in phist or _all_null(phist[m["market_id"]])]
    n_null_before = sum(1 for v in phist.values() if _all_null(v))
    if n_null_before:
        print("  %d cached series are ALL-NULL; refetching them" % n_null_before, flush=True)
    fetched = 0
    for m in todo:
        try:
            # use fetch_history(): it unwraps the {"marketById": ...} envelope correctly.
            # re-implementing that here is what caused every price history to come back
            # empty, which surfaced as VOL_UNKNOWN on all 60 markets -- a silent failure
            # that looked like "no volatility data available" rather than "wrong nesting".
            h = mf.fetch_history(m["market_id"])
            phist[m["market_id"]] = ((h or {}).get("collateralAsset") or {}).get("historicalPriceUsd") or []
        except Exception:
            # keep the old series on a fetch error: refetching must be able to IMPROVE the
            # cache, never to blank it
            phist.setdefault(m["market_id"], [])
        fetched += 1
        if fetched % 15 == 0:
            json.dump(phist, open(CACHE, "w"))
            print("  %d/%d fetched" % (fetched, len(todo)), flush=True)
    json.dump(phist, open(CACHE, "w"))
    usable = sum(1 for v in phist.values() if not _all_null(v))
    print("  %d with price history" % sum(1 for v in phist.values() if v), flush=True)
    print("  %d usable (%d still all-null: no prices published for their collateral)"
          % (usable, sum(1 for v in phist.values() if _all_null(v))), flush=True)

    res = allocate(markets, screen, otypes, phist)
    json.dump(res, open(OUT, "w"), indent=1)
    print("\nwrote %s" % OUT)
    print("  capital        $%s" % format(int(res["capital_usd"]), ","))
    print("  allocated      $%s (%.2f%%)" % (format(int(res["allocated_usd"]), ","), 
                                             res["allocated_usd"] / res["capital_usd"] * 100))
    print("  UNALLOCATED    $%s (%.2f%%)" % (format(int(res["unallocated_usd"]), ","),
                                             res["unallocated_pct"]))
    print("  eligible       %d of %d" % (res["n_eligible"], res["n_evaluated"]))
    import collections
    c = collections.Counter(f for r in res["markets"] for f in r["fails"])
    print("\n  rejection reasons:")
    for k, v in c.most_common():
        print("    %-20s %d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
