"""Real exchange rate explorer built on IMF CPI and exchange-rate data.

S(t)   = units of Country 2 currency per 1 unit of Country 1 currency
RER(t) = S(t) * P1(t) / P2(t)
Real Index(t) = 100 * RER(t) / RER*, where RER* is the mean RER over the selected sample.
"""

import io
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pycountry
import requests
import streamlit as st
from plotly.subplots import make_subplots

IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
START_PERIOD = pd.Period("1976-01", freq="M")
EURO_AREA = "G163"

CURRENCY_CODES = {
    "USA": "USD", "GBR": "GBP", EURO_AREA: "EUR", "JPN": "JPY", "CHN": "CNY",
    "CAN": "CAD", "AUS": "AUD", "CHE": "CHF", "IND": "INR", "BRA": "BRL",
    "MEX": "MXN", "KOR": "KRW", "ZAF": "ZAR", "SWE": "SEK", "NOR": "NOK",
    "DNK": "DKK", "NZL": "NZD", "SGP": "SGD", "HKG": "HKD", "TUR": "TRY",
    "RUS": "RUB", "IDN": "IDR", "THA": "THB", "MYS": "MYR", "PHL": "PHP",
    "POL": "PLN", "CZE": "CZK", "HUN": "HUF", "ISR": "ILS", "SAU": "SAR",
    "ARG": "ARS", "CHL": "CLP", "COL": "COP", "PER": "PEN", "EGY": "EGP",
    "NGA": "NGN", "PAK": "PKR", "VNM": "VND",
}

HEADERS = {"User-Agent": "real-exchange-rate-app/1.0 (Streamlit)"}
FORMATS = [
    ("json", "application/vnd.sdmx.data+json;version=2.0.0"),
    ("csv", "application/vnd.sdmx.data+csv;version=2.0.0"),
]


# ---------------------------------------------------------------------------
# Country list
# ---------------------------------------------------------------------------

def country_options() -> dict[str, str]:
    """Label -> ISO3. Euro area first, then all ISO countries alphabetically."""
    countries = sorted(
        (getattr(c, "common_name", None) or c.name, c.alpha_3) for c in pycountry.countries
    )
    options = {f"Euro area ({EURO_AREA})": EURO_AREA}
    options.update({f"{name} ({iso3})": iso3 for name, iso3 in countries})
    return options


def currency_label(iso3: str, label: str) -> str:
    code = CURRENCY_CODES.get(iso3)
    if code:
        return code
    return f"{label.rsplit(' (', 1)[0]} currency"


# ---------------------------------------------------------------------------
# IMF data retrieval
# ---------------------------------------------------------------------------

def parse_period(value: str) -> pd.Period | None:
    """IMF monthly periods look like '2020-M01'; also accept '2020-01'."""
    try:
        return pd.Period(str(value).replace("-M", "-"), freq="M")
    except (ValueError, TypeError):
        return None


def parse_sdmx_json(payload: dict) -> pd.Series:
    data = payload.get("data", payload)
    structures = data.get("structures") or [data.get("structure", {})]
    datasets = data.get("dataSets") or []
    if not datasets or not structures:
        return pd.Series(dtype=float)

    obs_dims = structures[0].get("dimensions", {}).get("observation", [])
    time_pos = next((i for i, d in enumerate(obs_dims) if d.get("id") == "TIME_PERIOD"), 0)
    times = [v.get("value", v.get("id")) for v in obs_dims[time_pos].get("values", [])]

    values: dict[pd.Period, float] = {}
    for series in (datasets[0].get("series") or {}).values():
        for obs_key, obs in (series.get("observations") or {}).items():
            idx = int(str(obs_key).split(":")[time_pos])
            period = parse_period(times[idx])
            raw = obs[0] if isinstance(obs, list) and obs else None
            if period is None or raw in (None, "", "NaN"):
                continue
            values.setdefault(period, float(raw))
    return pd.Series(values, dtype=float).sort_index()


def parse_sdmx_csv(text: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        return pd.Series(dtype=float)
    periods = df["TIME_PERIOD"].map(parse_period)
    values = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    s = pd.Series(values.values, index=periods.values).dropna()
    s = s[~s.index.isna()]
    return s[~s.index.duplicated()].sort_index()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_imf_series(dataflow: str, key: str) -> tuple[pd.Series, str | None]:
    """Return (monthly series, error message). Empty series means no data."""
    url = f"{IMF_BASE}/data/dataflow/IMF.STA/{dataflow}/+/{key}"
    params = {"dimensionAtObservation": "TIME_PERIOD", "attributes": "dsd", "measures": "all"}
    last_error = None

    for fmt, accept in FORMATS:
        for attempt in range(3):
            try:
                resp = requests.get(
                    url, params=params, headers={**HEADERS, "Accept": accept}, timeout=45
                )
                if resp.status_code == 404:
                    return pd.Series(dtype=float), None  # IMF: no results for this key
                resp.raise_for_status()
                s = parse_sdmx_json(resp.json()) if fmt == "json" else parse_sdmx_csv(resp.text)
                s = s[s.index >= START_PERIOD]
                return s, None
            except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(1.5 * (attempt + 1))
    return pd.Series(dtype=float), f"{dataflow} {key} failed. Last error: {last_error}"


def load_country(iso3: str) -> tuple[pd.Series, pd.Series, list[str]]:
    """CPI index and LCU-per-USD period-average exchange rate for one country."""
    errors = []
    cpi, err = fetch_imf_series("CPI", f"{iso3}.CPI._T.IX.M")
    if err:
        errors.append(err)

    if iso3 == "USA":
        # USD per USD is 1 by definition; the IMF does not publish it.
        idx = pd.period_range(START_PERIOD, pd.Timestamp.today().to_period("M"), freq="M")
        fx = pd.Series(1.0, index=idx)
    else:
        fx, err = fetch_imf_series("ER", f"{iso3}.XDC_USD.PA_RT.M")
        if err:
            errors.append(err)
    return cpi, fx, errors


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------

def build_panel(cpi1, fx1, cpi2, fx2) -> pd.DataFrame:
    """Monthly panel with S(t) and RER(t). FX inputs are LCU per USD."""
    df = pd.concat(
        {"P1_cpi": cpi1, "P2_cpi": cpi2, "E1_lcu_per_usd": fx1, "E2_lcu_per_usd": fx2},
        axis=1,
    ).sort_index()
    df = df[df.index >= START_PERIOD]
    # (C2 per USD) / (C1 per USD) = C2 per C1
    df["S_c2_per_c1"] = df["E2_lcu_per_usd"] / df["E1_lcu_per_usd"]
    df["RER"] = df["S_c2_per_c1"] * df["P1_cpi"] / df["P2_cpi"]
    df = df.replace([np.inf, -np.inf], np.nan)
    return df


def apply_sample(df: pd.DataFrame, start: pd.Period, end: pd.Period) -> tuple[pd.DataFrame, float]:
    sample = df.loc[(df.index >= start) & (df.index <= end)].copy()
    rer_star = sample["RER"].mean(skipna=True)
    sample["RER_star"] = rer_star
    sample["Real_index"] = 100 * sample["RER"] / rer_star
    return sample, rer_star


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def make_chart(sample: pd.DataFrame, mode: str, c1: str, c2: str) -> go.Figure:
    x = sample.index.to_timestamp()
    s_label = f"S(t): {c2} per 1 {c1}"
    fig = make_subplots(specs=[[{"secondary_y": mode == "Both"}]])

    if mode in ("Real", "Both"):
        fig.add_trace(
            go.Scatter(x=x, y=sample["Real_index"], name="Real index (sample mean = 100)",
                       line=dict(color="#1f77b4", width=2), connectgaps=False),
            secondary_y=False,
        )
        fig.add_hline(y=100, line_dash="dot", line_color="gray")
    if mode in ("Nominal", "Both"):
        fig.add_trace(
            go.Scatter(x=x, y=sample["S_c2_per_c1"], name=s_label,
                       line=dict(color="#d62728", width=2), connectgaps=False),
            secondary_y=(mode == "Both"),
        )

    if mode == "Real":
        fig.update_yaxes(title_text="Real index")
    elif mode == "Nominal":
        fig.update_yaxes(title_text=f"{c2} per 1 {c1}")
    else:
        fig.update_yaxes(title_text="Real index", secondary_y=False)
        fig.update_yaxes(title_text=f"{c2} per 1 {c1}", secondary_y=True)

    fig.update_layout(
        hovermode="x unified", height=520, margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def main():
    st.set_page_config(page_title="Real Exchange Rate App", layout="wide")
    st.title("Real Exchange Rate Explorer")
    st.caption(
        "Monthly IMF data (CPI and period-average exchange rates) from January 1976 where available. "
        "S(t) = Country 2 currency per 1 unit of Country 1 currency; RER(t) = S(t) × P1(t) / P2(t)."
    )

    options = country_options()
    labels = list(options)
    default1 = next(i for i, l in enumerate(labels) if options[l] == "GBR")
    default2 = next(i for i, l in enumerate(labels) if options[l] == "USA")

    with st.sidebar:
        st.header("Countries")
        label1 = st.selectbox("Country 1", labels, index=default1)
        label2 = st.selectbox("Country 2", labels, index=default2)

    iso1, iso2 = options[label1], options[label2]
    if iso1 == iso2:
        st.warning("Choose two different countries.")
        st.stop()

    with st.spinner("Downloading IMF data..."):
        cpi1, fx1, err1 = load_country(iso1)
        cpi2, fx2, err2 = load_country(iso2)

    for err in err1 + err2:
        st.error(err)

    cur1, cur2 = currency_label(iso1, label1), currency_label(iso2, label2)
    coverage = pd.DataFrame(
        {
            "Series": [f"CPI {label1}", f"FX {label1} (LCU/USD)", f"CPI {label2}", f"FX {label2} (LCU/USD)"],
            "First month": [str(s.index.min()) if len(s) else "none" for s in (cpi1, fx1, cpi2, fx2)],
            "Last month": [str(s.index.max()) if len(s) else "none" for s in (cpi1, fx1, cpi2, fx2)],
            "Observations": [int(s.notna().sum()) for s in (cpi1, fx1, cpi2, fx2)],
        }
    )

    panel = build_panel(cpi1, fx1, cpi2, fx2)
    valid = panel["RER"].dropna()
    if valid.empty:
        st.error(
            "No month has all four inputs (both CPIs and both exchange rates). "
            "The IMF may not publish these series for this pair, or the download failed."
        )
        st.dataframe(coverage, hide_index=True)
        st.stop()

    months = pd.period_range(valid.index.min(), valid.index.max(), freq="M")
    month_labels = [str(m) for m in months]

    with st.sidebar:
        st.header("Sample period")
        start_label, end_label = st.select_slider(
            "Start and end month", options=month_labels, value=(month_labels[0], month_labels[-1]),
            key=f"sample_{iso1}_{iso2}",
        )
        st.header("Chart")
        mode = st.radio("Show", ["Real", "Nominal", "Both"], index=2, horizontal=True)

    start, end = pd.Period(start_label, freq="M"), pd.Period(end_label, freq="M")
    sample, rer_star = apply_sample(panel, start, end)
    n_valid = int(sample["RER"].notna().sum())

    if n_valid == 0:
        st.warning("No valid months in the selected sample.")
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("RER* (sample mean RER)", f"{rer_star:,.4f}")
    m2.metric("Mean real index", f"{sample['Real_index'].mean():.2f}")
    m3.metric("Valid months", f"{n_valid} of {len(sample)}")
    latest = sample["S_c2_per_c1"].dropna()
    m4.metric(f"Latest S ({latest.index[-1]})", f"{latest.iloc[-1]:,.4f} {cur2}/{cur1}")

    st.plotly_chart(make_chart(sample, mode, cur1, cur2), width="stretch")
    st.caption(
        "Real index above 100: Country 1 is real-appreciated vs. its sample average "
        "(its goods are relatively more expensive). Gaps mean at least one input is missing."
    )

    export = sample.reset_index(names="month")
    export["month"] = export["month"].astype(str)
    export.insert(1, "country1", iso1)
    export.insert(2, "country2", iso2)
    export = export.rename(columns={"S_c2_per_c1": f"S_{cur2}_per_{cur1}".replace(" ", "_")})
    st.download_button(
        "Download CSV (selected sample)",
        export.to_csv(index=False).encode("utf-8"),
        file_name=f"rer_{iso1}_{iso2}_{start}_{end}.csv",
        mime="text/csv",
    )

    with st.expander("Check one month by hand"):
        check_month = st.selectbox("Month", [str(m) for m in sample["RER"].dropna().index][::-1])
        row = sample.loc[pd.Period(check_month, freq="M")]
        st.markdown(
            f"""
- E1 = {row['E1_lcu_per_usd']:,.6f} {cur1} per USD, E2 = {row['E2_lcu_per_usd']:,.6f} {cur2} per USD
- S = E2 / E1 = **{row['S_c2_per_c1']:,.6f}** {cur2} per 1 {cur1}
- P1 = {row['P1_cpi']:,.4f}, P2 = {row['P2_cpi']:,.4f}
- RER = S × P1 / P2 = {row['S_c2_per_c1']:,.6f} × {row['P1_cpi']:,.4f} / {row['P2_cpi']:,.4f} = **{row['RER']:,.6f}**
- Real index = 100 × RER / RER* = 100 × {row['RER']:,.6f} / {rer_star:,.6f} = **{row['Real_index']:,.4f}**
"""
        )

    with st.expander("Data coverage and table"):
        st.dataframe(coverage, hide_index=True)
        st.dataframe(export, hide_index=True)


if __name__ == "__main__":
    main()
