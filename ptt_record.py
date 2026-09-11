"""
ptt_record.py — Sahakar Seva Terminal — Master PTT Client
==========================================================
Run this alongside app.py (in a second terminal).

Controls
--------
  Hold SPACE  : Record your question in your local language (Kannada/Hindi)
  Release     : Sends to Bhashini ASR -> Flask /ask -> Bhashini TTS (spoken reply)
  ESC         : End the session, fetch summary, speak it aloud
  Ctrl+C      : Quit the program
"""

import sys
import os
import time
import queue

import keyboard
import sounddevice as sd
import soundfile as sf
import numpy as np
import requests

# ── Bhashini import (graceful fallback if missing) ────────────────────────
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bashini"))
try:
    import bhashini_stt_tts
    BHASHINI_OK = True
except Exception as _e:
    print(f"WARNING: Bhashini could not be loaded ({_e}). Transcription disabled.")
    BHASHINI_OK = False

# ── Configuration ─────────────────────────────────────────────────────────
FLASK_URL      = "http://localhost:5000"
FINGERPRINT_ID = 14         # Ramesh (Farmer from Krishnarajpet) — change for each demo
LANGUAGE       = "kn"       # "kn" = Kannada | "hi" = Hindi | "en" = English
SAMPLERATE     = 44100
TMP_WAV        = "temp_ptt_query.wav"


def record_until_released(key="space", samplerate=SAMPLERATE):
    """
    Block until `key` is pressed, then record audio continuously until
    the key is released. Returns the path to the saved WAV, or None if
    nothing was recorded (empty press).
    Also returns False if 'esc' was pressed instead of recording.
    """
    print(f"\n[READY] Hold '{key.upper()}' to speak  |  Press 'ESC' to finish session  |  Ctrl+C to quit")

    # Wait for either the PTT key or ESC
    while True:
        if keyboard.is_pressed('esc'):
            return False          # caller handles finish flow
        if keyboard.is_pressed(key):
            break
        time.sleep(0.02)

    print("● Recording… (release to stop)")
    buf_q = queue.Queue()

    def _cb(indata, frames, t, status):
        if status:
            print(f"  [audio warning] {status}", file=sys.stderr)
        buf_q.put(indata.copy())

    with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", callback=_cb):
        while keyboard.is_pressed(key):
            time.sleep(0.02)

    print("■ Stopped.")
    chunks = []
    while not buf_q.empty():
        chunks.append(buf_q.get())

    if not chunks:
        print("  (empty recording — nothing sent)")
        return None

    audio = np.concatenate(chunks, axis=0)
    sf.write(TMP_WAV, audio, samplerate)
    return TMP_WAV


def transcribe(wav_path):
    """Transcribe a local WAV file to English text via Bhashini."""
    if not BHASHINI_OK:
        return None
    # Bhashini STT requires a non-English source language
    if LANGUAGE == "en":
        print("  [note] Language is English — skipping ASR, prompting user to type instead.")
        return None
    try:
        text = bhashini_stt_tts.speech_to_text(wav_path, LANGUAGE)
        return text.strip() if text else None
    except Exception as e:
        print(f"  [Bhashini STT error] {e}")
        return None


def speak(english_text):
    """Translate english_text to the user's language and play it via Bhashini TTS."""
    if not BHASHINI_OK or not english_text:
        return
    if LANGUAGE == "en":
        # For English just use sounddevice to play if we had a wav;
        # for simplicity just print the text when language is English
        print(f"  [TTS] {english_text}")
        return
    try:
        bhashini_stt_tts.text_to_speech(english_text, LANGUAGE, "ptt_reply.wav", auto_play=True)
    except Exception as e:
        print(f"  [Bhashini TTS error] {e}")
        print(f"  [TTS text] {english_text}")


def ask_flask(english_query):
    """POST the English query text to Flask /ask and return the audio_response."""
    try:
        resp = requests.post(
            f"{FLASK_URL}/ask",
            json={
                "fingerprint_id": FINGERPRINT_ID,
                "language":       LANGUAGE,
                "query":          english_query
            },
            timeout=40
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ok":
            return data.get("audio_response") or data.get("answer", "")
        elif data.get("status") == "not_registered":
            return "This fingerprint is not registered in the database."
        else:
            print(f"  [Flask unexpected response] {data}")
            return None
    except requests.exceptions.ConnectionError:
        print("  [ERROR] Cannot reach Flask — is app.py running?")
        return None
    except Exception as e:
        print(f"  [Flask /ask error] {e}")
        return None


def finish_flask():
    """POST to Flask /finish, get the session summary dict."""
    try:
        resp = requests.post(
            f"{FLASK_URL}/finish",
            json={"fingerprint_id": FINGERPRINT_ID, "language": LANGUAGE},
            timeout=40
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "ok":
            return data.get("summary", {})
        else:
            print(f"  [Flask /finish unexpected] {data}")
            return {}
    except requests.exceptions.ConnectionError:
        print("  [ERROR] Cannot reach Flask — is app.py running?")
        return {}
    except Exception as e:
        print(f"  [Flask /finish error] {e}")
        return {}


def run_session():
    print("=" * 50)
    print("  SAHAKAR SEVA — PTT Client")
    print(f"  Fingerprint ID : {FINGERPRINT_ID}")
    print(f"  Language       : {LANGUAGE}")
    print(f"  Flask URL      : {FLASK_URL}")
    print("=" * 50)

    # Authenticate first so the backend knows which user we are
    try:
        r = requests.post(f"{FLASK_URL}/authenticate",
                          json={"fingerprint_id": FINGERPRINT_ID}, timeout=10)
        info = r.json()
        if info.get("status") == "ok":
            u = info["user"]
            print(f"\n  ✅ Authenticated: {u['name']} ({u['occupation']}, {u['village']})")
        else:
            print(f"\n  ⚠ Not registered (fingerprint_id={FINGERPRINT_ID}). Continuing in demo mode.")
    except Exception:
        print("\n  ⚠ Could not reach Flask for auth check. Continuing anyway.")

    while True:
        wav_or_signal = record_until_released(key="space")

        # ── ESC pressed → finish session ────────────────────────────────
        if wav_or_signal is False:
            print("\n  --- FINISHING SESSION ---")
            summary = finish_flask()
            if summary:
                issue = summary.get("main_issue", "")
                steps = summary.get("recommended_next_steps", "")
                combined = f"{issue}. {steps}".strip(". ")
                print(f"\n  Summary: {combined}")
                speak(combined)
            else:
                print("  (no summary returned)")
            print("\n  Session complete. Resetting for next user…\n")
            time.sleep(1)
            # Reset for the next farmer
            try:
                requests.post(f"{FLASK_URL}/reset",
                              json={"fingerprint_id": FINGERPRINT_ID}, timeout=5)
            except Exception:
                pass
            break   # Exit — operator can restart for the next person

        # ── Nothing recorded (empty press) ──────────────────────────────
        if wav_or_signal is None:
            continue

        # ── Transcribe with Bhashini ────────────────────────────────────
        print("  Transcribing with Bhashini ASR…")
        english_query = transcribe(wav_or_signal)

        if not english_query:
            # If ASR failed or language is 'en', ask the user to rephrase
            print("  ⚠ Could not transcribe audio. Please speak clearly and try again.")
            speak("Sorry, I could not understand. Please try again.")
            continue

        print(f"  [ASR] Understood: '{english_query}'")

        # ── Call Flask /ask ─────────────────────────────────────────────
        print("  Querying backend…")
        answer = ask_flask(english_query)

        if not answer:
            speak("Sorry, I could not get an answer right now. Please try again.")
            continue

        print(f"  [AI ] {answer}")

        # ── Speak the answer back ───────────────────────────────────────
        print("  Speaking response via Bhashini TTS…")
        speak(answer)

        # Clean up temp file
        try:
            os.remove(TMP_WAV)
        except OSError:
            pass


if __name__ == "__main__":
    run_session()
