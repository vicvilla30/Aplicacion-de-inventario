from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import os
import uuid
import pandas as pd
import smtplib
import unicodedata
from email.message import EmailMessage

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
app.secret_key = "supersecretkey"

# Quitar acentos para búsqueda insensible a tildes
def quitar_acentos(txt):
    if txt is None:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')

# Conexión a DB
def get_db_connection():
    conn = sqlite3.connect("inventario.db")
    conn.row_factory = sqlite3.Row
    conn.create_function("quitar_acentos", 1, quitar_acentos)
    return conn

# Crear tabla
def init_db():
    conn = get_db_connection()
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
    conn.commit()
    conn.close()

# helpers para conversion segura
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

# ------------------------------
# Enviar correo de stock bajo
# ------------------------------
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

# ------------------------------
# Rutas
# ------------------------------

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

    return render_template("index.html",
        items=items,
        ubicacion_filtro=ubicacion_filtro,
        busqueda=busqueda,
        low_count=low_count
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

# Agregar producto
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
        return redirect(url_for("index"))
    return render_template("agregar.html")

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
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

        conn.execute("""UPDATE inventario SET 
            MARCA=?, CODIGO=?, DESCRIPCION=?, CANTIDAD=?, MINIMO=?, UBICACION=?, SERIAL=?,
            PRECIO_COSTO=?, PRECIO_DIST=?, PRECIO_INT=?, PRECIO_GENERAL=?, IMAGEN=?
            WHERE id=?""",
            (marca, codigo, descripcion, cantidad, minimo, ubicacion, serial,
             precio_costo, precio_dist, precio_int, precio_general, imagen, id)
        )
        conn.commit()

        producto_actualizado = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
        if producto_actualizado and producto_actualizado["CANTIDAD"] <= producto_actualizado["MINIMO"]:
            enviar_alerta_stock(producto_actualizado)

        conn.close()
        return redirect(url_for("index"))
    conn.close()
    return render_template("editar.html", item=item)

@app.route("/eliminar/<int:id>")
def eliminar(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM inventario WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/detalle/<int:id>")
def detalle(id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM inventario WHERE id = ?", (id,)).fetchone()
    conn.close()
    return render_template("detalle.html", item=item)

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

if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    init_db()
    app.run(host="10.1.3.105", port=5000, debug=True)