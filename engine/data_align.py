"""Timestamp alignment for multi-feed data.

The signal engine and backtester pair cash/futures/index candles *by position*
(e.g. futures premium = futures[i].close - cash[i].close). A single missing or
extra candle in any feed silently shifts everything and corrupts those signals.

align_by_timestamp() intersects the feeds on their 'datetime' key so position i
refers to the same minute in every feed, and reports what was dropped.
"""


def _key(c: dict) -> str:
    return str(c.get("datetime", ""))


def align_by_timestamp(
    cash: list[dict],
    futures: list[dict] | None,
    index: list[dict] | None,
) -> tuple[list[dict], list[dict] | None, list[dict] | None, dict]:
    """Return (cash, futures, index) restricted to common timestamps + diagnostics.

    Cash is the anchor. If futures/index are absent they pass through as None.
    If an auxiliary feed shares no timestamps with cash it is dropped to None
    (better to ignore it than to misalign by position).
    """
    diag: dict = {
        "aligned": True,
        "cash_in": len(cash or []),
        "warnings": [],
    }
    if not cash:
        return cash, futures, index, diag

    def _intersect(name: str, aux: list[dict] | None) -> list[dict] | None:
        if not aux:
            return None
        aux_map = {_key(c): c for c in aux if _key(c)}
        common = [aux_map[_key(c)] for c in cash if _key(c) in aux_map]
        if len(common) != len(cash):
            diag["aligned"] = False
            diag["warnings"].append(
                f"{name}: {len(common)}/{len(cash)} candles aligned to cash "
                f"({len(aux)} {name} candles in)"
            )
        if not common:
            diag["warnings"].append(f"{name}: no overlapping timestamps — dropped")
            return None
        # Re-key auxiliary to cash's timeline; for missing minutes carry forward.
        aux_map2 = {_key(c): c for c in common}
        out, last = [], None
        for c in cash:
            hit = aux_map2.get(_key(c))
            if hit is not None:
                last = hit
            out.append(last if last is not None else c)
        return out

    fut_aligned = _intersect("futures", futures)
    idx_aligned = _intersect("index", index)
    diag["futures_aligned"] = bool(fut_aligned)
    diag["index_aligned"] = bool(idx_aligned)
    return cash, fut_aligned, idx_aligned, diag