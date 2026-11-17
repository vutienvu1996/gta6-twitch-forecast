# Model: launch-shape forecaster for GTA VI Twitch viewers

## What it forecasts

For a case — Twitch viewers of a game's category recorded up to the end of its UTC
release day's first hour, that hour's print included — `main.py` writes, for each of
hours 2–24, five quantiles (5%, 25%, 50%, 75%, 95%) of that hour's viewer count.
Scored by mean pinball loss on the log scale; a prize needs a loss strictly below the
best house entry's.

## How it works

1. **Launch-shape ratios.** For every comparable past launch in the case, take its UTC
   release-day hourly curve and form log-ratios `r_h = ln(v_h / v_1)`, h = 2..24. A
   launch's day curve is mostly its *shape* times its hour-1 scale, so ratios transfer
   across launches of very different sizes.
2. **Analogue pool.** Keep only comparables whose 24 release-day hours are all present,
   whose hour-1 print is at least 1,000 viewers, and whose unlock note does not say
   "early access". Tiny hour-1 launches are mostly single simultaneous global unlocks
   (the game had not opened yet at 00:00 UTC, so hour 1 is near zero and the ratios
   explode); early-access launches already peaked days before release, so their day
   curves are flat. Neither shape fits a rolling-midnight console launch without early
   access, which is what GTA VI is.
3. **Scale-similar weighting.** Weight each comparable by a Gaussian kernel on log
   hour-1 scale, `exp(-0.5 * ((ln p1_c - ln p1) / 1.0)^2)`. Small launches climb much
   harder over the day (median late-day ratio +2) than mega-launches (near flat), so
   hour-1 scale is the strongest predictor of the day's shape.
4. **Bias correction.** The weighted mean slightly under-predicts late hours, so add a
   per-hour intercept fitted by leave-one-out inside the pool: for each comparable,
   forecast its ratios from the other comparables and take the mean residual per hour.
5. **Quantiles.** Centre = weighted mean ratio + intercept; spread = the pool's weighted
   standard deviation of ratios around the centre, halved (the full cross-launch spread
   is wider than the residual uncertainty around a scale-matched centre), floored at
   0.15 in log units. `q_tau(h) = p1 * exp(centre_h + z_tau * sd_h)`, z the standard
   normal quantiles at the five scored levels, rounded to 2 decimals half-up.

Everything is fitted at run time from the case's own comparables — no constants were
taken from outside the case file, and the final case's 42 comparables (which include
the four practice launches) are used the same way. The case's `history`, `streams` and
`categories_hourly` are not used: they are null or minute-resolution in ways the
practice cases cannot validate, and unvalidatable inputs are a risk, not a feature.

## Validation (practice, scored with the contest's own rule)

Practice answers are SullyGnome's hourly averages for the four practice launches'
release days (verified: each case's hour-1 print matches its SullyGnome hour exactly).
Loss = mean pinball loss over 23 hours × 5 quantiles; typical miss = mean |log error|
of the median, in percent; coverage = share of hours inside the 5%–95% band.

| case | launch | hour-1 | loss | typical miss | coverage |
|---|---|---|---|---|---|
| p00 | Marvel's Wolverine | 23,357 | 0.191 | 36.9% | 1.00 |
| p01 | Red Dead Redemption 2 | 116,550 | 0.138 | 24.8% | 0.91 |
| p02 | God of War Ragnarök | 269,517 | 0.105 | 15.8% | 0.87 |
| p03 | Marvel's Spider-Man 2 | 119,087 | 0.196 | 30.0% | 0.74 |
| **mean** | | | **0.157** | | **0.88** |

House persistence baseline on the same four cases: mean loss **0.387**, coverage 0.78.
This entry beats it by 59%. The design was chosen on the practice mean, not on any
single case: the loss surface is flat around the chosen parameters (bandwidth 1.0,
spread multiplier 0.5, floor 0.15), and the runner-ups (plain weighted mean, no bias
correction) score 0.160–0.167, so the result does not hinge on a knife-edge choice.

## Determinism and limits

Comparables are processed in name order, no randomness, no network, no clock reads:
two runs on the same case write byte-identical output (verified, sha256-identical).
Runtime ~0.15 s per case on this machine, far under the 8 s / 1 CPU / 1024 MB cap.
Output is 23 rows, ~1.5 KB, under the 65,536-byte cap. If a case ships no usable
comparable, the program falls back to the house persistence formula rather than
crashing.
