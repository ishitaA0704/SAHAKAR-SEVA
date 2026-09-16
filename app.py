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


session_states = {}  # {fingerprint_id: "chatting" | "waiting_for_print"}

@app.route("/hardware_finish_session", methods=["POST"])
def hardware_finish_session():
    """Triggered by ESC key on the hardware client."""
    fingerprint_id = getattr(hw_listener, 'current_user_id', 14)
    language = request.form.get("language", "en")
    context = build_context(fingerprint_id, "", "")
    
    if fingerprint_id not in conversations or not conversations[fingerprint_id]:
        return jsonify({"status": "no_chat"})
        
    # Get the summary using the existing RAG function
    summary_json = get_session_summary(context, conversations[fingerprint_id], GEMINI_KEY, language)
    try:
        summary_data = json.loads(clean_json_response(summary_json))
    except json.JSONDecodeError:
        summary_data = {"main_issue": "Summary generation failed."}
        
    session_states[fingerprint_id] = "waiting_for_print"
    
    # Generate TTS for the question
    tts_b64 = ""
    issue = summary_data.get("main_issue", "")
    next_steps = summary_data.get("recommended_next_steps", "")
    
    prompt_text = f"Summary: {issue} Next steps: {next_steps} Would you like a print out of this? Say yes or no."
    if language == "hi":
        prompt_text = f"सारांश: {issue} अगला कदम: {next_steps} क्या आपको इसका प्रिंट आउट चाहिए? हाँ या ना कहें।"
    elif language == "kn":
        prompt_text = f"ಸಾರಾಂಶ: {issue} ಮುಂದಿನ ಹಂತಗಳು: {next_steps} ನಿಮಗೆ ಇದರ ಪ್ರಿಂಟ್ ಔಟ್ ಬೇಕೇ? ಹೌದು ಅಥವಾ ಇಲ್ಲ ಎಂದು ಹೇಳಿ."
        
    if BHASHINI_AVAILABLE:
        try:
            out_wav = tempfile.mktemp(suffix=".wav")
            tts_b64 = bhashini_stt_tts.text_to_speech(prompt_text, language, out_path=out_wav, auto_play=False, is_translated=True)
            if os.path.exists(out_wav): os.remove(out_wav)
        except Exception:
            pass

    socketio.emit('hardware_show_summary', {
        'summary': summary_data,
        'tts_audio_url': tts_b64
    })
    
    return jsonify({"status": "summary_sent"})


@app.route("/hardware_event", methods=["POST"])
def hardware_event():
    """Endpoint for hardware to report real-time events (recording status, language changes)."""
    data = request.json
    if not data:
        return jsonify({"status": "error"}), 400
        
    event_type = data.get("event")
    
    if event_type == "language_change":
        socketio.emit("language_changed", {"language": data.get("language")})
    elif event_type == "recording_started":
        socketio.emit("recording_status", {"status": "started"})
    elif event_type == "recording_stopped":
        socketio.emit("recording_status", {"status": "stopped"})
        
    return jsonify({"status": "ok"})


@app.route("/hardware_audio_upload", methods=["POST"])
def hardware_audio_upload():
    print("\n[FLASK] >>> Received audio upload from hardware script!", flush=True)
    if 'audio' not in request.files:
        return jsonify({"status": "error", "message": "No audio file provided"})

    audio_file = request.files['audio']
    language = request.form.get("language", "kn")
    fingerprint_id = getattr(hw_listener, 'current_user_id', 14)

    context = build_context(fingerprint_id, "", "")
    if context is None:
        return jsonify({"status": "not_registered"})

    tmp_wav = tempfile.mktemp(suffix=".wav")
    audio_file.save(tmp_wav)

    query_text = "(Audio unintelligible)"
    if BHASHINI_AVAILABLE:
        try:
            recognized_text = bhashini_stt_tts.speech_to_text(tmp_wav, language)
            if recognized_text and recognized_text.strip():
                query_text = recognized_text.lower()
        except Exception as e:
            print("Bhashini ASR Error:", e)
        finally:
            try:
                if os.path.exists(tmp_wav): os.remove(tmp_wav)
            except Exception: pass

    # If we are waiting for a yes/no to print the summary
    state = session_states.get(fingerprint_id, "chatting")
    if state == "waiting_for_print":
        socketio.emit('hardware_interaction_start', {'query': query_text})
        
        is_yes = any(word in query_text for word in ["yes", "yeah", "print", "ok", "haan", "ha", "howdu", "sari", "sure"])
        
        if is_yes:
            reply_text = "Successfully printed. Goodbye!"
            if language == "hi": reply_text = "सफलतापूर्वक प्रिंट हो गया। अलविदा!"
            elif language == "kn": reply_text = "ಯಶಸ್ವಿಯಾಗಿ ಮುದ್ರಿಸಲಾಗಿದೆ. ವಿದಾಯ!"
        else:
            reply_text = "Okay, no print out. Goodbye!"
            if language == "hi": reply_text = "ठीक है, कोई प्रिंट नहीं। अलविदा!"
            elif language == "kn": reply_text = "ಸರಿ, ಪ್ರಿಂಟ್ ಇಲ್ಲ. ವಿದಾಯ!"
            
        tts_b64 = ""
        if BHASHINI_AVAILABLE:
            try:
                out_wav = tempfile.mktemp(suffix=".wav")
                tts_b64 = bhashini_stt_tts.text_to_speech(reply_text, language, out_path=out_wav, auto_play=False, is_translated=True)
                if os.path.exists(out_wav): os.remove(out_wav)
            except Exception: pass
            
        # Send the final response
        socketio.emit('hardware_interaction_complete', {
            'answer': reply_text,
            'tts_audio_url': tts_b64,
            'is_final': True,
            'printed': is_yes
        })
        
        # Reset session
        conversations[fingerprint_id] = []
        session_states[fingerprint_id] = "chatting"
        return jsonify({"status": "session_ended"})

    # ---------------- NORMAL CHAT FLOW ----------------
    socketio.emit('hardware_interaction_start', {'query': query_text})

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
    if audio_resp and BHASHINI_AVAILABLE:
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
        try:
            subprocess.Popen('start "Sahakar Seva Hardware Client" cmd /k "python external_push_button.py"', shell=True)
        except Exception as e:
            print(f"Could not launch hardware button script: {e}")

    import webbrowser
    import threading
    
    def open_browser():
        try:
            webbrowser.get('windows-default').open("http://127.0.0.1:5000")
        except:
            webbrowser.open("http://127.0.0.1:5000")
            
    threading.Timer(1.5, open_browser).start()

    print("[*] Starting Flask-SocketIO server on http://127.0.0.1:5000")
    try:
        socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    finally:
        hw_listener.stop()