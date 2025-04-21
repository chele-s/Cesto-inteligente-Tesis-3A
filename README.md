# Cesto Inteligente: Clasificación Automatizada de Desechos con IA

![Smart Recycling Bin Banner](https://images.unsplash.com/photo-1611284446314-60a58ac0deb9?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D)

## Descripción General

Este proyecto implementa un cesto de basura inteligente capaz de clasificar automáticamente los desechos en tiempo real. Utiliza una **Raspberry Pi 4 B+**, una cámara, y un modelo de **Inteligencia Artificial (YOLOv8)** para identificar cuatro categorías de residuos: **Metal, Vidrio, Plástico y Cartón**. Una vez clasificado, un mecanismo accionado por **motores paso a paso** (controlados por drivers **A4988**) dirige el residuo al compartimento correspondiente.

El sistema cuenta con:
*   Una interfaz gráfica de usuario (GUI) desarrollada con **Tkinter** para visualización y control local.
*   **Sensores ultrasónicos (HC-SR04)** para medir el nivel de llenado de cada compartimento.
*   Una **interfaz web** opcional (Flask + HTML/CSS/JS) para monitoreo remoto del estado, niveles y estadísticas.
*   Un sistema de **logging** mejorado para facilitar la depuración.
*   Una configuración centralizada mediante un archivo `config.json`.

Este proyecto fue desarrollado como parte de las asignaturas Tecnología III, Práctica III y Laboratorio de Creatividad III, bajo la supervisión del docente Melquisidec Pérez Ramírez.

## Funcionalidades Principales

*   **Clasificación Automática:** Identifica 4 categorías de residuos (Metal, Vidrio, Plástico, Cartón) usando YOLOv8.
*   **Separación Mecanizada:** Motores paso a paso controlados por la Raspberry Pi (vía drivers A4988).
*   **Medición de Nivel:** Sensores ultrasónicos para monitorear el llenado de cada contenedor.
*   **Procesamiento en Tiempo Real:** Captura y análisis de video en tiempo real con optimizaciones (procesamiento en hilo separado).
*   **Interfaz Gráfica (GUI):** Muestra video, detecciones, estadísticas, niveles de llenado y permite ajustar parámetros básicos (confianza, tiempo de caída).
*   **Interfaz Web (Opcional):** Dashboard web para visualizar estado, niveles de llenado y estadísticas de clasificación en tiempo real.
*   **Configuración Flexible:** Parámetros clave (pines, modelo, umbrales, etc.) definidos en `config.json`.
*   **Logging Detallado:** Registro de eventos y errores en archivos de log con rotación.

## Requisitos de Hardware

*   **Computadora Principal:** Raspberry Pi 4 Modelo B+ (o superior)
*   **Cámara:** Módulo de Cámara para Raspberry Pi (v2, HQ, o compatible USB)
*   **Motores:** Motores Paso a Paso (ej. NEMA 17) - El número depende del diseño.
*   **Drivers de Motor:** Drivers A4988 (uno por motor).
*   **Sensores:** Sensores Ultrasónicos HC-SR04 (uno por compartimento).
*   **Fuente de Alimentación:**
    *   Fuente para Raspberry Pi (5V, >=3A, USB-C).
    *   Fuente **separada** para motores y drivers (ej. 12V-24V). **¡IMPORTANTE: Conectar GND de ambas fuentes!**
*   **Cableado:** Cables Dupont, protoboard (opcional), conectores.
*   **Estructura del Cesto:** Contenedor principal, compartimentos internos, mecanismo de clasificación.

## Requisitos de Software

*   **Sistema Operativo:** Raspberry Pi OS (o similar)
*   **Lenguaje:** Python 3.7+
*   **Librerías Principales (ver `requirements.txt`):**
    *   `ultralytics`: Para YOLOv8.
    *   `opencv-python`: Procesamiento de imágenes/video.
    *   `RPi.GPIO`: Control de GPIO (motor, sensores).
    *   `Pillow`: Manejo de imágenes en Tkinter.
    *   `numpy`: Operaciones numéricas.
    *   `imutils`: Utilidades de OpenCV.
    *   `tkinter`: Para la GUI local.
    *   `statistics`: Para promediar lecturas de sensores.
*   **Para Interfaz Web (ver `cesto_web/backend/requirements.txt`):**
    *   `Flask`, `Flask-SocketIO`, `eventlet`: Servidor web y WebSockets.
    *   `mysql-connector-python`: Conexión a MySQL.
    *   `python-dotenv`: Manejo de variables de entorno.
*   **Base de datos (para interfaz web):**
    *   `MySQL` (o MariaDB) Server.

## Estructura del Proyecto

```
Cesto_Inteligente_Proyecto/
│
├── main.py                 # Script principal (GUI, Inferencia, Orquestación)
├── config.json             # Archivo de configuración principal
├── motor_controller.py     # Control del motor paso a paso
├── sensor_controller.py    # Control de sensores ultrasónicos HC-SR04
├── main_web_adapter.py     # Módulo para comunicación entre main.py y backend web
├── train_yolo.py           # (Opcional) Script para entrenar el modelo YOLO
├── requirements.txt        # Dependencias Python del proyecto principal
├── README.md               # Este archivo
│
├── dataset_basura/         # (Opcional) Carpeta del dataset para YOLO
│   ├── data.yaml
│   ├── images/
│   └── labels/
│
├── models/                 # Modelos YOLO entrenados
│   └── best.pt
│
├── ui_assets/              # Recursos gráficos para la interfaz Tkinter
│   ├── Canva.png
│   └── ...
│
├── cesto_web/              # Interfaz web (opcional)
│   ├── backend/            # Servidor Flask (API, WebSockets, DB)
│   │   ├── app.py
│   │   ├── api.py
│   │   ├── database.py
│   │   ├── config.py
│   │   ├── requirements.txt  # Dependencias del backend
│   │   └── .env.example      # Ejemplo de variables de entorno
│   ├── frontend/           # Interfaz web (HTML, CSS, JS)
│   │   ├── index.html
│   │   ├── css/
│   │   └── js/
│   └── README.md           # README específico de la interfaz web
│
├── logs/                   # Archivos de log generados
│   └── *.log
│
├── docs/                   # (Opcional) Documentación adicional
│
└── runs/                   # (Opcional) Carpeta generada por YOLO durante el entrenamiento
```

## Instalación y Configuración

1.  **Clonar el Repositorio:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd Cesto_Inteligente_Proyecto
    ```

2.  **Configurar Entorno Python:** (Recomendado)
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate   # Windows
    ```

3.  **Instalar Dependencias Principales:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Conexiones de Hardware:**
    *   Conecta la **cámara**. Habilítala si es necesario (`sudo raspi-config`).
    *   Conecta los **drivers A4988** a los pines GPIO definidos en `config.json` (`motor` sección). Conecta los motores a los drivers.
    *   Conecta los **sensores HC-SR04** a los pines GPIO definidos en `config.json` (`sensors.pins`).
    *   Conecta las **fuentes de alimentación** (Raspberry Pi y Motores) **asegurando GND común**.

5.  **Configurar `config.json`:**
    *   Revisa y ajusta todos los parámetros en `config.json` según tu hardware y preferencias:
        *   `model_path`, `class_names`, `min_confidence`
        *   `target_steps_map`, `home_position_steps`, `drop_delay`
        *   `motor`: Pines GPIO (`DIR_PIN`, `STEP_PIN`, `ENABLE_PIN`, `USE_ENABLE`), velocidad (`STEP_DELAY`), ramping.
        *   `sensors`: Pines GPIO (`pins` por clase), `bin_depth_cm`, etc.
        *   `camera_index`, `frame_width`
        *   `window_title`, `window_geometry`, `ui_assets`

6.  **(Opcional) Configurar Interfaz Web:**
    *   **Instalar MySQL Server:** (Si no está instalado)
        ```bash
        sudo apt update
        sudo apt install mysql-server
        sudo systemctl start mysql
        sudo systemctl enable mysql
        ```
    *   **Crear Base de Datos y Usuario:**
        ```bash
        sudo mysql
        ```
        Ejecuta los comandos SQL (ver sección MySQL en `cesto_web/README.md` o abajo). Asegúrate de usar las credenciales que configurarás en `.env`.
        ```sql
        CREATE DATABASE cesto_inteligente_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
        CREATE USER 'cesto_user'@'localhost' IDENTIFIED BY 'cesto_password'; -- Usa una contraseña segura
        GRANT ALL PRIVILEGES ON cesto_inteligente_db.* TO 'cesto_user'@'localhost';
        FLUSH PRIVILEGES;
        EXIT;
        ```
    *   **Instalar Dependencias del Backend:**
        ```bash
        cd cesto_web/backend
        pip install -r requirements.txt
        cd ../.. # Volver al directorio raíz
        ```
    *   **Configurar Variables de Entorno del Backend:**
        Copia `cesto_web/backend/.env.example` a `cesto_web/backend/.env` y edítalo con tus credenciales de base de datos y configuraciones deseadas (puerto, etc.).
        ```bash
        cp cesto_web/backend/.env.example cesto_web/backend/.env
        nano cesto_web/backend/.env # O tu editor preferido
        ```

## Preparación del Dataset (Opcional)

* Para entrenar tu propio modelo, necesitas un dataset de imágenes en la carpeta `dataset_basura/` siguiendo el formato YOLO:
    * `dataset_basura/images/train/`: Imágenes de entrenamiento.
    * `dataset_basura/images/val/`: Imágenes de validación.
    * `dataset_basura/labels/train/`: Archivos `.txt` con las anotaciones (clase x_center y_center width height) para cada imagen de entrenamiento.
    * `dataset_basura/labels/val/`: Archivos `.txt` con las anotaciones para validación.
    * `dataset_basura/data.yaml`: Define rutas, `nc: 4`, y `names: ['Metal', 'Glass', 'Plastic', 'Carton']`. **El orden debe coincidir con `class_names` en `config.json` y `target_steps_map`**.

## Entrenamiento del Modelo (Opcional)

* Si has preparado tu propio dataset, puedes entrenar el modelo ejecutando:
    ```bash
    python train_yolo.py --data dataset_basura/data.yaml --epochs 100 --imgsz 640 --model yolov8n.pt --name CestoInteligente_Train
    ```
    * Ajusta los parámetros (`epochs`, `imgsz`, `model`, `name`) según sea necesario.
* Una vez finalizado el entrenamiento, copia el mejor modelo generado (`runs/detect/CestoInteligente_Train/weights/best.pt`) a la ruta especificada en `config.json` (`model_path`).

## Uso

1.  **Activar Entorno Virtual:**
    ```bash
    source venv/bin/activate
    ```
2.  **Ejecutar la Aplicación Principal (con GUI local):**
    Necesitarás permisos de superusuario para GPIO.
    ```bash
    sudo python main.py
    ```
    La GUI mostrará la cámara, detecciones, estadísticas y niveles. El sistema clasificará y moverá el mecanismo. Cierra la ventana o usa `Ctrl+C` para detener.

3.  **(Opcional) Ejecutar con Interfaz Web:**
    *   **Paso 1:** Inicia la aplicación principal en una terminal (necesaria para control de hardware y detección):
        ```bash
        sudo python main.py
        ```
    *   **Paso 2:** Inicia el backend web en *otra* terminal:
        ```bash
        cd cesto_web/backend
        python app.py
        ```
        El servidor se iniciará (por defecto en puerto 5000).
    *   **Paso 3:** Accede a la interfaz web desde un navegador:
        *   En la Raspberry Pi: `http://localhost:5000` (o el puerto configurado en `.env`)
        *   Desde otro dispositivo en la red: `http://<IP-DE-RASPBERRY>:<PORT>`

## Interfaz Web Detalles

Asegúrate de tener instalados los paquetes adicionales para la interfaz web:
```bash
pip install flask flask-socketio eventlet mysql-connector-python python-dotenv
```

## Licencia

Este proyecto se distribuye bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## Agradecimientos

* Al docente Melquisidec Pérez Ramírez por su guía.
* A las comunidades de Raspberry Pi, OpenCV, YOLO/Ultralytics, RPi.GPIO, Flask.
