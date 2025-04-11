import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env si existe
load_dotenv()

# Configuración de la base de datos MySQL
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'cesto_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'cesto_password')
DB_NAME = os.getenv('DB_NAME', 'cesto_inteligente_db')
DB_PORT = int(os.getenv('DB_PORT', '3306'))

# Configuración de la aplicación Flask
DEBUG = os.getenv('DEBUG', 'True') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY', 'clave_secreta_desarrollo')
PORT = int(os.getenv('PORT', '5000'))

# Configuración de comunicación con main.py
MAIN_PY_HOST = os.getenv('MAIN_PY_HOST', '127.0.0.1')
MAIN_PY_PORT = int(os.getenv('MAIN_PY_PORT', '5001'))

# Configuración de intervalos
# Intervalo de actualización de datos desde main.py (segundos)
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', '5')) 