"""Weighted choices driven by the weekly analysis (falls back to uniform)."""
from __future__ import annotations

import random


def get(con, dimension: str) -> dict[str, float]:
    return {r["value"]: r["weight"] for r in con.execute("SELECT value, weight FROM weights WHERE dimension=?", (dimension,))}


def choose(con, dimension: str, options: list[str], exclude: set[str] | None = None, rng=random) -> str | None:
    opts = [o for o in options if not exclude or o not in exclude] or list(options)
    if not opts:
        return None
    w = get(con, dimension)
    # unseen options get the mean weight so new things still get explored
    mean = sum(w.values()) / len(w) if w else 1.0
    ws = [max(0.01, w.get(o, mean)) for o in opts]
    return rng.choices(opts, weights=ws, k=1)[0]
