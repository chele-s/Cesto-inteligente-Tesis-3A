# Cesto Inteligente: Interfaz Web

![Smart Recycling Bin Banner](https://images.unsplash.com/photo-1611284446314-60a58ac0deb9?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D)

Este proyecto proporciona una interfaz web complementaria para el sistema "Cesto Inteligente". Permite monitorear el estado del sistema principal (`main.py`), los niveles de llenado de cada compartimento y las estadísticas de clasificación de residuos en tiempo real a través de un navegador web.

La comunicación entre el sistema principal y esta interfaz web se realiza mediante un adaptador (`main_web_adapter.py`) que expone datos vía HTTP, y un backend (`backend/app.py`) que consume estos datos, los almacena en una base de datos MySQL (opcionalmente) y los sirve al frontend mediante una API REST y WebSockets.

## Estructura del Proyecto (Dentro de `cesto_web/`)

```
cesto_web/
├── backend/              # Servidor backend (Flask)
│   ├── app.py            # Aplicación Flask (API, WebSockets, conexión a main.py)
│   ├── api.py            # Endpoints de la API REST
│   ├── database.py       # Lógica de conexión y operaciones con MySQL
│   ├── config.py         # Carga de configuración desde .env
│   ├── requirements.txt  # Dependencias Python del backend
│   └── .env.example      # Ejemplo de archivo de configuración .env
└── frontend/             # Interfaz de usuario web (servida por Flask)
    ├── index.html        # Página principal (Dashboard)
    ├── css/
    │   └── style.css     # Estilos CSS
    └── js/
        └── main.js       # Lógica JavaScript (conexión WebSocket, actualización UI)
```

## Requisitos

*   Python 3.7+
*   MySQL Server (o MariaDB) - Opcional, pero recomendado para persistencia.
*   Las dependencias listadas en `backend/requirements.txt` (Flask, Flask-SocketIO, etc.)

## Instalación y Configuración

(Estos pasos asumen que ya has configurado el proyecto principal como se describe en el `README.md` raíz)

### 1. Configurar Base de Datos MySQL (Opcional)

Si deseas almacenar datos históricos o persistentes:

*   Asegúrate de que MySQL Server esté instalado y en ejecución.
    ```bash
    sudo systemctl status mysql
    ```
*   Crea la base de datos y el usuario si aún no lo has hecho (usa una contraseña segura):
    ```bash
    sudo mysql
    ```
    ```sql
    CREATE DATABASE IF NOT EXISTS cesto_inteligente_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE USER IF NOT EXISTS 'cesto_user'@'localhost' IDENTIFIED BY 'cesto_password'; -- Reemplaza con tu contraseña
    GRANT ALL PRIVILEGES ON cesto_inteligente_db.* TO 'cesto_user'@'localhost';
    FLUSH PRIVILEGES;
    EXIT;
    ```

### 2. Configurar el Backend

*   **Instalar Dependencias:**
    ```bash
    cd cesto_web/backend
    pip install -r requirements.txt
    ```
*   **Configurar Variables de Entorno:**
    Copia el archivo de ejemplo y edítalo con tu configuración:
    ```bash
    cp .env.example .env
    nano .env # o tu editor preferido
    ```
    Asegúrate de que las credenciales de la base de datos (`DB_USER`, `DB_PASSWORD`, `DB_NAME`) coincidan con las que creaste. Ajusta `MAIN_PY_HOST` y `MAIN_PY_PORT` si el adaptador web (`main_web_adapter.py`) se ejecuta en una dirección o puerto diferente al predeterminado (`127.0.0.1:5001`). Ajusta el puerto del backend (`PORT`) si es necesario (predeterminado 5000).

### 3. Asegurar Integración con `main.py`

*   Verifica que el archivo `main_web_adapter.py` esté presente en el directorio raíz del proyecto (junto a `main.py`).
*   Confirma que `main.py` importa y utiliza `main_web_adapter` para iniciar el servidor adaptador al arrancar.

### 4. Ejecutar el Sistema Completo

Necesitarás dos terminales:

*   **Terminal 1 (Sistema Principal):**
    Navega al directorio raíz del proyecto.
    ```bash
    # Activa tu entorno virtual si usas uno
    # source ../venv/bin/activate
    sudo python ../main.py # Ejecuta main.py desde la raíz
    ```
*   **Terminal 2 (Backend Web):**
    Navega al directorio del backend.
    ```bash
    cd cesto_web/backend
    # Activa tu entorno virtual si usas uno
    # source ../../venv/bin/activate
    python app.py
    ```

### 5. Acceder al Frontend

*   Abre un navegador web y visita la dirección donde se ejecuta el backend Flask:
    *   Si estás en la misma Raspberry Pi: `http://localhost:5000` (o el puerto configurado en `.env`).
    *   Si accedes desde otro dispositivo en la misma red: `http://<IP_RASPBERRY_PI>:<PORT>`.

## Uso

### Dashboard

La página principal (`index.html`) muestra un dashboard con información actualizada en tiempo real mediante WebSockets:

*   **Estado del Sistema:** Indica si `main.py` está activo, inactivo o ha encontrado un error (basado en la comunicación con `main_web_adapter`).
*   **Niveles de Llenado:** Muestra el porcentaje de llenado de cada compartimento (obtenido de los sensores vía `main.py`).
*   **Estadísticas de Clasificación:** Conteo total de residuos clasificados por tipo.
*   **Última Detección:** Detalles del último residuo detectado por `main.py`.

### API REST

El backend (`app.py`) expone una API REST simple para obtener datos actuales:

*   **GET `/api/dashboard`:** Devuelve un JSON con el estado actual completo (estado del sistema, niveles, estadísticas, última detección).
*   **GET `/api/fill-levels`:** Devuelve solo los niveles de llenado.
*   **GET `/api/statistics`:** Devuelve solo las estadísticas de clasificación.
*   **GET `/api/system-status`:** Devuelve solo el estado actual del sistema.

Estos endpoints son utilizados internamente por el frontend y también pueden ser consultados por otras aplicaciones si es necesario.

### WebSockets

El frontend establece una conexión WebSocket con el backend al cargar la página. El backend (`app.py`) sondea periódicamente al `main_web_adapter` (o recibe actualizaciones) y envía mensajes WebSocket (`'update_data'`) al frontend cada vez que detecta cambios en el estado, niveles o estadísticas, permitiendo la actualización de la UI sin necesidad de recargar la página.

## Configuración (`.env`)

La configuración principal del backend se gestiona a través del archivo `.env` en `cesto_web/backend/`:

```dotenv
# Configuración de la Base de Datos (Opcional)
DB_HOST=localhost
DB_USER=cesto_user
DB_PASSWORD=cesto_password
DB_NAME=cesto_inteligente_db
DB_PORT=3306
USE_DATABASE=True # Poner a False para deshabilitar la conexión a DB

# Configuración de la Aplicación Flask
DEBUG=True
SECRET_KEY=TU_CLAVE_SECRETA_AQUI # Cambia esto por una clave segura
PORT=5000

# Configuración de Comunicación con main.py (vía main_web_adapter)
MAIN_PY_HOST=127.0.0.1
MAIN_PY_PORT=5001

# Intervalo de sondeo a main_web_adapter (en segundos)
UPDATE_INTERVAL=3
```

## Solución de problemas

### Frontend no carga datos / No hay actualizaciones

1.  **Verifica que `main.py` esté en ejecución:** Asegúrate de que el script principal esté corriendo sin errores en la Terminal 1.
2.  **Verifica que el backend (`app.py`) esté en ejecución:** Revisa la Terminal 2 en busca de errores. ¿Pudo conectarse a `main_web_adapter`? ¿Hay errores de base de datos (si está habilitada)?
3.  **Verifica la conexión Backend <-> `main_web_adapter`:** Revisa los logs en ambas terminales. ¿Coinciden `MAIN_PY_HOST` y `MAIN_PY_PORT` en `.env` con la dirección y puerto donde `main_web_adapter` está escuchando (generalmente `127.0.0.1:5001`)?
4.  **Verifica la conexión Frontend <-> Backend:** Abre las herramientas de desarrollador del navegador (F12). Revisa la consola en busca de errores de JavaScript o problemas de conexión WebSocket. ¿Se establece la conexión al puerto correcto (ej. 5000)?
5.  **Firewall:** Asegúrate de que los puertos necesarios (ej. 5000 para el backend, 5001 para el adaptador) no estén bloqueados.

### Problemas con la base de datos

1.  **Verifica credenciales:** Asegúrate de que `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT` en `.env` sean correctos.
2.  **Servicio MySQL:** Confirma que el servicio MySQL esté activo: `sudo systemctl status mysql`.
3.  **Permisos:** Verifica que el usuario (`cesto_user`) tenga los permisos necesarios sobre la base de datos (`cesto_inteligente_db`).
4.  **Deshabilitar DB:** Si no necesitas la base de datos, pon `USE_DATABASE=False` en `.env` para descartar problemas relacionados con ella.

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