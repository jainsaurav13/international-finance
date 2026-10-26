# LLM log

- **Model:** Claude Opus 5.5 (Anthropic), via Claude Code
- **Date:** 2026-10-26

## Prompt 1

> create a new repo on my github called international finance

## Prompt 2

> done, I created it — attach it

## Prompt 3

> edit things there itself. this is the instruction below. on what you are supposed to do.
>
> Build a real exchange rate app. Use an LLM to build a Streamlit app with IMF data, save the code on GitHub, and publish it online. [...]
>
> App and economic requirements:
> - Allow users to choose Country 1 and Country 2 from IMF countries and the Euro area. Retrieve monthly IMF CPI and exchange-rate data from January 1976 where available.
> - Define S(t) as units of Country 2 currency per one unit of Country 1 currency; let P1(t) and P2(t) be the respective monthly CPIs. Calculate RER(t) = S(t) × P1(t) / P2(t).
> - Over the user-selected start and end months, calculate RER* = average of RER(t) over valid months; plot Real Index(t) = 100 × RER(t) / RER*. Recalculate RER* if dates change. Plot nominal S(t) in actual currency units—do not normalize it.
> - Let users select Real, Nominal, or Both in interactive charts (use separate axes for Both) and provide a CSV download button of all observations and calculations within the selected sample period.
>
> Data hints: IMF API fetch is https://api.imf.org/external/sdmx/3.0; monthly CPI key {ISO3}.CPI._T.IX.M; exchange-rate key {ISO3}.XDC_USD.PA_RT.M, where ISO3 is the country code. The IMF uses G163 for the Euro area. IMF exchange rates are local-currency units per USD, so convert them to the stated S(t) direction. Ask your LLM for complete three files: app.py, requirements.txt, and README.md files compatible with Python 3.12. IMF data may have gaps or limited coverage.

## What the LLM did

- Wrote `app.py`, `requirements.txt` and `README.md`, and committed them to this repo.
- Tested the calculations with synthetic data. A GBP rate of 0.8 per USD gave S = 1.25 USD per GBP, and the real index averaged exactly 100 after the dates changed.
- Ran the app headlessly in Real, Nominal and Both modes.
- Couldn't test against the live IMF API, because its sandbox blocked api.imf.org. The live test happens after deploying to Streamlit.
