"""
offline_stt_tts.py
==================
Fully offline Speech-to-Text and Text-to-Speech fallback for Sahakar Seva.

Used automatically when Bhashini's cloud API is unreachable (no internet,
API outage, or rate-limiting).

  STT: faster-whisper  — runs the OpenAI Whisper "base" model locally on CPU.
                          Supports Kannada ("kn"), Hindi ("hi"), and English ("en")
                          with no internet after the one-time model download (~150 MB).

  TTS: pyttsx3          — wraps Windows built-in SAPI5 voices (zero install, zero internet).
                          Uses the installed Kannada / Hindi voice if present,
                          otherwise falls back to the English voice so the user
                          at least hears something.

Install (one-time):
    pip install faster-whisper pyttsx3
    # ffmpeg must be on PATH (required by faster-whisper for audio decoding)
    # On Windows: winget install Gyan.FFmpeg  OR  choco install ffmpeg

Supported language codes:
    "kn" — Kannada
    "hi" — Hindi
    "en" — English
"""

import os

# ── faster-whisper (STT) ─────────────────────────────────────────────────────
_whisper_model = None          # lazy-loaded on first STT call
WHISPER_MODEL_SIZE = "base"    # "tiny" (~75 MB, ~3 s) | "base" (~150 MB, ~5 s)

# Bhashini → Whisper language code map
_LANG_MAP = {
    "kn": "kn",   # Kannada
    "hi": "hi",   # Hindi
    "en": "en",   # English
}

# ── pyttsx3 (TTS) ────────────────────────────────────────────────────────────
# Windows SAPI5 voice name substrings to try per language (case-insensitive)
_VOICE_HINTS = {
    "kn": ["kannada", "heera"],           # e.g. "Microsoft Heera - Kannada (India)"
    "hi": ["hindi", "kalpana", "hemant"], # e.g. "Microsoft Kalpana - Hindi (India)"
    "en": ["english", "zira", "david"],   # default English voices
}


def _load_whisper():
    """Lazy-load faster-whisper model (downloads once, cached locally)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            print(f"[offline_stt] Loading Whisper '{WHISPER_MODEL_SIZE}' model (CPU)…")
            # compute_type="int8" is fastest on CPU without GPU
            _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
            print("[offline_stt] Whisper model loaded.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            )
    return _whisper_model


def offline_speech_to_text(wav_path: str, source_lang: str) -> str:
    """
    Transcribe a WAV file to text using local Whisper model.

    Args:
        wav_path:    Path to the .wav recording.
        source_lang: Language code ("kn", "hi", "en").

    Returns:
        Transcribed text string.  Returns "" on failure.
    """
    whisper_lang = _LANG_MAP.get(source_lang, None)  # None = auto-detect

    try:
        model = _load_whisper()
        segments, info = model.transcribe(
            wav_path,
            language=whisper_lang,
            beam_size=3,           # balance speed vs accuracy on CPU
            vad_filter=True,       # skip silence (Voice Activity Detection)
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(seg.text for seg in segments).strip()
        print(f"[offline_stt] Transcribed ({info.language}): {text!r}")
        return text
    except Exception as e:
        print(f"[offline_stt] Whisper transcription failed: {e}")
        return ""


def offline_text_to_speech(text: str, target_lang: str, out_path: str) -> bool:
    """
    Convert text to speech using Windows SAPI5 (pyttsx3).
    Saves audio to out_path as WAV.

    Args:
        text:        Text to speak.
        target_lang: Language code ("kn", "hi", "en").
        out_path:    Output .wav file path.

    Returns:
        True on success, False on failure.
    """
    if not text or not text.strip():
        print("[offline_tts] Empty text provided, skipping TTS.")
        return False

    try:
        import pyttsx3
    except ImportError:
        print("[offline_tts] pyttsx3 not installed. Run: pip install pyttsx3")
        return False

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")

        # Try to find a matching voice for the target language
        selected_voice = None
        hints = _VOICE_HINTS.get(target_lang, []) + _VOICE_HINTS["en"]
        for hint in hints:
            for voice in voices:
                if hint.lower() in voice.name.lower():
                    selected_voice = voice
                    break
            if selected_voice:
                break

        if selected_voice:
            print(f"[offline_tts] Using voice: {selected_voice.name}")
            engine.setProperty("voice", selected_voice.id)
        else:
            print("[offline_tts] No matching voice found, using system default.")

        # Speak at a slightly slower rate for rural kiosk clarity
        engine.setProperty("rate", 150)   # default ~200, slower = clearer
        engine.setProperty("volume", 1.0)

        engine.save_to_file(text, out_path)
        engine.runAndWait()

        # Verify file was actually created
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[offline_tts] Saved to {out_path}")
            return True
        else:
            print("[offline_tts] pyttsx3 produced no output file.")
            return False

    except Exception as e:
        print(f"[offline_tts] pyttsx3 TTS failed: {e}")
        return False
