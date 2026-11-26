"""Chat with the GastroFlow reviews (RAG over distinct review comments).

The reviews repeat heavily (294 distinct comments in 300,000 reviews), so we
embed each DISTINCT comment once and keep how many reviews use it. Embeddings
are cached in review_embeddings.parquet.

Run from the repo root:
    pip install -r app/requirements.txt
    gcloud auth application-default login
    streamlit run app/rag_chat.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import streamlit as st
from google.cloud import bigquery

from ai import llm

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

TOP_K = 5
MAX_COMMENTS = 1000  # safety cap on embedding calls
CACHE_FILE = "review_embeddings.parquet"

STAGING = llm.env("GASTROFLOW_DBT_DATASET", "DBT_DATASET", default="gastroflow_staging")
AI_DATASET = llm.env("GASTROFLOW_BQ_AI_DATASET", "BQ_AI_DATASET", default="gastroflow_ai")


def read_distinct_comments() -> pd.DataFrame:
    project = llm.project_id()
    bq = bigquery.Client(project=project)
    sql = f"""
        SELECT comment,
               COUNT(*) AS reviews,
               ROUND(AVG(rating), 2) AS avg_rating,
               COUNT(DISTINCT city) AS cities
        FROM `{project}.{STAGING}.stg_reviews`
        WHERE comment IS NOT NULL
        GROUP BY comment
        ORDER BY reviews DESC
        LIMIT {MAX_COMMENTS}
    """
    return bq.query(sql).to_dataframe()


@st.cache_data(show_spinner="Embedding distinct review comments (one-time)...")
def load_comments() -> pd.DataFrame:
    if os.path.exists(CACHE_FILE):
        return pd.read_parquet(CACHE_FILE)
    df = read_distinct_comments()
    client = llm.make_embedding_client()
    df["embedding"] = llm.embed_texts(client, df["comment"].tolist())
    df.to_parquet(CACHE_FILE)
    return df


def find_similar(question: str, df: pd.DataFrame) -> pd.DataFrame:
    client = llm.make_embedding_client()
    q = np.array(
        llm.embed_texts(client, [question], task_type="RETRIEVAL_QUERY")[0]
    )
    matrix = np.vstack(df["embedding"].to_numpy())
    scores = matrix @ q / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q))
    out = df.copy()
    out["score"] = scores
    return out.nlargest(TOP_K, "score")


def ask_llm(question: str, top: pd.DataFrame) -> str:
    context = "".join(
        f"- ({row['reviews']:,} reviews, avg {row['avg_rating']} stars) {row['comment']}\n"
        for _, row in top.iterrows()
    )
    system = (
        "Answer ONLY using the customer review comments provided. Each comment "
        "shows how many reviews used it. Be concise. If the reviews do not "
        "cover the question, say so."
    )
    user = f"Question: {question}\n\nReview comments:\n{context}"
    return llm.generate_text(llm.make_chat_client(), system, user)


st.title("Chat with your GastroFlow reviews")
reviews_df = load_comments()
st.caption(
    f"Searching {len(reviews_df):,} distinct comments, answering with {llm.chat_model()}"
)

question = st.text_input(
    "Ask a question about your reviews:",
    placeholder="e.g. What are the most common complaints about delivery?",
)

if question:
    top_reviews = find_similar(question, reviews_df)
    st.markdown("**Answer:**")
    st.write(ask_llm(question, top_reviews))
    with st.expander("Review comments used to build this answer"):
        st.dataframe(
            top_reviews[["comment", "reviews", "avg_rating", "score"]],
            hide_index=True,
        )
