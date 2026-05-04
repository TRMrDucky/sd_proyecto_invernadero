import socket
import json
import struct
import time
import random

GATEWAY_IP = "localhost"
GATEWAY_PORT = 5000

def enviar_datos(payload, es_binario=False):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((GATEWAY_IP, GATEWAY_PORT))
            s.sendall(payload)
            tipo = "BINARIO" if es_binario else "JSON"
            print(f"[Simulador] Enviado exitosamente en formato {tipo}")
    except ConnectionRefusedError:
        print("Error de conexión ")

def simular_sensores():
    
    while True:
        temp = random.uniform(5.0, 50.0) 
        hum = random.uniform(40.0, 80.0)
        
        # --- LÍNEA CORREGIDA ---
        # Ahora solo genera IDs del 1 al 5 para coincidir con tu BD
        sensor_id = random.randint(1, 5)

        if random.choice([True, False]):
            data = {
                "sensor_id": str(sensor_id),
                "temperatura": round(temp, 2),
                "humedad": round(hum, 2)
            }
            payload = json.dumps(data).encode('utf-8')
            enviar_datos(payload, es_binario=False)
        else:
            # FORMATO BINARIO (Estructura: !Hff -> Short, Float, Float)
            # Esto valida el struct.unpack del Gateway
            payload = struct.pack('!Hff', sensor_id, temp, hum)
            enviar_datos(payload, es_binario=True)

        time.sleep(5) 

if __name__ == "__main__":
    simular_sensores()