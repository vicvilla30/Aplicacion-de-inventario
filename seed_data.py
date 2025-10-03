import sqlite3

# Conexión a la base de datos
conn = sqlite3.connect("inventario.db")
cursor = conn.cursor()

# Lista de productos de ejemplo
productos = [
    ("Dell", "DL-001", "Laptop Dell Inspiron 15", 12, 5, "Almacén", "SN12345", 450.00, 500.00, 520.00, 550.00, None),
    ("HP", "HP-002", "Impresora HP LaserJet Pro", 8, 3, "Bodega", "SN67890", 120.00, 140.00, 150.00, 160.00, None),
    ("Logitech", "LG-003", "Mouse Logitech MX Master 3", 25, 10, "Almacén", "SN11111", 60.00, 70.00, 75.00, 80.00, None),
    ("Lenovo", "LN-004", "Monitor Lenovo ThinkVision 24\"", 15, 5, "Proyecto", "SN22222", 150.00, 170.00, 180.00, 200.00, None),
    ("Samsung", "SM-005", "SSD Samsung EVO 1TB", 30, 10, "Almacén", "SN33333", 90.00, 110.00, 115.00, 120.00, None),
    ("Kingston", "KS-006", "Memoria RAM Kingston 16GB DDR4", 40, 15, "Bodega", "SN44444", 55.00, 65.00, 70.00, 75.00, None),
    ("Cisco", "CS-007", "Router Cisco RV340", 6, 2, "Proyecto", "SN55555", 220.00, 250.00, 260.00, 280.00, None),
    ("Epson", "EP-008", "Proyector Epson XGA 3000 Lumens", 4, 2, "Almacén", "SN66666", 320.00, 360.00, 380.00, 400.00, None),
    ("Seagate", "SG-009", "Disco Duro Seagate 2TB", 20, 8, "Bodega", "SN77777", 65.00, 80.00, 85.00, 90.00, None),
    ("Asus", "AS-010", "Placa Madre ASUS Prime B450M", 10, 3, "Almacén", "SN88888", 100.00, 120.00, 130.00, 140.00, None),
]

# Insertar los productos en la tabla
cursor.executemany("""
INSERT INTO inventario 
(MARCA, CODIGO, DESCRIPCION, CANTIDAD, MINIMO, UBICACION, SERIAL,
 PRECIO_COSTO, PRECIO_DIST, PRECIO_INT, PRECIO_GENERAL, IMAGEN)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", productos)

# Guardar cambios
conn.commit()
conn.close()

print("✅ 10 productos de ejemplo insertados en inventario.db")
