import sqlite3
conn = sqlite3.connect("inventario.db")
conn.execute("ALTER TABLE movimientos ADD COLUMN proyecto TEXT;")
conn.commit()
conn.close()
print("Columna 'proyecto' agregada con éxito.")