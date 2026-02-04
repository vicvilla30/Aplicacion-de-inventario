import os
import sys
import sqlite3
from pathlib import Path

def diagnostico():
    print("=" * 60)
    print("   DIAGNÓSTICO COMPLETO DEL SISTEMA")
    print("=" * 60)
    print()
    
    errores = []
    advertencias = []
    
    # 1. Verificar Python
    print("1️⃣  Verificando Python...")
    print(f"   Versión: Python {sys.version}")
    print(f"   ✅ Python OK")
    print()
    
    # 2. Verificar estructura de carpetas
    print("2️⃣  Verificando estructura de carpetas...")
    carpetas_requeridas = ['templates', 'static', 'static/uploads']
    for carpeta in carpetas_requeridas:
        if os.path.exists(carpeta):
            print(f"   ✅ {carpeta}/")
        else:
            print(f"   ❌ {carpeta}/ NO EXISTE")
            errores.append(f"Falta carpeta: {carpeta}")
    print()
    
    # 3. Verificar archivos principales
    print("3️⃣  Verificando archivos principales...")
    archivos = {
        'app.py': 'Aplicación principal',
        'templates/login.html': 'Página de login',
        'templates/cambiar_password.html': 'Cambio de contraseña',
        'templates/index.html': 'Página principal',
        'inventario.db': 'Base de datos'
    }
    
    for archivo, desc in archivos.items():
        if os.path.exists(archivo):
            tamaño = os.path.getsize(archivo)
            if tamaño > 0:
                print(f"   ✅ {archivo} ({tamaño} bytes) - {desc}")
            else:
                print(f"   ⚠️  {archivo} (VACÍO) - {desc}")
                advertencias.append(f"{archivo} está vacío")
        else:
            print(f"   ❌ {archivo} NO EXISTE - {desc}")
            errores.append(f"Falta archivo: {archivo}")
    print()
    
    # 4. Verificar base de datos
    print("4️⃣  Verificando base de datos...")
    if os.path.exists('inventario.db'):
        try:
            conn = sqlite3.connect('inventario.db')
            cursor = conn.cursor()
            
            # Listar tablas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tablas = [row[0] for row in cursor.fetchall()]
            
            print(f"   Tablas encontradas: {len(tablas)}")
            
            tablas_requeridas = ['inventario', 'movimientos', 'ubicaciones', 'proyecto_items', 'usuarios']
            
            for tabla in tablas_requeridas:
                if tabla in tablas:
                    cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
                    count = cursor.fetchone()[0]
                    print(f"   ✅ {tabla}: {count} registros")
                else:
                    print(f"   ❌ {tabla}: NO EXISTE")
                    errores.append(f"Falta tabla: {tabla}")
            
            # Verificar usuarios específicamente
            if 'usuarios' in tablas:
                cursor.execute("SELECT username, nombre_completo FROM usuarios")
                usuarios = cursor.fetchall()
                if usuarios:
                    print()
                    print("   👥 Usuarios registrados:")
                    for user in usuarios:
                        print(f"      • {user[0]} ({user[1]})")
                else:
                    print("   ⚠️  Tabla usuarios existe pero está vacía")
                    advertencias.append("No hay usuarios registrados")
            
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Error al leer la base de datos: {e}")
            errores.append(f"Error en BD: {e}")
    else:
        print("   ❌ inventario.db NO EXISTE")
        errores.append("No existe inventario.db")
    print()
    
    # 5. Verificar módulos de Python
    print("5️⃣  Verificando módulos de Python...")
    modulos = ['flask', 'pandas', 'openpyxl', 'sqlite3']
    for modulo in modulos:
        try:
            __import__(modulo)
            print(f"   ✅ {modulo}")
        except ImportError:
            print(f"   ❌ {modulo} NO INSTALADO")
            errores.append(f"Falta módulo: {modulo}")
    print()
    
    # 6. Probar importar app.py
    print("6️⃣  Verificando app.py...")
    try:
        # Intentar parsear app.py para buscar errores de sintaxis
        with open('app.py', 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        # Verificar rutas clave
        rutas_importantes = [
            '@app.route("/login"',
            '@app.route("/"',
            'def login(',
            'def index(',
            'app.run('
        ]
        
        for ruta in rutas_importantes:
            if ruta in contenido:
                print(f"   ✅ Encontrada: {ruta}")
            else:
                print(f"   ⚠️  No encontrada: {ruta}")
                advertencias.append(f"Posible falta de ruta: {ruta}")
                
    except Exception as e:
        print(f"   ❌ Error al leer app.py: {e}")
        errores.append(f"Error leyendo app.py: {e}")
    print()
    
    # 7. Verificar contenido de login.html
    print("7️⃣  Verificando contenido de login.html...")
    if os.path.exists('templates/login.html'):
        try:
            with open('templates/login.html', 'r', encoding='utf-8') as f:
                contenido = f.read()
            
            elementos = [
                '<!DOCTYPE html>',
                '<form',
                'method="post"',
                'name="username"',
                'name="password"',
                '<button'
            ]
            
            for elemento in elementos:
                if elemento in contenido:
                    print(f"   ✅ {elemento}")
                else:
                    print(f"   ❌ Falta: {elemento}")
                    errores.append(f"login.html: falta {elemento}")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errores.append(f"Error leyendo login.html: {e}")
    print()
    
    # RESUMEN
    print()
    print("=" * 60)
    print("   RESUMEN")
    print("=" * 60)
    print()
    
    if not errores and not advertencias:
        print("✅ TODO ESTÁ CORRECTO")
        print()
        print("El sistema debería funcionar.")
        print()
        print("Siguiente paso:")
        print("  1. Ejecuta: python app.py")
        print("  2. Abre: http://127.0.0.1:5000/login")
        print("  3. Usuario: vvillavicencio")
        print("  4. Contraseña: LSI2025!")
    else:
        if errores:
            print(f"❌ ERRORES CRÍTICOS ({len(errores)}):")
            for i, error in enumerate(errores, 1):
                print(f"   {i}. {error}")
            print()
        
        if advertencias:
            print(f"⚠️  ADVERTENCIAS ({len(advertencias)}):")
            for i, adv in enumerate(advertencias, 1):
                print(f"   {i}. {adv}")
            print()
        
        print("=" * 60)
        print("   SOLUCIONES RECOMENDADAS")
        print("=" * 60)
        print()
        
        if any('usuarios' in e.lower() for e in errores):
            print("🔧 Ejecuta: python actualizar_db.py")
        
        if any('login.html' in e.lower() for e in errores):
            print("🔧 Recrea el archivo templates/login.html")
        
        if any('módulo' in e.lower() for e in errores):
            print("🔧 Ejecuta: pip install flask pandas openpyxl")
    
    print()
    print("=" * 60)
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    try:
        diagnostico()
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresiona Enter para cerrar...")