"""
Does weather explain delivery delays?  (Olist orders + Open-Meteo weather)
===========================================================================
PURPOSE
    EXPLAIN whether delivery-day weather is associated with late deliveries, and
    whether that association is distinguishable from noise.  This is NOT a
    prediction model, so what matters is unbiased, interpretable coefficients
    (confounding, redundancy between features, influential points), not
    out-of-sample accuracy.
THE MODEL
    one explanatory logistic regression, standard errors clustered by delivery date, 
    with weather category measurement plus all controls.
    FORMULA:
            is_delayed ~ weather category (baseline: Cloudy) + same-state + customer state 
            + seller state + purchase weekday + purchase year-month + log(distance) + log(price)
    HOW: 
        - cluster-robust standard errors (deliveries that share a delivery day are not independent)
        - a joint test of the whole weather block, and partial tests for each variable given the other
        - each variable's own effect is explained with predicted delay rates, not only with coefficients Reading an 
            odds ratio (OR) vs the baseline: OR 1.30 = 30% higher ODDS of delay (not 30% higher probability).

REQUIREMENTS  pandas, numpy, matplotlib, scipy, statsmodels; scikit-learn optional (AUC).
HOW TO RUN    put olist_weather_data.csv next to this file and run it (or run it cell by cell).

NOTES:
    - Weather is measured on the DELIVERY day only, but delay accumulates over the whole journey (seller handling +
        transit). The model can speak to last-mile association, not to the weather over the full transit.
    - Observational data: 'associated with', not 'causes'. Package weight/size, carrier and strikes are not in the data.
    - 'Any delay' mixes 1-day and 30-day slips.

Figures and CSV exports are saved to ./Images    
"""


#%% Setup
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import statsmodels.formula.api as smf
from sklearn.metrics import roc_auc_score

sns.set_theme('paper')

def save_show(fig, name):
    fig.tight_layout()
    fig.savefig('Images/'f"{name}.png", dpi=130, bbox_inches="tight")
    plt.show()
    plt.close(fig)

def joint_weather_test(res):
    """Wald test of 'ALL weather coefficients are zero', using the covariance the model was fitted with."""
    names = [n for n in res.params.index if "delivery_weather_category" in n]
    R = np.zeros((len(names), len(res.params)))
    for i, n in enumerate(names):
        R[i, list(res.params.index).index(n)] = 1.0
    try:
        w = res.wald_test(R, scalar=True)
    except TypeError:
        w = res.wald_test(R)
    return float(np.squeeze(w.statistic)), float(np.squeeze(w.pvalue)), len(names)


# Load data
df = pd.read_csv("data_processed/olist_weather_data.csv", 
                 parse_dates=["purchase_datetime", "posting_datetime", "delivery_datetime"]
                 )


#%%
# Initial EDA

print(f"\nDeliveries: {len(df):,} | distinct: {df.order_id.nunique():,} ")
n_events = int(df.is_delayed.sum())
print(f"Delayed deliveries: {n_events:,} ({df.is_delayed.mean():.2%})") 

# Start by exploring the relationships betwen the delayed deliveries and the weather, as well as 
# the impact of delays on the review scores.

# Review score vs Days delayed
df['days_delayed'] = df['days_delayed'].astype(int)
df_1= df.groupby(['days_delayed']).agg(review_score=('review_score', 'mean'))#.reset_index()

fig = plt.figure(figsize=(10, 5))
ax = sns.scatterplot(data=df_1,y='review_score',x = 'days_delayed')
ax.set(title="Review Scores vs. Days Delayed", ylabel="Review Score")
save_show(fig, "01_user_satisfaction")

print("""
Bad reviews are linked strongly to delays in delivery. 
This means that weather do no impact directly on how a customer would rate the product if they 
receive the package on a rainy day, but it is more important that the delivery gets on time.\n
""")

# Delay rate by weather
df_weather = df.groupby(by=['delivery_weather_category']).agg(
    n_deliveries = ('order_id', 'count'),
    delay_rate=('is_delayed', 'mean')
).sort_values(by='delay_rate')
print(df_weather.round(3))
print("""
An initial table of the weather impact shows that Rain conditions are directly proportional 
with the delivery delay rates, but this is not taking into account other factors like weather 
being highly correlated to the geolocation and season of the year. 
There are also other factors that could generate delays like the distance between the seller 
and the customer, parcel size, price of the goods in the order.
""")

print("""Given that delays are closely associated with customer satisfaction, I decided to use an 
exploratory logistics model to explain the fcators that are associated with delays.
The taget outcome is 'is_delayed'
""")
# %%
# Skewness

fig, axes = plt.subplots(2, 3, figsize=(12, 5))
variables = ['order_price', 'order_freight', 'distance_seller_customer']
log_vars = ['log_price', 'log_freight', 'log_distance']

for i, var in enumerate(variables):
    log_var = log_vars[i]
    #plot histograms
    axes[0, i].hist(df[var], bins=50)
    # log transform
    df[log_var]= np.log1p(df[var])
    # plot log histograms
    axes[1, i].hist(df[log_var], bins=50, color='green')
    axes[0, i].set_title(var)

axes[0, 0].set_ylabel("count (raw)")
axes[1, 0].set_ylabel("count (log1p)")
save_show(fig, "02_skewness")

print(
"""
Variables like 'order_price' and 'order_freight' are highly skewed,
'distance_seller_costumer' present some skewness as well.
A log transformation has been applied, as  logistic regression assumes each numeric feature acts LINEARLY on the log-odds.
"""
)

# %%
# Multicollinearity

# Check for correlated variables
df_2 = df[['is_delayed',
           'log_price',
           'log_freight', # let out of the formula
           'log_distance',
           'delivery_precipitation', # let out of the formula
           'delivery_temp_min', # let out of the formula
           'delivery_temp_max', # let out of the formula
           'delivery_temp_range', # let out of the formula
           ]]
# spearman correlation
corr = df_2.corr(method='spearman')


fig, axes = plt.subplots(1, 2, figsize=(14, 5))
# correlation heatmap
ax = sns.heatmap(corr, annot=True, fmt='.2f', cmap="Spectral",ax=axes[0])
ax.set_title("Spearman correlation")

# weather category vs precipitation
ax = sns.boxplot(data=df,
            y='delivery_weather_category',
            x='delivery_precipitation',
            order=['Clear','Cloudy', 'Drizzle', 'Light Rain', 'Moderate Rain', 'Heavy Rain'],
            fliersize=0,
            medianprops={"color": "r", "linewidth": 1},
            ax=axes[1]
            )
ax.set_xlim(-5,60)
ax.set_title("Precipitation per Weather category")
plt.subplots_adjust(wspace=0.5, hspace=0.5)

save_show(fig, "03_collinearity")

print(
""" 
- 'delivery_precipitation' is highly correlated with 'delivery_temp_range', and it is aligned with 'delivery_weather_category'.
- 'delivery_temp_min' and 'delivery_temp_max' are highly correlated, indicating a strong relationship with season and location.
- 'log_freight' is correlated with both 'log_price' and 'distance_seller_customer'. This could be because the freight is calculated based on the distance and price of the item."

In conclusion, 'log_freight', 'delivery_precipitation', 'delivery_temp_min' and 'delivery_temp_max' are discarded from the formula as they show some collinearity.
""")

# %%
# Confounders

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# delay rate by state
df_1 = df.groupby(by=['seller_state_grouped']).agg(
    delay_rate =('is_delayed','mean'),
    n_orders = ('order_id','count')
    ).sort_values(by='delay_rate', ascending=False)
ax = sns.barplot(data=df_1, x="delay_rate", y="seller_state_grouped", ax=axes[0])
ax.bar_label(ax.containers[0], fmt=lambda x: f'{x * 100:.1f}%', fontsize=10, padding=-32);
ax.xaxis.set_major_formatter('{x:.1%}')
ax.set_title("Delay Rate by Seller State")

#
df_1 = df.groupby(by=['customer_state_grouped']).agg(
    temp_min = ('delivery_temp_min','mean'),
    delay_rate =('is_delayed','mean'),
    n_orders = ('order_id','count')
    )
ax=sns.scatterplot(data=df_1, y="delay_rate", x="temp_min", 
                   size="n_orders", sizes=(80,800),
                   alpha=0.3,
                   legend=False,
                   ax=axes[1]
                   )
ax.yaxis.set_major_formatter('{x:.1%}')
ax.set_title("Customer State: Minimum Temperature vs. Delay Rate")

# adjust the position of dots that are too close
for state, row in df_1.iterrows():
    x_f = row['temp_min']
    y_f = row['delay_rate']
    if state=='CE':
        y_f -= 0.003
    elif state=='PI':
        y_f += 0.003
    ax.text(x=x_f, y=y_f, s=str(state), fontsize=11,
        ha='center',
        va='center',
    )
save_show(fig, "04_confounder")
#control for purchase year-month, customer state, seller state, same-state and weekday.

print("""
- Hotter states tend to be the Northeast/North, and several of them (AL, MA, SE, PI, CE) are hot AND slow. Small northern states (AM, AP, RO)
 are exceptions with very few rows. This shows a pattern of delays caused by Region and not weather connditions as initially displayed.
- Seller origin shows some importance primarily in MA, and in minor importance SP and RJ.
- High season events like Carnival (Feb-Mar) and Black Friday (Nov), where there is a high number of deliveries influence as well the delays.
""")

df['purchase_ym'] = pd.to_datetime(df['purchase_datetime']).dt.strftime('%Y-%m')
orders_per_month = df['purchase_ym'].value_counts()
months_few_orders = orders_per_month[ orders_per_month < 100]
df = df[~df['purchase_ym'].isin(months_few_orders.index)]

print('Dropped months with few deliveries (less than 100) '
      'to avoid biasing the model with extreme coefficients:\n\n',
        months_few_orders.to_string())

# %%
# Modelling

print("\nModel Features" 
"""
- delivery_weather_category: This is the variable of interest for this project. The baseline is Cloudy instead of Clear, as it has a better representation in the dta set of a clear/Dry day.
- customer_state_grouped: This is a confounder feature, weather and reginal logistics are closely tied to the location. THe baseline is São Paulo (SP) as one of the main states for consumers.
- seller_state_grouped: This is a control variable, and it accounts for the logistics at different locations.
- is_same_state: Deliveries inside the same state are faster (shorter distance)
- purchase_ym: This feature helps determine the impact of seasonal events, like Carnivals nad Black Friday. Weather also varies based on the season of the year. '2017-10' is the most common month, so it is a natural baseline for comparison.
- purchase_weekday: Purchasing on specific days affects on the delivery logistics.
- log_distance: The longer the distance the higher the likelihood of a delay.
- log_price: Bulkier items could impact the logistics.
- delivery_date: use as Cluster to mitigate standard errors. Weather is the same for deliveries made the same day at the same location, and this makes deliveries not independent. Clustering by delivery date helps getting better standard errors.
""")
print("""
FINAL MODEL  (one explanatory logistic regression, standard errors clustered by delivery date)
    is_delayed ~ weather category (baseline: Cloudy) + same-state + customer state + seller state
        + purchase weekday + purchase year-month + log(distance) + log(price)
""")

formula = (
    "is_delayed ~ "
    "C(delivery_weather_category, Treatment('Cloudy'))"
    " + C(is_same_state)"
    " + C(customer_state_grouped, Treatment('SP'))" #counfounder
    " + C(seller_state_grouped, Treatment('SP'))" 
    " + C(purchase_weekday)"
    " + C(purchase_ym, Treatment('2017-10'))"
    " + log_distance"
    " + log_price"
)

df['delivery_date'] = pd.to_datetime(df['delivery_datetime']).dt.date.astype(str) 
logit = smf.logit(formula=formula, data=df).fit(
    disp=0, maxiter=200, 
    cov_type='cluster', cov_kwds={'groups': df['delivery_date']}
)

print(logit.summary().tables[0])
auc = roc_auc_score(df.is_delayed, logit.predict(df))
print(f"AUC= {auc:.3f}")

chi2_w, p_w, n_w = joint_weather_test(logit)
print(f"\nWhole weather significance: p= {p_w:.3f}, chi2= {chi2_w:.2f}, coefficients= {n_w}")

#%%
# Weather Impact



#%%
# Adjusted delays
rates = {}
for cat in ['Clear', 'Cloudy', 'Drizzle', 'Light Rain', 'Moderate Rain', 'Heavy Rain']:
    d = df.copy()
    d['delivery_weather_category'] = cat
    rates[cat] = logit.predict(d).mean()

df_weather['adjusted_delays'] = df_weather.index.map(rates)
print(df_weather.round(3))

# %%
# Results
# Calculate Odds Ratios and 95% Confidence Intervals
params = logit.params
conf = logit.conf_int()
or_table = pd.DataFrame({
    "OR": np.exp(params),
    "p-val": logit.pvalues,
    "CI L": np.exp(conf[0]),
    "CI U": np.exp(conf[1])
})
significant = or_table[or_table['p-val'] < 0.05]
print("\nSignificant predictors:")
print(significant.round(3).sort_values(by='OR', ascending = False))

print("""
Predictors that drive delays, relative to its baseline:
- Customer in AL (OR 5.2) Deliveries to Alagoas are the most likely to be delayed.
- Customer in MA (OR 3.7) Maranhão is the second-worst destination. Maranhão is the second-worst destination.
- Customer in RJ (OR 2.4) A smaller effect, but RJ has about 11,000 deliveries.
- Seller in MA (OR 3.0) Orders shipped from Maranhão sellers are late far more often
- Purchased Mar 2018 (OR 6.1) and Purchased Feb 2018 (OR 4.1) are the strongest single driver.
    It points to a system-wide bottleneck (capacity, carrier or carnival holiday disruption), but the data can’t say which.
- Purchased Nov 2017 (OR 3.5) The Black Friday period. Demand spikes are a likely cause.
- Price: about +8.6% odds per doubling. Higher-value orders may involve bulkier items or more handling, but package size isn’t in the data, so this is a guess.
- Same-state delivery (OR 0.78) Deliveries within the same state are about 22% less likely to be late.
- Monday purchases: +27% odds vs Sunday. A possible explanation is the dispatch cutoff and weekend handling. 
""")