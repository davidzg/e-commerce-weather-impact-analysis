import os
from google.cloud import bigquery
import pandas as pd


os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "misc/e-commerce-weather-1d3de4573345.json"
client = bigquery.Client()


project_id = "e-commerce-weather"
dataset_id = "e_commerce_weather_data"
dataset_ref = f"{project_id}.{dataset_id}"


try:
    client.get_dataset(dataset_ref)
    print("Dataset already exists.")
except:
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "EU"
    client.create_dataset(dataset, timeout=30)
    print(f"Created dataset {dataset_id}")


files_to_upload = {
        'customers': 'data/olist_customers_dataset.csv',
        'geolocation': 'data/olist_geolocation_dataset.csv',
        'items': 'data/olist_order_items_dataset.csv',
        'payments': 'data/olist_order_payments_dataset.csv',
        'reviews': 'data/olist_order_reviews_dataset.csv',
        'orders': 'data/olist_orders_dataset.csv',
        'products': 'data/olist_products_dataset.csv',
        'sellers': 'data/olist_sellers_dataset.csv',
        'translation': 'data/product_category_name_translation.csv',
        'weather': 'data/historical_weather_brazil.parquet'
    }


def upload_csv(table_name, file_path):
    table_ref = f"{dataset_ref}.{table_name}"

    print(f"Reading {file_path} with pandas...")
    # Read CSV via pandas (handles quotes and special characters gracefully)
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_parquet(file_path)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, # Overwrite if exists
    )

    print(f"Uploading {file_path} to BigQuery table {table_ref}...")
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)

    job.result()  # Wait for the job to complete
    print(f"Successfully loaded {file_path} into {table_ref}\n")


for  table, file in files_to_upload.items():
    upload_csv(table, file)