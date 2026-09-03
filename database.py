import sqlite3
import time

connection = sqlite3.connect("pacs_local.db", check_same_thread=False)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    occupation TEXT NOT NULL CHECK(occupation IN ('Farmer', 'Artisan', 'Landless Labourer')),
    village TEXT,
    land_acres REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS Schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    occupation TEXT NOT NULL CHECK(occupation IN ('Farmer', 'Artisan', 'Landless Labourer')),
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS Jurisdiction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    village TEXT NOT NULL,
    occupation TEXT NOT NULL CHECK(occupation IN ('Farmer', 'Artisan', 'Landless Labourer')),
    office_name TEXT NOT NULL,
    office_address TEXT,
    nodal_officer TEXT,
    phone TEXT,
    UNIQUE(village, occupation)
)
""")

users = [
    (14, "Ramesh", "Farmer", "Krishnarajpet", 2.5),
    (27, "Suresh", "Farmer", "Maddur", 4.0),
    (35, "Lakshmi", "Farmer", "Krishnarajpet", 1.8),
    (41, "Manju", "Artisan", "Maddur", None),
    (52, "Ravi", "Artisan", "Krishnarajpet", None),
    (63, "Ganga", "Landless Labourer", "Maddur", None)
]

schemes = [
    ("PM-KISAN", "Farmer", "Income support for eligible farmers", "Small and marginal farmers"),
    ("Crop Insurance", "Farmer", "Insurance coverage for crop losses", "Farmers with eligible crops"),
    ("Kisan Credit Card", "Farmer", "Credit support for agricultural needs", "Eligible farmers"),
    ("Artisan Credit Scheme", "Artisan", "Working capital loan for craft materials", "Registered artisans"),
    ("PM Vishwakarma", "Artisan", "Toolkit + skill support for traditional artisans", "Artisans in listed trades"),
    ("MGNREGA Wage Support", "Landless Labourer", "Guaranteed wage employment", "Registered rural labourers")
]

jurisdictions = [
    ("Krishnarajpet", "Farmer", "PACS Office KR Pet", "Main Road, Krishnarajpet", "Mr. N. Shivaraju", "080-11122233"),
    ("Maddur", "Farmer", "PACS Office Maddur", "Bus Stand Road, Maddur", "Mrs. K. Deepa", "080-11122234"),
    ("Krishnarajpet", "Artisan", "Taluk Panchayat KR Pet", "Panchayat Bhavan, KR Pet", "Mr. R. Suresh", "080-11122235"),
    ("Maddur", "Artisan", "Taluk Panchayat Maddur", "Panchayat Bhavan, Maddur", "Mr. B. Manju", "080-11122236"),
    ("Maddur", "Landless Labourer", "MGNREGA Cell Maddur", "Gram Panchayat Office, Maddur", "Mrs. S. Ganga", "080-11122237")
]

cursor.executemany("""
INSERT OR IGNORE INTO Users
(fingerprint_id, name, occupation, village, land_acres)
VALUES (?, ?, ?, ?, ?)
""", users)

cursor.executemany("""
INSERT OR IGNORE INTO Schemes
(name, occupation, description, eligibility)
VALUES (?, ?, ?, ?)
""", schemes)

cursor.executemany("""
INSERT OR IGNORE INTO Jurisdiction
(village, occupation, office_name, office_address, nodal_officer, phone)
VALUES (?, ?, ?, ?, ?, ?)
""", jurisdictions)

connection.commit()


def get_user_profile(fingerprint_id):
    cursor.execute("""
        SELECT name, occupation, village, land_acres
        FROM Users
        WHERE fingerprint_id = ?
    """, (fingerprint_id,))
    user = cursor.fetchone()
    if user is None:
        return None
    return {
        "name": user[0],
        "occupation": user[1],
        "village": user[2],
        "land_acres": user[3]
    }


def create_guest_profile(occupation, village):
    guest_fingerprint_id = int(time.time())  # unique enough for a demo session
    cursor.execute("""
        INSERT INTO Users (fingerprint_id, name, occupation, village, land_acres)
        VALUES (?, 'Guest', ?, ?, NULL)
    """, (guest_fingerprint_id, occupation, village))
    connection.commit()
    return get_user_profile(guest_fingerprint_id)


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


def get_schemes_for_occupation(occupation):
    cursor.execute("""
        SELECT name, description, eligibility
        FROM Schemes
        WHERE occupation = ?
    """, (occupation,))
    schemes = cursor.fetchall()
    return [
        {"name": s[0], "description": s[1], "eligibility": s[2]}
        for s in schemes
    ]


def get_jurisdiction(village, occupation):
    cursor.execute("""
        SELECT office_name, office_address, nodal_officer, phone
        FROM Jurisdiction
        WHERE village = ? AND occupation = ?
    """, (village, occupation))
    j = cursor.fetchone()
    if j is None:
        return None
    return {
        "office_name": j[0],
        "office_address": j[1],
        "nodal_officer": j[2],
        "phone": j[3]
    }


def get_user_transactions(fingerprint_id):
    cursor.execute("""
        SELECT scheme_name, status
        FROM Transactions
        WHERE fingerprint_id = ?
    """, (fingerprint_id,))
    transactions = cursor.fetchall()
    return [
        {"scheme_name": t[0], "status": t[1]}
        for t in transactions
    ]