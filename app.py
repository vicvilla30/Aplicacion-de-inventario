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
    
    # Tabla ubicaciones
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ubicaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL,
        tipo TEXT DEFAULT 'FIJA',
        activa INTEGER DEFAULT 1
    )
    """)
    
    # Insertar ubicaciones por defecto
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
    ubicacion_filtro = request.args.get("ubicacion", "").strip()
    busqueda = request.args.get("busqueda", "").strip()
    solo_bajo_stock = request.args.get("solo_bajo_stock", "")
    conn = get_db_connection()
    query = "SELECT * FROM inventario WHERE 1=1"
    params = []
    if ubicacion_filtro:
        filtro_clean = quitar_acentos(ubicacion_filtro)
        query += " AND quitar_acentos(UBICACION) LIKE ? COLLATE NOCASE"
        params.append(f"%{filtro_clean}%")
    if busqueda:
        busqueda_clean = quitar_acentos(busqueda)
        query += (
            " AND (quitar_acentos(CODIGO) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(DESCRIPCION) LIKE ? COLLATE NOCASE "
            "OR quitar_acentos(MARCA) LIKE ? COLLATE NOCASE)"
        )
        params.extend([f"%{busqueda_clean}%", f"%{busqueda_clean}%", f"%{busqueda_clean}%"])
    if solo_bajo_stock:
        query += " AND CANTIDAD <= MINIMO"
    items = conn.execute(query, params).fetchall()
    conn.close()
    low_count = sum(1 for item in items if item["CANTIDAD"] <= item["MINIMO"])
    
    ubicaciones_fijas, proyectos = obtener_ubicaciones()
    
    return render_template("index.html",
        items=items,
        ubicacion_filtro=ubicacion_filtro,
        busqueda=busqueda,
        low_count=low_count,
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

        if not nombre:
            flash("El nombre del proyecto es obligatorio", "warning")
        else:
            conn = get_db_connection()
            try:
                conn.execute(
                    "INSERT INTO ubicaciones (nombre, tipo) VALUES (?, 'PROYECTO')",
                    (nombre,)
                )
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
        ORDER BY nombre DESC
    """).fetchall()
    conn.close()
    
    return render_template("crear_proyecto.html", proyectos=proyectos)

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
    ubicacion_filtro = request.args.get("ubicacion", "")
    busqueda = request.args.get("busqueda", "")
    conn = get_db_connection()
    query = "SELECT * FROM inventario WHERE 1=1"
    params = []
    if ubicacion_filtro:
        filtro_clean = quitar_acentos(ubicacion_filtro)
        query += " AND quitar_acentos(UBICACION) LIKE ? COLLATE NOCASE"
        params.append(f"%{filtro_clean}%")
    if busqueda:
        query += " AND (CODIGO LIKE ? COLLATE NOCASE OR DESCRIPCION LIKE ? COLLATE NOCASE OR MARCA LIKE ? COLLATE NOCASE)"
        params.extend([f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%"])
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
            
            columnas_requeridas = ['MARCA', 'CODIGO', 'DESCRIPCION']
            columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
            
            if columnas_faltantes:
                flash(f"Faltan columnas requeridas: {', '.join(columnas_faltantes)}", "danger")
                return redirect(url_for("importar"))
            
            conn = get_db_connection()
            insertados = 0
            actualizados = 0
            errores = []
            
            for index, row in df.iterrows():
                try:
                    existe = conn.execute(
                        "SELECT id FROM inventario WHERE CODIGO = ?", 
                        (str(row['CODIGO']),)
                    ).fetchone()
                    
                    datos = {
                        'marca': str(row.get('MARCA', '')),
                        'codigo': str(row.get('CODIGO', '')),
                        'descripcion': str(row.get('DESCRIPCION', '')),
                        'cantidad': to_int(row.get('CANTIDAD', 0)),
                        'minimo': to_int(row.get('MINIMO', 0)),
                        'ubicacion': str(row.get('UBICACION', 'BODEGA')),
                        'serial': str(row.get('SERIAL', '')),
                        'precio_costo': to_float(row.get('PRECIO_COSTO', 0)),
                        'precio_dist': to_float(row.get('PRECIO_DIST', 0)),
                        'precio_int': to_float(row.get('PRECIO_INT', 0)),
                        'precio_general': to_float(row.get('PRECIO_GENERAL', 0)),
                    }
                    
                    if existe:
                        conn.execute("""
                            UPDATE inventario SET 
                                MARCA=?, DESCRIPCION=?, CANTIDAD=?, MINIMO=?, 
                                UBICACION=?, SERIAL=?, PRECIO_COSTO=?, PRECIO_DIST=?, 
                                PRECIO_INT=?, PRECIO_GENERAL=?
                            WHERE CODIGO=?
                        """, (
                            datos['marca'], datos['descripcion'], datos['cantidad'],
                            datos['minimo'], datos['ubicacion'], datos['serial'],
                            datos['precio_costo'], datos['precio_dist'], datos['precio_int'],
                            datos['precio_general'], datos['codigo']
                        ))
                        actualizados += 1
                    else:
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
                    errores.append(f"Fila {index + 2}: {str(e)}")
            
            conn.commit()
            conn.close()
            
            mensaje = f"✅ Importación completa: {insertados} insertados, {actualizados} actualizados"
            if errores:
                mensaje += f". {len(errores)} errores."
                for err in errores[:5]:
                    flash(err, "warning")
            
            flash(mensaje, "success")
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
    
    # Convertir a DataFrame
    df = pd.DataFrame([dict(item) for item in items])
    
    # Seleccionar solo las columnas necesarias (sin id ni IMAGEN)
    columnas_exportar = [
        'MARCA', 'CODIGO', 'DESCRIPCION', 'CANTIDAD', 'MINIMO', 
        'UBICACION', 'SERIAL', 'PRECIO_COSTO', 'PRECIO_DIST', 
        'PRECIO_INT', 'PRECIO_GENERAL'
    ]
    df = df[columnas_exportar]
    
    export_path = os.path.join("static", "inventario_LSI.xlsx")
    df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True)

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    init_db()
    app.run(host="10.1.3.105", port=5000, debug=True)