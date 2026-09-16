import rag_engine

schema_reminder = '''
{ "audio_response": "...", "end_session": false, "print_summary": false, "printed_receipt": {} }
'''

res = rag_engine.ollama_fallback_engine(
    "Answer in Hindi. You are a helper.",
    "What schemes are there for farmers?",
    {"error": "fallback"},
    schema_reminder
)

print(res)
