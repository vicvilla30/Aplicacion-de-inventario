import sqlite3

# Crear base de datos
conn = sqlite3.connect("inventario.db")
cursor = conn.cursor()

# Crear tabla
cursor.execute("""
CREATE TABLE inventario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    MARCA TEXT,
    CODIGO TEXT,
    DESCRIPCION TEXT,
    CANTIDAD INTEGER,
    UBICACION TEXT,
    SERIAL TEXT,
    PRECIO_COSTO REAL,
    PRECIO_DIST REAL,
    PRECIO_INT REAL,
    PRECIO_GENERAL REAL,
    IMAGEN TEXT,
    MINIMO INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()
print("✅ Base de datos y tabla inventario creadas correctamente.")
