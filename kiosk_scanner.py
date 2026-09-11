from pyfingerprint.pyfingerprint import PyFingerprint
import database  # This imports Ishita's database.py file!

def run_kiosk():
    try:
        f = PyFingerprint('COM17', 57600, 0xFFFFFFFF, 0x00000000)
        if not f.verifyPassword():
            raise ValueError('Could not connect to the R307')
    except Exception as e:
        print(f"Sensor connection failed: {e}")
        return

    print("--- SAHAKAR SEVA TERMINAL ---")
    print("Please place your finger on the scanner to log in...\n")

    while not f.readImage():
        pass

    f.convertImage(0x01)

    # Search the sensor memory for the finger
    position_number, accuracy_score = f.searchTemplate()

    if position_number == -1:
        print("Fingerprint not recognized. Are you enrolled?")
        return

    print(f"Finger recognized! (Sensor ID: {position_number})")
    
    # We pass the sensor's position_number directly into Ishita's database function
    user_profile = database.get_user_profile(position_number)

    if user_profile:
        print("\n--- USER PROFILE FOUND ---")
        print(f"Name:       {user_profile['name']}")
        print(f"Occupation: {user_profile['occupation']}")
        print(f"Village:    {user_profile['village']}")
        print(f"Land:       {user_profile['land_acres']} acres")
        
        # We can also pull schemes for them automatically!
        print("\n--- ELIGIBLE SCHEMES ---")
        schemes = database.get_schemes_for_occupation(user_profile['occupation'])
        for scheme in schemes:
            print(f"- {scheme['name']}: {scheme['description']}")
    else:
        print(f"\nError: Fingerprint {position_number} exists in sensor, but has no matching profile in the database!")

if __name__ == "__main__":
    run_kiosk()