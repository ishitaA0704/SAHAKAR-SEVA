from flask import Flask, render_template, request, jsonify
from context_builder import build_context

app = Flask(__name__)

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

if __name__ == "__main__":
    app.run(debug=True)