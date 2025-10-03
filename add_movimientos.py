
import sqlite3

conn = sqlite3.connect("inventario.db")
cursor = conn.cursor()

# Crear la tabla movimientos si no existe
cursor.execute("""
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventario_id INTEGER,
    tipo TEXT, -- 'entrada' o 'salida'
    cantidad INTEGER,
    fecha TEXT,
    observacion TEXT,
    FOREIGN KEY (inventario_id) REFERENCES inventario(id)
)
""")

conn.commit()
conn.close()
print("✅ Tabla movimientos creada (o ya existía) sin afectar tus datos de inventario.")