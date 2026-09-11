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
SAMPLE_RATE = 44100
PHYSICAL_BUTTON_KEY = 'space'  # Emulating the physical button via USB encoder

# Default session context (in a real scenario, the R307 scanner daemon 
# in app.py handles the active user, but we pass a fallback ID here)
ACTIVE_FINGERPRINT_ID = 14  
LANGUAGE = "kn"  


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


def wait_for_button_and_record():
    """Blocks until the physical button is pressed, records audio, and saves to WAV."""
    print(f"\n=======================================================")
    print(f"Hardware Button Client Active")
    print(f"-> Hold the 'SPACE' key (ESP32) to record, release to stop.")
    print(f"-> OR press 'ENTER' here to do a standard 5-second recording.")
    print(f"-> Press 'ESC' to quit this script.")
    print(f"=======================================================\n")

    # Wait for keys to be released before listening for a new press
    while keyboard.is_pressed('enter') or keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
        time.sleep(0.1)

    mode = None
    while True:
        if keyboard.is_pressed('esc'):
            print("Exiting hardware script.")
            sys.exit(0)
            
        if keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
            mode = "hold"
            break
            
        if keyboard.is_pressed('enter'):
            mode = "5sec"
            break
            
        time.sleep(0.05)

    print("\n● Recording started... (Speak now)")
    audio_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            pass
        audio_queue.put(indata.copy())

    # Start recording
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback):
        if mode == "hold":
            while keyboard.is_pressed(PHYSICAL_BUTTON_KEY):
                time.sleep(0.05)
            print("■ Button released. Recording stopped.")
        elif mode == "5sec":
            time.sleep(5.0)
            print("■ 5 seconds elapsed. Recording stopped.")

    # Drain the queue into a list
    chunks = []
    while not audio_queue.empty():
        chunks.append(audio_queue.get())

    if not chunks:
        print("[⚠] No audio recorded. Try holding the button longer.")
        return None

    # Concatenate and save to WAV
    audio_data = np.concatenate(chunks, axis=0)
    sf.write(TMP_WAV_FILE, audio_data, SAMPLE_RATE)
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
        while True:
            # 1. Wait for physical button press and record
            wav_path = wait_for_button_and_record()
            
            # 2. If recording was successful, send it to the website
            if wav_path:
                send_audio_to_kiosk(wav_path)
                
            time.sleep(1) # Small debounce delay before next press
            
    except KeyboardInterrupt:
        print("\nHardware script stopped by user.")
