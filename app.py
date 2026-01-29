from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import os
import uuid
import pandas as pd
import smtplib
import unicodedata
from email.message import EmailMessage
from datetime import datetime

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.secret_key = "supersecretkey"

def quitar_acentos(txt):
    if txt is None:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

def get_db_connection():
    conn = sqlite3.connect("inventario.db")
    conn.row_factory = sqlite3.Row
    conn.create_function("quitar_acentos", 1, quitar_acentos)
    return conn

def obtener_ubicaciones():
    conn = get_db_connection()
    ubicaciones_fijas = conn.execute("""
        SELECT nombre AS NOMBRE
        FROM ubicaciones
        WHERE tipo = 'FIJA' AND activa = 1
        ORDER BY nombre
    """).fetchall()
    proyectos = conn.execute("""
        SELECT nombre AS NOMBRE
        FROM ubicaciones
        WHERE tipo = 'PROYECTO' AND activa = 1
        ORDER BY nombre
    """).fetchall()
    conn.close()
    return ubicaciones_fijas, proyectos

def init_db():
    conn = get_db_connection()
    
    # Tabla inventario
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
    
    # Tabla movimientos
    conn.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inventario_id INTEGER,
        tipo TEXT,
        cantidad INTEGER,
        fecha TEXT,
        observacion TEXT,
        proyecto TEXT,
        FOREIGN KEY (inventario_id) REFERENCES inventario(id)
    )
    """)
    
    # Tabla ubicaciones (ahora incluye proyectos con más información)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ubicaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        tipo TEXT DEFAULT 'FIJA',
        activa INTEGER DEFAULT 1,
        descripcion TEXT,
        cliente TEXT,
        fecha_inicio TEXT,
        fecha_fin TEXT,
        estado TEXT DEFAULT 'ACTIVO'
    )
    """)
    
    # Tabla proyecto_items (productos asignados a proyectos)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS proyecto_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proyecto_id INTEGER,
        inventario_id INTEGER,
        cantidad_asignada INTEGER,
        fecha_asignacion TEXT,
        observacion TEXT,
        FOREIGN KEY (proyecto_id) REFERENCES ubicaciones(id),
        FOREIGN KEY (inventario_id) REFERENCES inventario(id)
    )
    """)
    
    # Insertar ubicaciones fijas por defecto
    ubicaciones_default = ['BODEGA', 'OFICINA', 'ALMACEN', 'TALLER']
    for ub in ubicaciones_default:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO ubicaciones (nombre, tipo) VALUES (?, 'FIJA')",
                (ub,)
            )
        except:
            pass
    
    conn.commit()
    conn.close()

def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def enviar_alerta_stock(producto):
    try:
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        if not smtp_user or not smtp_pass:
            print("⚠ SMTP credentials not configured. Skipping enviar_alerta_stock.")
            return
        msg = EmailMessage()
        msg["Subject"] = f"⚠️ Alerta de stock bajo: {producto['DESCRIPCION']}"
        msg["From"] = smtp_user
        msg["To"] = smtp_user
        msg.set_content(
            f"El producto {producto['DESCRIPCION']} (Código {producto['CODIGO']}) "
            f"está por debajo del stock mínimo.\n"
            f"Cantidad actual: {producto['CANTIDAD']} | Stock mínimo: {producto['MINIMO']}"
        )
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print("✅ Correo de alerta enviado correctamente")
    except Exception as e:
        print("❌ Error enviando correo:", e)

@app.route("/", methods=["GET"])
def index():
    busqueda = request.args.get("busqueda", "").strip()
    solo_bajo_stock = request.args.get("solo_bajo_stock", "")
    conn = get_db_connection()
    
    # Obtener totales generales (sin filtros) - SIEMPRE FIJOS
    total_productos = conn.execute("SELECT COUNT(*) as total FROM inventario").fetchone()["total"]
    total_bajo_stock = conn.execute(
        "SELECT COUNT(*) as total FROM inventario WHERE CANTIDAD <= MINIMO"
    ).fetchone()["total"]
    
    # Aplicar filtros para la tabla
    query = "SELECT * FROM inventario WHERE 1=1"
    params = []
    
    if busqueda:
        busqueda_clean = quitar_acentos(busqueda)
        query += (
            " AND (quitar_acentos(CODIGO) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(DESCRIPCION) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(MARCA) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(UBICACION) LIKE ? COLLATE NOCASE)"
        )
        params.extend([f"%{busqueda_clean}%", f"%{busqueda_clean}%", f"%{busqueda_clean}%", f"%{busqueda_clean}%"])
    
    if solo_bajo_stock:
        query += " AND CANTIDAD <= MINIMO"
    
    items = conn.execute(query, params).fetchall()
    conn.close()
    
    ubicaciones_fijas, proyectos = obtener_ubicaciones()
    
    return render_template("index.html",
        items=items,
        busqueda=busqueda,
        total_productos=total_productos,
        total_bajo_stock=total_bajo_stock,
        ubicaciones_fijas=ubicaciones_fijas,
        proyectos=proyectos
    )

@app.route("/exportar_seleccionados", methods=["POST"])
def exportar_seleccionados():
    seleccionados = request.form.getlist('seleccionados')
    if not seleccionados:
        flash("No seleccionaste ningún producto.", "warning")
        return redirect(url_for("index"))
    placeholders = ','.join(['?'] * len(seleccionados))
    conn = get_db_connection()
    query = f"SELECT CODIGO, DESCRIPCION, CANTIDAD FROM inventario WHERE id IN ({placeholders})"
    items = conn.execute(query, seleccionados).fetchall()
    conn.close()
    df = pd.DataFrame([dict(item) for item in items])
    export_path = os.path.join("static", "export_seleccionados.xlsx")
    df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True)

@app.route("/agregar", methods=["GET", "POST"])
def agregar():
    if request.method == "POST":
        marca = request.form.get("marca", "").strip()
        codigo = request.form.get("codigo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        cantidad = to_int(request.form.get("cantidad"), 0)
        minimo = to_int(request.form.get("minimo"), 0)
        ubicacion = request.form.get("ubicacion", "").strip()
        serial = request.form.get("serial", "").strip()
        precio_costo = to_float(request.form.get("precio_costo"), 0.0)
        precio_dist = to_float(request.form.get("precio_dist"), 0.0)
        precio_int = to_float(request.form.get("precio_int"), 0.0)
        precio_general = to_float(request.form.get("precio_general"), 0.0)

        if not marca or not codigo or not descripcion:
            flash("Marca, código y descripción son obligatorios.", "warning")
            return redirect(url_for("agregar"))
        if cantidad < 0 or minimo < 0:
            flash("Cantidad y mínimo no pueden ser negativos.", "warning")
            return redirect(url_for("agregar"))

        imagen = None
        if "imagen" in request.files:
            file = request.files["imagen"]
            if file and file.filename != "":
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                ext = os.path.splitext(file.filename)[1]
                unique_name = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
                file.save(filepath)
                imagen = unique_name

        conn = get_db_connection()
        conn.execute("""INSERT INTO inventario 
            (MARCA, CODIGO, DESCRIPCION, CANTIDAD, MINIMO, UBICACION, SERIAL,
            PRECIO_COSTO, PRECIO_DIST, PRECIO_INT, PRECIO_GENERAL, IMAGEN)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (marca, codigo, descripcion, cantidad, minimo, ubicacion, serial,
             precio_costo, precio_dist, precio_int, precio_general, imagen)
        )
        conn.commit()
        nuevo = conn.execute("SELECT * FROM inventario WHERE id = last_insert_rowid()").fetchone()
        if nuevo and nuevo["CANTIDAD"] <= nuevo["MINIMO"]:
            enviar_alerta_stock(nuevo)
        conn.close()
        flash("Producto agregado correctamente.", "success")
        return redirect(url_for("index"))
    
    ubicaciones_fijas, proyectos = obtener_ubicaciones()
    return render_template(
        "agregar.html",
        ubicaciones_fijas=ubicaciones_fijas,
        proyectos=proyectos
    )

@app.route("/crear_proyecto", methods=["GET", "POST"])
def crear_proyecto():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip().upper()
        solicitado_por = request.form.get("descripcion", "").strip().upper()
        fecha_inicio = request.form.get("fecha_inicio", "").strip()

        if not nombre:
            flash("El nombre del proyecto es obligatorio", "warning")
        else:
            conn = get_db_connection()
            try:
                conn.execute("""
                    INSERT INTO ubicaciones (nombre, tipo, descripcion, fecha_inicio, estado)
                    VALUES (?, 'PROYECTO', ?, ?, 'ACTIVO')
                """, (nombre, solicitado_por, fecha_inicio))
                conn.commit()
                flash("Proyecto creado correctamente", "success")
            except sqlite3.IntegrityError:
                flash("Ese proyecto ya existe", "danger")
            conn.close()

        return redirect(url_for("crear_proyecto"))

    conn = get_db_connection()
    proyectos = conn.execute("""
        SELECT * FROM ubicaciones 
        WHERE tipo = 'PROYECTO' 
        ORDER BY fecha_inicio DESC, nombre DESC
    """).fetchall()
    conn.close()
    
    # Pasar fecha actual para el formulario
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    
    return render_template("crear_proyecto.html", proyectos=proyectos, today=today)

@app.route("/entrada/<int:id>", methods=["GET", "POST"])
def entrada(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
    if not item:
        conn.close()
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("index"))
    if request.method == "POST":
        cantidad = int(request.form.get("cantidad", 0))
        observacion = request.form.get("observacion", "")
        proyecto = request.form.get("proyecto", "").strip()
        if cantidad <= 0:
            flash("Cantidad inválida.", "danger")
            return redirect(url_for("entrada", id=id))
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO movimientos (inventario_id, tipo, cantidad, fecha, observacion, proyecto)
            VALUES (?, 'entrada', ?, ?, ?, ?)
        """, (id, cantidad, fecha, observacion, proyecto))
        nueva_cantidad = item["CANTIDAD"] + cantidad
        conn.execute("UPDATE inventario SET CANTIDAD = ? WHERE id = ?", (nueva_cantidad, id))
        conn.commit()
        conn.close()
        flash("Entrada registrada correctamente.", "success")
        return redirect(url_for("index"))
    
    ubicaciones_fijas, proyectos = obtener_ubicaciones()
    conn.close()
    return render_template("entrada.html", item=item, proyectos=proyectos)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conn = get_db_connection()
    item = conn.execute(
        "SELECT * FROM inventario WHERE id = ?",
        (id,)
    ).fetchone()
    conn.close()

    if not item:
        flash("Producto no encontrado", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        marca = request.form.get("marca", "").strip()
        codigo = request.form.get("codigo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()
        cantidad = to_int(request.form.get("cantidad"), 0)
        minimo = to_int(request.form.get("minimo"), 0)
        ubicacion = request.form.get("ubicacion", "").strip()
        serial = request.form.get("serial", "").strip()
        precio_costo = to_float(request.form.get("precio_costo"), 0.0)
        precio_dist = to_float(request.form.get("precio_dist"), 0.0)
        precio_int = to_float(request.form.get("precio_int"), 0.0)
        precio_general = to_float(request.form.get("precio_general"), 0.0)

        imagen = item["IMAGEN"]

        if "imagen" in request.files:
            file = request.files["imagen"]
            if file and file.filename != "":
                os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
                ext = os.path.splitext(file.filename)[1]
                unique_name = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
                file.save(filepath)

                if item["IMAGEN"]:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER"], item["IMAGEN"])
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception:
                            pass

                imagen = unique_name

        conn = get_db_connection()
        conn.execute("""
            UPDATE inventario SET 
                MARCA=?, CODIGO=?, DESCRIPCION=?, CANTIDAD=?, MINIMO=?, UBICACION=?, SERIAL=?,
                PRECIO_COSTO=?, PRECIO_DIST=?, PRECIO_INT=?, PRECIO_GENERAL=?, IMAGEN=?
            WHERE id=?
        """, (
            marca, codigo, descripcion, cantidad, minimo, ubicacion, serial,
            precio_costo, precio_dist, precio_int, precio_general, imagen, id
        ))
        conn.commit()
        conn.close()
        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for("index"))

    ubicaciones_fijas, proyectos = obtener_ubicaciones()

    return render_template(
        "editar.html",
        item=item,
        ubicaciones_fijas=ubicaciones_fijas,
        proyectos=proyectos
    )

@app.route("/eliminar/<int:id>")
def eliminar(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM inventario WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Producto eliminado correctamente.", "success")
    return redirect(url_for("index"))

@app.route("/detalle/<int:id>")
def detalle(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
    conn.close()
    return render_template("detalle.html", item=item)

@app.route("/salida/<int:id>", methods=["GET", "POST"])
def salida(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
    if not item:
        conn.close()
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("index"))
    if request.method == "POST":
        cantidad = int(request.form.get("cantidad", 0))
        observacion = request.form.get("observacion", "")
        proyecto = request.form.get("proyecto", "").strip()
        if cantidad <= 0 or cantidad > item["CANTIDAD"]:
            flash("Cantidad inválida.", "danger")
            return redirect(url_for("salida", id=id))
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO movimientos (inventario_id, tipo, cantidad, fecha, observacion, proyecto)
            VALUES (?, 'salida', ?, ?, ?, ?)
        """, (id, cantidad, fecha, observacion, proyecto))
        nueva_cantidad = item["CANTIDAD"] - cantidad
        conn.execute("UPDATE inventario SET CANTIDAD = ? WHERE id = ?", (nueva_cantidad, id))
        producto_actualizado = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
        if producto_actualizado and producto_actualizado["CANTIDAD"] <= producto_actualizado["MINIMO"]:
            enviar_alerta_stock(producto_actualizado)
        conn.commit()
        conn.close()
        flash("Salida registrada correctamente.", "success")
        return redirect(url_for("index"))
    
    ubicaciones_fijas, proyectos = obtener_ubicaciones()
    conn.close()
    return render_template("salida.html", item=item, proyectos=proyectos)

@app.route("/exportar")
def exportar():
    busqueda = request.args.get("busqueda", "")
    conn = get_db_connection()
    query = "SELECT * FROM inventario WHERE 1=1"
    params = []
    
    if busqueda:
        busqueda_clean = quitar_acentos(busqueda)
        query += (
            " AND (quitar_acentos(CODIGO) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(DESCRIPCION) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(MARCA) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(UBICACION) LIKE ? COLLATE NOCASE)"
        )
        params.extend([f"%{busqueda_clean}%", f"%{busqueda_clean}%", f"%{busqueda_clean}%", f"%{busqueda_clean}%"])
    
    items = conn.execute(query, params).fetchall()
    conn.close()
    df = pd.DataFrame([dict(item) for item in items])
    export_path = os.path.join("static", "export_inventario.xlsx")
    df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True)

@app.route("/movimientos/<int:id>")
def movimientos(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
    movimientos = conn.execute("SELECT * FROM movimientos WHERE inventario_id = ? ORDER BY fecha DESC", (id,)).fetchall()
    conn.close()
    return render_template("movimientos.html", item=item, movimientos=movimientos)

@app.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "POST":
        if "archivo" not in request.files:
            flash("No se seleccionó ningún archivo", "warning")
            return redirect(url_for("importar"))
        
        file = request.files["archivo"]
        if file.filename == "":
            flash("No se seleccionó ningún archivo", "warning")
            return redirect(url_for("importar"))
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash("Solo se permiten archivos Excel (.xlsx, .xls)", "danger")
            return redirect(url_for("importar"))
        
        try:
            df = pd.read_excel(file)
            total_filas = len(df)
            
            columnas_requeridas = ['MARCA', 'CODIGO', 'DESCRIPCION']
            columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
            
            if columnas_faltantes:
                flash(f"Faltan columnas requeridas: {', '.join(columnas_faltantes)}", "danger")
                return redirect(url_for("importar"))
            
            conn = get_db_connection()
            insertados = 0
            omitidos = 0
            errores_detallados = []
            
            for index, row in df.iterrows():
                try:
                    codigo = str(row.get('CODIGO', '')).strip()
                    descripcion = str(row.get('DESCRIPCION', '')).strip()
                    marca = str(row.get('MARCA', '')).strip()
                    
                    # Limpiar 'nan'
                    if codigo == 'nan':
                        codigo = ''
                    if descripcion == 'nan':
                        descripcion = ''
                    if marca == 'nan':
                        marca = ''
                    
                    datos = {
                        'marca': marca,
                        'codigo': codigo,
                        'descripcion': descripcion,
                        'cantidad': to_int(row.get('CANTIDAD', 0)),
                        'minimo': to_int(row.get('MINIMO', 0)),
                        'ubicacion': str(row.get('UBICACION', 'BODEGA')),
                        'serial': str(row.get('SERIAL', '')),
                        'precio_costo': to_float(row.get('PRECIO_COSTO', 0)),
                        'precio_dist': to_float(row.get('PRECIO_DIST', 0)),
                        'precio_int': to_float(row.get('PRECIO_INT', 0)),
                        'precio_general': to_float(row.get('PRECIO_GENERAL', 0)),
                    }
                    
                    if datos['ubicacion'] == 'nan':
                        datos['ubicacion'] = 'BODEGA'
                    if datos['serial'] == 'nan':
                        datos['serial'] = ''
                    
                    conn.execute("""
                        INSERT INTO inventario 
                        (MARCA, CODIGO, DESCRIPCION, CANTIDAD, MINIMO, UBICACION, SERIAL,
                         PRECIO_COSTO, PRECIO_DIST, PRECIO_INT, PRECIO_GENERAL)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datos['marca'], datos['codigo'], datos['descripcion'],
                        datos['cantidad'], datos['minimo'], datos['ubicacion'],
                        datos['serial'], datos['precio_costo'], datos['precio_dist'],
                        datos['precio_int'], datos['precio_general']
                    ))
                    insertados += 1
                
                except Exception as e:
                    omitidos += 1
                    errores_detallados.append({
                        'fila': index + 2,
                        'marca': str(row.get('MARCA', '')),
                        'codigo': str(row.get('CODIGO', '')),
                        'descripcion': str(row.get('DESCRIPCION', ''))[:50],
                        'motivo': f'Error: {str(e)}'
                    })
            
            conn.commit()
            conn.close()
            
            flash(f"✅ Importación completa: {insertados} productos insertados de {total_filas} filas", "success")
            
            if omitidos > 0:
                flash(f"⚠️ Se omitieron {omitidos} filas con errores", "warning")
                
                for error in errores_detallados[:10]:
                    flash(f"Fila {error['fila']}: {error['motivo']}", "warning")
                
                if len(errores_detallados) > 10:
                    flash(f"... y {len(errores_detallados) - 10} errores más", "info")
            
            return redirect(url_for("index"))
        
        except Exception as e:
            flash(f"Error al procesar el archivo: {str(e)}", "danger")
            return redirect(url_for("importar"))
    
    return render_template("importar.html")

@app.route("/descargar_plantilla")
def descargar_plantilla():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM inventario ORDER BY id").fetchall()
    conn.close()
    
    if not items:
        flash("No hay productos en el inventario para exportar.", "warning")
        return redirect(url_for("importar"))
    
    df = pd.DataFrame([dict(item) for item in items])
    
    columnas_exportar = [
        'MARCA', 'CODIGO', 'DESCRIPCION', 'CANTIDAD', 'MINIMO', 
        'UBICACION', 'SERIAL', 'PRECIO_COSTO', 'PRECIO_DIST', 
        'PRECIO_INT', 'PRECIO_GENERAL'
    ]
    df = df[columnas_exportar]
    
    export_path = os.path.join("static", "inventario_LSI.xlsx")
    df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True)


# ============================================
# ⬇️ NUEVAS RUTAS PARA GESTIÓN DE PROYECTOS ⬇️
# ============================================

@app.route("/detalle_proyecto/<int:id>")
def detalle_proyecto(id):
    conn = get_db_connection()
    proyecto = conn.execute("SELECT * FROM ubicaciones WHERE id = ?", (id,)).fetchone()
    
    if not proyecto:
        conn.close()
        flash("Proyecto no encontrado", "danger")
        return redirect(url_for("crear_proyecto"))
    
    # Obtener items asignados al proyecto
    items = conn.execute("""
        SELECT 
            pi.id as asignacion_id,
            pi.cantidad_asignada,
            pi.fecha_asignacion,
            pi.observacion,
            i.id as inventario_id,
            i.CODIGO,
            i.DESCRIPCION,
            i.MARCA,
            i.CANTIDAD as stock_actual
        FROM proyecto_items pi
        JOIN inventario i ON pi.inventario_id = i.id
        WHERE pi.proyecto_id = ?
        ORDER BY pi.fecha_asignacion DESC
    """, (id,)).fetchall()
    
    conn.close()
    
    return render_template("detalle_proyecto.html", proyecto=proyecto, items=items)


@app.route("/asignar_items/<int:proyecto_id>", methods=["GET", "POST"])
def asignar_items(proyecto_id):
    conn = get_db_connection()
    proyecto = conn.execute("SELECT * FROM ubicaciones WHERE id = ?", (proyecto_id,)).fetchone()
    
    if not proyecto:
        conn.close()
        flash("Proyecto no encontrado", "danger")
        return redirect(url_for("crear_proyecto"))
    
    if request.method == "POST":
        inventario_id = request.form.get("inventario_id")
        cantidad = int(request.form.get("cantidad", 0))
        observacion = request.form.get("observacion", "").strip().upper()
        
        if not inventario_id or cantidad <= 0:
            flash("Debe seleccionar un producto y cantidad válida", "warning")
            return redirect(url_for("asignar_items", proyecto_id=proyecto_id))
        
        # Verificar stock disponible
        item = conn.execute("SELECT * FROM inventario WHERE id = ?", (inventario_id,)).fetchone()
        
        if not item:
            flash("Producto no encontrado", "danger")
            return redirect(url_for("asignar_items", proyecto_id=proyecto_id))
        
        if item['CANTIDAD'] < cantidad:
            flash(f"Stock insuficiente. Disponible: {item['CANTIDAD']}", "danger")
            return redirect(url_for("asignar_items", proyecto_id=proyecto_id))
        
        # Asignar item al proyecto
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO proyecto_items (proyecto_id, inventario_id, cantidad_asignada, fecha_asignacion, observacion)
            VALUES (?, ?, ?, ?, ?)
        """, (proyecto_id, inventario_id, cantidad, fecha, observacion))
        
        # Descontar del stock
        nueva_cantidad = item['CANTIDAD'] - cantidad
        conn.execute("UPDATE inventario SET CANTIDAD = ? WHERE id = ?", (nueva_cantidad, inventario_id))
        
        # Registrar movimiento
        conn.execute("""
            INSERT INTO movimientos (inventario_id, tipo, cantidad, fecha, observacion, proyecto)
            VALUES (?, 'salida', ?, ?, ?, ?)
        """, (inventario_id, cantidad, fecha, f"Asignado a proyecto: {observacion}", proyecto['nombre']))
        
        conn.commit()
        
        # Verificar si el producto quedó con stock bajo
        producto_actualizado = conn.execute("SELECT * FROM inventario WHERE id = ?", (inventario_id,)).fetchone()
        if producto_actualizado and producto_actualizado['CANTIDAD'] <= producto_actualizado['MINIMO']:
            enviar_alerta_stock(producto_actualizado)
            flash(f"⚠️ {producto_actualizado['DESCRIPCION']} está en stock bajo", "warning")
        
        conn.close()
        
        flash(f"✅ {cantidad} unidades asignadas al proyecto correctamente", "success")
        return redirect(url_for("detalle_proyecto", id=proyecto_id))
    
    # Obtener productos disponibles
    productos = conn.execute("SELECT * FROM inventario WHERE CANTIDAD > 0 ORDER BY DESCRIPCION").fetchall()
    conn.close()
    
    return render_template("asignar_items.html", proyecto=proyecto, productos=productos)


@app.route("/devolver_item/<int:asignacion_id>", methods=["POST"])
def devolver_item(asignacion_id):
    cantidad_devolver = int(request.form.get("cantidad", 0))
    
    if cantidad_devolver <= 0:
        flash("Cantidad inválida", "danger")
        return redirect(request.referrer)
    
    conn = get_db_connection()
    
    # Obtener información de la asignación
    asignacion = conn.execute("""
        SELECT pi.*, u.nombre as proyecto_nombre, i.CODIGO, i.DESCRIPCION
        FROM proyecto_items pi
        JOIN ubicaciones u ON pi.proyecto_id = u.id
        JOIN inventario i ON pi.inventario_id = i.id
        WHERE pi.id = ?
    """, (asignacion_id,)).fetchone()
    
    if not asignacion:
        conn.close()
        flash("Asignación no encontrada", "danger")
        return redirect(request.referrer)
    
    if cantidad_devolver > asignacion['cantidad_asignada']:
        flash(f"No puedes devolver más de {asignacion['cantidad_asignada']} unidades", "danger")
        conn.close()
        return redirect(request.referrer)
    
    # Actualizar cantidad asignada
    nueva_cantidad_asignada = asignacion['cantidad_asignada'] - cantidad_devolver
    
    if nueva_cantidad_asignada == 0:
        # Eliminar asignación si se devuelve todo
        conn.execute("DELETE FROM proyecto_items WHERE id = ?", (asignacion_id,))
    else:
        # Actualizar cantidad
        conn.execute("UPDATE proyecto_items SET cantidad_asignada = ? WHERE id = ?", 
                    (nueva_cantidad_asignada, asignacion_id))
    
    # Devolver al stock
    conn.execute("""
        UPDATE inventario 
        SET CANTIDAD = CANTIDAD + ? 
        WHERE id = ?
    """, (cantidad_devolver, asignacion['inventario_id']))
    
    # Registrar movimiento
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO movimientos (inventario_id, tipo, cantidad, fecha, observacion, proyecto)
        VALUES (?, 'entrada', ?, ?, ?, ?)
    """, (asignacion['inventario_id'], cantidad_devolver, fecha, 
          f"Devuelto desde proyecto", asignacion['proyecto_nombre']))
    
    conn.commit()
    conn.close()
    
    flash(f"✅ {cantidad_devolver} unidades devueltas al stock correctamente", "success")
    return redirect(request.referrer)


@app.route("/eliminar_proyecto/<int:id>", methods=["POST"])
def eliminar_proyecto(id):
    conn = get_db_connection()
    proyecto = conn.execute("SELECT * FROM ubicaciones WHERE id = ?", (id,)).fetchone()
    
    if not proyecto:
        conn.close()
        flash("Proyecto no encontrado", "danger")
        return redirect(url_for("crear_proyecto"))
    
    # Obtener todos los items asignados al proyecto
    items_asignados = conn.execute("""
        SELECT pi.*, i.CODIGO, i.DESCRIPCION
        FROM proyecto_items pi
        JOIN inventario i ON pi.inventario_id = i.id
        WHERE pi.proyecto_id = ?
    """, (id,)).fetchall()
    
    # Devolver todos los productos al stock
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in items_asignados:
        # Devolver al stock
        conn.execute("""
            UPDATE inventario 
            SET CANTIDAD = CANTIDAD + ? 
            WHERE id = ?
        """, (item['cantidad_asignada'], item['inventario_id']))
        
        # Registrar movimiento
        conn.execute("""
            INSERT INTO movimientos (inventario_id, tipo, cantidad, fecha, observacion, proyecto)
            VALUES (?, 'entrada', ?, ?, ?, ?)
        """, (item['inventario_id'], item['cantidad_asignada'], fecha, 
              f"Devuelto por eliminación de proyecto", proyecto['nombre']))
    
    # Eliminar todas las asignaciones del proyecto
    conn.execute("DELETE FROM proyecto_items WHERE proyecto_id = ?", (id,))
    
    # Eliminar el proyecto
    conn.execute("DELETE FROM ubicaciones WHERE id = ?", (id,))
    
    conn.commit()
    conn.close()
    
    flash(f"✅ Proyecto '{proyecto['nombre']}' eliminado. Productos devueltos al stock.", "success")
    return redirect(url_for("crear_proyecto"))


# ============================================
# ⬆️ FIN DE LAS NUEVAS RUTAS ⬆️
# ============================================

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    init_db()
    app.run(host="10.1.3.105", port=5000, debug=True)