from BD.db_manager import UsuarioRepo, SensorRepo
import mysql.connector
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from flask_cors import CORS
import os
from dotenv import load_dotenv
import utils.encryptation as encryptation

load_dotenv()

app = Flask(__name__)
CORS(app)


app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2) 

jwt = JWTManager(app)
usr_repo = UsuarioRepo()
sensor_repo = SensorRepo()

db = mysql.connector.connect(
    host=os.getenv("HOST"),
    user=os.getenv("USER"),
    password=os.getenv("PASSWORD"),
    database=os.getenv("DATABASE")
)

cursor = db.cursor()


@app.route("/sensores", methods=["POST"])
@jwt_required()
def registrar_sensor():
    Usuario_id = get_jwt_identity()  
    
    data = request.json

    id_sensor = sensor_repo.crear(
        marca=data.get("marca"),
        modelo=data.get("modelo"),
        ubicacion=data.get("ubicacion"),
        estado=data.get("estado"),
        id_invernadero=data.get("id_invernadero"),
    )

    return jsonify({"mensaje": "Sensor registrado", "id": id_sensor}), 201


#Generar token JWT 
@app.route("/api/auth/login", methods=["POST"])
def login():
    
    datos = request.get_json()
    email = datos.get("email")
    password = datos.get("password") 

    if not email or not password:
        return jsonify({"error": "Faltan credenciales"}), 400

    usuario = usr_repo.obtener_por_email(email) 
    
    if usuario and encryptation.Encryptation.check_password(password, usuario["password"]):
        token_acceso = create_access_token(identity=usuario["id"])
        return jsonify({
            "mensaje": "Autenticación exitosa",
            "token": token_acceso,
            "usuario": {
                "nombre": usuario["nombre"],
                "email": usuario["email"]
            }
        }), 200
    
    return jsonify({"error": "Credenciales inválidas"}), 401

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    nombre = data.get("nombre")
    email = data.get("email")
    telefono = data.get("telefono")
    password = data.get("password")

    if not nombre or not email or not telefono or not password:
        return jsonify({"error": "Faltan datos requeridos"}), 400

    # Verificar si el usuario ya existe
    if usr_repo.obtener_por_email(email):
        return jsonify({"error": "El email ya está registrado"}), 400

    # Hashear la pwd
    hashed_password = encryptation.Encryptation.hash_password(password)

    # Crear el usuario
    try:
        #TODO: modificar el método crear() de UsuarioRepo para aceptar el campo password y guardarlo en la base de datos
        id_usuario = usr_repo.crear(nombre, email, telefono)
        return jsonify({"mensaje": "Usuario registrado", "id": id_usuario}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
