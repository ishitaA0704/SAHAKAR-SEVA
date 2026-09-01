import sqlite3

connection = sqlite3.connect("pacs_local.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    land_acres REAL,
    crop TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    eligibility TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_id INTEGER NOT NULL,
    scheme_name TEXT NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(fingerprint_id, scheme_name)
)
""")

users = [
    (14, "Ramesh", 2.5, "Paddy"),
    (27, "Suresh", 4.0, "Ragi"),
    (35, "Lakshmi", 1.8, "Maize")
]

schemes = [
    ("PM-KISAN", "Income support for eligible farmers", "Small and marginal farmers"),
    ("Crop Insurance", "Insurance coverage for crop losses", "Farmers with eligible crops"),
    ("Kisan Credit Card", "Credit support for agricultural needs", "Eligible farmers")
]

transactions = [
    (14, "PM-KISAN", "Approved"),
    (27, "Crop Insurance", "Pending"),
    (35, "Kisan Credit Card", "Rejected")
]

cursor.executemany("""
INSERT OR IGNORE INTO Users
(fingerprint_id, name, land_acres, crop)
VALUES (?, ?, ?, ?)
""", users)

cursor.executemany("""
INSERT OR IGNORE INTO Schemes
(name, description, eligibility)
VALUES (?, ?, ?)
""", schemes)

cursor.executemany("""
INSERT OR IGNORE INTO Transactions
(fingerprint_id, scheme_name, status)
VALUES (?, ?, ?)
""", transactions)

connection.commit()

def get_user_profile(fingerprint_id):
    cursor.execute("""
        SELECT name, land_acres, crop
        FROM Users
        WHERE fingerprint_id = ?
    """, (fingerprint_id,))
    user = cursor.fetchone()
    if user is None:
        return None
    return {
        "name": user[0],
        "land_acres": user[1],
        "crop": user[2]
    }

def get_scheme_info(scheme_name):
    cursor.execute("""
        SELECT name, description, eligibility
        FROM Schemes
        WHERE name = ?
    """, (scheme_name,))
    scheme = cursor.fetchone()
    if scheme is None:
        return None
    return {
        "name": scheme[0],
        "description": scheme[1],
        "eligibility": scheme[2]
    }

def get_user_transactions(fingerprint_id):
    cursor.execute("""
        SELECT scheme_name, status
        FROM Transactions
        WHERE fingerprint_id = ?
    """, (fingerprint_id,))
    transactions = cursor.fetchall()
    return [
        {
            "scheme_name": transaction[0],
            "status": transaction[1]
        }
        for transaction in transactions
    ]