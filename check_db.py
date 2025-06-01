import sqlite3

conn = sqlite3.connect('bank.db')
cursor = conn.cursor()

print("Isi tabel users:")
cursor.execute("SELECT * FROM users")
for row in cursor.fetchall():
    print(row)

print("\nIsi tabel nasabah:")
cursor.execute("SELECT * FROM nasabah")
for row in cursor.fetchall():
    print(row)

conn.close()