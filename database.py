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

users = [
    (14, "Ramesh", 2.5, "Paddy"),
    (27, "Suresh", 4.0, "Ragi"),
    (35, "Lakshmi", 1.8, "Maize")
]

cursor.executemany("""
INSERT OR IGNORE INTO Users
(fingerprint_id, name, land_acres, crop)
VALUES (?, ?, ?, ?)
""", users)

connection.commit()

print("Dummy users inserted!")

connection.close()