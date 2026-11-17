
#%% 
# setup
import os
from google.cloud import bigquery
import pandas as pd


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "misc/e-commerce-weather-1d3de4573345.json"
client = bigquery.Client()

# Read the SQL query from your portfolio file
with open("bigquery_query.sql", "r", encoding="utf-8") as file:
    query = file.read()

# Execute it
query_job = client.query(query)
df = query_job.to_dataframe()
df.to_csv("data_processed/olist_weather_data.csv", index=False)
print(f"Successfully loaded dataset with shape: {df.shape}")

#%% 
# prepare data for viz in Tableau

df_viz = df.drop(columns=[#'purchase_datetime',
                          'posting_datetime',
                          'seller_state_grouped',
                          'customer_state_grouped',
                          'purchase_month'
                          ])
df_viz['purchase_datetime'] = pd.to_datetime(df_viz['purchase_datetime']).dt.tz_localize(None).astype('datetime64[us]')
df_viz['delivery_datetime'] = pd.to_datetime(df_viz['delivery_datetime']).dt.tz_localize(None).astype('datetime64[us]')
df_viz['country_code'] = "BR"
df_viz.to_csv('data_processed/final_df.csv', index=False)
df_viz.info()

# %%
