# Cesto Inteligente: Interfaz Web

Este proyecto proporciona una interfaz web para el sistema Cesto Inteligente, permitiendo monitorear el estado del sistema, los niveles de llenado de cada compartimento y las estadísticas de clasificación de residuos a través de un navegador web.

## Estructura del Proyecto

```
cesto_web/
├── backend/              # Servidor backend con API REST y WebSockets
│   ├── app.py            # Aplicación principal Flask
│   ├── api.py            # Endpoints de API
│   ├── database.py       # Conexión y funciones de base de datos
│   ├── config.py         # Configuración
│   └── requirements.txt  # Dependencias
└── frontend/             # Interfaz de usuario
    ├── index.html        # Página principal
    ├── css/              # Estilos
    │   └── style.css
    └── js/               # Scripts
        └── main.js
```

## Requisitos

- Python 3.7+
- MySQL (o MariaDB)
- Node.js y npm (opcional, para desarrollo)

## Instalación

### 1. Configurar MySQL

```bash
# Iniciar MySQL
sudo systemctl start mysql

# Crear base de datos y usuario
mysql -u root -p
```

En la consola MySQL:
```sql
CREATE DATABASE cesto_inteligente_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cesto_user'@'localhost' IDENTIFIED BY 'cesto_password';
GRANT ALL PRIVILEGES ON cesto_inteligente_db.* TO 'cesto_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 2. Configurar el Backend

```bash
# Instalar dependencias
cd cesto_web/backend
pip install -r requirements.txt

# Configurar variables de entorno (opcional, también puede editar el archivo .env)
cp .env.example .env
# Editar .env con tu configuración
```

### 3. Integrar el Adaptador Web con main.py

1. Copiar el archivo `main_web_adapter.py` al directorio principal del proyecto
2. Modificar `main.py` siguiendo las instrucciones en `add_web_integration.py`

### 4. Ejecutar el Sistema

1. Inicia el programa principal en una terminal:
   ```bash
   python main.py
   ```

2. Inicia el backend en otra terminal:
   ```bash
   cd cesto_web/backend
   python app.py
   ```

3. Abre el frontend en tu navegador:
   - Si estás ejecutando en la Raspberry Pi con pantalla HDMI: `http://localhost:5000/frontend/index.html`
   - Si estás accediendo desde otro dispositivo: `http://IP_DE_TU_RASPBERRY:5000/frontend/index.html`

## Uso

### Dashboard

El dashboard muestra la siguiente información:

- **Niveles de Llenado**: Porcentaje de llenado de cada compartimento
- **Estadísticas**: Conteo total de residuos clasificados por tipo
- **Estado del Sistema**: Estado actual del sistema (activo, inactivo, error)
- **Última Detección**: Información sobre el último residuo detectado

### API REST

El backend proporciona los siguientes endpoints:

- **GET /api/dashboard**: Todos los datos del sistema
- **GET /api/fill-levels**: Niveles de llenado actuales
- **GET /api/statistics**: Estadísticas de clasificación
- **GET /api/system-status**: Estado del sistema

### WebSockets

Para actualizaciones en tiempo real, el frontend se conecta al backend mediante WebSockets, lo que permite recibir notificaciones instantáneas cuando hay cambios en el sistema.

## Configuración

La configuración se realiza a través del archivo `.env` en el directorio `backend`:

```
# Configuración de la Base de Datos
DB_HOST=localhost
DB_USER=cesto_user
DB_PASSWORD=cesto_password
DB_NAME=cesto_inteligente_db
DB_PORT=3306

# Configuración de la Aplicación
DEBUG=True
SECRET_KEY=CestoInteligenteClave2024
PORT=5000

# Configuración de Comunicación con main.py
MAIN_PY_HOST=127.0.0.1
MAIN_PY_PORT=5001

# Configuración de Intervalos
UPDATE_INTERVAL=5
```

## Solución de problemas

### Problemas de conexión con el backend

Si el frontend no puede conectarse al backend:

1. Verifica que el backend esté en ejecución (`python app.py`)
2. Comprueba que puedes acceder a la API: `http://localhost:5000/api/dashboard`
3. Verifica que el puerto 5000 no esté bloqueado por el firewall

### Problemas de conexión con main.py

Si el backend no puede conectarse a main.py:

1. Asegúrate de que `main.py` está en ejecución con el adaptador web integrado
2. Verifica que los puertos configurados coincidan (por defecto 5001)
3. Comprueba que la dirección IP en `.env` sea correcta

### Problemas con la base de datos

Si hay errores relacionados con la base de datos:

1. Verifica las credenciales en `.env`
2. Asegúrate de que MySQL esté en ejecución: `sudo systemctl status mysql`
3. Comprueba los permisos del usuario de la base de datos

## Desarrollo

Para el desarrollo, puedes usar herramientas como:

- Visual Studio Code con extensiones para Python, HTML, CSS y JavaScript
- Browser-sync para recargar automáticamente el frontend durante el desarrollo
- MySQL Workbench para gestionar la base de datos

## Licencia

Este proyecto se distribuye bajo la Licencia MIT.

## Autores

- Gabriel Calderón
- Elias Bautista
- Cristian Hernandez 