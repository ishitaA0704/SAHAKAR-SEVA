import os
import sys
import json
import requests
sys.path.insert(0, '.')
from rag_engine import load_knowledge_for_occupation

api_key = os.environ.get('GEMINI_API_KEY')
knowledge = load_knowledge_for_occupation('Farmer')

context = {
    'user': {'name': 'Ramesh', 'occupation': 'Farmer', 'district': 'Mandya'},
    'jurisdiction': {'pacs_name': 'Mandya PACS'},
    'document_text': '',
    'query': 'मुझे फसल ऋण (crop loan) के लिए क्या दस्तावेज चाहिए?'
}

language = 'hi'
lang_name = 'Hindi'
script_name = 'Devanagari script'

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

print("=== TEST 1: Current setup (gemini-flash-lite-latest, prompt only) ===")
res1 = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
    params={"key": api_key},
    json={"contents": [{"parts": [{"text": prompt_current}]}]},
    timeout=30
)
print("STATUS:", res1.status_code)
if res1.status_code == 200:
    raw_text = res1.json()["candidates"][0]["content"]["parts"][0]["text"]
    with open("scratch/test1_output.json", "w", encoding="utf-8") as f:
        f.write(raw_text)
    print("SAVED TO scratch/test1_output.json")

# TEST 2: Using systemInstruction
print("\n=== TEST 2: Using systemInstruction field ===")
system_instruction = f"You are a helpful cooperative assistant for rural citizens. You MUST respond entirely in {lang_name} ({script_name}) for all fields in your JSON output. Translate any background information or scheme rules from English into {lang_name}."

user_prompt = f"""You are a cooperative assistant helping a rural {context['user']['occupation']}.

User profile: {context['user']}
Jurisdiction (nearest office): {context['jurisdiction']}
Document text (OCR): {context['document_text']}
Question: {context['query']}

Relevant scheme rules:
{knowledge}

Answer ONLY using the rules above. If the question is unrelated to cooperative/scheme matters, politely refuse and redirect to cooperative topics.

Respond strictly in JSON with no other text:
{{"answer": "...", "next_steps": "...", "reference": "..."}}
"""

res2 = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
    params={"key": api_key},
    json={
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [{"parts": [{"text": user_prompt}]}]
    },
    timeout=30
)
print("STATUS:", res2.status_code)
if res2.status_code == 200:
    raw_text2 = res2.json()["candidates"][0]["content"]["parts"][0]["text"]
    with open("scratch/test2_output.json", "w", encoding="utf-8") as f:
        f.write(raw_text2)
    print("SAVED TO scratch/test2_output.json")

# TEST 3: System Instruction + responseMimeType: application/json
print("\n=== TEST 3: systemInstruction + generationConfig application/json ===")
res3 = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
    params={"key": api_key},
    json={
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    },
    timeout=30
)
print("STATUS:", res3.status_code)
if res3.status_code == 200:
    raw_text3 = res3.json()["candidates"][0]["content"]["parts"][0]["text"]
    with open("scratch/test3_output.json", "w", encoding="utf-8") as f:
        f.write(raw_text3)
    print("SAVED TO scratch/test3_output.json")
