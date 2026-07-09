"""Small statistical helpers used by the pure-Python signal engine."""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def sign(value: float, deadband: float = 0.0) -> int:
    if value > deadband:
        return 1
    if value < -deadband:
        return -1
    return 0


def safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den == 0 or den is None:
        return default
    return num / den


def mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return default
    return sum(vals) / len(vals)


def std(values: Iterable[float], default: float = 0.0, sample: bool = False) -> float:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    n = len(vals)
    if n < 2:
        return default
    m = sum(vals) / n
    denom = n - 1 if sample and n > 1 else n
    var = sum((v - m) ** 2 for v in vals) / denom
    return math.sqrt(max(var, 0.0))


def z_score(value: float, baseline: Sequence[float], min_std: float = 1e-12) -> float:
    vals = [float(v) for v in baseline if v is not None and not math.isnan(float(v))]
    if len(vals) < 2:
        return 0.0
    s = max(std(vals), min_std)
    return (float(value) - mean(vals)) / s


def pct_change(old: float, new: float) -> float:
    return safe_div(new - old, abs(old), 0.0)


def simple_returns(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev != 0:
            out.append((curr - prev) / abs(prev))
    return out


def log_returns(values: Sequence[float]) -> List[float]:
    out: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev > 0 and curr > 0:
            out.append(math.log(curr / prev))
    return out


def percentile_rank(values: Sequence[float], value: float) -> float:
    """Return the percentile rank (0-100) of `value` in `values`."""

    vals = sorted(float(v) for v in values if v is not None and not math.isnan(float(v)))
    if not vals:
        return 50.0
    le = sum(1 for v in vals if v <= value)
    return 100.0 * le / len(vals)


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0
    x = [float(v) for v in xs[-n:]]
    y = [float(v) for v in ys[-n:]]
    mx = mean(x)
    my = mean(y)
    sx = std(x)
    sy = std(y)
    if sx <= 1e-12 or sy <= 1e-12:
        return 0.0
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y)) / n
    return clamp(cov / (sx * sy), -1.0, 1.0)


def rolling_correlations(xs: Sequence[float], ys: Sequence[float], window: int) -> List[float]:
    n = min(len(xs), len(ys))
    if n < window:
        return []
    out: List[float] = []
    x = list(xs[-n:])
    y = list(ys[-n:])
    for end in range(window, n + 1):
        out.append(correlation(x[end - window : end], y[end - window : end]))
    return out


def rolling_mean(values: Sequence[float], window: int) -> List[float]:
    if window <= 0 or len(values) < window:
        return []
    vals = list(values)
    out = []
    running = sum(vals[:window])
    out.append(running / window)
    for i in range(window, len(vals)):
        running += vals[i] - vals[i - window]
        out.append(running / window)
    return out


def rolling_std(values: Sequence[float], window: int) -> List[float]:
    if window <= 0 or len(values) < window:
        return []
    vals = list(values)
    return [std(vals[i - window : i]) for i in range(window, len(vals) + 1)]


def true_ranges(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> List[float]:
    n = min(len(highs), len(lows), len(closes))
    if n == 0:
        return []
    out = [float(highs[0]) - float(lows[0])]
    for i in range(1, n):
        high = float(highs[i])
        low = float(lows[i])
        prev_close = float(closes[i - 1])
        out.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return out


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], window: int) -> float:
    trs = true_ranges(highs, lows, closes)
    if len(trs) < window:
        return mean(trs, 0.0)
    return mean(trs[-window:])


def bollinger_widths(closes: Sequence[float], window: int = 20, deviations: float = 2.0) -> List[float]:
    if len(closes) < window:
        return []
    out: List[float] = []
    vals = list(float(v) for v in closes)
    for i in range(window, len(vals) + 1):
        chunk = vals[i - window : i]
        m = mean(chunk)
        s = std(chunk)
        if abs(m) <= 1e-12:
            out.append(0.0)
        else:
            out.append(((m + deviations * s) - (m - deviations * s)) / abs(m))
    return out


def normalised_sign_entropy(values: Sequence[float]) -> float:
    """Shannon entropy of negative/flat/positive changes, scaled 0-1.

    Low values mean movement states have collapsed into one bucket, a useful
    companion reading for volatility compression.
    """

    if len(values) < 2:
        return 1.0
    rets = simple_returns(values)
    if not rets:
        return 1.0
    eps = max(std(rets) * 0.1, 1e-12)
    counts = [0, 0, 0]
    for r in rets:
        if r > eps:
            counts[2] += 1
        elif r < -eps:
            counts[0] += 1
        else:
            counts[1] += 1
    total = sum(counts)
    if total == 0:
        return 1.0
    ent = 0.0
    for c in counts:
        if c:
            p = c / total
            ent -= p * math.log(p)
    return ent / math.log(3)


def linear_slope(values: Sequence[float]) -> float:
    """Least-squares slope for equally spaced observations."""

    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = mean(xs)
    my = mean(values)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom <= 1e-12:
        return 0.0
    return sum((x - mx) * (float(y) - my) for x, y in zip(xs, values)) / denom
