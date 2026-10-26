# Real Exchange Rate App

A Streamlit app that builds bilateral real exchange rates from IMF monthly CPI and exchange-rate data (January 1976 onward, where available).

## Economics

- **S(t)**: units of Country 2 currency per 1 unit of Country 1 currency.
  The IMF reports each currency in local currency units per USD (E), so S(t) = E2(t) / E1(t).
  Example: Country 1 = UK, Country 2 = US gives S in USD per GBP.
- **RER(t) = S(t) × P1(t) / P2(t)**, where P1 and P2 are the monthly CPI indices.
- **RER\***: the average of RER(t) over valid months in the selected sample. It is recalculated whenever the dates change.
- **Real Index(t) = 100 × RER(t) / RER\***, so it averages 100 over the sample. Above 100 means Country 1 is real-appreciated relative to its sample average.
- Nominal S(t) is plotted in actual currency units, not normalized.

## Features

- Choose any two countries, including the Euro area (IMF code `G163`).
- Choose the start and end months.
- Chart the Real index, Nominal S(t), or Both (on separate y-axes).
- Download a CSV of every month in the sample: both CPIs, both FX rates (LCU per USD), S, RER, RER\* and the real index.
- Check one month by hand: the app shows the full RER calculation for any month you pick.

## Data

The data comes from the IMF SDMX 3.0 API at `https://api.imf.org/external/sdmx/3.0`. No API key is needed.

| Series | Dataflow | Key |
|---|---|---|
| CPI, all items, index | `IMF.STA/CPI` | `{ISO3}.CPI._T.IX.M` |
| Exchange rate, LCU per USD, period average | `IMF.STA/ER` | `{ISO3}.XDC_USD.PA_RT.M` |

- The US exchange rate is set to 1 (USD per USD), since the IMF doesn't publish it.
- A month only counts if all four inputs exist. Gaps show as breaks in the chart and blanks in the CSV.
- Coverage varies by country. Use the "Data coverage" panel to see each series' first and last month.
- Downloads are cached for 24 hours. If the IMF API is down, the app shows the exact error.

## Run it

**Streamlit Community Cloud:** deploy this repo with main file `app.py` and Python 3.12.

**Locally:**

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Files

- `app.py`: the app
- `requirements.txt`: Python dependencies (Python 3.12)
- `PROMPTS.md`: the LLM prompts, model and date used to build this
