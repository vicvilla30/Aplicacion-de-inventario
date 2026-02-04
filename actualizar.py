import sqlite3
from datetime import datetime

def actualizar_base_datos():
    print("=" * 50)
    print("   ACTUALIZADOR DE BASE DE DATOS")
    print("   Inventario LSI")
    print("=" * 50)
    print()
    
    conn = sqlite3.connect('inventario.db')
    cursor = conn.cursor()
    
    try:
        # Verificar si la tabla usuarios ya existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'")
        existe = cursor.fetchone()
        
        if existe:
            print("✅ La tabla 'usuarios' ya existe")
            print()
            
            # Verificar si tiene la columna debe_cambiar_password
            cursor.execute("PRAGMA table_info(usuarios)")
            columnas = [col[1] for col in cursor.fetchall()]
            
            if 'debe_cambiar_password' not in columnas:
                print("⚙️  Agregando columna 'debe_cambiar_password'...")
                cursor.execute("ALTER TABLE usuarios ADD COLUMN debe_cambiar_password INTEGER DEFAULT 1")
                print("✅ Columna agregada")
            else:
                print("✅ Columna 'debe_cambiar_password' ya existe")
        else:
            print("⚙️  Creando tabla 'usuarios'...")
            cursor.execute("""
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    nombre_completo TEXT,
                    rol TEXT DEFAULT 'admin',
                    activo INTEGER DEFAULT 1,
                    fecha_creacion TEXT,
                    debe_cambiar_password INTEGER DEFAULT 1
                )
            """)
            print("✅ Tabla 'usuarios' creada")
        
        print()
        print("⚙️  Insertando usuarios por defecto...")
        
        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        usuarios = [
            ('vvillavicencio', 'LSI2025!', 'Victor Villavicencio', 'admin'),
            ('edasilva', 'LSI2025!', 'Eduardo Da Silva', 'admin'),
            ('mrodriguez', 'LSI2025!', 'Maria Rodriguez', 'admin')
        ]
        
        insertados = 0
        existentes = 0
        
        for username, password, nombre, rol in usuarios:
            try:
                cursor.execute("""
                    INSERT INTO usuarios (username, password, nombre_completo, rol, fecha_creacion, debe_cambiar_password)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (username, password, nombre, rol, fecha_actual))
                insertados += 1
                print(f"   ✅ Usuario '{username}' creado")
            except sqlite3.IntegrityError:
                existentes += 1
                print(f"   ℹ️  Usuario '{username}' ya existe")
        
        conn.commit()
        
        print()
        print("=" * 50)
        print("   ACTUALIZACIÓN COMPLETADA")
        print("=" * 50)
        print()
        print(f"Usuarios insertados: {insertados}")
        print(f"Usuarios existentes: {existentes}")
        print()
        print("=" * 50)
        print("   CREDENCIALES DE ACCESO")
        print("=" * 50)
        print()
        print("  Usuario: vvillavicencio")
        print("  Contraseña: LSI2025!")
        print()
        print("  Usuario: edasilva")
        print("  Contraseña: LSI2025!")
        print()
        print("  Usuario: mrodriguez")
        print("  Contraseña: LSI2025!")
        print()
        print("=" * 50)
        print()
        print("⚠️  IMPORTANTE: Cambiar contraseña en el primer inicio")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    actualizar_base_datos()