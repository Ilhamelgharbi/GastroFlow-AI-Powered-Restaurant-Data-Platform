from google import genai
import os

client = genai.Client(
    api_key=os.environ["GASTROFLOW_GEMINI_API_KEY"]
)

response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents="Classify this restaurant review: Food was excellent!"
)

print(response.text)