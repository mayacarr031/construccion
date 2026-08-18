import os
import pymysql

# Cargar variables de .env
def load_env_file(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

load_env_file()

host = os.getenv("DB_HOST", "172.20.64.1")
port = int(os.getenv("DB_PORT", 3306))
user = os.getenv("DB_USER", "testmike")
password = os.getenv("DB_PASSWORD", "lasalle")
db_name = os.getenv("DB_NAME", "db_sentimientos")

print("=" * 60)
print("[INFO] PROBANDO CONEXION A MARIADB EN CONTENEDOR REMOTO")
print("=" * 60)
print(f"Host:          {host}")
print(f"Puerto:        {port}")
print(f"Usuario:       {user}")
print(f"Base de Datos: {db_name}")
print("=" * 60)

try:
    print(f"Intentando conectar a {host}:{port}...")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cursor:
        cursor.execute("SELECT VERSION() AS version, DATABASE() AS db;")
        info = cursor.fetchone()
        print("[OK] CONEXION EXITOSA!")
        print(f"   Version MariaDB: {info.get('version')}")
        print(f"   Base de datos:   {info.get('db')}")
        
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        table_names = [list(t.values())[0] for t in tables]
        print(f"   Tablas existentes: {table_names}")

        if "tweets" in table_names:
            cursor.execute("SELECT COUNT(*) AS total FROM tweets;")
            count = cursor.fetchone()
            print(f"   Total registros en 'tweets': {count.get('total')}")

    conn.close()
    print("=" * 60)
    print("[SUCCESS] Todo listo. La base de datos remota esta lista para ser leida y utilizada.")

except Exception as e:
    print("\n[ERROR] ERROR DE CONEXION:")
    print(f"   {e}")
    print("\nVerificaciones:")
    print(f"   1. El contenedor de MariaDB en {host} debe estar corriendo.")
    print(f"   2. El usuario '{user}' debe tener permisos de conexion remota ('%').")
    print(f"   3. El puerto {port} debe estar abierto en el firewall de la maquina remota.")
    print("=" * 60)
