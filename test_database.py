from database import get_user_profile, get_scheme_info, get_user_transactions

print("User Profile:", get_user_profile(14))
print("Scheme Info:", get_scheme_info("PM-KISAN"))
print("User Transactions:", get_user_transactions(14))