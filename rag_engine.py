import os
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

    response = requests.post(
"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=15
    )
    response.raise_for_status()
    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return raw_text