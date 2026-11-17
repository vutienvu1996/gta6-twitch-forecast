# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/vutienvu1996/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/vutienvu1996/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Launch-shape forecaster: from the Twitch viewer count of Grand Theft Auto VI recorded
up to the end of its release day's first hour, it forecasts how many people will be
watching it live in each of the other 23 hours, as five quantiles an hour. It learns the
launch-day shape from the case's own comparables — past big launches' hourly curves —
weighting each by how close its hour-1 scale is to the target's, and calibrates its
spreads from the cross-launch variation. Practice loss 0.157 on the contest's pinball
score, against the house persistence baseline's 0.387.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` (Python 3.13, standard library only) reads every `<id>.in` case in the input
directory and writes `<id>.out` — 23 rows, hours 2–24, five quantiles each — to the
output directory. Deterministic: two runs on the same case write byte-identical output.

---

<sub>Entered on [make.fun](https://make.fun/?ref=sjsbmmtj&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
