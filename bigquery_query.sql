--------------------------------------------------------------------------------
-- E-COMMERCE & WEATHER PREDICTIVE MODELING PIPELINE
-- Description: Cleans, joins, and engineers features from Olist e-commerce 
--              and regional weather data for delivery delay prediction.
--------------------------------------------------------------------------------

WITH
    -- Clean and standardize customer location data (lowercase, trim, remove accents)
    customer_t AS(
        SELECT 
            customer_id,
            customer_zip_code_prefix AS customer_zip,
            TRANSLATE(
                LOWER(TRIM(customer_city)),
                'áàâãäéèêëíìîïóòôõöúùûüç',
                'aaaaaeeeeiiiiooooouuuuc'
                ) AS customer_city,
            UPPER(TRIM(customer_state)) AS customer_state
        FROM `e-commerce-weather.e_commerce_weather_data.customers` 
    ),

    -- Clean and standardize seller location data
    seller_t  AS(
        SELECT
            seller_id,
            seller_zip_code_prefix AS seller_zip,
            TRANSLATE(
                LOWER(TRIM(seller_city)),
                'áàâãäéèêëíìîïóòôõöúùûüç',
                'aaaaaeeeeiiiiooooouuuuc'
                ) AS seller_city,
            UPPER(TRIM(seller_state)) AS seller_state
        FROM `e-commerce-weather.e_commerce_weather_data.sellers`
    ),

    -- Aggregate geolocation data by zip code and filter within valid geographic bounds (Brazil)
    location_t AS(
        SELECT
            geolocation_zip_code_prefix AS geo_zip,
            ROUND(APPROX_QUANTILES(geolocation_lat, 4)[OFFSET(2)],2) AS geo_lat,
            ROUND(APPROX_QUANTILES(geolocation_lng, 4)[OFFSET(2)],2) AS geo_lng,
        FROM `e-commerce-weather.e_commerce_weather_data.geolocation`
        WHERE (geolocation_lat BETWEEN -33.7508 AND 5.2719) 
            AND (geolocation_lng BETWEEN -73.9831 AND -34.7931)
        GROUP BY geo_zip
    ),

    -- Map customer records to their geographic coordinates
    customer_location AS(
        SELECT
            c.customer_id,
            c.customer_city,
            c.customer_state,
            l.geo_lat,
            l.geo_lng
        FROM customer_t c
        LEFT JOIN location_t l ON c.customer_zip=l.geo_zip
        WHERE geo_lat IS NOT NULL and geo_lng IS NOT NULL
    ),

    -- Map seller records to their geographic coordinates
    seller_location AS(
        SELECT
            s.seller_id,
            s.seller_zip,
            s.seller_city,
            s.seller_state,
            l.geo_lat,
            l.geo_lng
        FROM seller_t s
        LEFT JOIN location_t l ON s.seller_zip=l.geo_zip
        WHERE geo_lat IS NOT NULL AND geo_lng IS NOT NULL
    ),

    -- Calculate order fulfillment durations and delay metrics
    calculated_orders AS(
        SELECT
            order_id,
            customer_id,
            CAST(order_purchase_timestamp AS TIMESTAMP) AS purchase_datetime,
            CAST(order_delivered_carrier_date AS TIMESTAMP) AS posting_datetime,
            CAST(order_delivered_customer_date AS TIMESTAMP) AS delivery_datetime,
            CAST(order_estimated_delivery_date AS TIMESTAMP) AS estimated_delivery_datetime,
            --TIMESTAMP_DIFF(CAST(order_delivered_customer_date AS TIMESTAMP), 
            --    CAST(order_estimated_delivery_date AS TIMESTAMP),
            --    SECOND)/86400.0 AS days_delayed_float,
            TIMESTAMP_DIFF(CAST(order_delivered_customer_date AS TIMESTAMP),
          CAST(order_estimated_delivery_date AS TIMESTAMP), DAY) AS days_delayed,
            TIMESTAMP_DIFF(CAST(order_delivered_customer_date AS TIMESTAMP),
                CAST(order_delivered_carrier_date AS TIMESTAMP),
                SECOND)/86400.0 AS days_delivering
        FROM `e-commerce-weather.e_commerce_weather_data.orders`
        WHERE order_status = 'delivered'
            AND order_delivered_customer_date IS NOT NULL
            AND order_delivered_carrier_date IS NOT NULL
            AND order_delivered_carrier_date > order_purchase_timestamp
            
    ),

    -- Filter orders for logical delivery timeframes and realistic delays
    orders_delivered AS(
        SELECT *
        FROM calculated_orders
        WHERE days_delivering > 0
            AND days_delayed BETWEEN -30 AND 30
    ),

    -- Combine filtered orders with customer location details
    orders_customer_location AS(
        SELECT
            od.order_id,
            od.purchase_datetime,
            od.posting_datetime,
            od.delivery_datetime,
            od.days_delayed,
            od.days_delivering,
            cl.customer_city,
            cl.customer_state,
            cl.geo_lat AS customer_lat,
            cl.geo_lng AS customer_lng
        FROM orders_delivered od
        INNER JOIN customer_location cl ON od.customer_id = cl.customer_id
    ),

    -- Select the most recent review for each order, if available
    reviews_t AS(
        SELECT
            order_id,
            review_score
        FROM (
            SELECT
                *,
                ROW_NUMBER()
                    OVER(PARTITION BY order_id ORDER BY review_creation_date DESC) AS rn
            FROM `e-commerce-weather.e_commerce_weather_data.reviews`
            )
        WHERE rn = 1
        AND review_score IS NOT NULL
    ),

    -- Combine order, customer, and review data into a single dataset
    customer_overall AS(
        SELECT
            ocl.order_id,
            ocl.purchase_datetime,
            ocl.posting_datetime,
            ocl.delivery_datetime,
            ocl.days_delayed,
            ocl.days_delivering,
            ocl.customer_city,
            ocl.customer_state,
            ocl.customer_lat,
            ocl.customer_lng,
            r.review_score
        FROM orders_customer_location ocl
        LEFT JOIN reviews_t r ON ocl.order_id = r.order_id
    ),

    -- Map product IDs to their corresponding categories in English, defaulting to 'Unknown' if not found
    product_t AS(
        SELECT
            p.product_id,
            COALESCE(tr.product_category_name_english,'Unknown') AS product_category
        FROM `e-commerce-weather.e_commerce_weather_data.products` p
        LEFT JOIN `e-commerce-weather.e_commerce_weather_data.translation` tr
            ON p.product_category_name = tr.product_category_name
    ),

    -- Aggregate item prices and freight values per order and seller
    item_prod AS(
        SELECT
            i.order_id,
            i.seller_id,
            SUM(i.price) AS order_price,
            SUM(i.freight_value) As order_freight,
            p.product_category
        FROM `e-commerce-weather.e_commerce_weather_data.items` i
        LEFT JOIN product_t p ON i.product_id = p.product_id
        GROUP BY i.order_id, i.seller_id, p.product_category
    ),

    -- Map specific product categories into broader product family groups
    category_map AS(
        SELECT * FROM UNNEST([
        STRUCT('Unknown' AS category, 'Unknown' AS family),
            -- Home & Furniture
            ('housewares', 'Home & Furniture'),
            ('office_furniture', 'Home & Furniture'),
            ('bed_bath_table', 'Home & Furniture'),
            ('furniture_decor', 'Home & Furniture'),
            ('furniture_bedroom', 'Home & Furniture'),
            ('kitchen_dining_laundry_garden_furniture', 'Home & Furniture'),
            ('furniture_living_room', 'Home & Furniture'),
            ('furniture_mattress_and_upholstery', 'Home & Furniture'),
            ('home_confort', 'Home & Furniture'),
            ('home_comfort_2', 'Home & Furniture'),
            ('home_appliances', 'Home & Furniture'),
            ('home_appliances_2', 'Home & Furniture'),
            ('small_appliances', 'Home & Furniture'),
            ('small_appliances_home_oven_and_coffee', 'Home & Furniture'),
            ('air_conditioning', 'Home & Furniture'),
            ('la_cuisine', 'Home & Furniture'),

            -- Electronics & Tech
            ('computers_accessories', 'Electronics & Tech'),
            ('telephony', 'Electronics & Tech'),
            ('electronics', 'Electronics & Tech'),
            ('fixed_telephony', 'Electronics & Tech'),
            ('audio', 'Electronics & Tech'),
            ('cine_photo', 'Electronics & Tech'),
            ('tablets_printing_image', 'Electronics & Tech'),
            ('computers', 'Electronics & Tech'),
            ('signaling_and_security', 'Electronics & Tech'),
            ('security_and_services', 'Electronics & Tech'),

            -- Fashion & Accessories
            ('watches_gifts', 'Fashion & Accessories'),
            ('fashion_underwear_beach', 'Fashion & Accessories'),
            ('fashion_bags_accessories', 'Fashion & Accessories'),
            ('luggage_accessories', 'Fashion & Accessories'),
            ('fashion_shoes', 'Fashion & Accessories'),
            ('fashion_male_clothing', 'Fashion & Accessories'),
            ('fashion_sport', 'Fashion & Accessories'),
            ('fashio_female_clothing', 'Fashion & Accessories'),
            ('fashion_childrens_clothes', 'Fashion & Accessories'),

            -- Health & Beauty
            ('perfumery', 'Health & Beauty'),
            ('health_beauty', 'Health & Beauty'),
            ('diapers_and_hygiene', 'Health & Beauty'),

            -- Sports, Toys & Entertainment
            ('toys', 'Sports, Toys & Entertainment'),
            ('cool_stuff', 'Sports, Toys & Entertainment'),
            ('sports_leisure', 'Sports, Toys & Entertainment'),
            ('musical_instruments', 'Sports, Toys & Entertainment'),
            ('party_supplies', 'Sports, Toys & Entertainment'),
            ('cds_dvds_musicals', 'Sports, Toys & Entertainment'),
            ('consoles_games', 'Sports, Toys & Entertainment'),
            ('art', 'Sports, Toys & Entertainment'),
            ('christmas_supplies', 'Sports, Toys & Entertainment'),
            ('dvds_blu_ray', 'Sports, Toys & Entertainment'),
            ('music', 'Sports, Toys & Entertainment'),
            ('arts_and_craftmanship', 'Sports, Toys & Entertainment'),

            -- Construction & Tools
            ('garden_tools', 'Construction & Tools'),
            ('construction_tools_construction', 'Construction & Tools'),
            ('construction_tools_lights', 'Construction & Tools'),
            ('construction_tools_safety', 'Construction & Tools'),
            ('home_construction', 'Construction & Tools'),
            ('costruction_tools_garden', 'Construction & Tools'),
            ('costruction_tools_tools', 'Construction & Tools'),

            -- Books & Stationery
            ('stationery', 'Books & Stationery'),
            ('books_general_interest', 'Books & Stationery'),
            ('books_technical', 'Books & Stationery'),
            ('books_imported', 'Books & Stationery'),

            -- Groceries & Food
            ('food', 'Groceries & Food'),
            ('drinks', 'Groceries & Food'),
            ('food_drink', 'Groceries & Food'),
            ('flowers', 'Groceries & Food'),

            -- Baby & Pets
            ('pet_shop', 'Baby & Pets'),
            ('baby', 'Baby & Pets'),

            -- Auto, Industry & Misc
            ('auto', 'Auto, Industry & Misc'),
            ('market_place', 'Auto, Industry & Misc'),
            ('agro_industry_and_commerce', 'Auto, Industry & Misc'),
            ('industry_commerce_and_business', 'Auto, Industry & Misc')
        ])
    ),

    -- Join item-level product data with seller location and product family information
    item_prod_seller AS(
        SELECT
            ip.order_id, 
            sl.seller_id,
            ip.order_price,
            ip.order_freight,
            ip.product_category,
            cm.family AS product_family,
            sl.seller_city,
            sl.seller_state,
            sl.geo_lat AS seller_lat,
            sl.geo_lng AS seller_lng,
        FROM item_prod ip
        INNER JOIN seller_location sl ON ip.seller_id = sl.seller_id
        LEFT JOIN category_map cm ON ip.product_category = cm.category
    ),

    -- Combine customer, order, and seller data into a comprehensive dataset with geographical distance calculations
    olist_dataset AS(
        SELECT
            -- unique identifier for each order-seller pair (an order can have multiple products from multiple sellers)
            CONCAT(co.order_id, ips.seller_id) AS order_id,
            co.* EXCEPT (order_id),
            ips.* EXCEPT (order_id, seller_id),
            ST_DISTANCE(ST_GEOGPOINT(customer_lng, customer_lat),
                    ST_GEOGPOINT(seller_lng, seller_lat)) / 1000 AS distance_seller_customer
        FROM customer_overall co
        INNER JOIN item_prod_seller ips USING (order_id)
    ),
    
    -- Map weather codes to broader weather categories for analysis
    weather_map AS(
        SELECT * FROM UNNEST([
            STRUCT(0 AS code, 'Clear' AS weather_category),
                (1, 'Clear'),
                (2, 'Cloudy'),
                (3, 'Cloudy'),
                (51, 'Drizzle'),
                (53, 'Drizzle'),
                (55, 'Drizzle'),
                (61, 'Light Rain'),
                (63, 'Moderate Rain'),
                (65, 'Heavy Rain'),
                (71, 'Light Rain'),
                (73, 'Moderate Rain')
            ])
    ),

    -- Select the most relevant weather data and deduplicate raw daily weather data observations
    weather_data AS (
        SELECT 
            * EXCEPT (rn)
        FROM (
            SELECT
                CAST(w.date AS DATE) AS weather_date,
                w.latitude,
                w.longitude,
                w.precipitation AS delivery_precipitation,
                w.temp_min AS delivery_temp_min,
                w.temp_max AS delivery_temp_max,
                w.temp_max - w.temp_min AS delivery_temp_range,
                COALESCE(wm.weather_category, 'Other') AS delivery_weather_category,
                ROW_NUMBER() OVER (
                    PARTITION BY 
                    CAST(w.date AS DATE),
                    CAST(ROUND(w.latitude, 2) AS NUMERIC), 
                    CAST(ROUND(w.longitude, 2) AS NUMERIC)
                ) AS rn
            FROM `e-commerce-weather.e_commerce_weather_data.weather` w
            LEFT JOIN weather_map wm ON w.weather_code = wm.code
        )
        WHERE rn = 1
    ),

    -- Select distinct customer locations for distance calculations
    loc1 AS(
        SELECT DISTINCT 
            customer_lat AS lat,
            customer_lng AS lng
        FROM olist_dataset
    ),

    -- Select distinct weather station locations for distance calculations
    loc2 AS(
        SELECT DISTINCT
            latitude AS lat,
            longitude AS lng
        FROM weather_data
    ),
    
    -- Calculate the closest weather station for each customer location using a cross join and distance calculation
    cross_loc AS(
        SELECT
            l1.lat AS c_lat,
            l1.lng AS c_lng,
            l2.lat AS w_lat,
            l2.lng AS w_lng,
            ST_DISTANCE(ST_GEOGPOINT(l1.lng, l1.lat), ST_GEOGPOINT(l2.lng, l2.lat)) / 1000 AS distance_km
        FROM loc1 l1
        CROSS JOIN loc2 l2
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY 
                CAST(l1.lat AS NUMERIC),
                CAST(l1.lng AS NUMERIC)
            ORDER BY distance_km ASC
        ) = 1
    ),

    -- Join the main dataset with the closest weather station coordinates for each customer location
    df_translated AS(
        SELECT
            od.*,
            cl.w_lat,
            cl.w_lng
        FROM olist_dataset od
        LEFT JOIN cross_loc cl 
            ON od.customer_lat = cl.c_lat 
            AND od.customer_lng = cl.c_lng
    ),

    -- Join orders with daily weather data corresponding to the delivery date and station
    olist_weather_data AS(
        SELECT
            * EXCEPT(w_lat,w_lng,
                seller_lat, seller_lng,
                customer_lat, customer_lng,
                latitude, longitude,
                weather_date)

        FROM df_translated dt
        INNER JOIN weather_data wd
            ON CAST(dt.delivery_datetime AS DATE) = CAST(wd.weather_date AS DATE)
            AND dt.w_lat = wd.latitude 
            AND dt.w_lng = wd.longitude
    ),

    -- Add additional features to the dataset for predictive modeling
    final_df AS (
        SELECT
            *,
            -- Binary target indicator for late deliveries
            CASE WHEN days_delayed > 0 THEN 1 ELSE 0 END AS is_delayed,
            -- Geographic match flags
            CASE WHEN seller_state = customer_state THEN 1 ELSE 0 END AS is_same_state,
            CASE WHEN seller_city = customer_city THEN 1 ELSE 0 END AS is_same_city,
            -- Extract temporal features from the purchase datetime
            EXTRACT(MONTH FROM purchase_datetime) AS purchase_month,
            EXTRACT(DAYOFWEEK FROM purchase_datetime) AS purchase_weekday,
            -- Group states with low representation into an 'OTHER' category to reduce sparsity
            CASE
                WHEN COUNT(*) OVER (PARTITION BY seller_state) >= 100 THEN seller_state 
                ELSE 'OTHER' 
            END AS seller_state_grouped,
            CASE
                WHEN COUNT(*) OVER (PARTITION BY customer_state) >= 200 THEN customer_state 
                ELSE 'OTHER' 
            END AS customer_state_grouped
        FROM olist_weather_data owd
    )
    
-- Select final dataset ready for consumption or model training
SELECT * FROM final_df