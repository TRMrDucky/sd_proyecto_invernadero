import socket
import json
import struct
import paho.mqtt.client as mqtt

BROKER_ADDRESS = "localhost" 
TOPIC_MEDICIONES = "invernadero/sensores/mediciones"

class Gateway:
    def __init__(self, host='0.0.0.0', port=5000):
        self.host = host
        self.port = port
        self.mqtt_client = mqtt.Client()
        
    def conectar_broker(self):
        self.mqtt_client.connect(BROKER_ADDRESS)
        print(f"Conectado al Broker MQTT en {BROKER_ADDRESS}")

    def adaptador_protocolo(self, data):
        try:
            decoded_data = data.decode('utf-8')
            return json.loads(decoded_data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Si falla, se procesa como binario (ejemplo: 2 bytes ID, 4 bytes Temp, 4 bytes Hum)
            print("Procesando formato binario...")
            if len(data) >= 10:
                #2 bytes para ID, 4 para temperatura y 4 para humedad
                #'H' (unsigned short, 2b), 'f' (float, 4b), 'f' (float, 4b)
                sensor_id, temp, hum = struct.unpack('!Hff', data[:10])
                return {
                    "sensor_id": str(sensor_id),
                    "temperatura": round(temp, 2),
                    "humedad": round(hum, 2)
                }
        return None

    def iniciar(self):
        self.conectar_broker()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"Gateway escuchando en {self.host}:{self.port}...")
            
            while True:
                conn, addr = s.accept()
                with conn:
                    data = conn.recv(1024)
                    if data:
                        lectura_estandar = self.adaptador_protocolo(data)
                        
                        if lectura_estandar:
                            payload = json.dumps(lectura_estandar)
                            self.mqtt_client.publish(TOPIC_MEDICIONES, payload)
                            print(f"Publicado: {payload}")

if __name__ == "__main__":
    gateway = Gateway()
    gateway.iniciar()