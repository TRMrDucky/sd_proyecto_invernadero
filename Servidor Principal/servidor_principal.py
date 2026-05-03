import paho.mqtt.client as mqtt
import json

# Configuración
BROKER_ADDRESS = "localhost"
TOPIC = "invernadero/sensores/mediciones"

def al_recibir_mensaje(client, userdata, message):

    try:
        payload = message.payload.decode("utf-8")
        datos = json.loads(payload)
        
        print(f"--- Nuevo Evento Detectado ---")
        print(f"Sensor ID: {datos['sensor_id']}")
        print(f"Lectura: {datos['temperatura']}°C, {datos['humedad']}% Humedad")
        
        # AQUÍ IRÁ LA LÓGICA DE PERSISTENCIA Y ALARMAS:
        # 1. Guardar en Base de Datos 
        # 2. Evaluar Alarmas (¿Temperatura > umbral?)
        
    except Exception as e:
        print(f"Error procesando el evento: {e}")

cliente = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
    client_id="ProcesadorEventos"
)

cliente.on_message = al_recibir_mensaje


cliente.connect(BROKER_ADDRESS)
print(f"Conectado al Broker en Mosquitto en {BROKER_ADDRESS}")

cliente.subscribe(TOPIC)
print(f"Servidor Principal suscrito al tópico: {TOPIC}")

cliente.loop_forever() 