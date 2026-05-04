# =====================================================================
#  FUNCIÓN PRINCIPAL DE RESET
# =====================================================================


import mysql

from BD.invernaderoDB import *
from BD.invernaderoDB import _TABLAS
from BD.invernaderoDB import _TRIGGERS
from BD.invernaderoDB import _PROCEDURES
from BD.invernaderoDB import _VISTAS
from BD.invernaderoDB import _pool

def setup_database() -> None:
    """
    Ejecuta al inicio de cada corrida:
      1. Conecta al servidor MySQL sin seleccionar BD.
      2. Borra la BD si existe.
      3. La crea nueva con charset utf8mb4.
      4. Crea tablas, índices, triggers, procedimientos y vistas.
      5. Inserta los datos de prueba hardcodeados (SEED).
    """
    log.info("══════════════════════════════════════════")
    log.info("  Iniciando reset de la base de datos...")
    log.info("══════════════════════════════════════════")

    conn = mysql.connector.connect(**DB_CONFIG_ROOT)
    cur  = conn.cursor()

    # 1 · Borrar BD existente
    cur.execute(f"DROP DATABASE IF EXISTS `{DB_NAME}`")
    log.info("  [1/5] BD '%s' eliminada (si existía).", DB_NAME)

    # 2 · Crear BD limpia
    cur.execute(
        f"CREATE DATABASE `{DB_NAME}` "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cur.execute(f"USE `{DB_NAME}`")
    log.info("  [2/5] BD '%s' creada.", DB_NAME)

    # 3 · Tablas e índices
    for stmt in _TABLAS.strip().split(";"):
        s = stmt.strip()
        if s:
            cur.execute(s)
    log.info("  [3/5] Tablas e índices creados.")

    # 4 · Triggers, procedimientos y vistas
    for trg  in _TRIGGERS:    cur.execute(trg.strip())
    for proc in _PROCEDURES:  cur.execute(proc.strip())
    for view in _VISTAS:      cur.execute(view.strip())
    log.info("  [4/5] Triggers, procedimientos y vistas listos.")

    # 5 · Seed data
    _insertar_seed(cur)
    log.info("  [5/5] Datos de prueba insertados.")

    cur.close()
    conn.close()
    log.info("══ Reset completado ══\n")


def _insertar_seed(cur) -> None:
    """Inserta todos los registros del diccionario SEED en orden correcto."""

    cur.executemany(
        "INSERT INTO usuario (id,nombre,email,telefono) VALUES (%(id)s,%(nombre)s,%(email)s,%(telefono)s)",
        SEED["usuarios"],
    )
    cur.executemany(
        "INSERT INTO invernadero (id,nombre,ubicacion) VALUES (%(id)s,%(nombre)s,%(ubicacion)s)",
        SEED["invernaderos"],
    )
    cur.executemany(
        "INSERT INTO sensor (id,marca,modelo,ubicacion,estado,id_invernadero) "
        "VALUES (%(id)s,%(marca)s,%(modelo)s,%(ubicacion)s,%(estado)s,%(id_invernadero)s)",
        SEED["sensores"],
    )
    cur.executemany(
        "INSERT INTO notificacion (id,email,telefono) VALUES (%(id)s,%(email)s,%(telefono)s)",
        SEED["notificaciones"],
    )
    # Métricas: INSERT directo con fecha fija para evitar que el trigger
    # rechace el sensor inactivo sen-0004 (no tiene métricas en SEED, ok).
    cur.executemany(
        "INSERT INTO metrica (id,id_sensor,temperatura,fecha_hora) "
        "VALUES (%(id)s,%(id_sensor)s,%(temperatura)s,%(fecha_hora)s)",
        SEED["metricas"],
    )
    cur.executemany(
        "INSERT INTO alarma (id,tipo,operador,id_sensor,id_notificacion) "
        "VALUES (%(id)s,%(tipo)s,%(operador)s,%(id_sensor)s,%(id_notificacion)s)",
        SEED["alarmas"],
    )


# =====================================================================
#  POOL DE CONEXIONES (se inicializa DESPUÉS del setup)
# =====================================================================
def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(pool_name="inv_pool", pool_size=5, **DB_CONFIG)
        log.info("Pool de conexiones listo.")
    return _pool


@contextmanager
def get_conn():
    """Obtiene conexión del pool; commit en éxito, rollback en error."""
    conn = get_pool().get_connection()
    try:
        yield conn
        conn.commit()
    except Error as e:
        conn.rollback()
        log.error("Rollback aplicado: %s", e)
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(conn, dictionary: bool = True):
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield cur
    finally:
        cur.close()


# =====================================================================
#  REPOSITORIOS
# =====================================================================
class InvernaderoRepo:
    def crear(self, nombre: str, ubicacion: str) -> str:
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("INSERT INTO invernadero (id,nombre,ubicacion) VALUES (%s,%s,%s)", (nid,nombre,ubicacion))
        return nid

    def obtener(self, id_inv: str) -> dict | None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM invernadero WHERE id=%s", (id_inv,))
            return cur.fetchone()

    def listar(self) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM invernadero ORDER BY nombre")
            return cur.fetchall()

    def actualizar(self, id_inv: str, nombre: str, ubicacion: str) -> bool:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("UPDATE invernadero SET nombre=%s,ubicacion=%s WHERE id=%s", (nombre,ubicacion,id_inv))
            return cur.rowcount > 0

    def eliminar(self, id_inv: str) -> bool:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("DELETE FROM invernadero WHERE id=%s", (id_inv,))
            return cur.rowcount > 0

    def sensores(self, id_inv: str) -> list[dict]:
        """Equivale a listaSensores[] del diagrama."""
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM v_sensores_por_invernadero WHERE invernadero_id=%s", (id_inv,))
            return cur.fetchall()


class SensorRepo:
    def crear(self, marca: str, modelo: str, ubicacion: str,
              id_invernadero: str | None = None, estado: bool = True) -> str:
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "INSERT INTO sensor (id,marca,modelo,ubicacion,estado,id_invernadero) VALUES (%s,%s,%s,%s,%s,%s)",
                (nid, marca, modelo, ubicacion, int(estado), id_invernadero),
            )
        return nid

    def obtener(self, id_sensor: str) -> dict | None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM sensor WHERE id=%s", (id_sensor,))
            return cur.fetchone()

    def listar(self, solo_activos: bool = False) -> list[dict]:
        sql = "SELECT * FROM sensor" + (" WHERE estado=1" if solo_activos else "")
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(sql)
            return cur.fetchall()

    def cambiar_estado(self, id_sensor: str, activo: bool) -> bool:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("UPDATE sensor SET estado=%s WHERE id=%s", (int(activo), id_sensor))
            return cur.rowcount > 0

    def eliminar(self, id_sensor: str) -> bool:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("DELETE FROM sensor WHERE id=%s", (id_sensor,))
            return cur.rowcount > 0


class MetricaRepo:
    def registrar(self, id_sensor: str, temperatura: int) -> str:
        """
        Inserta una métrica y devuelve su id.
        Se genera el UUID en Python para evitar problemas de recuperación
        de parámetros OUT con el conector C de MySQL en Python 3.12+.
        """
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "INSERT INTO metrica (id, fecha_hora, temperatura, id_sensor) "
                "VALUES (%s, CURRENT_TIMESTAMP(3), %s, %s)",
                (nid, temperatura, id_sensor),
            )
        log.info("Métrica registrada: sensor=%s  temp=%d°C  id=%s", id_sensor, temperatura, nid)
        return nid

    def listar_por_sensor(self, id_sensor: str, limite: int = 100) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "SELECT * FROM metrica WHERE id_sensor=%s ORDER BY fecha_hora DESC LIMIT %s",
                (id_sensor, limite),
            )
            return cur.fetchall()

    def ultima_por_sensor(self, id_sensor: str) -> dict | None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM v_ultima_metrica_sensor WHERE sensor_id=%s", (id_sensor,))
            return cur.fetchone()

    def promedio_temperatura(self, id_sensor: str,
                             desde: datetime | None = None,
                             hasta: datetime | None = None) -> float | None:
        sql, params = "SELECT AVG(temperatura) AS promedio FROM metrica WHERE id_sensor=%s", [id_sensor]
        if desde: sql += " AND fecha_hora>=%s"; params.append(desde)
        if hasta: sql += " AND fecha_hora<=%s"; params.append(hasta)
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return float(row["promedio"]) if row and row["promedio"] else None


class NotificacionRepo:
    def crear(self, email: str, telefono: str) -> str:
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("INSERT INTO notificacion (id,email,telefono) VALUES (%s,%s,%s)", (nid,email,telefono))
        return nid

    def enviar(self, id_notificacion: str) -> None:
        """Llama al SP enviar_notificacion()."""
        with get_conn() as c, get_cursor(c) as cur:
            cur.callproc("enviar_notificacion", [id_notificacion])

    def obtener(self, id_notificacion: str) -> dict | None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM notificacion WHERE id=%s", (id_notificacion,))
            return cur.fetchone()

    def pendientes(self) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM notificacion WHERE enviada=0")
            return cur.fetchall()


class AlarmaRepo:
    OPERADORES = {">", "<", ">=", "<=", "=", "!="}

    def crear(self, tipo: str, operador: str, id_sensor: str,
              id_notificacion: str | None = None) -> str:
        if operador not in self.OPERADORES:
            raise ValueError(f"Operador invalido. Use: {self.OPERADORES}")
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "INSERT INTO alarma (id,tipo,operador,id_sensor,id_notificacion) VALUES (%s,%s,%s,%s,%s)",
                (nid, tipo, operador, id_sensor, id_notificacion),
            )
        return nid

    def evaluar(self, id_alarma: str, id_metrica: str) -> dict:
        """Llama al SP evaluar_alarma() y retorna si se disparó."""
        with get_conn() as c, get_cursor(c) as cur:
            cur.callproc("evaluar_alarma", [id_alarma, id_metrica])
            for res in cur.stored_results():
                row = res.fetchone()
                if row:
                    return dict(row)
        return {}

    def alarmas_disparadas(self) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM v_alarmas_disparadas")
            return cur.fetchall()

    def listar(self, id_sensor: str | None = None) -> list[dict]:
        sql = "SELECT * FROM alarma" + (" WHERE id_sensor=%s" if id_sensor else "")
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(sql, (id_sensor,) if id_sensor else ())
            return cur.fetchall()


class UsuarioRepo:
    def crear(self, nombre: str, email: str, telefono: str) -> str:
        nid = str(uuid.uuid4())
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "INSERT INTO usuario (id,nombre,email,telefono) VALUES (%s,%s,%s,%s)",
                (nid, nombre, email, telefono),
            )
        return nid

    def listar(self) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM usuario ORDER BY nombre")
            return cur.fetchall()

    def obtener_por_email(self, email: str) -> dict | None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM usuario WHERE email=%s", (email,))
            return cur.fetchone()


class TCPServerLogger:
    def iniciar_sesion(self, ip_origen: str) -> int:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("INSERT INTO tcpserver_log (ip_origen) VALUES (%s)", (ip_origen,))
            return cur.lastrowid

    def cerrar_sesion(self, log_id: int, metricas_reg: int = 0) -> None:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute(
                "UPDATE tcpserver_log SET desconectado_en=CURRENT_TIMESTAMP,metricas_reg=%s WHERE id=%s",
                (metricas_reg, log_id),
            )

    def historial(self, limite: int = 50) -> list[dict]:
        with get_conn() as c, get_cursor(c) as cur:
            cur.execute("SELECT * FROM tcpserver_log ORDER BY conectado_en DESC LIMIT %s", (limite,))
            return cur.fetchall()


# =====================================================================
#  DEMO
# =====================================================================
def _titulo(texto: str) -> None:
    print(f"\n{'─'*55}")
    print(f"  {texto}")
    print(f"{'─'*55}")


def main() -> None:
    # ══ 1. Reset total de la BD ══════════════════════════════════
    setup_database()

    inv_repo    = InvernaderoRepo()
    sensor_repo = SensorRepo()
    met_repo    = MetricaRepo()
    notif_repo  = NotificacionRepo()
    alarma_repo = AlarmaRepo()
    usr_repo    = UsuarioRepo()
    tcp_logger  = TCPServerLogger()

    # ── Invernaderos ─────────────────────────────────────────────
    _titulo("1 · Invernaderos y sus sensores")
    for inv in inv_repo.listar():
        sensores = inv_repo.sensores(inv["id"])
        total = sum(1 for s in sensores if s["sensor_id"])
        print(f"  🌿 {inv['nombre']:<25} | {inv['ubicacion']:<30} | {total} sensor(es)")

    # ── Sensores ─────────────────────────────────────────────────
    _titulo("2 · Estado de todos los sensores")
    for s in sensor_repo.listar():
        icono = "✅" if s["estado"] else "❌"
        print(f"  {icono} [{s['id']}] {s['marca']:<12} {s['modelo']:<8} — {s['ubicacion']}")

    # ── Últimas métricas ─────────────────────────────────────────
    _titulo("3 · Última métrica por sensor activo")
    for s in sensor_repo.listar(solo_activos=True):
        ultima = met_repo.ultima_por_sensor(s["id"])
        if ultima:
            print(f"  🌡  {ultima['marca']:<12} {ultima['modelo']:<8} "
                  f"→ {ultima['temperatura']:>3}°C  ({ultima['fecha_hora']})")

    # ── Sesión TCP y nueva lectura ────────────────────────────────
    _titulo("4 · Nueva lectura vía TCPServer")
    sensor_prueba = SEED["sensores"][0]["id"]   # sen-0001 (Bosch BME280, activo)
    nueva_temp    = 37
    log_id        = tcp_logger.iniciar_sesion("192.168.1.10")
    nuevo_met     = met_repo.registrar(sensor_prueba, nueva_temp)
    tcp_logger.cerrar_sesion(log_id, metricas_reg=1)
    print(f"  📡 Sensor  : {sensor_prueba}")
    print(f"  🌡  Temp.   : {nueva_temp}°C")
    print(f"  🆔 Métrica : {nuevo_met}")

    # ── Evaluación de alarmas ─────────────────────────────────────
    _titulo("5 · Evaluación de alarmas sobre nueva métrica")
    for alr in SEED["alarmas"]:
        if alr["id_sensor"] == sensor_prueba:
            resultado  = alarma_repo.evaluar(alr["id"], nuevo_met)
            disparada  = resultado.get("alarma_disparada", 0)
            icono      = "🔴 DISPARADA" if disparada else "🟢 OK"
            print(f"  {icono} | {alr['tipo']:<25} operador={alr['operador']}")

    # ── Notificaciones pendientes ─────────────────────────────────
    _titulo("6 · Notificaciones pendientes")
    for n in notif_repo.pendientes():
        print(f"  📧 {n['email']:<35} 📱 {n['telefono']}")

    # ── Usuarios ─────────────────────────────────────────────────
    _titulo("7 · Usuarios del sistema")
    for u in usr_repo.listar():
        print(f"  👤 {u['nombre']:<25} {u['email']}")

    _titulo("✔  Demo completado — BD en estado inicial fresco.")
    print()


if __name__ == "__main__":
    main()