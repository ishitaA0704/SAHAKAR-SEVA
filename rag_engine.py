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


def ollama_fallback_engine(system_instruction, user_prompt, default_fallback, schema_reminder=None):
    """Call local Ollama instance for offline fallback."""
    url = "http://127.0.0.1:11434/api/generate"
    
    if not schema_reminder:
        schema_reminder = """
    
CRITICAL: You MUST answer the user's question using the scheme rules above.
Respond ONLY with a JSON object exactly matching this schema:
{
  "audio_response": "Your answer to the user in the target language.",
  "end_session": false,
  "print_summary": false,
  "printed_receipt": {}
}"""
    
    # llama3.2:3b is ~3x faster than llama3.1 on CPU (~8-12s on i7)
    payload = {
        "model": "llama3.2:3b",
        "system": system_instruction,
        "prompt": user_prompt + "\n\n" + schema_reminder,
        "format": "json",
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "temperature": 0.0,
            "top_k": 5
        }
    }
    
    try:
        # 60 seconds is sufficient for llama3.2:3b on CPU (typically 8-15s)
        response = requests.post(url, json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"Ollama local fallback failed: {e}")
        return json.dumps(default_fallback)


def get_ai_answer(context, api_key, language="en", query_text="", image_b64=""):
    """
    Call Gemini to answer a user query.
    Returns a JSON string with keys: audio_response, printed_receipt.
    """
    if not api_key:
        print("WARNING: GEMINI_API_KEY is not set. Will attempt local Ollama fallback.")

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

SESSION MANAGEMENT RULES:
- "end_session": boolean, "print_summary": boolean.
- Default to "end_session": false and "print_summary": false for almost all questions.
- ONLY set "end_session": true if the user EXPLICITLY and UNAMBIGUOUSLY states they are leaving, want to end the chat, or says goodbye.
- ONLY set "print_summary": true if the user EXPLICITLY commands the kiosk to print a receipt of the current conversation (e.g., "print this receipt", "give me a printout of our chat").
- CRITICAL: If the user asks a question about how to print scheme documents or forms (e.g., "can I print the application?"), they are asking a question, NOT ending the session. Set both to false and answer normally.

Respond ONLY with valid JSON in this exact schema — no extra text:
{{
  "audio_response": "...",
  "end_session": false,
  "print_summary": false,
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
    if api_key:
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

    print(f"Using local Ollama fallback for answer.")
    default_fallback = {
        "audio_response": "Offline mode is active. Please hand your document to the clerk for manual assistance.",
        "printed_receipt": {"status": "OFFLINE", "instruction": "Manual Review Required"}
    }
    
    chat_schema_reminder = f"""
CRITICAL: You MUST write ALL JSON string values in {lang_name} ({script_name}). Do not use any other language!
If the user EXPLICITLY asks to exit, say goodbye, or print a receipt (e.g. "exit", "finish", "print receipt"), set "end_session": true. Otherwise it MUST be false.
Respond ONLY with a JSON object exactly matching this schema:
{{
  "audio_response": "Your answer to the user in {lang_name}.",
  "end_session": false,
  "print_summary": false,
  "printed_receipt": {{}}
}}"""
    return ollama_fallback_engine(system_instruction, user_prompt, default_fallback, schema_reminder=chat_schema_reminder)


def get_session_summary(context, conversation_history, api_key, language="en"):
    """
    Produce a structured session summary using the full Q&A history.
    """
    if not api_key:
        print("WARNING: GEMINI_API_KEY is not set. Will attempt local Ollama fallback for summary.")

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
    if api_key:
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

    print(f"Using local Ollama fallback for summary.")
    default_fallback = {
        "main_issue": "System offline. / ಸಿಸ್ಟಮ್ ಆಫ್‌ಲೈನ್‌ನಲ್ಲಿದೆ.",
        "questions_discussed": [],
        "recommended_next_steps": "Please try again later. / ದಯವಿಟ್ಟು ನಂತರ ಪ್ರಯತ್ನಿಸಿ.",
        "required_documents": [],
        "reference": "ERR-OFFLINE"
    }
    
    summary_schema_reminder = f"""
CRITICAL: You MUST write ALL JSON string values in {lang_name} ({script_name}). Do not use any other language!
Respond ONLY with a JSON object exactly matching this schema:
{{
  "main_issue": "Short sentence summarizing the main problem in {lang_name}",
  "questions_discussed": ["question 1", "question 2"],
  "recommended_next_steps": "What the user should do next",
  "required_documents": ["doc 1", "doc 2"],
  "reference": "Any reference number or rule mentioned"
}}"""
    
    return ollama_fallback_engine(system_instruction, user_prompt, default_fallback, schema_reminder=summary_schema_reminder)