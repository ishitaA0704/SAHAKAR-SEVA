from pyfingerprint.pyfingerprint import PyFingerprint
import time

def enroll_team_member():
    try:
        # Connect to your specific Windows port
        f = PyFingerprint('COM12', 57600, 0xFFFFFFFF, 0x00000000)
        if not f.verifyPassword():
            raise ValueError('Could not connect to the R307')
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print("--- PACS TEAM ENROLLMENT ---")
    print("Available IDs: Ramesh(14), Suresh(27), Lakshmi(35), Manju(41), Ravi(52), Ganga(63)")
    
    # We ask which specific ID from Ishita's database we are enrolling
    target_id = int(input("Enter the fingerprint_id for the person you are enrolling: "))

    print("\nScan 1: Place finger on sensor...")
    while not f.readImage():
        pass
    f.convertImage(0x01)

    print("Remove finger.")
    time.sleep(1)
    while f.readImage():
        pass

    print("Scan 2: Place the SAME finger on sensor again...")
    while not f.readImage():
        pass
    f.convertImage(0x02)

    if f.compareCharacteristics() == 0:
        print("Error: Scans did not match. Try again.")
        return

    f.createTemplate()
    # Here is the magic: We force the sensor to save it at Ishita's exact ID
    saved_position = f.storeTemplate(target_id)
    print(f"\nSUCCESS! Fingerprint hard-linked to database ID: {saved_position}")

if __name__ == "__main__":
    enroll_team_member()