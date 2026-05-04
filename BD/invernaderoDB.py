"""
=====================================================================
  Sistema de Monitoreo de Invernadero — Cliente Python
  Requiere: pip install mysql-connector-python python-dotenv

  Al ejecutarse: borra y recrea la BD con datos de prueba fijos.
=====================================================================
"""

import os
import uuid
import logging
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv

import mysql.connector
from mysql.connector import Error, pooling

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Variables de entorno
# ─────────────────────────────────────────────
load_dotenv()

DB_NAME = os.getenv("DB_NAME", "invernadero_db")

# Config SIN base de datos (para poder borrarla y crearla)
DB_CONFIG_ROOT = {
    "host":               os.getenv("DB_HOST",     "localhost"),
    "port":               int(os.getenv("DB_PORT", "3306")),
    "user":               os.getenv("DB_USER",     "root"),
    "password":           os.getenv("DB_PASSWORD", "root"),
    "charset":            "utf8mb4",
    "use_unicode":        True,
    "autocommit":         True,
    "connection_timeout": 10,
}

# Config CON base de datos (para el pool normal de operaciones)
DB_CONFIG = {**DB_CONFIG_ROOT, "database": DB_NAME, "autocommit": False}

_pool: pooling.MySQLConnectionPool | None = None


# =====================================================================
#  DATOS DE PRUEBA HARDCODEADOS
#  Modifica aquí para cambiar el estado inicial en cada ejecución.
# =====================================================================
SEED = {
    "invernaderos": [
        {"id": "inv-0001", "nombre": "Invernadero Alpha", "ubicacion": "Bloque Norte, Zona 1"},
        {"id": "inv-0002", "nombre": "Invernadero Beta",  "ubicacion": "Bloque Sur, Zona 2"},
        {"id": "inv-0003", "nombre": "Invernadero Gamma", "ubicacion": "Bloque Este, Zona 3"},
    ],
    "sensores": [
        {"id": "sen-0001", "marca": "Bosch",     "modelo": "BME280", "ubicacion": "Pasillo Central", "estado": 1, "id_invernadero": "inv-0001"},
        {"id": "sen-0002", "marca": "Sensirion", "modelo": "SHT31",  "ubicacion": "Entrada Norte",   "estado": 1, "id_invernadero": "inv-0001"},
        {"id": "sen-0003", "marca": "Bosch",     "modelo": "BME680", "ubicacion": "Centro Sur",      "estado": 1, "id_invernadero": "inv-0002"},
        {"id": "sen-0004", "marca": "Texas Ins", "modelo": "HDC1080","ubicacion": "Area de riego",   "estado": 0, "id_invernadero": "inv-0002"},
        {"id": "sen-0005", "marca": "Honeywell", "modelo": "HIH8121","ubicacion": "Techo Este",      "estado": 1, "id_invernadero": "inv-0003"},
    ],
    "usuarios": [
        {"id": "usr-0001", "nombre": "Admin Sistema",   "email": "admin@invernadero.mx",     "telefono": "+526441000001"},
        {"id": "usr-0002", "nombre": "Operador Campo",  "email": "operador@invernadero.mx",  "telefono": "+526441000002"},
        {"id": "usr-0003", "nombre": "Supervisor TI",   "email": "supervisor@invernadero.mx","telefono": "+526441000003"},
    ],
    "notificaciones": [
        {"id": "not-0001", "email": "admin@invernadero.mx",    "telefono": "+526441000001"},
        {"id": "not-0002", "email": "operador@invernadero.mx", "telefono": "+526441000002"},
    ],
    # Solo métricas de sensores activos (estado=1)
    "metricas": [
        {"id": "met-0001", "id_sensor": "sen-0001", "temperatura": 22, "fecha_hora": "2024-06-01 08:00:00"},
        {"id": "met-0002", "id_sensor": "sen-0001", "temperatura": 27, "fecha_hora": "2024-06-01 10:00:00"},
        {"id": "met-0003", "id_sensor": "sen-0001", "temperatura": 36, "fecha_hora": "2024-06-01 12:00:00"},  # > 35 → dispara alr-0001
        {"id": "met-0004", "id_sensor": "sen-0002", "temperatura": 18, "fecha_hora": "2024-06-01 08:00:00"},
        {"id": "met-0005", "id_sensor": "sen-0002", "temperatura":  8, "fecha_hora": "2024-06-01 06:00:00"},  # < 10 → dispara alr-0002
        {"id": "met-0006", "id_sensor": "sen-0003", "temperatura": 30, "fecha_hora": "2024-06-01 09:00:00"},
        {"id": "met-0007", "id_sensor": "sen-0005", "temperatura": 25, "fecha_hora": "2024-06-01 11:00:00"},
    ],
    "alarmas": [
        {"id": "alr-0001", "tipo": "TEMPERATURA_ALTA:35", "operador": ">",  "id_sensor": "sen-0001", "id_notificacion": "not-0001"},
        {"id": "alr-0002", "tipo": "TEMPERATURA_BAJA:10", "operador": "<",  "id_sensor": "sen-0002", "id_notificacion": "not-0002"},
        {"id": "alr-0003", "tipo": "TEMPERATURA_ALTA:38", "operador": ">=", "id_sensor": "sen-0003", "id_notificacion": "not-0001"},
    ],
}


# =====================================================================
#  DDL: tablas, índices, triggers, procedimientos y vistas
# =====================================================================
_TABLAS = """
SET sql_mode = 'STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO';

CREATE TABLE usuario (
    id       VARCHAR(36)  NOT NULL,
    nombre   VARCHAR(120) NOT NULL,
    email    VARCHAR(255) NOT NULL,
    telefono VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_usuario          PRIMARY KEY (id),
    CONSTRAINT uq_usuario_email    UNIQUE (email),
    CONSTRAINT uq_usuario_tel      UNIQUE (telefono),
    CONSTRAINT ck_usuario_email    CHECK (email    REGEXP '^[A-Za-z0-9._%+\\\\-]+@[A-Za-z0-9.\\\\-]+\\\\.[A-Za-z]{2,}$'),
    CONSTRAINT ck_usuario_telefono CHECK (telefono REGEXP '^[+]?[0-9]{7,15}$'),
    CONSTRAINT ck_usuario_nombre   CHECK (CHAR_LENGTH(TRIM(nombre)) >= 2)
) ENGINE=InnoDB;

CREATE TABLE invernadero (
    id        VARCHAR(36)  NOT NULL,
    nombre    VARCHAR(150) NOT NULL,
    ubicacion VARCHAR(255) NOT NULL,
    CONSTRAINT pk_invernadero        PRIMARY KEY (id),
    CONSTRAINT uq_invernadero_nombre UNIQUE (nombre),
    CONSTRAINT ck_invernadero_nombre CHECK (CHAR_LENGTH(TRIM(nombre)) >= 2)
) ENGINE=InnoDB;

CREATE TABLE sensor (
    id             VARCHAR(36)  NOT NULL,
    marca          VARCHAR(100) NOT NULL,
    modelo         VARCHAR(100) NOT NULL,
    ubicacion      VARCHAR(255) NOT NULL,
    estado         TINYINT(1)   NOT NULL DEFAULT 1,
    id_invernadero VARCHAR(36)  NULL,
    CONSTRAINT pk_sensor        PRIMARY KEY (id),
    CONSTRAINT fk_sensor_inv    FOREIGN KEY (id_invernadero)
                                    REFERENCES invernadero(id)
                                    ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT ck_sensor_estado CHECK (estado IN (0,1)),
    CONSTRAINT ck_sensor_marca  CHECK (CHAR_LENGTH(TRIM(marca))  >= 1),
    CONSTRAINT ck_sensor_modelo CHECK (CHAR_LENGTH(TRIM(modelo)) >= 1)
) ENGINE=InnoDB;

CREATE INDEX idx_sensor_inv    ON sensor(id_invernadero);
CREATE INDEX idx_sensor_estado ON sensor(estado);

CREATE TABLE notificacion (
    id         VARCHAR(36)  NOT NULL,
    email      VARCHAR(255) NOT NULL,
    telefono   VARCHAR(20)  NOT NULL,
    enviada    TINYINT(1)   NOT NULL DEFAULT 0,
    enviada_en DATETIME     NULL,
    CONSTRAINT pk_notificacion         PRIMARY KEY (id),
    CONSTRAINT ck_notificacion_email   CHECK (email    REGEXP '^[A-Za-z0-9._%+\\\\-]+@[A-Za-z0-9.\\\\-]+\\\\.[A-Za-z]{2,}$'),
    CONSTRAINT ck_notificacion_tel     CHECK (telefono REGEXP '^[+]?[0-9]{7,15}$'),
    CONSTRAINT ck_notificacion_enviada CHECK (enviada IN (0,1))
) ENGINE=InnoDB;

CREATE TABLE metrica (
    id          VARCHAR(36) NOT NULL,
    fecha_hora  DATETIME(3) NOT NULL DEFAULT (CURRENT_TIMESTAMP(3)),
    temperatura INT         NOT NULL,
    id_sensor   VARCHAR(36) NOT NULL,
    CONSTRAINT pk_metrica        PRIMARY KEY (id),
    CONSTRAINT fk_metrica_sensor FOREIGN KEY (id_sensor)
                                     REFERENCES sensor(id)
                                     ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_metrica_temp   CHECK (temperatura BETWEEN -50 AND 100)
) ENGINE=InnoDB;

CREATE INDEX idx_metrica_sensor    ON metrica(id_sensor);
CREATE INDEX idx_metrica_fecha     ON metrica(fecha_hora);
CREATE INDEX idx_metrica_sensor_dt ON metrica(id_sensor, fecha_hora DESC);

CREATE TABLE alarma (
    id              VARCHAR(36) NOT NULL,
    tipo            VARCHAR(80) NOT NULL,
    operador        VARCHAR(10) NOT NULL,
    id_sensor       VARCHAR(36) NOT NULL,
    id_notificacion VARCHAR(36) NULL,
    CONSTRAINT pk_alarma              PRIMARY KEY (id),
    CONSTRAINT fk_alarma_sensor       FOREIGN KEY (id_sensor)
                                          REFERENCES sensor(id)
                                          ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_alarma_notificacion FOREIGN KEY (id_notificacion)
                                          REFERENCES notificacion(id)
                                          ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT ck_alarma_operador     CHECK (operador IN ('>','<','>=','<=','=','!=')),
    CONSTRAINT ck_alarma_tipo         CHECK (CHAR_LENGTH(TRIM(tipo)) >= 1)
) ENGINE=InnoDB;

CREATE INDEX idx_alarma_sensor ON alarma(id_sensor);

CREATE TABLE alarma_evaluacion (
    id          VARCHAR(36) NOT NULL,
    id_alarma   VARCHAR(36) NOT NULL,
    id_metrica  VARCHAR(36) NOT NULL,
    evaluada_en DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disparada   TINYINT(1)  NOT NULL DEFAULT 0,
    CONSTRAINT pk_alarma_eval  PRIMARY KEY (id),
    CONSTRAINT fk_ae_alarma    FOREIGN KEY (id_alarma)  REFERENCES alarma(id)  ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ae_metrica   FOREIGN KEY (id_metrica) REFERENCES metrica(id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT ck_ae_disparada CHECK (disparada IN (0,1))
) ENGINE=InnoDB;

CREATE INDEX idx_ae_alarma  ON alarma_evaluacion(id_alarma);
CREATE INDEX idx_ae_metrica ON alarma_evaluacion(id_metrica);

CREATE TABLE tcpserver_log (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    ip_origen       VARCHAR(45)     NOT NULL,
    conectado_en    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    desconectado_en DATETIME        NULL,
    metricas_reg    INT UNSIGNED    NOT NULL DEFAULT 0,
    CONSTRAINT pk_tcpserver PRIMARY KEY (id),
    CONSTRAINT ck_tcp_ip    CHECK (CHAR_LENGTH(TRIM(ip_origen)) >= 7)
) ENGINE=InnoDB;
"""

_TRIGGERS = [
    """CREATE TRIGGER trg_notificacion_enviada
       BEFORE UPDATE ON notificacion FOR EACH ROW
       BEGIN
           IF NEW.enviada = 1 AND OLD.enviada = 0 THEN
               SET NEW.enviada_en = CURRENT_TIMESTAMP;
           END IF;
       END""",

    """CREATE TRIGGER trg_metrica_sensor_activo
       BEFORE INSERT ON metrica FOR EACH ROW
       BEGIN
           DECLARE v_estado TINYINT(1);
           SELECT estado INTO v_estado FROM sensor WHERE id = NEW.id_sensor;
           IF v_estado = 0 THEN
               SIGNAL SQLSTATE '45000'
                   SET MESSAGE_TEXT = 'No se pueden registrar metricas en sensor inactivo.';
           END IF;
       END""",
]

_PROCEDURES = [
    """CREATE PROCEDURE registrar_metrica(
           IN  p_id_sensor   VARCHAR(36),
           IN  p_temperatura INT,
           OUT p_id_metrica  VARCHAR(36)
       )
       BEGIN
           DECLARE v_id VARCHAR(36) DEFAULT (UUID());
           INSERT INTO metrica (id, fecha_hora, temperatura, id_sensor)
           VALUES (v_id, CURRENT_TIMESTAMP(3), p_temperatura, p_id_sensor);
           SET p_id_metrica = v_id;
       END""",

    """CREATE PROCEDURE enviar_notificacion(IN p_id VARCHAR(36))
       BEGIN
           UPDATE notificacion SET enviada = 1 WHERE id = p_id AND enviada = 0;
           IF ROW_COUNT() = 0 THEN
               SIGNAL SQLSTATE '45000'
                   SET MESSAGE_TEXT = 'Notificacion no encontrada o ya enviada.';
           END IF;
       END""",

    """CREATE PROCEDURE evaluar_alarma(
           IN p_id_alarma  VARCHAR(36),
           IN p_id_metrica VARCHAR(36)
       )
       BEGIN
           DECLARE v_operador  VARCHAR(10);
           DECLARE v_tipo      VARCHAR(80);
           DECLARE v_temp      INT;
           DECLARE v_umbral    INT;
           DECLARE v_disparada TINYINT(1) DEFAULT 0;
           DECLARE v_id_eval   VARCHAR(36) DEFAULT (UUID());

           SELECT operador, tipo INTO v_operador, v_tipo FROM alarma  WHERE id = p_id_alarma;
           SELECT temperatura      INTO v_temp            FROM metrica WHERE id = p_id_metrica;
           SET v_umbral = CAST(SUBSTRING_INDEX(v_tipo, ':', -1) AS UNSIGNED);

           SET v_disparada = CASE v_operador
               WHEN '>'  THEN IF(v_temp >  v_umbral, 1, 0)
               WHEN '<'  THEN IF(v_temp <  v_umbral, 1, 0)
               WHEN '>=' THEN IF(v_temp >= v_umbral, 1, 0)
               WHEN '<=' THEN IF(v_temp <= v_umbral, 1, 0)
               WHEN '='  THEN IF(v_temp =  v_umbral, 1, 0)
               WHEN '!=' THEN IF(v_temp != v_umbral, 1, 0)
               ELSE 0
           END;

           INSERT INTO alarma_evaluacion (id, id_alarma, id_metrica, disparada)
           VALUES (v_id_eval, p_id_alarma, p_id_metrica, v_disparada);

           SELECT v_disparada AS alarma_disparada, v_id_eval AS id_evaluacion;
       END""",
]

_VISTAS = [
    """CREATE VIEW v_sensores_por_invernadero AS
       SELECT i.id  AS invernadero_id,  i.nombre   AS invernadero_nombre,
              i.ubicacion AS invernadero_ubicacion,
              s.id  AS sensor_id,       s.marca,   s.modelo,
              s.ubicacion AS sensor_ubicacion,      s.estado
       FROM invernadero i LEFT JOIN sensor s ON s.id_invernadero = i.id""",

    """CREATE VIEW v_ultima_metrica_sensor AS
       SELECT s.id AS sensor_id, s.marca, s.modelo, m.temperatura, m.fecha_hora
       FROM sensor s JOIN metrica m ON m.id_sensor = s.id
       WHERE m.fecha_hora = (
           SELECT MAX(m2.fecha_hora) FROM metrica m2 WHERE m2.id_sensor = s.id
       )""",

    """CREATE VIEW v_alarmas_disparadas AS
       SELECT ae.evaluada_en, a.tipo AS alarma_tipo, a.operador,
              s.marca, s.modelo, m.temperatura,
              n.email AS notificacion_email, n.telefono AS notificacion_telefono, n.enviada
       FROM alarma_evaluacion ae
       JOIN alarma  a ON a.id  = ae.id_alarma
       JOIN metrica m ON m.id  = ae.id_metrica
       JOIN sensor  s ON s.id  = a.id_sensor
       LEFT JOIN notificacion n ON n.id = a.id_notificacion
       WHERE ae.disparada = 1
       ORDER BY ae.evaluada_en DESC""",
]


