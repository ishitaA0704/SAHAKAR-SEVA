import os
from context_builder import build_context
from rag_engine import get_ai_answer

context = build_context(14, "LOAN APPLICATION REJECTED DUE TO MISSING LAND DOCUMENT", "Why was my loan rejected?")

api_key = os.environ.get("GEMINI_API_KEY")
answer = get_ai_answer(context, api_key)
print(answer)