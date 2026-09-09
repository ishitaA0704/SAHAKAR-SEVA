import os
import sys
import json
import requests
sys.path.insert(0, '.')
from rag_engine import load_knowledge_for_occupation

api_key = os.environ.get('GEMINI_API_KEY')
knowledge = load_knowledge_for_occupation('Farmer')

# Case A: English Query, language="hi"
context_hi = {
    'user': {'name': 'Ramesh', 'occupation': 'Farmer', 'district': 'Mandya'},
    'jurisdiction': {'pacs_name': 'Mandya PACS'},
    'document_text': '',
    'query': 'What documents do I need for a crop loan?'
}

# Case B: English Query, language="kn"
context_kn = {
    'user': {'name': 'Ramesh', 'occupation': 'Farmer', 'district': 'Mandya'},
    'jurisdiction': {'pacs_name': 'Mandya PACS'},
    'document_text': '',
    'query': 'What documents do I need for a crop loan?'
}

# Case C: Kannada Query, language="kn"
context_kn_query = {
    'user': {'name': 'Ramesh', 'occupation': 'Farmer', 'district': 'Mandya'},
    'jurisdiction': {'pacs_name': 'Mandya PACS'},
    'document_text': '',
    'query': 'ಬೆಳೆ ಸಾಲಕ್ಕೆ ಏನೇನು ದಾಖಲೆಗಳು ಬೇಕು?'
}

def test_prompt(context, language, filename_prefix):
    lang_name = "Hindi" if language == "hi" else "Kannada" if language == "kn" else "English"
    script_name = "Devanagari script" if language == "hi" else "Kannada script" if language == "kn" else "English"

    # Current approach (embedded in prompt)
    prompt_current = f"""IMPORTANT: You must respond entirely in {lang_name} ({script_name}). This applies to the "answer", "next_steps", and "reference" fields in your JSON output. This is mandatory regardless of what language the source documents below are written in.

You are a cooperative assistant helping a rural {context['user']['occupation']}.

User profile: {context['user']}
Jurisdiction (nearest office): {context['jurisdiction']}
Document text (OCR): {context['document_text']}
Question: {context['query']}

Relevant scheme rules:
{knowledge}

Answer ONLY using the rules above. If the question is unrelated to cooperative/scheme matters, politely refuse and redirect to cooperative topics.

REMINDER: Write your "answer", "next_steps", and "reference" values entirely in {lang_name}, even though the scheme rules above are in English. Translate the relevant information into {lang_name} yourself.

Respond strictly in JSON with no other text:
{{"answer": "...", "next_steps": "...", "reference": "..."}}
"""

    res_current = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt_current}]}]},
        timeout=30
    )
    if res_current.status_code == 200:
        with open(f"scratch/{filename_prefix}_current.json", "w", encoding="utf-8") as f:
            f.write(res_current.json()["candidates"][0]["content"]["parts"][0]["text"])

    # System Instruction + JSON mime type approach
    system_instruction = f"""You are a helpful cooperative assistant for rural citizens.
CRITICAL MANDATE: You MUST respond entirely in {lang_name} ({script_name}) for ALL string fields in your JSON output ("answer", "next_steps", "reference").
Translate all information, scheme details, and advice from the English reference documents into {lang_name} ({script_name}).
Do NOT use English in the output values under any circumstances when target language is {lang_name}."""

    user_content = f"""You are a cooperative assistant helping a rural {context['user']['occupation']}.

User profile: {context['user']}
Jurisdiction (nearest office): {context['jurisdiction']}
Document text (OCR): {context['document_text']}
Question: {context['query']}

Relevant scheme rules:
{knowledge}

Answer ONLY using the rules above. If the question is unrelated to cooperative/scheme matters, politely refuse and redirect to cooperative topics.

Respond strictly in JSON:
{{"answer": "...", "next_steps": "...", "reference": "..."}}
"""

    res_system = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
        params={"key": api_key},
        json={
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        },
        timeout=30
    )
    if res_system.status_code == 200:
        with open(f"scratch/{filename_prefix}_system.json", "w", encoding="utf-8") as f:
            f.write(res_system.json()["candidates"][0]["content"]["parts"][0]["text"])

print("Running tests for English query -> Hindi target...")
test_prompt(context_hi, "hi", "enQuery_to_hi")

print("Running tests for English query -> Kannada target...")
test_prompt(context_kn, "kn", "enQuery_to_kn")

print("Running tests for Kannada query -> Kannada target...")
test_prompt(context_kn_query, "kn", "knQuery_to_kn")

print("Done testing!")
