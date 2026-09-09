from flask import Flask, render_template, request, jsonify, send_file
from context_builder import build_context
from rag_engine import get_ai_answer, get_session_summary
from pdf_printer import generate_and_print
import os
import json

app = Flask(__name__)

conversations = {}  # {fingerprint_id: [{"query": ..., "answer": ...}, ...]}
GEMINI_KEY = os.environ.get("AQ.Ab8RN6KISs6xiKM1vMHGv0_s2zgPM0RrwMknazC3Gwk7mZgSqw")

def clean_json_response(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


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
    language = data.get("language", "en")

    context = build_context(fingerprint_id, document_text, query)
    if context is None:
        return jsonify({"status": "not_registered"})

    raw_answer = get_ai_answer(context, GEMINI_KEY, language)

    try:
        parsed_answer = json.loads(clean_json_response(raw_answer))
    except json.JSONDecodeError:
        parsed_answer = {"answer": raw_answer, "next_steps": "", "reference": ""}

    conversations.setdefault(fingerprint_id, []).append({
        "query": query,
        "answer": parsed_answer.get("answer", "")
    })

    return jsonify({"status": "ok", **parsed_answer})


@app.route("/finish", methods=["POST"])
def finish():
    data = request.json
    fingerprint_id = int(data["fingerprint_id"])

    context = build_context(fingerprint_id, document_text="", query_text="")
    if context is None:
        return jsonify({"status": "not_registered"})

    history = conversations.get(fingerprint_id, [])
    raw_summary = get_session_summary(context, history, GEMINI_KEY)

    try:
        parsed_summary = json.loads(clean_json_response(raw_summary))
    except json.JSONDecodeError:
        parsed_summary = {"main_issue": raw_summary}

    conversations.pop(fingerprint_id, None)

    return jsonify({"status": "ok", "summary": parsed_summary})


@app.route("/print_summary", methods=["POST"])
def print_summary():
    """
    Receives the session summary + fingerprint_id, generates an A4 PDF,
    and silently prints it to the default Windows printer via pywin32.
    Body: { fingerprint_id, summary: {...} }
    Returns: { status: 'printed'|'print_error'|'error', message, pdf_path? }
    """
    data = request.json
    fingerprint_id = int(data.get("fingerprint_id", 0))
    summary = data.get("summary", {})

    context = build_context(fingerprint_id, document_text="", query_text="")
    if context is None:
        return jsonify({"status": "error", "message": "User not found — cannot generate PDF."}), 400

    result = generate_and_print(summary, context["user"], context["jurisdiction"])
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)