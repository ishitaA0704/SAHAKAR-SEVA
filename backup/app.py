from flask import Flask, render_template, request, jsonify
from context_builder import build_context
from rag_engine import get_ai_answer
import os
import json

app = Flask(__name__)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/authenticate", methods=["POST"])
def authenticate():
    fingerprint_id = int(request.json.get("fingerprint_id", 14))

    context = build_context(fingerprint_id, document_text="", query_text="")
    if context is None:
        return jsonify({"status": "not_registered"})

    return jsonify({
        "status": "ok",
        "user": context["user"]
    })

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json
    fingerprint_id = int(data["fingerprint_id"])
    query = data["query"]
    document_text = data.get("document_text", "")

    context = build_context(fingerprint_id, document_text, query)
    if context is None:
        return jsonify({"status": "not_registered"})

    raw_answer = get_ai_answer(context, GEMINI_KEY)

    try:
        parsed_answer = json.loads(raw_answer)
    except json.JSONDecodeError:
        parsed_answer = {"answer": raw_answer, "next_steps": "", "reference": ""}

    return jsonify({"status": "ok", **parsed_answer})

if __name__ == "__main__":
    app.run(debug=True)