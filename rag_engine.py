import os
import json
import requests

LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}


def load_knowledge_for_occupation(occupation):
    """Load all text/markdown knowledge files for a given occupation."""
    folder_map = {
        "Farmer": "knowledge_base/farmer",
        "Artisan": "knowledge_base/artisan",
        "Landless Labourer": "knowledge_base/landless_labourer"
    }
    folder = folder_map.get(occupation)
    if not folder or not os.path.exists(folder):
        return ""

    combined_text = ""
    for filename in sorted(os.listdir(folder)):
        filepath = os.path.join(folder, filename)
        # Only read files, skip any subdirectories
        if not os.path.isfile(filepath):
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                combined_text += f"### {filename}\n" + f.read() + "\n\n---\n\n"
        except Exception as e:
            print(f"Could not read knowledge file {filepath}: {e}")
    return combined_text


def fallback_regex_engine(image_text, user_occupation):
    """Basic offline fallback when cloud API is unreachable."""
    text = (image_text or "").upper()
    if "REJECTED" in text:
        return {
            "audio_response": "Your application shows as rejected. Please check the printed receipt and visit counter 3.",
            "printed_receipt": {"status": "REJECTED", "reference": "ERR-701", "instruction": "Visit Counter 3"}
        }
    elif "FERTILIZER" in text or "FERTILISER" in text:
        return {
            "audio_response": "Your fertilizer subsidy is approved. Please collect it from the warehouse using this receipt.",
            "printed_receipt": {"status": "APPROVED", "item": "Fertilizer Subsidy", "warehouse_zone": "A"}
        }
    return {
        "audio_response": "Offline mode is active. Please hand your document to the clerk for manual assistance.",
        "printed_receipt": {"status": "OFFLINE", "instruction": "Manual Review Required"}
    }


def get_ai_answer(context, api_key, language="en", query_text="", image_b64=""):
    """
    Call Gemini to answer a user query.
    Returns a JSON string with keys: audio_response, printed_receipt.
    """
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not set. Returning offline fallback.")
        return json.dumps(fallback_regex_engine("", context["user"].get("occupation", "")))

    knowledge = load_knowledge_for_occupation(context["user"]["occupation"])

    if not knowledge.strip():
        fallback = {
            "audio_response": "I don't have verified scheme information for this category yet. Please contact your nearest cooperative office.",
            "printed_receipt": {"reference": "No knowledge documents available for this occupation"}
        }
        return json.dumps(fallback)

    lang_name = LANG_NAMES.get(language, "English")
    script_name = "Devanagari script" if language == "hi" else "Kannada script" if language == "kn" else "Latin script"

    system_instruction = f"""You are a cooperative assistant kiosk helping a rural {context['user']['occupation']} in India.
LANGUAGE MANDATE: ALL string values in your JSON response MUST be written in {lang_name} ({script_name}).
Do NOT use English in any JSON string value when the target language is {lang_name}.

PRIVACY RULE — split your answer into two channels:
1. "audio_response": Safe, general guidance to be spoken aloud in public. NO financial amounts, account numbers, or private figures.
2. "printed_receipt": Private details (amounts, account numbers, references) to be printed silently on paper.

CRITICAL RULE: Do NOT greet the user by name, and do NOT mention their location or occupation in your response. Skip the pleasantries and answer the question directly and concisely.

If the question is unrelated to cooperative/agricultural/government scheme matters, politely decline in {lang_name}.

Respond ONLY with valid JSON in this exact schema — no extra text:
{{
  "audio_response": "...",
  "printed_receipt": {{
    "amounts": "...",
    "account_info": "...",
    "reference": "..."
  }}
}}"""

    user_prompt = (
        f"User Profile: {context['user']}\n"
        f"Jurisdiction (nearest office): {context['jurisdiction']}\n"
        f"User's Question: {query_text}\n\n"
        f"Relevant Scheme Rules (use these as your ONLY source of truth):\n{knowledge}"
    )

    parts = [{"text": user_prompt}]

    if image_b64:
        clean_b64 = image_b64.split(',')[1] if ',' in image_b64 else image_b64
        parts.append({"inlineData": {"mimeType": "image/jpeg", "data": clean_b64}})

    models_to_try = [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
    ]
    
    request_body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    import time
    for model_url in models_to_try:
        retries = 3
        while retries > 0:
            try:
                response = requests.post(
                    model_url,
                    params={"key": api_key},
                    json=request_body,
                    timeout=30
                )
                if response.status_code == 429:
                    # Try to extract exact retry delay, otherwise default to 15s
                    delay = 15
                    try:
                        err_data = response.json()
                        details = err_data.get("error", {}).get("details", [])
                        for d in details:
                            if "retryDelay" in d:
                                delay = int(d["retryDelay"].replace("s","")) + 1
                    except: pass
                    print(f"Model {model_url.split('/')[-1]} rate-limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    retries -= 1
                    continue
                response.raise_for_status()
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                if getattr(e, 'response', None) is not None and e.response.status_code == 429:
                    pass # Handled above
                else:
                    print(f"Model {model_url.split('/')[-1]} failed: {e}.")
                    break

    print(f"All Gemini models failed/rate-limited — using offline regex fallback.")
    return json.dumps(fallback_regex_engine("", context["user"].get("occupation", "")))


def get_session_summary(context, conversation_history, api_key, language="en"):
    """
    Produce a structured session summary using the full Q&A history.
    """
    if not api_key:
        return json.dumps({
            "main_issue": "API key not configured. Summary unavailable.",
            "questions_discussed": [],
            "recommended_next_steps": "Please visit your nearest cooperative office.",
            "required_documents": [],
            "reference": "Offline"
        })

    knowledge = load_knowledge_for_occupation(context["user"]["occupation"])

    # Build readable history with both questions AND answers
    history_text = ""
    for i, turn in enumerate(conversation_history, 1):
        history_text += f"Q{i}: {turn.get('query', '')}\nA{i}: {turn.get('answer', '')}\n\n"

    if not history_text.strip():
        history_text = "No conversation recorded yet."

    lang_name = LANG_NAMES.get(language, "English")
    script_name = "Devanagari script" if language == "hi" else "Kannada script" if language == "kn" else "Latin script"

    system_instruction = (
        f"You are summarizing a cooperative assistance session for a rural {context['user']['occupation']}. "
        f"LANGUAGE MANDATE: ALL string values in your JSON response MUST be in {lang_name} ({script_name})."
    )

    user_prompt = (
        f"User Profile: {context['user']}\n"
        f"Jurisdiction: {context['jurisdiction']}\n\n"
        f"Full Conversation:\n{history_text}\n"
        f"Create a concise summary. Respond ONLY with valid JSON:\n"
        f'{{"main_issue": "...", "questions_discussed": ["...", "..."], '
        f'"recommended_next_steps": "...", "required_documents": ["...", "..."], "reference": "..."}}'
    )

    models_to_try = [
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent"
    ]
    
    request_body = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    import time
    for model_url in models_to_try:
        retries = 3
        while retries > 0:
            try:
                response = requests.post(
                    model_url,
                    params={"key": api_key},
                    json=request_body,
                    timeout=30
                )
                if response.status_code == 429:
                    delay = 15
                    try:
                        err_data = response.json()
                        details = err_data.get("error", {}).get("details", [])
                        for d in details:
                            if "retryDelay" in d:
                                delay = int(d["retryDelay"].replace("s","")) + 1
                    except: pass
                    print(f"Summary: Model {model_url.split('/')[-1]} rate-limited. Retrying in {delay}s...")
                    time.sleep(delay)
                    retries -= 1
                    continue
                response.raise_for_status()
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                if getattr(e, 'response', None) is not None and e.response.status_code == 429:
                    pass
                else:
                    print(f"Model {model_url.split('/')[-1]} failed: {e}.")
                    break

    return json.dumps({
        "main_issue": "System offline. / ಸಿಸ್ಟಮ್ ಆಫ್‌ಲೈನ್‌ನಲ್ಲಿದೆ.",
        "questions_discussed": [],
        "recommended_next_steps": "Please try again later. / ದಯವಿಟ್ಟು ನಂತರ ಪ್ರಯತ್ನಿಸಿ.",
        "required_documents": [],
        "reference": "ERR-OFFLINE"
    })