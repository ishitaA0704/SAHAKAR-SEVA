from database import (
    get_user_profile, get_schemes_for_occupation,
    get_jurisdiction, create_guest_profile
)

print("Farmer profile:", get_user_profile(14))
print("Farmer schemes:", get_schemes_for_occupation("Farmer"))
print("Jurisdiction:", get_jurisdiction("Krishnarajpet", "Farmer"))
print("Guest profile:", create_guest_profile("Artisan", "Maddur"))