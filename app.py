import base64
import datetime
from datetime import datetime, timedelta
import os
import random
import re
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from flask_mail import Mail, Message
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import mysql.connector
import requests
from twilio.rest import Client
import json
from werkzeug.utils import secure_filename

# 1. Crear la instancia única de Flask
app = Flask(__name__)

# 2. Configuración global de CORS para TODAS las rutas
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

GOOGLE_CLIENT_ID = (
    "144324961012-sv6ggpbi9gn0sc3f6jap6n9ckkfhcc5q.apps.googleusercontent.com"
)

# -------------------------------------------------------------------
# CONFIGURACIÓN DE BASE DE DATOS
# -------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "kova_db",
    "charset": "utf8mb4",
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# --- Configuración de Flask-Mail (Gmail) ---
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USERNAME"] = "kevinurielremigioelizalde@gmail.com"
app.config["MAIL_PASSWORD"] = "mwfr xqhn nfmm cymk"
app.config["MAIL_DEFAULT_SENDER"] = (
    "KOVA",
    "kevinurielremigioelizalde@gmail.com",
)
app.config["MAIL_ASCII_ATTACHMENTS"] = False
app.config["MAIL_CHARSET"] = "utf-8"

mail = Mail(app)

# --- Configuración de Carpetas de Carga ---
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
GENERADOS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'generados')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERADOS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERADOS_FOLDER'] = GENERADOS_FOLDER


# -------------------------------------------------------------------
# ENDPOINTS DE AUTENTICACIÓN Y USUARIOS
# -------------------------------------------------------------------

@app.route("/api/google_login", methods=["POST", "OPTIONS"])
def google_login():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json() or {}
        token = data.get("credential")

        if not token:
            return jsonify({"success": False, "message": "Token no proporcionado."}), 400

        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )

        email = idinfo.get("email")
        nombre = idinfo.get("name")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM usuarios WHERE correo_electronico = %s", (email,))
        usuario = cursor.fetchone()

        if not usuario:
            cursor.execute(
                "INSERT INTO usuarios (nombre_completo, correo_electronico) VALUES (%s, %s)",
                (nombre, email),
            )
            conn.commit()
            cursor.execute("SELECT * FROM usuarios WHERE correo_electronico = %s", (email,))
            usuario = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Inicio de sesión con Google exitoso.",
            "redirect": "kova_usuarios.html",
            "user": usuario,
        }), 200

    except Exception as e:
        print("Error en google_login:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return "", 200

    try:
        data = request.get_json() or {}
        nombre = data.get('nombre_completo', '').strip()
        correo = data.get('correo_electronico', '').strip()
        telefono = data.get('telefono', '').strip()
        contrasena = data.get('contrasena', '').strip()
        tipo_usuario = data.get('tipo_usuario', 'Titular de mascota').strip()

        if not nombre or not correo or not contrasena:
            return jsonify({
                "success": False,
                "message": "Por favor completa todos los campos obligatorios."
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_usuario FROM usuarios WHERE correo_electronico = %s", (correo,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({
                "success": False,
                "message": "El correo electrónico ya está registrado."
            }), 400

        query = """
            INSERT INTO usuarios (nombre_completo, correo_electronico, telefono, contrasena, tipo_usuario)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (nombre, correo, telefono, contrasena, tipo_usuario))
        conn.commit()
        
        nuevo_id = cursor.lastrowid

        cursor.execute("SELECT id_usuario, nombre_completo, correo_electronico, telefono, tipo_usuario FROM usuarios WHERE id_usuario = %s", (nuevo_id,))
        usuario = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "¡Cuenta creada con éxito!",
            "user": usuario,
            "tipo_usuario": tipo_usuario
        }), 200

    except Exception as e:
        print("Error en /api/register:", str(e))
        return jsonify({
            "success": False,
            "message": f"Error en el servidor: {str(e)}"
        }), 500
    

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return "", 200

    try:
        data = request.get_json() or {}
        correo = data.get('correo_electronico', '').strip()
        contrasena = data.get('contrasena', '').strip()

        if not correo or not contrasena:
            return jsonify({
                "success": False,
                "message": "Por favor ingresa correo y contraseña."
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT id_usuario, nombre_completo, correo_electronico, telefono, tipo_usuario 
            FROM usuarios 
            WHERE correo_electronico = %s AND contrasena = %s
        """
        cursor.execute(query, (correo, contrasena))
        usuario = cursor.fetchone()

        cursor.close()
        conn.close()

        if usuario:
            tipo_usuario = usuario.get('tipo_usuario', 'Titular de mascota').strip()
            return jsonify({
                "success": True,
                "message": f"¡Bienvenido de nuevo, {usuario['nombre_completo']}!",
                "user": usuario,
                "tipo_usuario": tipo_usuario
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Correo o contraseña incorrectos."
            }), 401

    except Exception as e:
        print("Error en /api/login:", str(e))
        return jsonify({
            "success": False,
            "message": f"Error en el servidor: {str(e)}"
        }), 500


# -------------------------------------------------------------------
# ENDPOINTS DE MASCOTAS E HISTORIAL
# -------------------------------------------------------------------

@app.route('/api/registrar_mascota', methods=['POST', 'OPTIONS'])
def registrar_mascota():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json() or {}
        
        usuario_id = data.get('usuario_id')
        nombre_mascota = data.get('nombre_mascota')
        fecha_nacimiento = data.get('fecha_nacimiento') or None
        raza = data.get('raza', '')
        color = data.get('color')
        peso_kg = data.get('peso_kg') or None
        imagen = data.get('imagen', '')
        token_nfc = data.get('token_nfc', '')
        nom_tutor = data.get('nom_tutor', '')
        tel_cont_1 = data.get('tel_cont_1', '')
        tel_cont_2 = data.get('tel_cont_2', '')
        tel_cont_3 = data.get('tel_cont_3', '')
        tel_cont_4 = data.get('tel_cont_4', '')
        tel_cont_5 = data.get('tel_cont_5', '')
        descripcion = data.get('descripcion', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO registro_mascota 
            (id_usuario, nombre_mascota, fecha_nacimiento, raza, color, peso_kg, imagen, token_nfc, nom_tutor, 
             tel_cont_1, tel_cont_2, tel_cont_3, tel_cont_4, tel_cont_5, descripcion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            usuario_id, nombre_mascota, fecha_nacimiento, raza, color, peso_kg, imagen, token_nfc, nom_tutor,
            tel_cont_1, tel_cont_2, tel_cont_3, tel_cont_4, tel_cont_5, descripcion
        )

        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Mascota registrada exitosamente."}), 200

    except Exception as e:
        print("Error en /api/registrar_mascota:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/mascotas/<int:usuario_id>', methods=['GET'])
def obtener_mascotas_usuario(usuario_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                id_mascota, id_usuario, nombre_mascota, fecha_nacimiento, color,
                peso_kg, imagen, token_nfc, nom_tutor, tel_cont_1, tel_cont_2,
                tel_cont_3, tel_cont_4, tel_cont_5, descripcion, fecha_registro
            FROM registro_mascota 
            WHERE id_usuario = %s
            ORDER BY id_mascota DESC
        """
        cursor.execute(query, (usuario_id,))
        mascotas = cursor.fetchall()

        cursor.close()
        conn.close()

        for m in mascotas:
            for k, v in m.items():
                if hasattr(v, 'isoformat'):
                    m[k] = v.isoformat()

        return jsonify({"status": "success", "mascotas": mascotas}), 200

    except Exception as e:
        print("Error en /api/mascotas:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/editar_mascota/<int:mascota_id>", methods=["POST", "PUT", "OPTIONS"])
def editar_mascota(mascota_id):
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json() or {}
        nombre_mascota = data.get("nombre_mascota")
        fecha_nacimiento = data.get("fecha_nacimiento") or None
        color = data.get("color")
        peso_kg = data.get("peso_kg") or None
        imagen = data.get("imagen")
        token_nfc = data.get("token_nfc")
        nom_tutor = data.get("nom_tutor")
        tel_cont_1 = data.get("tel_cont_1")
        tel_cont_2 = data.get("tel_cont_2")
        tel_cont_3 = data.get("tel_cont_3")
        tel_cont_4 = data.get("tel_cont_4")
        tel_cont_5 = data.get("tel_cont_5")
        descripcion = data.get("descripcion")
        raza = data.get('raza', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        if imagen and len(str(imagen).strip()) > 0:
            query = """
                UPDATE registro_mascota
                SET nombre_mascota=%s, fecha_nacimiento=%s, color=%s, peso_kg=%s, imagen=%s, token_nfc=%s, nom_tutor=%s, tel_cont_1=%s, tel_cont_2=%s, tel_cont_3=%s, tel_cont_4=%s, tel_cont_5=%s, descripcion=%s, raza=%s
                WHERE id_mascota=%s
            """
            cursor.execute(query, (nombre_mascota, fecha_nacimiento, color, peso_kg, imagen, token_nfc, nom_tutor, tel_cont_1, tel_cont_2, tel_cont_3, tel_cont_4, tel_cont_5, descripcion, raza, mascota_id))
        else:
            query = """
                UPDATE registro_mascota
                SET nombre_mascota=%s, fecha_nacimiento=%s, color=%s, peso_kg=%s, token_nfc=%s, nom_tutor=%s, tel_cont_1=%s, tel_cont_2=%s, tel_cont_3=%s, tel_cont_4=%s, tel_cont_5=%s, descripcion=%s, raza=%s
                WHERE id_mascota=%s
            """
            cursor.execute(query, (nombre_mascota, fecha_nacimiento, color, peso_kg, token_nfc, nom_tutor, tel_cont_1, tel_cont_2, tel_cont_3, tel_cont_4, tel_cont_5, descripcion, raza, mascota_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Datos de la mascota actualizados exitosamente."
        }), 200

    except Exception as err:
        print("Error en /api/editar_mascota:", str(err))
        return jsonify({"status": "error", "message": str(err)}), 400


# -------------------------------------------------------------------
# ENDPOINTS DE PRODUCTOS Y VENDEDOR (ACTUALIZADOS CON NOMBRES ÚNICOS)
# -------------------------------------------------------------------

@app.route('/api/registrar_producto', methods=['POST'])
def registrar_producto():
    try:
        id_vendedor = request.form.get('id_vendedor')
        nombre = request.form.get('nombre_producto')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        cantidad = request.form.get('cantidad')
        nombre_proveedor = request.form.get('nombre_proveedor')
        contacto_proveedor = request.form.get('contacto_proveedor')

        imgs = []
        for i in range(1, 6):
            file = request.files.get(f'imagen_{i}')
            if file and file.filename != '':
                # Nombre único con timestamp para evitar colisiones
                filename = f"{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                imgs.append(filename)
            else:
                imgs.append(None)

        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO productos_vendedor 
            (id_vendedor, nombre_producto, descripcion, precio, cantidad, imagen_1, imagen_2, imagen_3, imagen_4, imagen_5, nombre_proveedor, contacto_proveedor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            id_vendedor, nombre, descripcion, precio, cantidad, 
            imgs[0], imgs[1], imgs[2], imgs[3], imgs[4], 
            nombre_proveedor, contacto_proveedor
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Producto registrado correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/productos', methods=['GET'])
def obtener_productos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM productos_vendedor ORDER BY fecha_registro DESC")
        productos = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "productos": productos}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/comprar_producto', methods=['POST'])
def comprar_producto():
    try:
        data = request.get_json() or {}
        id_producto = data.get('id_producto')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT cantidad FROM productos_vendedor WHERE id_producto = %s", (id_producto,))
        prod = cursor.fetchone()
        
        if not prod:
            return jsonify({"status": "error", "message": "Producto no encontrado"}), 404
            
        stock_actual = int(prod['cantidad'])
        if stock_actual > 0:
            nuevo_stock = stock_actual - 1
            cursor.execute("UPDATE productos_vendedor SET cantidad = %s WHERE id_producto = %s", (nuevo_stock, id_producto))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success", "message": "Compra realizada con éxito", "stock_restante": nuevo_stock}), 200
        else:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Producto agotado"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/actualizar_producto/<int:id_producto>', methods=['POST'])
def actualizar_producto(id_producto):
    try:
        nombre = request.form.get('nombre_producto')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        cantidad = request.form.get('cantidad')
        nombre_proveedor = request.form.get('nombre_proveedor')
        contacto_proveedor = request.form.get('contacto_proveedor')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Actualizar campos de texto básicos mediante id_producto exacto
        query = """
            UPDATE productos_vendedor 
            SET nombre_producto = %s, descripcion = %s, precio = %s, cantidad = %s, nombre_proveedor = %s, contacto_proveedor = %s
            WHERE id_producto = %s
        """
        cursor.execute(query, (nombre, descripcion, precio, cantidad, nombre_proveedor, contacto_proveedor, id_producto))

        # Actualizar imágenes solo si se adjuntaron nuevas
        for i in range(1, 6):
            file = request.files.get(f'imagen_{i}')
            if file and file.filename != '':
                filename = f"{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                cursor.execute(f"UPDATE productos_vendedor SET imagen_{i} = %s WHERE id_producto = %s", (filename, id_producto))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Producto actualizado correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# -------------------------------------------------------------------
# OTROS ENDPOINTS (RECUPERACIÓN, HISTORIAL, ALERTAS, IA)
# -------------------------------------------------------------------

@app.route("/api/request-reset-code", methods=["POST", "OPTIONS"])
def request_reset_code():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json() or {}
        correo_electronico = data.get("correo_electronico")

        if not correo_electronico:
            return jsonify({"success": False, "message": "El correo es requerido"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT correo_electronico FROM usuarios WHERE correo_electronico = %s", (correo_electronico,))
        usuario = cursor.fetchone()

        if not usuario:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "El correo no esta registrado"}), 404

        code = str(random.randint(100000, 999999))
        expires_at = datetime.now() + timedelta(minutes=15)

        cursor.execute(
            """
                UPDATE usuarios
                SET reset_code = %s, reset_code_expires = %s
                WHERE correo_electronico = %s
            """,
            (code, expires_at, correo_electronico),
        )
        conn.commit()
        cursor.close()
        conn.close()

        msg = Message()
        msg.subject = "Codigo de Verificacion KOVA"
        msg.recipients = [correo_electronico]
        msg.body = f"Hola,\n\nTu codigo de verificacion para restablecer tu contrasena en KOVA es: {code}\n\nEste codigo expira en 15 minutos."
        msg.charset = "utf-8"

        mail.send(msg)

        return jsonify({"success": True, "message": "Codigo enviado exitosamente al correo"}), 200

    except Exception as e:
        mensaje_error = str(e).encode("ascii", errors="ignore").decode("utf-8")
        return jsonify({"success": False, "message": f"Error en el servidor: {mensaje_error}"}), 500


@app.route("/api/verify-reset-code", methods=["POST", "OPTIONS"])
def verify_reset_code():
    if request.method == "OPTIONS":
        return "", 200

    try:
        data = request.get_json() or {}
        correo_electronico = data.get("correo_electronico")
        codigo = data.get("codigo")
        nueva_contrasena = data.get("nueva_contrasena")

        if not all([correo_electronico, codigo, nueva_contrasena]):
            return jsonify({"success": False, "message": "Todos los campos son obligatorios"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
                SELECT reset_code, reset_code_expires
                FROM usuarios
                WHERE correo_electronico = %s
            """,
            (correo_electronico,),
        )
        usuario = cursor.fetchone()

        if not usuario or usuario["reset_code"] != codigo:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "Codigo de verificacion incorrecto"}), 400

        if datetime.now() > usuario["reset_code_expires"]:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "El codigo ha expirado. Solicita uno nuevo"}), 400

        cursor.execute(
            """
                UPDATE usuarios
                SET contrasena = %s, reset_code = NULL, reset_code_expires = NULL
                WHERE correo_electronico = %s
            """,
            (nueva_contrasena, correo_electronico),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Contrasena actualizada correctamente"}), 200

    except Exception as e:
        mensaje_error = str(e).encode("ascii", errors="ignore").decode("utf-8")
        return jsonify({"success": False, "message": f"Error en el servidor: {mensaje_error}"}), 500


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/actualizar_historial', methods=['POST', 'OPTIONS'])
def actualizar_historial():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        id_mascota = request.form.get('id_mascota', 1)
        
        cursor.execute("SELECT * FROM registro_mascota WHERE id_mascota = %s", (id_mascota,))
        pet_data = cursor.fetchone()

        nombre_mascota = request.form.get('nombre_mascota') or (pet_data[2] if pet_data else '')
        sexo = request.form.get('sexo', 'Macho')
        fecha_nacimiento = request.form.get('fecha_nacimiento') or (pet_data[3] if pet_data else None)
        peso = request.form.get('peso') or (pet_data[5] if pet_data else None)
        raza = request.form.get('raza', '')
        color = request.form.get('color') or (pet_data[4] if pet_data else '')
        esterilizado = request.form.get('esterilizado', 'No (Entero)')
        senas_particulares = request.form.get('senas_particulares') or (pet_data[13] if pet_data else '')

        nombre_tutor = request.form.get('nombre_tutor') or (pet_data[9] if pet_data else '')
        telefono_1 = request.form.get('telefono_1') or (pet_data[10] if pet_data else '')
        telefono_2 = request.form.get('telefono_2') or (pet_data[11] if pet_data else '')
        
        email_tutor = request.form.get('email_tutor', '')
        direccion_tutor = request.form.get('direccion', '')

        actividad_medica = request.form.get('actividad_medica', '')
        subopcion_medica = request.form.get('subopcion_medica', '')

        form_data_dict = {key: value for key, value in request.form.items() 
                          if key not in ['id_mascota', 'nombre_mascota', 'sexo', 'fecha_nacimiento', 
                                         'peso', 'raza', 'color', 'esterilizado', 'senas_particulares', 
                                         'nombre_tutor', 'telefono_1', 'telefono_2', 'email_tutor', 
                                         'direccion', 'actividad_medica', 'subopcion_medica']}
        
        detalles_json = json.dumps(form_data_dict)
        consulta_fecha = datetime.now()

        consulta_imagen_nombre = None
        if 'consulta_imagen' in request.files:
            file = request.files['consulta_imagen']
            if file and file.filename != '':
                filename = f"{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                consulta_imagen_nombre = filename

        query = """
            INSERT INTO historial_clinico (
                id_mascota, nombre_mascota, sexo, fecha_nacimiento, peso, raza, color, esterilizado, senas_particulares,
                nombre_tutor, telefono_1, telefono_2, email_tutor, direccion_tutor,
                actividad_medica, subopcion_medica, detalles_formulario,
                consulta_fecha, consulta_imagen
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
        """

        values = (
            id_mascota, nombre_mascota, sexo, fecha_nacimiento, peso, raza, color, esterilizado, senas_particulares,
            nombre_tutor, telefono_1, telefono_2, email_tutor, direccion_tutor,
            actividad_medica, subopcion_medica, detalles_json,
            consulta_fecha, consulta_imagen_nombre
        )

        cursor.execute(query, values)
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Historial y datos específicos guardados correctamente"}), 200

    except Exception as e:
        print("Error en /actualizar_historial:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/obtener_historial/<int:id_mascota>', methods=['GET'])
def obtener_historial(id_mascota):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT 
                h.*,
                m.nombre_mascota AS nombre_registrado,
                m.fecha_nacimiento AS fecha_nac_registrada,
                m.color AS color_registrado,
                m.peso_kg AS peso_registrado
            FROM historial_clinico h
            INNER JOIN registro_mascota m ON h.id_mascota = m.id_mascota
            WHERE h.id_mascota = %s
            ORDER BY h.id_historial_clinico DESC
        """
        cursor.execute(query, (id_mascota,))
        registros = cursor.fetchall()

        cursor.close()
        conn.close()

        for r in registros:
            if not r.get('fecha_nacimiento') and r.get('fecha_nac_registrada'):
                r['fecha_nacimiento'] = r['fecha_nac_registrada']
            
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()

        return jsonify({"status": "success", "data": registros}), 200

    except Exception as e:
        print("Error en /obtener_historial:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/enviar_alerta_geocerca', methods=['POST', 'OPTIONS'])
def enviar_alerta_geocerca():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json() or {}
        nombre_mascota = data.get('nombre_mascota', 'Mascota')
        tutor = data.get('tutor', 'Tutor')
        email_tutor = data.get('email', 'kevinurielremigioelizalde@gmail.com')
        telefono = data.get('telefono', 'N/A')
        token_nfc = data.get('token_nfc', 'N/A')
        fecha = data.get('fecha', '')
        hora = data.get('hora', '')

        msg = Message()
        msg.subject = f"🚨 URGENTE: Alerta de Geocerca - {nombre_mascota} fuera de perímetro"
        msg.recipients = [email_tutor]
        msg.body = (
            f"Hola {tutor},\n\n"
            f"El sistema de rastreo IoT KOVA ha detectado una incidencia de seguridad:\n\n"
            f"⚠️ Tu familiar '{nombre_mascota}' ha salido del perímetro establecido.\n\n"
            f"📅 Fecha del evento: {fecha}\n"
            f"⏰ Hora del evento: {hora}\n\n"
            f"📋 INFORMACIÓN DE LA MASCOTA:\n"
            f"- Nombre: {nombre_mascota}\n"
            f"- Tutor a cargo: {tutor}\n"
            f"- Teléfono de contacto: {telefono}\n"
            f"- Token de rastreo NFC: {token_nfc}\n\n"
            f"Por favor, verifique el mapa en su panel de usuario de KOVA.\n\n"
            f"Atentamente,\n"
            f"Sistema de Seguridad KOVA IoT"
        )
        msg.charset = 'utf-8'

        mail.send(msg)

        return jsonify({"status": "success", "message": "Alerta enviada por correo exitosamente."}), 200

    except Exception as e:
        print("Error al enviar correo de alerta:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


def ejecutar_ia_propia(input_path, output_path, efecto):
    import shutil
    shutil.copyfile(input_path, output_path) 
    return True 


@app.route('/api/subir_y_procesar_ia', methods=['POST'])
def subir_y_procesar_ia():
    if 'imagen' not in request.files:
        return jsonify({'status': 'error', 'message': 'No se adjuntó archivo'}), 400
    
    file = request.files['imagen']
    id_mascota = request.form.get('id_mascota')
    efecto = request.form.get('efecto', 'filtro_generico')
    descripcion = request.form.get('descripcion', 'Efecto generado con KOVA-IA')

    if file.filename == '' or not id_mascota:
        return jsonify({'status': 'error', 'message': 'Faltan datos'}), 400

    filename_original = f"{int(datetime.now().timestamp())}_{secure_filename(file.filename)}"
    filepath_original = os.path.join(app.config['UPLOAD_FOLDER'], filename_original)
    file.save(filepath_original)

    nombre_generado = f"ia_{efecto}_{id_mascota}_{filename_original}"
    filepath_generado = os.path.join(app.config['GENERADOS_FOLDER'], nombre_generado)
    
    ejecutar_ia_propia(filepath_original, filepath_generado, efecto)

    tipo = 'video' if filepath_generado.endswith(('.mp4', '.avi')) else 'imagen'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        INSERT INTO galeria_ia (id_mascota, tipo_archivo, nombre_archivo, titulo_efecto, descripcion_efecto)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (id_mascota, tipo, nombre_generado, efecto, descripcion))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'status': 'success',
        'message': 'IA ejecutada correctamente',
        'archivo': nombre_generado,
        'tipo': tipo
    }), 200


@app.route('/api/galeria/<int:id_mascota>')
def obtener_galeria(id_mascota):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT * FROM galeria_ia WHERE id_mascota = %s ORDER BY fecha_creacion DESC"
    cursor.execute(query, (id_mascota,))
    galeria = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify({'status': 'success', 'galeria': galeria}), 200


@app.route('/static/generados/<filename>')
def servir_generados(filename):
    return send_from_directory(app.config['GENERADOS_FOLDER'], filename)


@app.route('/api/actualizar_foto_perfil_ia', methods=['POST'])
def actualizar_foto_perfil_ia():
    data = request.get_json()
    id_mascota = data.get('id_mascota')
    nombre_archivo = data.get('nombre_archivo')

    if not id_mascota or not nombre_archivo:
        return jsonify({'status': 'error', 'message': 'Datos incompletos'}), 400

    nueva_ruta_imagen = f"static/generados/{nombre_archivo}"

    conn = get_db_connection()
    cursor = conn.cursor()
    query = "UPDATE registro_mascota SET imagen = %s WHERE id_mascota = %s"
    cursor.execute(query, (nueva_ruta_imagen, id_mascota))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Foto de perfil actualizada'}), 200

# --- 4. ELIMINAR PRODUCTO ---
@app.route('/api/eliminar_producto/<int:id_producto>', methods=['DELETE', 'OPTIONS'])
def eliminar_producto(id_producto):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM productos_vendedor WHERE id_producto = %s", (id_producto,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "Producto eliminado correctamente"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



if __name__ == "__main__":
    app.run(debug=True, port=5000)