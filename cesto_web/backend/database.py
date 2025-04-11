import mysql.connector
import logging
from datetime import datetime
import config

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('database')

# Clase para manejar la conexión y operaciones de la base de datos
class Database:
    def __init__(self):
        """Inicializa la conexión a la base de datos."""
        self.connection = None
        try:
            self.connection = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                port=config.DB_PORT,
                database=config.DB_NAME
            )
            logger.info("Conexión a la base de datos establecida")
        except mysql.connector.Error as e:
            logger.error(f"Error conectando a MySQL: {e}")
            # Si la base de datos no existe, la creamos
            if e.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                self._create_database()
            else:
                raise

    def _create_database(self):
        """Crea la base de datos si no existe."""
        try:
            conn = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                port=config.DB_PORT
            )
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE {config.DB_NAME}")
            cursor.close()
            conn.close()
            logger.info(f"Base de datos {config.DB_NAME} creada exitosamente")
            
            # Conectar a la base de datos recién creada
            self.connection = mysql.connector.connect(
                host=config.DB_HOST,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                port=config.DB_PORT,
                database=config.DB_NAME
            )
            
            # Crear tablas
            self._create_tables()
            
        except mysql.connector.Error as e:
            logger.error(f"Error al crear la base de datos: {e}")
            raise

    def _create_tables(self):
        """Crea las tablas necesarias si no existen."""
        cursor = self.connection.cursor()
        
        # Tabla para los niveles de llenado de cada compartimento
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fill_levels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            compartment VARCHAR(50) NOT NULL,
            level FLOAT NOT NULL,
            timestamp DATETIME NOT NULL
        )
        ''')
        
        # Tabla para las detecciones de residuos
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INT AUTO_INCREMENT PRIMARY KEY,
            waste_type VARCHAR(50) NOT NULL,
            confidence FLOAT NOT NULL,
            timestamp DATETIME NOT NULL
        )
        ''')
        
        # Tabla para estadísticas
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS statistics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            waste_type VARCHAR(50) NOT NULL,
            count INT NOT NULL,
            last_updated DATETIME NOT NULL
        )
        ''')
        
        # Tabla para estado del sistema
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_status (
            id INT AUTO_INCREMENT PRIMARY KEY,
            status VARCHAR(50) NOT NULL,
            message TEXT,
            timestamp DATETIME NOT NULL
        )
        ''')
        
        self.connection.commit()
        cursor.close()
        logger.info("Tablas creadas exitosamente")

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.connection:
            self.connection.close()
            logger.info("Conexión a la base de datos cerrada")

    # Métodos para operaciones con niveles de llenado
    def insert_fill_level(self, compartment, level):
        """
        Inserta un nuevo registro de nivel de llenado.
        
        Args:
            compartment (str): Nombre del compartimento (Metal, Glass, Plastic, Carton)
            level (float): Nivel de llenado (0-100%)
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return
            
        try:
            cursor = self.connection.cursor()
            query = """
            INSERT INTO fill_levels (compartment, level, timestamp) 
            VALUES (%s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (compartment, level, now))
            self.connection.commit()
            cursor.close()
            logger.debug(f"Nivel de llenado para {compartment}: {level}% insertado")
        except mysql.connector.Error as e:
            logger.error(f"Error insertando nivel de llenado: {e}")

    def get_latest_fill_levels(self):
        """
        Obtiene los últimos niveles de llenado de todos los compartimentos.
        
        Returns:
            dict: Diccionario con los niveles de llenado por compartimento
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return {}
            
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
            SELECT t1.compartment, t1.level, t1.timestamp
            FROM fill_levels t1
            INNER JOIN (
                SELECT compartment, MAX(timestamp) as max_timestamp
                FROM fill_levels
                GROUP BY compartment
            ) t2
            ON t1.compartment = t2.compartment AND t1.timestamp = t2.max_timestamp
            """
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            # Convertir a diccionario {compartment: level}
            levels = {}
            for row in results:
                levels[row['compartment']] = row['level']
                
            return levels
            
        except mysql.connector.Error as e:
            logger.error(f"Error obteniendo niveles de llenado: {e}")
            return {}

    # Métodos para operaciones con detecciones
    def insert_detection(self, waste_type, confidence):
        """
        Inserta un nuevo registro de detección de residuo.
        
        Args:
            waste_type (str): Tipo de residuo detectado (Metal, Glass, Plastic, Carton)
            confidence (float): Confianza de la detección (0-1)
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return
            
        try:
            cursor = self.connection.cursor()
            query = """
            INSERT INTO detections (waste_type, confidence, timestamp) 
            VALUES (%s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (waste_type, confidence, now))
            self.connection.commit()
            
            # Actualizar estadísticas
            self._update_statistics(waste_type)
            
            cursor.close()
            logger.debug(f"Detección de {waste_type} (conf: {confidence}) insertada")
        except mysql.connector.Error as e:
            logger.error(f"Error insertando detección: {e}")

    def _update_statistics(self, waste_type):
        """
        Actualiza las estadísticas de conteo para un tipo de residuo.
        
        Args:
            waste_type (str): Tipo de residuo detectado
        """
        try:
            cursor = self.connection.cursor()
            
            # Verificar si ya existe una entrada para este tipo
            query = "SELECT count FROM statistics WHERE waste_type = %s"
            cursor.execute(query, (waste_type,))
            result = cursor.fetchone()
            
            now = datetime.now()
            
            if result:
                # Actualizar contador existente
                current_count = result[0]
                query = """
                UPDATE statistics 
                SET count = %s, last_updated = %s 
                WHERE waste_type = %s
                """
                cursor.execute(query, (current_count + 1, now, waste_type))
            else:
                # Insertar nuevo contador
                query = """
                INSERT INTO statistics (waste_type, count, last_updated) 
                VALUES (%s, %s, %s)
                """
                cursor.execute(query, (waste_type, 1, now))
                
            self.connection.commit()
            cursor.close()
            
        except mysql.connector.Error as e:
            logger.error(f"Error actualizando estadísticas: {e}")

    def get_statistics(self):
        """
        Obtiene las estadísticas de conteo para todos los tipos de residuos.
        
        Returns:
            dict: Diccionario con los conteos por tipo de residuo
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return {}
            
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = "SELECT waste_type, count FROM statistics"
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            # Convertir a diccionario {waste_type: count}
            stats = {}
            for row in results:
                stats[row['waste_type']] = row['count']
                
            return stats
            
        except mysql.connector.Error as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

    # Métodos para operaciones con estado del sistema
    def update_system_status(self, status, message=None):
        """
        Actualiza el estado del sistema.
        
        Args:
            status (str): Estado del sistema (active, inactive, error, etc)
            message (str, optional): Mensaje descriptivo
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return
            
        try:
            cursor = self.connection.cursor()
            query = """
            INSERT INTO system_status (status, message, timestamp) 
            VALUES (%s, %s, %s)
            """
            now = datetime.now()
            cursor.execute(query, (status, message, now))
            self.connection.commit()
            cursor.close()
            logger.debug(f"Estado del sistema actualizado: {status}")
        except mysql.connector.Error as e:
            logger.error(f"Error actualizando estado del sistema: {e}")

    def get_system_status(self):
        """
        Obtiene el estado actual del sistema.
        
        Returns:
            dict: Diccionario con el estado actual
        """
        if not self.connection:
            logger.error("No hay conexión a la base de datos")
            return {}
            
        try:
            cursor = self.connection.cursor(dictionary=True)
            query = """
            SELECT status, message, timestamp
            FROM system_status
            ORDER BY timestamp DESC
            LIMIT 1
            """
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return result
            else:
                return {"status": "unknown", "message": "No hay datos de estado", "timestamp": None}
                
        except mysql.connector.Error as e:
            logger.error(f"Error obteniendo estado del sistema: {e}")
            return {"status": "error", "message": str(e), "timestamp": None}


# Instancia global de la base de datos
db = None

def get_db():
    """
    Obtiene la instancia de la base de datos.
    Si no existe, la crea.
    """
    global db
    if db is None:
        db = Database()
    return db 