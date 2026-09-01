from database import get_user_profile, get_user_transactions

def build_context(fingerprint_id, document_text, query_text):
    user = get_user_profile(fingerprint_id)
    if user is None:
        return None

    transactions = get_user_transactions(fingerprint_id)

    context = {
        "user": user,
        "transactions": transactions,
        "document_text": document_text,
        "query": query_text
    }

    return context