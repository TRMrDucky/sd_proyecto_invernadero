import paho.mqtt.client as mqtt
import json
import sys
import os

# Agregamos la ruta principal del proyecto para que Python encuentre invernaderoDB.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importamos los repositorios de tu base de datos
from BD.db_manager import MetricaRepo, AlarmaRepo, setup_database

# Configuración
BROKER_ADDRESS = "localhost"
TOPIC = "invernadero/sensores/mediciones"
TOPIC_ALARMAS = "invernadero/sensores/alarmas"

# 1. (Opcional para la PoC) Reiniciar y poblar la BD cada que inicies el servidor
print("Inicializando Base de Datos...")
setup_database()

# 2. Instanciar los repositorios
met_repo = MetricaRepo()
alarma_repo = AlarmaRepo()

def al_recibir_mensaje(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        datos = json.loads(payload)
        
        # Obtenemos el ID original (ej. "2")
        sensor_id_raw = str(datos['sensor_id'])
        
        # --- REGLA DE TRADUCCIÓN ---
        # Si es solo un número, lo rellenamos con ceros para que quede como "sen-0002"
        if sensor_id_raw.isdigit():
            sensor_id = f"sen-{int(sensor_id_raw):04d}"
        else:
            sensor_id = sensor_id_raw
        # -----------------------------------------
        
        temperatura = int(datos['temperatura']) 
        
        print(f"\n--- Nuevo Evento Detectado ---")
        print(f"Sensor Original: {sensor_id_raw} -> Traducido a: {sensor_id} | Temp: {temperatura}°C | Hum: {datos['humedad']}%")
        
        # 1. Guardar en Base de Datos usando tu Repositorio
        id_metrica = met_repo.registrar(id_sensor=sensor_id, temperatura=temperatura)
        print(f"Métrica guardada en BD con ID: {id_metrica}")
        
        # 2. Evaluar Alarmas desde la Base de Datos
        evaluar_alarmas_db(sensor_id, id_metrica, temperatura, client)
        
    except Exception as e:
        print(f"Error procesando el evento: {e}")
        
def evaluar_alarmas_db(sensor_id, id_metrica, temperatura, cliente_mqtt):
    # Obtenemos las alarmas configuradas en la BD para ESTE sensor específico
    alarmas_del_sensor = alarma_repo.listar(id_sensor=sensor_id)
    
    for alr in alarmas_del_sensor:
        # La BD evalúa si la métrica rompe el umbral
        resultado = alarma_repo.evaluar(alr['id'], id_metrica)
        disparada = resultado.get("alarma_disparada", 0)
        
        
        if disparada == 1:
            # Construimos el mensaje para el Servidor de Correo
            alarma_payload = {
                "sensor_id": sensor_id,
                "tipo": alr['tipo'],
                "valor": temperatura,
                "mensaje": f"Alerta desde BD: Temperatura de {temperatura}°C superó el umbral de {alr['tipo']} (Operador: {alr['operador']})"
            }
            # Publicamos en MQTT para que mail_server.py lo reciba
            cliente_mqtt.publish(TOPIC_ALARMAS, json.dumps(alarma_payload))
            print(f"¡ALARMA DISPARADA Y PUBLICADA! -> {alarma_payload['tipo']}")

# Usamos VERSION2 para evitar el warning de Deprecation
cliente = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="ProcesadorEventos"
)
cliente.on_message = al_recibir_mensaje

cliente.connect(BROKER_ADDRESS)
print(f"Conectado al Broker MQTT en {BROKER_ADDRESS}")
cliente.subscribe(TOPIC)
print(f"Servidor Principal suscrito a: {TOPIC}")

cliente.loop_forever()