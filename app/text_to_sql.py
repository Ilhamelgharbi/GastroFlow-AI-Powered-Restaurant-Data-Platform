"""Chat with the GastroFlow marts: English question -> Gemini writes BigQuery SQL.

Run from the repo root:
    pip install -r app/requirements.txt
    gcloud auth application-default login
    streamlit run app/text_to_sql.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import streamlit as st
from google.cloud import bigquery
from pydantic import BaseModel

from ai import llm
from ai.sql_safety import MARTS_DATASET, clean_sql, is_safe

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

MAX_BYTES_BILLED = int(
    llm.env("GASTROFLOW_APP_MAX_BYTES_BILLED", default=str(10 * 1024**3))
)  # 10 GB cap per query

EXAMPLE_QUESTIONS = [
    "Top 10 cities by GMV",
    "Which cuisine has the most orders?",
    "Average delivery time by city, worst first",
    "Cancel rate by city",
]

SCHEMA = """
BigQuery tables in dataset gastroflow_marts. Use bare table names (no project or
dataset prefix).

IMPORTANT TYPE NOTE: most order columns come from raw text and are STRING.
Use SAFE_CAST(col AS NUMERIC / INT64 / DATE) before doing math or date logic.

fct_orders(order_id, order_timestamp TIMESTAMP, order_date STRING, customer_id,
           restaurant_id, city, cuisine, payment_method, order_status,
           is_delivered BOOL, items_count, sales_qty, subtotal, discount,
           delivery_fee, gst, sales_amount, customer_rating, delivery_time_min)
           -- order_status is one of 'Delivered', 'Cancelled', 'Refunded'
fct_order_items(order_item_id, order_id, restaurant_id, f_id, order_ts TIMESTAMP,
                order_date, city, price, quantity, line_amount)
dim_restaurants(restaurant_id INT64, restaurant_name, city, cuisine,
                rating NUMERIC, rating_count INT64, cost_for_two INT64)
dim_customers(customer_id INT64, customer_name, age INT64, age_group, gender,
              marital_status, occupation, income_band, education, family_size)
dim_food(f_id, food_name, veg_or_non_veg)
mart_daily_city_revenune(order_date, city, orders, delivered_orders, cancel_rate,
                         gmv, aov)
mart_monthly_city_sales(order_month DATE, city, order_count, delivered_order_count,
                        cancelled_order_count, delivered_gmv)
mart_restaurant_performance(restaurant_id, restaurant_name, city, cuisine, orders,
                            revenue, avg_customer_rating, avg_delivery_min)
mart_delivery_sla(city, order_hour, delivered_orders, p50, p90)
mart_customer_order_summary(customer_id, customer_name, age_group, order_count,
                            delivered_order_count, delivered_sales,
                            first_order_timestamp, last_order_timestamp)
mart_food_performance(food_id, food_name, veg_or_non_veg, order_count,
                      quantity_sold, sales_amount)

Note: gmv means delivered revenue. Prefer the mart_ tables when they fit the question.
"""

SYSTEM_PROMPT = f"""You are a BigQuery Standard SQL expert. Write ONE SELECT query
that answers the question.

Rules:
- SELECT queries only, never modify data.
- Use bare table names exactly as listed below.
- Never select email or password columns.
- Add LIMIT 100 or less, unless the question asks for a single total.

{SCHEMA}
"""


class SqlAnswer(BaseModel):
    sql: str


@st.cache_resource
def get_clients():
    project = llm.project_id()
    return bigquery.Client(project=project), llm.make_chat_client(), project


def generate_sql(question: str) -> str:
    _, chat_client, _ = get_clients()
    answer = llm.generate_json(chat_client, SYSTEM_PROMPT, question, SqlAnswer)
    return clean_sql(answer.sql)


def run_query(sql: str) -> pd.DataFrame:
    bq, _, project = get_clients()
    config = bigquery.QueryJobConfig(
        default_dataset=f"{project}.{MARTS_DATASET}",
        maximum_bytes_billed=MAX_BYTES_BILLED,
    )
    return bq.query(sql, job_config=config).to_dataframe()


st.title("Chat with your GastroFlow data")
st.caption(f"Ask in English, {llm.chat_model()} writes the SQL, BigQuery runs it")

with st.sidebar:
    st.header("Example questions")
    for q in EXAMPLE_QUESTIONS:
        st.markdown(f"- {q}")

question = st.text_input(
    "Enter your question here",
    placeholder="e.g. Top 10 restaurants by revenue in Bangalore",
)

if question:
    try:
        sql = generate_sql(question)
    except Exception as exc:
        st.error(f"Could not generate SQL: {exc}")
        st.stop()

    st.code(sql, language="sql")
    ok, reason = is_safe(sql)
    if not ok:
        st.error(f"The generated SQL is not safe to run ({reason}). Rephrase your question.")
    else:
        try:
            df = run_query(sql)
            st.success(f"{len(df)} rows returned")
            st.dataframe(df, hide_index=True)
            if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
                st.bar_chart(df, x=df.columns[0], y=df.columns[1])
        except Exception as exc:
            st.error(f"Error running query: {exc}")
