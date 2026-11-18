# Executive Summary: Does Weather Explain Delivery Delays?

[![Tableau Public](https://img.shields.io/badge/Tableau%20Public-Dashboard-blue)](https://public.tableau.com/app/profile/david.zapata3472/viz/weather_impact_on_delivery_delays/Dashboard)
[![Project README](https://img.shields.io/badge/Back%20to-Project%20README-lightgrey)](README.md)

*Olist e-commerce deliveries in Brazil · 91,865 deliveries, Oct 2016 – Sep 2018 · Delivery-day weather from Open-Meteo*

## Bottom line

**Day-of-delivery weather is not what makes deliveries late.** Rain looks guilty in the raw numbers, but the pattern disappears once we compare deliveries from the same region and the same period. Delays are driven by **where the parcel is going** and **when it was ordered**.

## Why it matters

Only **6.5%** of deliveries arrive late, but late orders average a review score of **2.3**, against **4.3** for on-time ones. Reducing late deliveries is the most direct lever on customer satisfaction.

## What we found

1. **Rain looks like a cause.** 9.3% of deliveries on heavy-rain days are late, versus 3.7% on clear days.
2. **It is a coincidence.** Rainy days cluster where delays were already high: peak seasons (late rates of 11.8% in Nov 2017, 13.0% in Feb 2018 and 18.1% in Mar 2018) and remote Northeast states (Alagoas 21.0%, Maranhão 17.3%, against 4.3% in São Paulo).
3. **Comparing like with like, weather barely matters.** Holding region, seller location, order month and order profile constant, late rates are **5.8–7.1% in every weather type**.

| | Clear | Heavy rain |
|---|---|---|
| Raw late rate | 3.7% | 9.3% |
| Adjusted late rate | 5.8% | 6.5% |

4. **Even the worst case is small.** The data cannot rule out a heavy-rain effect of about **1 percentage point** (roughly 1 extra late delivery per 100), but show no evidence of more.

## What does drive delays

- **Destination:** remote Northeast states (Alagoas, Maranhão, Sergipe) stay far more delay-prone even after adjustment.
- **Timing:** orders placed in the peak periods above, with March 2018 the worst.
- **Seller location:** Maranhão-based sellers ship late far more often.

## Recommendations

- **Do not make weather contingency the main lever.** It targets a factor with little measurable effect.
- **Prioritize peak-period capacity and Northeast delivery lanes**, where the largest and most consistent gaps are.
- **Treat unadjusted weather charts with caution.** They suggest a rain effect the adjusted analysis does not support.

## Confidence and limits

We are highly confident that any weather effect is small. The overall statistical test for a weather effect is borderline (p = 0.09) and, if anything, points the opposite way from "rain causes delays". Only weather on the **delivery day** is measured, not along the whole journey, and the data are observational: parcel size, carrier performance and strikes are not available.

## Next steps

1. Test weather along the full route, not just on delivery day.
2. Add carrier, parcel size and strike data to separate logistics bottlenecks from regional effects.
3. Investigate the Northeast lanes and the Feb–Mar 2018 peak for specific operational causes.
