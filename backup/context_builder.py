from database import get_user_profile, get_user_transactions, get_jurisdiction

def build_context(fingerprint_id, document_text, query_text):
    user = get_user_profile(fingerprint_id)
    if user is None:
        return None

    transactions = get_user_transactions(fingerprint_id)
    jurisdiction = get_jurisdiction(user["village"], user["occupation"])

    context = {
        "user": user,
        "transactions": transactions,
        "jurisdiction": jurisdiction,
        "document_text": document_text,
        "query": query_text
    }

    return context