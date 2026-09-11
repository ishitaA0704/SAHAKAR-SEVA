import os
import sys
import json
import base64
import tempfile

# All imports at the top, before anything else
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from context_builder import build_context
from rag_engine import get_ai_answer, get_session_summary
from thermal_printer import generate_and_print_receipt
from hardware_listener import HardwareListener

# Bhashini — imported here but used inside try/except so server still starts
# even if the Bhashini module has dependency issues
sys.path.append(os.path.join(os.path.dirname(__file__), "bashini"))
try:
    import bhashini_stt_tts
    BHASHINI_AVAILABLE = True
except Exception as _e:
    print(f"WARNING: Bhashini module could not be loaded ({_e}). TTS/STT disabled.")
    BHASHINI_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sahakar-seva-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

conversations = {}  # {fingerprint_id: [{"query": ..., "answer": ...}, ...]}
GEMINI_KEY = "AQ.Ab8RN6Kfuq0t8r8pv2uVLFfyA2h0HlSfx3QC9U_tZR1DZcHPDQ"

# Initialize and start hardware listener daemon
hw_listener = HardwareListener(socketio)
hw_listener.start()


def clean_json_response(raw_text):
    """Strip markdown code fences from Gemini responses."""
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content inside the fences
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ─────────────────────────── ROUTES ────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/authenticate", methods=["POST"])
def authenticate():
    fingerprint_id = int(request.json.get("fingerprint_id", 14))
    context = build_context(fingerprint_id, document_text="", query_text="")
    if context is None:
        return jsonify({"status": "not_registered"})
    return jsonify({"status": "ok", "user": context["user"]})


@app.route("/ask", methods=["POST"])
def ask():
    """
    Accepts a text query from BOTH:
      - the browser UI (uses data.answer / data.next_steps / data.reference)
      - the Python PTT client (uses data.audio_response)
    We return ALL keys so either consumer works.
    """
    data = request.json
    fingerprint_id = int(data.get("fingerprint_id", 14))
    query_text = data.get("query", "")
    language = data.get("language", "en")
    image_base64 = data.get("image_data", "")

    context = build_context(fingerprint_id, "", "")
    if context is None:
        return jsonify({"status": "not_registered"})

    raw_answer = get_ai_answer(
        context, GEMINI_KEY,
        language=language,
        query_text=query_text,
        image_b64=image_base64
    )

    try:
        parsed = json.loads(clean_json_response(raw_answer))
    except json.JSONDecodeError:
        parsed = {
            "audio_response": raw_answer,
            "printed_receipt": {"reference": "Parse Error"}
        }

    # Normalise: browser expects "answer"/"next_steps"/"reference",
    # PTT client expects "audio_response". Surface both.
    audio_resp = parsed.get("audio_response", "")
    receipt = parsed.get("printed_receipt", {})

    conversations.setdefault(fingerprint_id, []).append({
        "query": query_text,
        "answer": audio_resp
    })

    # Print receipt if there is one
    if receipt:
        try:
            generate_and_print_receipt(receipt, context["user"])
        except Exception as e:
            print(f"Thermal printer error: {e}")

    return jsonify({
        "status": "ok",
        # Keys for the browser UI
        "answer": audio_resp,
        "next_steps": receipt.get("amounts", ""),
        "reference": receipt.get("reference", ""),
        # Keys for the PTT client
        "audio_response": audio_resp,
        "printed_receipt": receipt,
    })


@app.route("/process_interaction", methods=["POST"])
def process_interaction():
    """
    Used by the browser's Push-To-Talk (Spacebar) flow.
    Receives base64 WAV + base64 JPEG, runs Bhashini STT, then calls /ask logic.
    """
    data = request.json
    fingerprint_id = int(data.get("fingerprint_id", 14))
    language = data.get("language", "en")
    audio_base64 = data.get("audio_data", "")
    image_base64 = data.get("image_data", "")

    context = build_context(fingerprint_id, "", "")
    if context is None:
        return jsonify({"status": "not_registered"})

    query_text = "What can you help me with today?"  # safe default
    if audio_base64 and BHASHINI_AVAILABLE:
        if ',' in audio_base64:
            audio_base64 = audio_base64.split(',')[1]
        tmp_wav = tempfile.mktemp(suffix=".wav")
        try:
            with open(tmp_wav, "wb") as f:
                f.write(base64.b64decode(audio_base64))
            query_text = bhashini_stt_tts.speech_to_text(tmp_wav, language)
        except Exception as e:
            print("Bhashini ASR Error:", e)
        finally:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

    raw_answer = get_ai_answer(
        context, GEMINI_KEY,
        language=language,
        query_text=query_text,
        image_b64=image_base64
    )

    try:
        parsed = json.loads(clean_json_response(raw_answer))
    except json.JSONDecodeError:
        parsed = {
            "audio_response": raw_answer,
            "printed_receipt": {"reference": "Parse Error"}
        }

    audio_resp = parsed.get("audio_response", "")
    receipt = parsed.get("printed_receipt", {})

    conversations.setdefault(fingerprint_id, []).append({
        "query": query_text,
        "answer": audio_resp
    })

    if receipt:
        try:
            generate_and_print_receipt(receipt, context["user"])
        except Exception as e:
            print(f"Thermal printer error: {e}")

    # Generate TTS via Bhashini and send back as base64 audio
    tts_b64 = ""
    if audio_resp and BHASHINI_AVAILABLE and language != "en":
        try:
            out_wav = tempfile.mktemp(suffix=".wav")
            bhashini_stt_tts.text_to_speech(
                audio_resp, language, out_path=out_wav, auto_play=False
            )
            with open(out_wav, "rb") as f:
                tts_b64 = "data:audio/wav;base64," + base64.b64encode(f.read()).decode("utf-8")
            os.remove(out_wav)
        except Exception as e:
            print("Bhashini TTS Error:", e)

    return jsonify({
        "status": "ok",
        "audio_response": audio_resp,
        "tts_text": audio_resp,        # fallback for browser speechSynthesis
        "tts_audio_url": tts_b64       # real Bhashini audio when available
    })


@app.route("/hardware_audio_upload", methods=["POST"])
def hardware_audio_upload():
    """
    Endpoint for external hardware (like a physical push button script) to upload a recorded WAV file.
    It processes it with Bhashini/Gemini and pushes the updates live to the browser UI via WebSocket.
    """
    print("\n[FLASK] >>> Received audio upload from hardware script!", flush=True)
    if 'audio' not in request.files:
        return jsonify({"status": "error", "message": "No audio file provided"})

    audio_file = request.files['audio']
    language = request.form.get("language", "kn")

    # Automatically fetch the user ID that was authenticated by the fingerprint scanner!
    fingerprint_id = getattr(hw_listener, 'current_user_id', 14)

    context = build_context(fingerprint_id, "", "")
    if context is None:
        return jsonify({"status": "not_registered"})

    # 1. Save uploaded file temporarily
    tmp_wav = tempfile.mktemp(suffix=".wav")
    audio_file.save(tmp_wav)

    # 2. Transcribe
    query_text = "What can you help me with today?"
    if BHASHINI_AVAILABLE:
        try:
            query_text = bhashini_stt_tts.speech_to_text(tmp_wav, language)
        except Exception as e:
            print("Bhashini ASR Error:", e)

    # Tell the UI that a hardware query has started
    socketio.emit('hardware_interaction_start', {'query': query_text})

    # 3. Gemini RAG
    raw_answer = get_ai_answer(
        context, GEMINI_KEY,
        language=language,
        query_text=query_text,
        image_b64=""
    )

    try:
        parsed = json.loads(clean_json_response(raw_answer))
    except json.JSONDecodeError:
        parsed = {"audio_response": raw_answer, "printed_receipt": {"reference": "Parse Error"}}

    audio_resp = parsed.get("audio_response", "")
    receipt = parsed.get("printed_receipt", {})

    conversations.setdefault(fingerprint_id, []).append({
        "query": query_text,
        "answer": audio_resp
    })

    if receipt:
        try:
            generate_and_print_receipt(receipt, context["user"])
        except Exception as e:
            print(f"Thermal printer error: {e}")

    # 4. Generate TTS
    tts_b64 = ""
    if audio_resp and BHASHINI_AVAILABLE and language != "en":
        try:
            out_wav = tempfile.mktemp(suffix=".wav")
            bhashini_stt_tts.text_to_speech(audio_resp, language, out_path=out_wav, auto_play=False)
            with open(out_wav, "rb") as f:
                tts_b64 = "data:audio/wav;base64," + base64.b64encode(f.read()).decode("utf-8")
            os.remove(out_wav)
        except Exception as e:
            print("Bhashini TTS Error:", e)

    try:
        os.remove(tmp_wav)
    except OSError:
        pass

    # Tell the UI the answer is ready so it plays the audio and updates chat
    socketio.emit('hardware_interaction_complete', {
        'answer': audio_resp,
        'next_steps': receipt.get("amounts", ""),
        'reference': receipt.get("reference", ""),
        'tts_audio_url': tts_b64,
        'tts_text': audio_resp,
        'language': language
    })

    return jsonify({"status": "ok"})


@app.route("/reset", methods=["POST"])
def reset():
    data = request.json
    fingerprint_id = int(data.get("fingerprint_id", 0))
    conversations.pop(fingerprint_id, None)
    return jsonify({"status": "reset_ok"})


@app.route("/finish", methods=["POST"])
def finish():
    data = request.json
    fingerprint_id = int(data.get("fingerprint_id", 14))
    language = data.get("language", "en")

    context = build_context(fingerprint_id, document_text="", query_text="")
    if context is None:
        return jsonify({"status": "not_registered"})

    history = conversations.get(fingerprint_id, [])
    raw_summary = get_session_summary(context, history, GEMINI_KEY, language=language)

    try:
        parsed_summary = json.loads(clean_json_response(raw_summary))
    except json.JSONDecodeError:
        parsed_summary = {"main_issue": raw_summary}

    conversations.pop(fingerprint_id, None)
    return jsonify({"status": "ok", "summary": parsed_summary})


if __name__ == "__main__":
    import subprocess
    import os

    # Automatically launch the hardware button script in a NEW visible terminal window
    # so that keyboard hooks work and the user can see the recording status.
    print("\n[STARTUP] Launching external hardware button client in a new window...\n")
    if os.name == 'nt':
        subprocess.Popen('start "Sahakar Seva Hardware Client" cmd /k "python external_push_button.py"', shell=True)
    
    try:
        socketio.run(app, debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
    finally:
        hw_listener.stop()