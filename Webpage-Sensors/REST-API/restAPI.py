import uuid

import mysql.connector
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


db = mysql.connector.connect(
    host="localhost", user="root", password="tu_password", database="tu_database"
)

cursor = db.cursor()


@app.route("/sensores", methods=["POST"])
def registrar_sensor():

    data = request.json

    id_sensor = str(uuid.uuid4())

    sql = """
        INSERT INTO sensor
        (id, marca, modelo, ubicacion, estado, id_invernadero)
        VALUES (%s, %s, %s, %s, %s, %s)
    """

    valores = (
        id_sensor,
        data["marca"],
        data["modelo"],
        data["ubicacion"],
        data["estado"],
        data["id_invernadero"],
    )

    cursor.execute(sql, valores)
    db.commit()

    return jsonify({"mensaje": "Sensor registrado", "id": id_sensor})


if __name__ == "__main__":
    app.run(debug=True)
