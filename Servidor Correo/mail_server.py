import paho.mqtt.client as mqtt
import json
import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

BROKER_ADDRESS = "localhost"
TOPIC_ALARMAS = "invernadero/sensores/alarmas"

def enviar_email(datos_alarma):
    try:
        msg = MIMEText(datos_alarma['mensaje'])
        msg['Subject'] = f"ALERTA INVERNADERO: {datos_alarma['tipo']}"
        msg['From'] = os.getenv('EMAIL_USER')
        msg['To'] = os.getenv('EMAIL_RECEIVER')

        with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls() 
            server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
            server.send_message(msg)
            
        print(f"Correo de alerta enviado. Sensor {datos_alarma['sensor_id']}.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

def al_recibir_alarma(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        datos_alarma = json.loads(payload)
        enviar_email(datos_alarma)
    except Exception as e:
        print(f"Error en el suscriptor de correo: {e}")

cliente_correo = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="ServicioNotificaciones"
)
cliente_correo.on_message = al_recibir_alarma

cliente_correo.connect(BROKER_ADDRESS)
cliente_correo.subscribe(TOPIC_ALARMAS)
print(f"Conectado al Broker en {BROKER_ADDRESS}")
print(f"Suscrito a: {TOPIC_ALARMAS}")
cliente_correo.loop_forever()