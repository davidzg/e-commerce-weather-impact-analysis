# Does Weather Explain Delivery Delays?

**An explanatory analysis of ~92,000 Olist e-commerce deliveries in Brazil, combining BigQuery SQL, Python (logistic regression) and a Tableau dashboard.**

[![Executive Summary](https://img.shields.io/badge/Read-Executive%20Summary-green)](Executive_Summary.md)

[![Tableau Public](https://img.shields.io/badge/Tableau%20Public-Dashboard-blue)](https://public.tableau.com/app/profile/david.zapata3472/viz/weather_impact_on_delivery_delays/Dashboard)

![Dashboard](Images/dashboard.png)

## TL;DR

Raw data says rain causes late deliveries: **9.3%** of deliveries on heavy-rain days are late versus **3.7%** on clear days. After comparing same destination state, seller state, purchase period and order profile, that pattern disappears. Late rates sit at **about 6–7% in every weather category**. Rainy days simply coincide with peak-season periods and slow regions. **Destination state and peak-season timing drive delays; day-of-delivery weather does not.**

## Business question

Late deliveries are expensive: reviews drop from **4.27** (on time) to **2.28** (late) on average, and to **1.6** when a parcel is more than two weeks late. Can weather on the delivery day explain which deliveries arrive late, or are other factors responsible?

Scope: this project looks at **last-mile association only**. All weather metrics are measured on the day the order was delivered.

## Key findings

1. **Delays destroy satisfaction.** Average review score by lateness: on time 4.27, 1–3 days late 3.30, 4–7 days 2.10, 8–14 days 1.66, 15+ days 1.60.
2. **The unadjusted weather chart is misleading.** Late rate rises steadily from clear (3.7%) to heavy rain (9.3%).
3. **Time of year is the confounder that matters most.** Purchase months with spikes in late deliveries (Nov 2017: 11.8%, Feb 2018: 13.0%, Mar 2018: 18.1%) are also months when 80–90% of deliveries land on rainy days (vs 62% across the whole period). Adding purchase month to the model flips the weather effect from "rain is worse" to "no rain penalty".
4. **After adjustment, weather is flat and statistically weak.** Adjusted late rates are 5.8–7.1% across categories. Joint test of the whole weather block: p = 0.087. Adding weather to the model barely changes discrimination (AUC 0.7426 → 0.7429).
5. **Geography and timing are the real drivers.**
   - Destination state (raw late rate): AL 21.0%, MA 17.3%, SE 14.6% vs SP 4.3%.
   - Seller in Maranhão (MA): odds of delay about 3x those of São Paulo sellers.
   - Purchases in Mar 2018: odds about 6x those of Oct 2017.
   - Higher-priced orders are slightly more likely to be late (+8.6% odds per doubling of price). Same-state deliveries are less likely to be late.

**So what?** Weather contingency planning is unlikely to reduce delays. Peak-period capacity and Northeast delivery lanes are the better levers.

## Data and pipeline

| Source | Used for |
|---|---|
| [Olist Brazilian E-Commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, CC BY-NC-SA 4.0) | Orders, delivery dates, review scores, prices, freight, customer and seller locations |
| [Open-Meteo Historical Weather API](https://open-meteo.com/) (CC BY 4.0) | Daily precipitation, temperature and weather category at the delivery location |

```
Olist tables + Open-Meteo  ->  BigQuery SQL (join + feature engineering)  ->  olist_weather_data.csv
                                                                              |-> Tableau Public dashboard
                                                                              '-> Python: EDA + logistic regression
```

- **Grain:** one row per delivery (91,865 rows from 91,682 distinct orders; multi-seller orders appear more than once). Period: purchases from Oct 2016 to Aug 2018, deliveries from Oct 2016 to Sep 2018.
- **Outcome:** `is_delayed = 1` when the order arrived after the estimated delivery date (6.49% of deliveries).
- **Model sample:** 91,800 deliveries. Purchase months with fewer than 100 deliveries were dropped to avoid unstable coefficients.

## Methodology

**Model:** one explanatory logistic regression (not a prediction model, so the focus is on unbiased, interpretable coefficients).

```
is_delayed ~ weather category (baseline: Cloudy)
           + customer state (baseline: SP) + seller state (baseline: SP) + same-state flag
           + purchase weekday + purchase year-month (baseline: 2017-10)
           + log(distance) + log(price)
```

| Feature | Why it is in the model |
|---|---|
| Weather category | The variable of interest |
| Customer state | Confounder: weather, season and logistics all vary by region |
| Seller state, same-state flag, log(distance) | Logistics controls |
| Purchase year-month | Confounder: absorbs seasonality, Carnival, Black Friday and other period effects |
| Purchase weekday | Logistics control |
| log(price) | Proxy for bulkier or higher-value items |

**Features left out:** precipitation, minimum/maximum temperature and temperature range (redundant with weather category, state and season), and freight (correlated with distance and price).

**Inference:** standard errors are clustered by delivery date, since deliveries on the same day share weather and are not independent. Because the question is whether weather matters as a whole, results are judged with a **joint Wald test of all weather coefficients**, not only individual p-values.

## Results

Odds ratios (OR) are relative to **Cloudy** days (*OR 0.87 means 13% lower odds of delay, not 13% lower probability*). "Adjusted rate" is the predicted late rate if every delivery had that weather, holding everything else at its observed values.

| Weather | Raw late rate | OR | 95% CI | p | Adjusted late rate |
|---|---|---|---|---|---|
| Clear | 3.7% | 0.81 | 0.67 – 0.98 | 0.028 | 5.8% |
| Cloudy | 5.1% | 1 (baseline) | | | 7.1% |
| Drizzle | 7.3% | 0.89 | 0.80 – 0.99 | 0.033 | 6.4% |
| Light Rain | 7.2% | 0.87 | 0.75 – 1.00 | 0.042 | 6.2% |
| Moderate Rain | 8.0% | 0.87 | 0.75 – 1.01 | 0.074 | 6.3% |
| Heavy Rain | 9.3% | 0.91 | 0.72 – 1.14 | 0.404 | 6.5% |

Joint test of the weather block: chi2 = 9.63, df = 5, **p = 0.087**. Model fit: pseudo R² = 0.109, AUC = 0.743, 594 delivery-date clusters.

**How to read this:**
- No category is worse than Cloudy and there is no dose-response (heavy rain is not meaningfully worse than drizzle). The data do not support "rain causes delays".
- Individual p-values around 0.03–0.04 are fragile when five categories are tested, so the joint test is the fairer verdict.
- Heavy Rain has the least data (~1,700 deliveries) and the widest interval. The data cannot rule out up to about 14% higher odds, which would be roughly +1 percentage point (about 8.0% vs 7.1%).
- I would not read Clear/rain being "better than Cloudy" as a real benefit. It is more likely noise, category definition or residual mix.

## Limitations

- Delay accumulates over the whole journey (seller handling plus transit), so this speaks to last-mile association, not weather along the full route.
- Results show association, not causation. Parcel weight and size, carrier and strikes are not in the data.
- **The delivery date depends on the outcome.** Late orders are delivered on later calendar dates. A cleaner design would use weather on the *estimated* delivery date.
- **"Any delay" mixes 1-day and 30-day slips.**

## Repository structure

```
.
├── README.md
├── Executive_Summary.md
├── requirements.txt
├── .gitignore
├── 01_upload_data_sources.py     # loads Olist + Open-Meteo into BigQuery
├── 02_run_query.py               # builds olist_weather_data.csv
├── 03_eda_model.py               # EDA + logistic regression (run cell by cell or as a script)
├── bigquery_query.sql            # BigQuery queries that build the dataset
├── olist_weather_data.csv        # query output
├── data_raw/                     # Kaggle / Open-Meteo downloads (gitignored)
├── data_processed/
│   └── olist_weather_data.csv    # query output used by Tableau and the model
├── images/                       # Figures exported by EDA.py + dashboard screenshot
└── dashboard/                    # .twbx workbook

```

## How to run

```bash
pip install -r requirements.txt
python 01_upload_data_sources.py   # loads Olist + Open-Meteo into BigQuery
python 02_run_query.py             # builds olist_weather_data.csv
python 03_eda_model.py             # EDA + logistic regression
```

`03_eda_model.py` expects the dataset at `data_processed/olist_weather_data.csv` and saves its figures to `Images/`.

## Tools

BigQuery SQL · Python (pandas, statsmodels, scikit-learn, matplotlib, seaborn) · Tableau Public

## Author

**David Zapata** · [LinkedIn](https://www.linkedin.com/in/david-zapata-garcia/) · [Portfolio](https://github.com/davidzg)

*Data: Olist Brazilian E-Commerce dataset (Kaggle) and Open-Meteo Historical Weather API. This is an independent portfolio project and is not affiliated with Olist.*
