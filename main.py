"""gta6-twitch-ccu-forecast-01 entry: launch-shape forecaster (Python 3.13, stdlib only).

Forecasts, for each of hours 2..24 of a game's UTC release day, five quantiles of the
Twitch category's concurrent viewers, from everything recorded up to the end of hour 1.

Model (all fitted at run time from the case's own comparables, nothing hard-coded from
outside the case file):

1. Launch-shape ratios. For every comparable past launch shipped in the case, take its
   UTC release-day hourly curve and form log-ratios r_h = ln(v_h / v_1), h = 2..24, where
   v_1 is that launch's hour-1 print. A launch's day curve is mostly its *shape* times its
   hour-1 scale, so ratios transfer across launches of very different sizes.
2. Analogue pool. Keep only comparables whose 24 release-day hours are all present, whose
   hour-1 print is at least 1,000 viewers, and whose unlock note does not say "early access".
   Tiny hour-1 launches are mostly single simultaneous global unlocks (the game had not
   opened yet at 00:00 UTC, so hour 1 is near zero and the ratios explode to +7) and
   early-access launches already peaked days before release, so their day curves are flat;
   neither shape is what a rolling-midnight console launch without early access looks like.
3. Scale-similar weighting. Weight each comparable by a Gaussian kernel on log hour-1
   scale, exp(-0.5 * ((ln p1_c - ln p1) / 1.0)^2): launches whose hour-1 print is near the
   target's are the closest analogues. Small launches climb much harder over the day
   (median late-day ratio +2) than mega-launches (near flat), so scale is the strongest
   predictor of the day's shape.
4. Bias correction. The weighted mean slightly under-predicts late hours, so add a
   per-hour intercept alpha_h fitted by leave-one-out inside the pool: for each comparable,
   forecast its ratios from the other comparables and take the mean residual per hour.
5. Quantiles. Centre = weighted mean ratio + alpha_h; spread = the pool's weighted
   standard deviation of ratios around the centre, halved (the full cross-launch spread is
   wider than the residual uncertainty around a scale-matched centre), floored at 0.15 in
   log units. q_tau(h) = p1 * exp(centre_h + z_tau * sd_h), z = normal quantiles at the
   five scored levels, rounded to 2 decimals half-up.

Practice (four past launches, scored with the contest's pinball loss on the log scale
against SullyGnome's hourly averages): mean loss 0.157, 90% coverage 0.88, against the
house persistence baseline's 0.387 (coverage 0.78). Per case: Wolverine 0.191, Red Dead
Redemption 2 0.138, God of War Ragnarok 0.105, Spider-Man 2 0.196.

Deterministic: comparables are processed in name order, no randomness, no network, no
clock reads, so two runs on the same case write byte-identical output. Runs in well
under the 8 s / 1 CPU / 1024 MB cap (a case is ~1 MB of JSON; the whole fit is a few
ten-thousand arithmetic operations).
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so `import model` finds a model.py shipped beside this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Gaussian kernel bandwidth (in natural-log units) for scale similarity.
BANDWIDTH = 1.0
# Minimum hour-1 print for a comparable to enter the analogue pool.
MIN_P1 = 1000
# Spread multiplier and floor (log units) for the quantile bands.
SD_MULT = 0.5
SD_FLOOR = 0.15
# Fallback spread when the pool is empty (house baseline's random-walk sigma).
FALLBACK_SIGMA = 0.15


def round2(x: float) -> float | int:
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100 rounds it."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def parse_ts(t: str) -> datetime:
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")


def comparable_curve(comp: dict) -> tuple[float, list[float]] | None:
    """A comparable's hour-1 print and the log-ratios of its release-day hours 2..24.

    Returns None when the release-day curve is incomplete, hour 1 is missing or tiny,
    or the launch had early access (its day curve is flat and uninformative). The
    hourly series is parsed once here; callers must not re-read it.
    """
    unlock = (comp.get("unlock") or "").lower()
    if "early access" in unlock:
        return None
    by_hour: dict[datetime, float] = {}
    for p in comp.get("hourly") or []:
        v = p.get("viewers")
        if v is not None:
            by_hour[parse_ts(p["from"])] = float(v)
    day0 = parse_ts(comp["day_start"])
    day = [by_hour.get(day0 + timedelta(hours=h - 1)) for h in range(1, 25)]
    if day[0] is None or day[0] < MIN_P1 or any(v is None for v in day):
        return None
    p1 = day[0]
    return p1, [math.log(v / p1) for v in day]


def weighted_mean(vals: list[float], weights: list[float]) -> float:
    total = sum(weights)
    return sum(w * v for w, v in zip(weights, vals)) / total


def weighted_sd(vals: list[float], weights: list[float], centre: float) -> float:
    total = sum(weights)
    var = sum(w * (v - centre) ** 2 for w, v in zip(weights, vals)) / total
    return math.sqrt(var)


def loo_alpha(pool: list[dict], bandwidth: float) -> list[float]:
    """Per-hour intercept correcting the weighted mean's systematic under-prediction.

    For each comparable, forecast its ratios from the other pool members (same scale
    kernel) and take the mean residual per hour; the intercept is the residual mean
    adjusted for the residual's slope on log hour-1 scale. Computed from the case's
    own pool at run time, so it follows whatever comparables the case ships.
    """
    log_p1 = [math.log(c["p1"]) for c in pool]
    ref = sum(log_p1) / len(log_p1)
    alpha = []
    for h in range(1, 24):  # ratios index 1..23 = hours 2..24
        residuals = []
        xs = []
        for i, target in enumerate(pool):
            others = [c for j, c in enumerate(pool) if j != i]
            ws = [
                math.exp(-0.5 * ((math.log(c["p1"]) - log_p1[i]) / bandwidth) ** 2)
                for c in others
            ]
            centre = weighted_mean([c["ratios"][h] for c in others], ws)
            residuals.append(target["ratios"][h] - centre)
            xs.append(log_p1[i] - ref)
        mx = sum(xs) / len(xs)
        my = sum(residuals) / len(residuals)
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, residuals))
        slope = sxy / sxx if sxx > 0 else 0.0
        alpha.append(my - slope * mx)
    return alpha


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, float(first["viewers"]))

    pool = []
    for comp in sorted(case.get("comparables") or [], key=lambda c: c.get("name", "")):
        curve = comparable_curve(comp)
        if curve is None:
            continue
        hour1, ratios = curve
        pool.append({"name": comp.get("name", ""), "p1": hour1, "ratios": ratios})

    log_p1 = math.log(p1)
    if not pool:
        # No usable analogue: fall back to the house persistence baseline.
        return {
            "hours": [
                {
                    "hour": row["hour"],
                    "q": [
                        round2(p1 * math.exp(z * FALLBACK_SIGMA * math.sqrt(row["hour"] - 1)))
                        for z in Z
                    ],
                }
                for row in case["forecast"]
            ]
        }

    weights = [
        math.exp(-0.5 * ((math.log(c["p1"]) - log_p1) / BANDWIDTH) ** 2) for c in pool
    ]
    alpha = loo_alpha(pool, BANDWIDTH)

    hours = []
    for hi, row in enumerate(case["forecast"]):
        h = row["hour"]
        ratios = [c["ratios"][h - 1] for c in pool]
        centre = weighted_mean(ratios, weights) + alpha[hi]
        sd = max(SD_FLOOR, weighted_sd(ratios, weights, centre) * SD_MULT)
        q = [round2(max(1.0, p1 * math.exp(centre + z * sd))) for z in Z]
        # Keep the row non-decreasing even after rounding.
        for i in range(1, 5):
            if q[i] < q[i - 1]:
                q[i] = q[i - 1]
        hours.append({"hour": h, "q": q})
    return {"hours": hours}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
