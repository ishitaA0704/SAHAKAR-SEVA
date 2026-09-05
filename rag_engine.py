import os
import json
import requests

def load_knowledge_for_occupation(occupation):
    folder_map = {
        "Farmer": "knowledge_base/farmer",
        "Artisan": "knowledge_base/artisan",
        "Landless Labourer": "knowledge_base/landless_labourer"
    }
    folder = folder_map[occupation]
    combined_text = ""
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            combined_text += f.read() + "\n\n---\n\n"
    return combined_text


def get_ai_answer(context, api_key):
    knowledge = load_knowledge_for_occupation(context["user"]["occupation"])

    if not knowledge.strip():
        fallback = {
            "answer": "I don't have verified scheme information for this category yet. Please contact your local cooperative office directly for accurate guidance.",
            "next_steps": "Visit your nearest PACS/cooperative office for scheme information.",
            "reference": "No grounding documents available for this occupation"
        }
        return json.dumps(fallback)

    prompt = f"""You are a cooperative assistant helping a rural {context['user']['occupation']}.

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

    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        response.raise_for_status()
        raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return raw_text

    except requests.exceptions.RequestException as e:
        print("GEMINI API ERROR:", e)
        fallback = {
            "answer": "We're having trouble reaching our systems right now. Please try again in a moment, or visit your nearest cooperative office for assistance.",
            "next_steps": "Retry shortly, or contact your local PACS/cooperative office directly.",
            "reference": "Offline fallback response"
        }
        return json.dumps(fallback)


def get_session_summary(context, conversation_history, api_key):
    knowledge = load_knowledge_for_occupation(context["user"]["occupation"])

    if not knowledge.strip():
        fallback = {
            "main_issue": "No verified scheme information available for this category.",
            "questions_discussed": [turn["query"] for turn in conversation_history],
            "recommended_next_steps": "Please visit your nearest cooperative office for accurate guidance.",
            "required_documents": [],
            "reference": "No grounding documents available for this occupation"
        }
        return json.dumps(fallback)

    history_text = "\n".join(
        f"Q: {turn['query']}\nA: {turn['answer']}" for turn in conversation_history
    )

    prompt = f"""You are summarizing a cooperative assistance session for a rural {context['user']['occupation']}.

Farmer profile: {context['user']}
Jurisdiction: {context['jurisdiction']}

Full conversation:
{history_text}

Create a concise final summary. Respond strictly in JSON with no other text:
{{
    "main_issue": "...",
    "questions_discussed": ["...", "..."],
    "recommended_next_steps": "...",
    "required_documents": ["...", "..."],
    "reference": "..."
}}
Do not add information that wasn't established in the conversation.
"""

    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.RequestException as e:
        print("GEMINI SUMMARY ERROR:", e)
        fallback = {
            "main_issue": "Summary unavailable due to a connection issue.",
            "questions_discussed": [turn["query"] for turn in conversation_history],
            "recommended_next_steps": "Please visit your nearest cooperative office for assistance.",
            "required_documents": [],
            "reference": "Offline fallback summary"
        }
        return json.dumps(fallback)