import pandas as pd
import sqlite3
import os

# Configuración de archivo
CSV_FILENAME = "abb.csv"
DB_FILENAME = "inventario.db"

# Verifica que el archivo CSV existe
if not os.path.exists(CSV_FILENAME):
    print(f"ERROR: El archivo {CSV_FILENAME} no existe en esta carpeta.")
    exit(1)

# Lee el CSV (delimitado por punto y coma)
try:
    df = pd.read_csv(CSV_FILENAME, sep=";", encoding="utf-8")
except Exception as e:
    print(f"Error al leer el archivo CSV: {e}")
    exit(1)

# Renombra la columna 'UBICACIÓN' a 'UBICACION' si existe
if "UBICACIÓN" in df.columns:
    df = df.rename(columns={"UBICACIÓN": "UBICACION"})

# Rellena valores nulos
for col in [
    "MARCA", "CODIGO", "DESCRIPCION", "CANTIDAD", "MINIMO", "UBICACION", "SERIAL",
    "PRECIO_COSTO", "PRECIO_DIST", "PRECIO_INT", "PRECIO_GENERAL", "IMAGEN"
]:
    if col not in df.columns:
        df[col] = "" if col in ["MARCA", "CODIGO", "DESCRIPCION", "UBICACION", "SERIAL", "IMAGEN"] else 0

df = df.fillna({
    "MARCA": "",
    "CODIGO": "",
    "DESCRIPCION": "",
    "CANTIDAD": 0,
    "MINIMO": 0,
    "UBICACION": "",
    "SERIAL": "",
    "PRECIO_COSTO": 0.0,
    "PRECIO_DIST": 0.0,
    "PRECIO_INT": 0.0,
    "PRECIO_GENERAL": 0.0,
    "IMAGEN": ""
})

# Solo selecciona las columnas necesarias
columnas = [
    "MARCA", "CODIGO", "DESCRIPCION", "CANTIDAD", "MINIMO", "UBICACION", "SERIAL",
    "PRECIO_COSTO", "PRECIO_DIST", "PRECIO_INT", "PRECIO_GENERAL", "IMAGEN"
]
df = df[columnas]

# Conexión a la base de datos
conn = sqlite3.connect(DB_FILENAME)

# Crea la tabla si no existe
conn.execute("""
CREATE TABLE IF NOT EXISTS inventario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    MARCA TEXT,
    CODIGO TEXT,
    DESCRIPCION TEXT,
    CANTIDAD INTEGER,
    MINIMO INTEGER,
    UBICACION TEXT,
    SERIAL TEXT,
    PRECIO_COSTO REAL,
    PRECIO_DIST REAL,
    PRECIO_INT REAL,
    PRECIO_GENERAL REAL,
    IMAGEN TEXT
)
""")

# Borra todo antes de importar (opcional, recomendado en pruebas)
conn.execute("DELETE FROM inventario")

# Importa los datos
try:
    df.to_sql("inventario", conn, if_exists="append", index=False)
    print("¡Importación completa! Revisa tu app Flask.")
except Exception as e:
    print(f"Error importando los datos: {e}")

conn.commit()
conn.close()