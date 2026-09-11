import time
import threading
from pyfingerprint.pyfingerprint import PyFingerprint
import database

class HardwareListener:
    def __init__(self, socketio):
        self.socketio = socketio
        self.running = False
        self.thread = None
        self.strikes = 0
        self.current_user_id = 14 # Default fallback to Ramesh if no scan happens
        try:
            # Connect to R307 scanner
            self.f = PyFingerprint('COM17', 57600, 0xFFFFFFFF, 0x00000000)
            if not self.f.verifyPassword():
                print("HardwareListener: Could not connect to R307 password.")
                self.f = None
        except Exception as e:
            print(f"HardwareListener: Scanner connection failed: {e}")
            self.f = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._poll_scanner, daemon=True)
        self.thread.start()
        print("HardwareListener: Background polling started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _poll_scanner(self):
        while self.running:
            if self.f is None:
                time.sleep(2)
                continue

            # Check if finger is pressed
            if not self.f.readImage():
                time.sleep(0.1)
                continue

            try:
                self.f.convertImage(0x01)
                position_number, accuracy_score = self.f.searchTemplate()
            except Exception as e:
                print(f"HardwareListener: Search error ({e}). Treating as unrecognized.")
                position_number = -1

            if position_number == -1:
                print("HardwareListener: Fingerprint not recognized.")
                self.strikes += 1
                if self.strikes >= 3:
                    print("HardwareListener: 3 strikes reached. Falling back to Guest Mode.")
                    self.strikes = 0
                    self.current_user_id = 9999999
                    self.socketio.emit('guest_fallback', {'message': 'Please state your name or ID.'})
                    time.sleep(3) # Debounce
                else:
                    time.sleep(1) # Wait before next attempt
                continue

            # Finger recognized
            self.strikes = 0
            user_profile = database.get_user_profile(position_number)
            
            if user_profile:
                print(f"HardwareListener: Authenticated {user_profile['name']} (ID: {position_number})", flush=True)
                self.current_user_id = position_number
                # Emit over websockets with explicit namespace and broadcast
                self.socketio.emit('user_authenticated', {
                    'fingerprint_id': position_number,
                    'user': user_profile
                }, namespace='/')
            else:
                print(f"HardwareListener: ID {position_number} found in sensor but not in DB.", flush=True)
            
            # Wait until finger is removed to prevent multiple triggers
            while self.f.readImage():
                time.sleep(0.5)
            time.sleep(1) # Debounce
