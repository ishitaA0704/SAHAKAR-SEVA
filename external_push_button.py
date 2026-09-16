"""
external_push_button.py

This script controls a physical push button (e.g., connected via GPIO on a Raspberry Pi, 
or emulated via a keyboard key on Windows) and records audio locally using `sounddevice`.

When the button is released, it saves a .wav file and sends it to the Sahakar Seva 
Flask backend (`/hardware_audio_upload`). The website UI will automatically update 
in real-time to show the transcribed query and play the AI's audio response.

Usage:
  Run this script in a separate terminal while `app.py` is running.
  Hold the 'SPACE' key (acting as the push button) to record.
  Release to send to the kiosk UI.
"""

import os
import sys
import time
import queue
import requests
import numpy as np
import sounddevice as sd
import soundfile as sf
import keyboard  # Using keyboard to simulate a physical push button on Windows

# --- Configuration ---
FLASK_URL = "http://127.0.0.1:5000/hardware_audio_upload"
TMP_WAV_FILE = "hardware_recording.wav"
SAMPLE_RATE = 16000
PHYSICAL_BUTTON_KEY = 'space'  # Emulating the physical button via USB encoder

# Default session context (in a real scenario, the R307 scanner daemon 
# in app.py handles the active user, but we pass a fallback ID here)
ACTIVE_FINGERPRINT_ID = 14  
LANGUAGE = "en"  


def send_audio_to_kiosk(wav_path):
    """POST the recorded WAV file to the running Flask kiosk."""
    print(f"\n[➡] Sending {wav_path} to kiosk backend...")
    try:
        with open(wav_path, "rb") as f:
            files = {"audio": f}
            data = {
                "fingerprint_id": ACTIVE_FINGERPRINT_ID,
                "language": LANGUAGE
            }
            resp = requests.post(FLASK_URL, files=files, data=data, timeout=30)
            
        if resp.status_code == 200:
            print("[✅] Success! The website UI should now be updating.")
        else:
            print(f"[❌] Error from server: {resp.status_code} - {resp.text}")
    except requests.exceptions.ConnectionError:
        print("[❌] Connection Error: Is app.py running?")
    except Exception as e:
        print(f"[❌] Unexpected error: {e}")

def send_event(event_type, **kwargs):
    """Fire-and-forget event notification to the UI."""
    import threading
    def _send():
        try:
            data = {"event": event_type}
            data.update(kwargs)
            event_url = FLASK_URL.replace("/hardware_audio_upload", "/hardware_event")
            requests.post(event_url, json=data, timeout=2)
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

def wait_for_button_and_record():
    """Blocks until the physical button is pressed, records audio, and saves to WAV."""
    try:
        import sounddevice as sd
        default_idx = sd.default.device[0]
        device_info = sd.query_devices(default_idx, 'input')
        NATIVE_SAMPLERATE = int(device_info['default_samplerate'])
        NATIVE_CHANNELS = min(2, device_info['max_input_channels'])
        print(f"[🎤] Default Microphone: {device_info['name']} ({NATIVE_SAMPLERATE}Hz, {NATIVE_CHANNELS}ch)")
    except Exception as e:
        print(f"[🎤] Default Microphone: Unknown (Error: {e})")
        NATIVE_SAMPLERATE = 44100
        NATIVE_CHANNELS = 1
        default_idx = None
        
    print(f"=======================================================")
    print(f"Hardware Button Client Active")
    print(f"-> Hold the 'SPACE' key (ESP32) to record, release to stop.")
    print(f"-> OR press 'ENTER' here to do a standard 5-second recording.")
    print(f"-> Press 'ESC' to quit this script.")
    print(f"=======================================================\n")

    # State variable for language
    global LANGUAGE
    
    # Wait for keys to be released before listening for a new press
    while keyboard.is_pressed('enter') or keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
        time.sleep(0.1)

    mode = None
    while True:
        if keyboard.is_pressed('esc'):
            print("\n[🏁] ESC pressed. Ending session and fetching summary...")
            try:
                requests.post(FLASK_URL.replace("/hardware_audio_upload", "/hardware_finish_session"), data={"language": LANGUAGE}, timeout=60)
                print("[✅] Sent finish signal to server.")
            except Exception as e:
                print(f"[❌] Could not finish session: {e}")
            time.sleep(2) # Prevent rapid firing
            continue
        # Language Toggles
        if keyboard.is_pressed('e'):
            if LANGUAGE != "en":
                LANGUAGE = "en"
                print("\n[🌐] Language switched to: ENGLISH (en)")
                send_event("language_change", language="en")
            time.sleep(0.2)
            
        if keyboard.is_pressed('h'):
            if LANGUAGE != "hi":
                LANGUAGE = "hi"
                print("\n[🌐] Language switched to: HINDI (hi)")
                send_event("language_change", language="hi")
            time.sleep(0.2)
            
        if keyboard.is_pressed('k'):
            if LANGUAGE != "kn":
                LANGUAGE = "kn"
                print("\n[🌐] Language switched to: KANNADA (kn)")
                send_event("language_change", language="kn")
            time.sleep(0.2)
            
        if keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
            mode = "hold"
            break
            
        if keyboard.is_pressed('enter'):
            mode = "5sec"
            break
            
        time.sleep(0.05)

    print("\n● Recording started... (Speak now)")
    send_event("recording_started")
    audio_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            pass
        audio_queue.put(indata.copy())

    # Start recording using the default microphone's NATIVE settings
    with sd.InputStream(device=default_idx, samplerate=NATIVE_SAMPLERATE, channels=NATIVE_CHANNELS, dtype="float32", callback=callback):
        if mode == "hold":
            while keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
                time.sleep(0.05)
            print("■ Button released. Recording stopped.")
            send_event("recording_stopped")
        elif mode == "5sec":
            time.sleep(5.0)
            print("■ 5 seconds elapsed. Recording stopped.")
            send_event("recording_stopped")

    # Drain the queue into a list
    chunks = []
    while not audio_queue.empty():
        chunks.append(audio_queue.get())

    if not chunks:
        print("[⚠] No audio recorded. Try holding the button longer.")
        return None

    # Concatenate audio chunks
    audio_data = np.concatenate(chunks, axis=0)
    
    # 1. Mixdown to Mono
    if NATIVE_CHANNELS > 1:
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

    # 2. Resample exactly to 16000 Hz (Strict Bhashini Requirement)
    TARGET_SR = 16000
    if NATIVE_SAMPLERATE != TARGET_SR:
        try:
            import scipy.signal
            num_samples = int(len(audio_data) * float(TARGET_SR) / NATIVE_SAMPLERATE)
            audio_data = scipy.signal.resample(audio_data, num_samples)
        except ImportError:
            pass

    # 3. Convert to 16-bit PCM
    audio_data_int16 = np.int16(np.clip(audio_data, -1.0, 1.0) * 32767)
    
    # 4. Save the pristine 16000Hz WAV file
    sf.write(TMP_WAV_FILE, audio_data_int16, TARGET_SR, subtype='PCM_16')
    print(f"[💾] Saved local recording to {TMP_WAV_FILE}")
            
    return TMP_WAV_FILE

if __name__ == "__main__":
    # Ensure dependencies are installed
    try:
        import sounddevice
        import soundfile
        import keyboard
        import requests
    except ImportError:
        print("Missing dependencies. Please run:")
        print("pip install sounddevice soundfile keyboard requests numpy")
        sys.exit(1)

    try:
        # Prevent these keys from typing into the browser UI!
        keyboard.block_key('space')
        keyboard.block_key('e')
        keyboard.block_key('h')
        keyboard.block_key('k')
        keyboard.block_key('esc')
        keyboard.block_key('enter')
        
        while True:
            # 1. Wait for physical button press and record
            wav_path = wait_for_button_and_record()
            
            # 2. If recording was successful, send it to the website
            if wav_path:
                send_audio_to_kiosk(wav_path)
                
                # Delete the local file after upload as requested
                try:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                        print(f"[🗑] Deleted local file: {wav_path}")
                except Exception as e:
                    print(f"Could not delete local file: {e}")
                    
            time.sleep(1) # Small debounce delay before next press
            
    except KeyboardInterrupt:
        print("\nHardware script stopped by user.")
