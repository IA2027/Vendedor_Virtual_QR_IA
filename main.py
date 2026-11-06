
import os
import sqlite3
import io

from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from google import genai
import qrcode


# =====================================
# CONFIGURACION
# =====================================

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

client = genai.Client(api_key=API_KEY) if API_KEY else None

DB_NAME = "tienda.db"


# =====================================
# CONEXION BASE DE DATOS
# =====================================

def conectar_db():

    conexion = sqlite3.connect(DB_NAME)

    conexion.row_factory = sqlite3.Row

    return conexion


# =====================================
# CREAR TABLA Y PRODUCTOS
# =====================================

def inicializar_db():

    conexion = conectar_db()

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS productos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT NOT NULL,

            descripcion TEXT,

            precio REAL NOT NULL,

            stock INTEGER NOT NULL DEFAULT 0

        )
    """)

    cantidad = conexion.execute(
        "SELECT COUNT(*) FROM productos"
    ).fetchone()[0]

    if cantidad == 0:

        productos = [

            (
                "Notebook Lenovo",
                "16 GB RAM y SSD de 512 GB",
                850000,
                5
            ),

            (
                "Mouse Logitech",
                "Mouse inalámbrico USB",
                25000,
                15
            ),

            (
                "Teclado Gamer",
                "Teclado mecánico RGB",
                65000,
                8
            ),

            (
                "Monitor Samsung",
                "Monitor LED de 24 pulgadas Full HD",
                220000,
                3
            ),

            (
                "Auriculares Bluetooth",
                "Auriculares inalámbricos con micrófono",
                45000,
                12
            )

        ]

        conexion.executemany("""
            INSERT INTO productos
            (nombre, descripcion, precio, stock)
            VALUES (?, ?, ?, ?)
        """, productos)

    conexion.commit()

    conexion.close()


# =====================================
# OBTENER PRODUCTOS
# =====================================

def obtener_productos():

    conexion = conectar_db()

    productos = conexion.execute(
        "SELECT * FROM productos ORDER BY nombre"
    ).fetchall()

    conexion.close()

    return productos


# =====================================
# PAGINA PRINCIPAL
# =====================================

@app.route("/")
def inicio():

    productos = obtener_productos()

    return render_template(
        "index.html",
        productos=productos
    )


# =====================================
# GENERAR QR
# =====================================

@app.route("/qr.png")
def generar_qr():

    direccion = request.host_url

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )

    qr.add_data(direccion)

    qr.make(fit=True)

    imagen = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    archivo = io.BytesIO()

    imagen.save(archivo, format="PNG")

    archivo.seek(0)

    return send_file(
        archivo,
        mimetype="image/png"
    )


# =====================================
# CHAT GEMINI
# =====================================

@app.route("/api/chat", methods=["POST"])
def chat():

    if client is None:

        return jsonify({
            "respuesta": "Falta configurar la API KEY de Gemini."
        }), 500

    datos = request.get_json(silent=True) or {}

    pregunta = str(datos.get("mensaje", "")).strip()

    historial = datos.get("historial", [])

    if not pregunta:

        return jsonify({
            "respuesta": "Escribí una consulta."
        }), 400

    if len(pregunta) > 1000:

        return jsonify({
            "respuesta": "La consulta es demasiado larga."
        }), 400

    productos = obtener_productos()

    catalogo = ""

    for p in productos:

        catalogo += f"""
        Producto: {p['nombre']}
        Descripción: {p['descripcion']}
        Precio: ${p['precio']:,.2f}
        Stock: {p['stock']}
        """

    instrucciones = f"""
    Sos un vendedor virtual profesional.

    Atendés clientes de una tienda de productos.

    REGLAS:

    - Respondé siempre en español.
    - Sé amable y profesional.
    - Utilizá solamente el catálogo.
    - No inventes precios.
    - No inventes productos.
    - No inventes disponibilidad.
    - Recomendá alternativas.
    - Si no hay stock, informalo.
    - No confirmes ventas ni pagos.
    - Para comprar, invitá a contactar al negocio.

    CATÁLOGO:

    {catalogo}
    """

    conversacion = instrucciones + "\n"

    if isinstance(historial, list):

        for item in historial[-8:]:

            if not isinstance(item, dict):
                continue

            rol = item.get("role")

            contenido = str(
                item.get("content", "")
            )[:1000]

            if rol == "user":

                conversacion += (
                    f"\nCliente: {contenido}"
                )

            elif rol == "assistant":

                conversacion += (
                    f"\nVendedor: {contenido}"
                )

    conversacion += f"\nCliente: {pregunta}\nVendedor:"

    try:

        respuesta = client.models.generate_content(
            model=MODEL,
            contents=conversacion
        )

        texto = respuesta.text

        if not texto:

            texto = "No pude generar una respuesta."

        return jsonify({
            "respuesta": texto
        })

    except Exception as error:

        print("ERROR GEMINI:", error)

        return jsonify({
            "respuesta": "No pude conectarme con Gemini. Intentá nuevamente."
        }), 500


# =====================================
# INICIAR SERVIDOR
# =====================================

if __name__ == "__main__":

    inicializar_db()

    print("==============================")
    print(" VENDEDOR VIRTUAL IA + QR")
    print("==============================")

    print("Servidor iniciado")
    print("http://127.0.0.1:5000")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
