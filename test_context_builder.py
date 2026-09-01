from context_builder import build_context

dummy_document_text = "LOAN APPLICATION REJECTED DUE TO MISSING LAND DOCUMENT"
dummy_query = "Why was my loan rejected?"

context = build_context(14, dummy_document_text, dummy_query)
print(context)