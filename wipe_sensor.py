from pyfingerprint.pyfingerprint import PyFingerprint

try:
    f = PyFingerprint('COM12', 57600, 0xFFFFFFFF, 0x00000000)
    if f.verifyPassword():
        print(f"Templates before wipe: {f.getTemplateCount()}")
        f.clearDatabase()  # This deletes all fingerprints from the hardware
        print(f"Templates after wipe: {f.getTemplateCount()}")
        print("Sensor memory is now completely blank!")
    else:
        print("Could not connect.")
except Exception as e:
    print(f"Error: {e}")