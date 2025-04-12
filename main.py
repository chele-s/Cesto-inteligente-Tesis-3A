#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# main.py - Programa principal del Cesto Inteligente
# Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
# Fecha: Abril de 2024
# Descripción: Aplicación principal para el Cesto Inteligente que integra
#              detección de residuos usando YOLOv8, control de motor paso a paso,
#              y sensores de nivel de llenado.
# -----------------------------------------------------------------------------

# --- Importación de Librerías ---
import tkinter as tk # Renombrado para claridad
from tkinter import Label, Scale, Frame, Button, HORIZONTAL # Importar widgets adicionales
from PIL import Image, ImageTk
import imutils
import cv2
import numpy as np
from ultralytics import YOLO
import math
import time
import threading # Para evitar bloqueo de GUI con el motor
import logging
import logging.handlers
import os
from datetime import datetime
import queue
import json

# Importar módulos del proyecto
import motor_controller
import sensor_controller
# Nuevo: Importar el adaptador web para comunicación con el backend
import main_web_adapter

# --- Configuración y Parámetros ---
class Config:
    """Clase para manejar la configuración del sistema con valores por defecto y persistencia."""
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.defaults = {
            # Configuración del Modelo y Detección
            'model_path': 'models/best.pt',
            'class_names': ['Metal', 'Glass', 'Plastic', 'Carton'],
            'min_confidence': 0.5,
            
            # Configuración del Mecanismo y Motor
            'target_steps_map': {
                '0': 0,      # Metal 
                '1': 50,     # Glass
                '2': 100,    # Plastic
                '3': 150     # Carton
            },
            'home_position_steps': 0,
            'drop_delay': 2.0,
            
            # Configuración de la Cámara
            'camera_index': 0,
            'frame_width': 640,
            
            # Configuración de la GUI
            'window_title': "Cesto Inteligente - Clasificador de Residuos",
            'window_geometry': "1280x720"
        }
        
        # Intentar cargar configuración desde archivo
        self.load()
    
    def get(self, key, default=None):
        """Obtener valor de configuración, con fallback a valor por defecto."""
        parts = key.split('.')
        
        # Manejar acceso a diccionarios anidados
        if len(parts) > 1:
            current = self.config
            for part in parts[:-1]:
                if part not in current:
                    return self.defaults.get(key, default)
                current = current[part]
            return current.get(parts[-1], self.defaults.get(key, default))
        
        # Acceso directo a primer nivel
        return self.config.get(key, self.defaults.get(key, default))
    
    def set(self, key, value):
        """Establecer valor de configuración."""
        self.config[key] = value
    
    def load(self):
        """Cargar configuración desde archivo JSON."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                    logger.info(f"Configuración cargada desde {self.config_file}")
            else:
                logger.warning(f"Archivo de configuración {self.config_file} no encontrado. Usando valores por defecto.")
                self.config = self.defaults.copy()
                self.save()  # Crear archivo con valores por defecto
        except Exception as e:
            logger.error(f"Error al cargar configuración: {e}")
            self.config = self.defaults.copy()
    
    def save(self):
        """Guardar configuración a archivo JSON."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
                logger.info(f"Configuración guardada en {self.config_file}")
        except Exception as e:
            logger.error(f"Error al guardar configuración: {e}")

# --- Configuración del sistema de logging ---
def setup_logging():
    """Configura el sistema de logging con rotación de archivos y salida por consola."""
    # Crear directorio de logs si no existe
    os.makedirs('logs', exist_ok=True)
    
    # Configurar formato de log
    log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, date_format)
    
    # Configurar logger raíz
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler para archivo con rotación
    log_filename = f'logs/cesto_inteligente_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_filename,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Inicializar el logger
logger = setup_logging()

# --- Módulos Locales ---
try:
    import motor_controller # Asume que motor_controller.py está en la misma carpeta
    import sensor_controller # Controlador de sensores ultrasónicos HC-SR04
except ImportError as e:
    logger = logging.getLogger("main")
    logger.critical(f"No se pudo importar un módulo local: {e}. Asegúrate de que esté en la misma carpeta.")
    exit() # Salir si algún controlador no se encuentra

# --- Inicializar configuración ---
config = Config()

# --- Reemplazar constantes con acceso a configuración ---
MODEL_PATH = config.get('model_path')
CLASS_NAMES = config.get('class_names')
NUM_CLASSES = len(CLASS_NAMES)
MIN_CONFIDENCE = config.get('min_confidence')

# Mapeo de Target Steps desde config
TARGET_STEPS_MAP = {int(k): v for k, v in config.get('target_steps_map').items()}
HOME_POSITION_STEPS = config.get('home_position_steps')
DROP_DELAY = config.get('drop_delay')

CAMERA_INDEX = config.get('camera_index')
FRAME_WIDTH = config.get('frame_width')

WINDOW_TITLE = config.get('window_title')
WINDOW_GEOMETRY = config.get('window_geometry')

# --- Configuración de la GUI ---
# Rutas a los recursos gráficos (obtenidas del config.json)
UI_ASSETS_PATH = config.get('ui_assets.base_path', "ui_assets/")
BACKGROUND_IMG_PATH = config.get('ui_assets.background', UI_ASSETS_PATH + "Canva.png")
EXAMPLE_IMG_PATHS = config.get('ui_assets.example_images', {
    'Metal': UI_ASSETS_PATH + "metal.png",
    'Glass': UI_ASSETS_PATH + "vidrio.png",
    'Plastic': UI_ASSETS_PATH + "plastico.png",
    'Carton': UI_ASSETS_PATH + "carton.png",
})
EXAMPLE_TXT_PATHS = config.get('ui_assets.example_texts', {
    'Metal': UI_ASSETS_PATH + "metaltxt.png",
    'Glass': UI_ASSETS_PATH + "vidriotxt.png",
    'Plastic': UI_ASSETS_PATH + "plasticotxt.png",
    'Carton': UI_ASSETS_PATH + "cartontxt.png",
})

# --- Variables Globales ---
# Usadas para compartir estado entre funciones y la GUI
cap = None              # Objeto de captura de video OpenCV
model = None            # Modelo YOLO cargado
pantalla = None         # Objeto raíz de la ventana Tkinter
lblVideo = None         # Label de Tkinter para mostrar el video
lblImgExample = None    # Label para mostrar imagen de ejemplo del residuo
lblTxtExample = None    # Label para mostrar texto de ejemplo del residuo

# Imágenes de ejemplo precargadas (diccionarios)
example_images = {}
example_texts = {}

# Estado de la aplicación
last_detected_class_index = -1 # Índice de la última clase detectada y procesada
motor_busy = False             # Flag para indicar si el motor está en movimiento (controlado por el hilo)
motor_thread = None            # Referencia al hilo del motor

# Añadir contadores y estadísticas
processing_stats = {
    'frame_count': 0,
    'last_fps_time': time.time(),
    'fps': 0.0,
    'detection_counts': {class_name: 0 for class_name in CLASS_NAMES},
    'total_detections': 0,
}

# Variables para los sensores de nivel
bin_level_labels = {}  # Etiquetas para mostrar nivel de llenado
sensor_monitoring_active = False  # Indica si el monitoreo de sensores está activo

# --- Funciones Auxiliares de GUI ---

def load_ui_assets():
    """Carga las imágenes de ejemplo desde las rutas especificadas."""
    global example_images, example_texts
    logger.info("INFO: Cargando imágenes de ejemplo para la GUI...")
    for name, path in EXAMPLE_IMG_PATHS.items():
        try:
            img = cv2.imread(path)
            if img is not None:
                example_images[name] = img
            else:
                logger.warning(f"ADVERTENCIA: No se pudo cargar la imagen de ejemplo: {path}")
        except Exception as e:
            logger.error(f"ERROR: Cargando imagen {path}: {e}")

    for name, path in EXAMPLE_TXT_PATHS.items():
        try:
            img = cv2.imread(path)
            if img is not None:
                example_texts[name] = img
            else:
                logger.warning(f"ADVERTENCIA: No se pudo cargar el texto de ejemplo: {path}")
        except Exception as e:
            logger.error(f"ERROR: Cargando texto {path}: {e}")
    logger.info("INFO: Carga de imágenes de ejemplo finalizada.")

def display_example_images(class_name):
    """Muestra la imagen y texto de ejemplo para la clase dada."""
    global lblImgExample, lblTxtExample

    img_to_show = example_images.get(class_name)
    txt_to_show = example_texts.get(class_name)

    # Mostrar imagen de ejemplo
    if img_to_show is not None and lblImgExample:
        try:
            img_rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            img_tk = ImageTk.PhotoImage(image=img_pil)
            lblImgExample.configure(image=img_tk)
            lblImgExample.image = img_tk # Guardar referencia
        except Exception as e:
            logger.error(f"ERROR: Mostrando imagen de ejemplo para {class_name}: {e}")
    elif lblImgExample:
        lblImgExample.configure(image='') # Limpiar si no hay imagen

    # Mostrar texto de ejemplo
    if txt_to_show is not None and lblTxtExample:
        try:
            txt_rgb = cv2.cvtColor(txt_to_show, cv2.COLOR_BGR2RGB)
            txt_pil = Image.fromarray(txt_rgb)
            txt_tk = ImageTk.PhotoImage(image=txt_pil)
            lblTxtExample.configure(image=txt_tk)
            lblTxtExample.image = txt_tk # Guardar referencia
        except Exception as e:
            logger.error(f"ERROR: Mostrando texto de ejemplo para {class_name}: {e}")
    elif lblTxtExample:
        lblTxtExample.configure(image='') # Limpiar si no hay texto

def clear_example_images():
    """Limpia las etiquetas de imágenes de ejemplo en la GUI."""
    if lblImgExample:
        lblImgExample.configure(image='')
        lblImgExample.image = None
    if lblTxtExample:
        lblTxtExample.configure(image='')
        lblTxtExample.image = None

# --- Funciones de Interfaz de Usuario Mejoradas ---
def update_status_indicators():
    """Actualiza los indicadores de estado en la interfaz de usuario."""
    global lblMotorStatus, lblFPS, lblTotalCount, class_count_labels, bin_level_labels

    # Actualizar indicador de estado del motor
    if lblMotorStatus:
        if motor_busy:
            lblMotorStatus.config(text="MOTOR: OCUPADO", fg="red", bg="#ffcccc")
        else:
            lblMotorStatus.config(text="MOTOR: LISTO", fg="green", bg="#ccffcc")
    
    # Actualizar contador de FPS
    if lblFPS:
        lblFPS.config(text=f"FPS: {processing_stats['fps']:.1f}")
    
    # Actualizar contador total
    if lblTotalCount:
        lblTotalCount.config(text=f"Total Clasificados: {processing_stats['total_detections']}")
    
    # Actualizar contadores por clase
    for class_name, label in class_count_labels.items():
        count = processing_stats['detection_counts'].get(class_name, 0)
        label.config(text=f"{class_name}: {count}")
        
    # Actualizar indicadores de nivel de llenado (si existen)
    if bin_level_labels and sensor_monitoring_active:
        try:
            # Obtener los niveles actuales (lectura única)
            bin_levels = sensor_controller.get_fill_levels(use_average=True, num_readings=1)
            
            # Actualizar cada etiqueta de nivel
            for bin_name, level in bin_levels.items():
                if level is not None:
                    # Determinar color según nivel de llenado
                    if level > 80:
                        color = "#ff4444"  # Rojo (casi lleno)
                    elif level > 50:
                        color = "#ffaa44"  # Naranja (medio)
                    else:
                        color = "#44aa44"  # Verde (vacío)
                    
                    label = bin_level_labels[bin_name]
                    label.config(text=f"Nivel: {level:.1f}%", fg=color)
                else:
                    label.config(text="Nivel: Error", fg="gray")
        except Exception as e:
            logger.error(f"Error al actualizar niveles de llenado: {e}")

def create_status_panel(parent):
    """Crea un panel de estado para mostrar información en tiempo real."""
    global lblMotorStatus, lblFPS, lblTotalCount, class_count_labels, bin_level_labels
    
    # Panel principal para estadísticas
    stats_frame = Frame(parent, bg='#f0f0f0', padx=10, pady=10, relief="ridge", bd=2)
    stats_frame.place(x=10, y=170, width=300, height=380)  # Aumentar altura para acomodar nuevos indicadores
    
    # Título del panel
    title_label = Label(stats_frame, text="ESTADO DEL SISTEMA", 
                        font=("Arial", 12, "bold"), bg='#f0f0f0')
    title_label.grid(row=0, column=0, columnspan=2, pady=5)
    
    # Indicador de estado del motor
    lblMotorStatus = Label(stats_frame, text="MOTOR: LISTO", 
                           font=("Arial", 10, "bold"), fg="green", bg="#ccffcc",
                           width=20, height=2)
    lblMotorStatus.grid(row=1, column=0, columnspan=2, pady=10, padx=5)
    
    # Indicador de FPS
    lblFPS = Label(stats_frame, text="FPS: 0.0", font=("Arial", 10), bg='#f0f0f0')
    lblFPS.grid(row=2, column=0, columnspan=2, pady=5, sticky='w')
    
    # Contador total
    lblTotalCount = Label(stats_frame, text="Total Clasificados: 0", 
                          font=("Arial", 10, "bold"), bg='#f0f0f0')
    lblTotalCount.grid(row=3, column=0, columnspan=2, pady=5, sticky='w')
    
    # Línea separadora
    separator = Frame(stats_frame, height=2, bg="gray")
    separator.grid(row=4, column=0, columnspan=2, sticky='ew', pady=8)
    
    # Contadores por clase
    class_count_labels = {}
    
    class_counter_title = Label(stats_frame, text="OBJETOS CLASIFICADOS", 
                               font=("Arial", 10, "bold"), bg='#f0f0f0')
    class_counter_title.grid(row=5, column=0, columnspan=2, pady=5)
    
    for i, class_name in enumerate(CLASS_NAMES):
        count_label = Label(stats_frame, text=f"{class_name}: 0", 
                            font=("Arial", 9), bg='#f0f0f0')
        count_label.grid(row=6+i, column=0, columnspan=2, sticky='w', pady=2)
        class_count_labels[class_name] = count_label
    
    # Botón para reiniciar contadores
    reset_button = Button(
        stats_frame,
        text="Reiniciar Contadores",
        command=reset_counters
    )
    reset_button.grid(row=6+len(CLASS_NAMES), column=0, columnspan=2, pady=10)
    
    # Línea separadora para sección de niveles
    separator2 = Frame(stats_frame, height=2, bg="gray")
    separator2.grid(row=7+len(CLASS_NAMES), column=0, columnspan=2, sticky='ew', pady=8)
    
    # Sección para indicadores de nivel de llenado
    bin_level_title = Label(stats_frame, text="NIVEL DE LLENADO", 
                         font=("Arial", 10, "bold"), bg='#f0f0f0')
    bin_level_title.grid(row=8+len(CLASS_NAMES), column=0, columnspan=2, pady=5)
    
    # Crear indicadores de nivel para cada compartimento
    bin_level_labels = {}
    for i, class_name in enumerate(CLASS_NAMES):
        level_label = Label(stats_frame, text=f"Nivel: --", 
                         font=("Arial", 9), bg='#f0f0f0', fg="gray")
        level_label.grid(row=9+len(CLASS_NAMES)+i, column=0, columnspan=2, sticky='w', pady=2)
        bin_level_labels[class_name] = level_label
    
    return stats_frame

def reset_counters():
    """Reinicia los contadores de detecciones."""
    processing_stats['detection_counts'] = {class_name: 0 for class_name in CLASS_NAMES}
    processing_stats['total_detections'] = 0
    update_status_indicators()
    logger.info("Contadores reiniciados")

# --- Función de Control del Motor (Ejecutada en Hilo Separado) ---

def _handle_motor_sequence(target_position, class_name):
    """
    Ejecuta la secuencia completa del motor en un hilo dedicado.
    Esto evita bloquear el hilo principal y la interfaz gráfica.
    """
    global motor_busy # Necesitamos modificar la variable global

    logger.info(f"THREAD: Iniciando secuencia de motor para '{class_name}' a {target_position} pasos.")
    try:
        # 1. Mover a la posición de la clase detectada
        logger.info(f"THREAD: Moviendo a posición {target_position}...")
        motor_controller.move_motor_to_position(target_position)
        logger.info(f"THREAD: Motor en posición {target_position}.")

        # 2. Esperar a que el objeto caiga
        logger.info(f"THREAD: Esperando {DROP_DELAY:.1f} segundos para que caiga el objeto...")
        time.sleep(DROP_DELAY) # time.sleep() es seguro aquí (hilo separado)

        # 3. Volver a la posición HOME (si es diferente)
        if target_position != HOME_POSITION_STEPS:
            logger.info(f"THREAD: Volviendo a posición HOME ({HOME_POSITION_STEPS} pasos)...")
            motor_controller.move_motor_to_position(HOME_POSITION_STEPS)
            time.sleep(0.5) # Pequeña pausa después de volver
            logger.info("THREAD: Motor en posición HOME.")
        else:
            logger.info("THREAD: Ya estaba en posición HOME, no se requiere retorno.")

        logger.info(f"THREAD: Secuencia de motor para '{class_name}' completada.")

    except Exception as e:
        logger.error(f"ERROR EN THREAD DEL MOTOR: {e}")
        # Intentar volver a HOME si falla en medio del movimiento (opcional)
        try:
             logger.info("THREAD: Intentando volver a HOME después de error...")
             motor_controller.move_motor_to_position(HOME_POSITION_STEPS)
        except Exception as e2:
             logger.error(f"ERROR EN THREAD: No se pudo volver a HOME: {e2}")

    finally:
        # 4. ¡MUY IMPORTANTE! Liberar el flag para permitir nuevas detecciones.
        logger.info("THREAD: Liberando bandera 'motor_busy'.")
        motor_busy = False
        # Usar after para actualizar la UI desde el hilo principal
        if pantalla:
            pantalla.after(10, update_status_indicators)

# --- Procesamiento de Video Mejorado ---
class FrameProcessor:
    """Clase para manejar el procesamiento de frames de video de forma eficiente."""
    def __init__(self, buffer_size=5, skip_frames=2):
        """
        Inicializar el procesador de frames.
        
        Args:
            buffer_size: Tamaño del buffer de frames
            skip_frames: Número de frames a saltar entre detecciones (para reducir carga)
        """
        self.frame_buffer = queue.Queue(maxsize=buffer_size)
        self.last_processed_frame = None
        self.last_detections = []  # Lista de todas las detecciones válidas del último frame
        self.skip_frames = skip_frames
        self.frame_counter = 0
        self.processing_thread = None
        self.processing_active = False
        self.is_running = False  # Estado para verificar si está activo
        
    def start_processing(self, model, min_confidence, callback):
        """
        Inicia el hilo de procesamiento.
        
        Args:
            model: Modelo YOLO a utilizar
            min_confidence: Umbral de confianza para detecciones
            callback: Función a llamar con los resultados de la detección
        """
        self.processing_active = True
        self.is_running = True
        self.processing_thread = threading.Thread(
            target=self._process_frames_loop,
            args=(model, min_confidence, callback),
            daemon=True
        )
        self.processing_thread.start()
        logger.info("Hilo de procesamiento de frames iniciado")
        
    def stop_processing(self):
        """Detiene el hilo de procesamiento."""
        self.processing_active = False
        if self.processing_thread and self.processing_thread.is_alive():
            # Esperar a que termine el hilo, con timeout
            self.processing_thread.join(timeout=1.0)
            logger.info("Hilo de procesamiento de frames detenido")
        self.is_running = False
        
    def add_frame(self, frame):
        """
        Añade un frame al buffer, sin bloquear si está lleno.
        
        Args:
            frame: Frame de OpenCV a añadir
        """
        try:
            # Si el buffer está lleno, descartar el frame más antiguo
            if self.frame_buffer.full():
                try:
                    self.frame_buffer.get_nowait()
                except queue.Empty:
                    pass  # Ya vacío (improbable)
            
            # Añadir el nuevo frame
            self.frame_buffer.put_nowait(frame.copy())
        except Exception as e:
            logger.warning(f"Error añadiendo frame al buffer: {e}")
    
    def _process_frames_loop(self, model, min_confidence, callback):
        """
        Bucle de procesamiento de frames en segundo plano.
        
        Args:
            model: Modelo YOLO
            min_confidence: Umbral de confianza
            callback: Función a llamar con resultados
        """
        while self.processing_active:
            try:
                # Obtener frame del buffer, esperar hasta 100ms
                try:
                    frame = self.frame_buffer.get(timeout=0.1)
                except queue.Empty:
                    continue  # No hay frames, verificar si seguimos activos
                
                # Incrementar contador y saltar frames según configuración
                self.frame_counter += 1
                if self.frame_counter % (self.skip_frames + 1) != 0:
                    continue  # Saltar este frame
                
                # Procesar frame con YOLO
                results = model(frame, stream=True, verbose=False)
                
                # Lista para almacenar todas las detecciones válidas
                all_detections = []
                
                # Obtener detecciones válidas
                for res in results:
                    boxes = res.boxes
                    for box in boxes:
                        conf = float(box.conf[0])
                        if conf >= min_confidence:
                            cls_index = int(box.cls[0])
                            # Verificar si el índice es válido
                            if 0 <= cls_index < len(CLASS_NAMES):
                                detection = {
                                    'box': list(map(int, box.xyxy[0])),
                                    'conf': conf,
                                    'cls_index': cls_index,
                                    'cls_name': CLASS_NAMES[cls_index]
                                }
                                all_detections.append(detection)
                
                # Ordenar detecciones por confianza (mayor a menor)
                if all_detections:
                    all_detections.sort(key=lambda x: x['conf'], reverse=True)
                
                # Guardar referencias
                self.last_processed_frame = frame.copy()
                self.last_detections = all_detections
                
                # Llamar al callback con la mejor detección (si hay) y todas las detecciones
                best_detection = all_detections[0] if all_detections else None
                if best_detection:
                    best_detection['frame'] = frame.copy()
                
                callback(best_detection, all_detections)
                
            except Exception as e:
                logger.error(f"Error en hilo de procesamiento de frames: {e}")

# --- Modificar scanning_loop para usar las detecciones guardadas ---
# Crear una instancia global del procesador
frame_processor = FrameProcessor(buffer_size=5, skip_frames=1)

def detection_callback(best_detection, all_detections=None):
    """
    Callback que se llama cuando el procesador de frames tiene una detección.
    
    Args:
        best_detection: La mejor detección (mayor confianza)
        all_detections: Lista de todas las detecciones válidas
    """
    global last_detected_class_index, motor_busy

    if best_detection:
        # Tenemos una detección
        cls_index = best_detection['cls_index']
        cls_name = best_detection['cls_name']
        
        # Mostrar la imagen de ejemplo asociada
        display_example_images(cls_name)
        
        # Si el motor no está ocupado y es una nueva clase, activar motor
        if not motor_busy and cls_index in TARGET_STEPS_MAP and cls_index != last_detected_class_index:
            motor_busy = True
            update_status_indicators()
            target_position = TARGET_STEPS_MAP[cls_index]
            logger.info(f"Detección válida: '{cls_name}'. Iniciando motor hacia {target_position} pasos.")
            
            # Actualizar contadores
            processing_stats['detection_counts'][cls_name] = processing_stats['detection_counts'].get(cls_name, 0) + 1
            processing_stats['total_detections'] += 1
            update_status_indicators()
            
            # Iniciar hilo del motor
            motor_thread = threading.Thread(
                target=_handle_motor_sequence,
                args=(target_position, cls_name),
                daemon=True
            )
            motor_thread.start()
            
            # Actualizar última clase
            last_detected_class_index = cls_index

            # Nuevo: Actualizar adaptador web con la detección actual
            detection_data = {
                'class_name': cls_name,
                'confidence': best_detection['conf']
            }
            # Actualizar adaptador web
            main_web_adapter.update_data(detection=detection_data)
    else:
        # No hay detección, limpiar si no hay motor activo
        if not motor_busy and last_detected_class_index != -1:
            last_detected_class_index = -1
            clear_example_images()

def scanning_loop():
    """
    Bucle principal modificado para usar el procesador de frames en segundo plano.
    """
    global last_detected_class_index, motor_busy, cap, model
    global lblVideo
    
    # Variables de seguimiento para reintentos de cámara
    MAX_CAMERA_RETRIES = 5
    camera_retries = 0
    
    # Actualizar contador de frames y calcular FPS
    processing_stats['frame_count'] += 1
    current_time = time.time()
    time_diff = current_time - processing_stats['last_fps_time']
    
    # Actualizar FPS cada segundo
    if time_diff >= 1.0:
        processing_stats['fps'] = processing_stats['frame_count'] / time_diff
        processing_stats['last_fps_time'] = current_time
        processing_stats['frame_count'] = 0
        update_status_indicators()
    
    if cap is None or not cap.isOpened():
        logger.error("Cámara no disponible o cerrada. Intentando reconectar...")
        try:
            if cap is not None:
                cap.release()  # Liberar recursos antes de intentar reconectar
            
            # Verificar si excedimos el número máximo de reintentos
            if camera_retries >= MAX_CAMERA_RETRIES:
                logger.critical(f"Se alcanzó el máximo de {MAX_CAMERA_RETRIES} reintentos de reconexión de cámara. Deteniendo escaneo.")
                if pantalla:
                    # Mostrar mensaje de error en la GUI
                    if lblVideo:
                        error_img = np.zeros((300, 400, 3), dtype=np.uint8)
                        cv2.putText(error_img, "ERROR DE CAMARA", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        img_rgb = cv2.cvtColor(error_img, cv2.COLOR_BGR2RGB)
                        img_pil = Image.fromarray(img_rgb)
                        img_tk = ImageTk.PhotoImage(image=img_pil)
                        lblVideo.configure(image=img_tk)
                        lblVideo.image = img_tk
                    # Continuar el bucle sin intentar capturar frames
                    pantalla.after(100, scanning_loop)
                return
            
            # Intentar reconectar
            cap = cv2.VideoCapture(CAMERA_INDEX)
            if cap.isOpened():
                logger.info("Cámara reconectada exitosamente.")
                camera_retries = 0  # Reiniciar contador de reintentos si tuvimos éxito
            else:
                camera_retries += 1
                logger.warning(f"Reintento {camera_retries}/{MAX_CAMERA_RETRIES} fallido. Esperando antes de volver a intentar...")
                time.sleep(1.0)  # Esperar antes de reintentar
                pantalla.after(100, scanning_loop)
                return
        except Exception as e:
            camera_retries += 1
            logger.error(f"Error al reconectar cámara: {e}. Reintento {camera_retries}/{MAX_CAMERA_RETRIES}")
            time.sleep(1.0)
            if pantalla:
                pantalla.after(100, scanning_loop)
            return
    
    # Capturar frame de la cámara
    ret, frame = cap.read()
    if not ret:
        logger.error("No se pudo capturar frame de la cámara.")
        camera_retries += 1
        if camera_retries >= MAX_CAMERA_RETRIES:
            logger.critical(f"Se alcanzó el máximo de {MAX_CAMERA_RETRIES} reintentos de captura de frame. Reconectando cámara...")
            # Resetear la cámara
            try:
                if cap is not None:
                    cap.release()
                cap = None  # Forzar reconexión en la próxima iteración
            except Exception as e:
                logger.error(f"Error al liberar cámara para reconexión: {e}")
        
        time.sleep(0.5)
        if pantalla:
            pantalla.after(50, scanning_loop)
        return
    
    # Resetear contador de reintentos si llegamos aquí (captura exitosa)
    camera_retries = 0
    
    # Añadir frame al buffer para procesamiento en segundo plano
    frame_processor.add_frame(frame)
    
    # Preparar frame para mostrar (sin anotaciones de detección)
    display_frame = frame.copy()
    
    # Usar las detecciones procesadas anteriormente en lugar de hacer re-inferencia
    if frame_processor.last_processed_frame is not None:
        # Obtener todas las detecciones ya procesadas
        all_detections = frame_processor.last_detections
        
        # Dibujar bounding boxes en el frame
        if all_detections:
            # Convertir a RGB para Tkinter/PIL
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Dibujar cada detección
            for detection in all_detections:
                b_box = detection['box']
                conf = detection['conf']
                cls_name = detection['cls_name']
                
                x1, y1, x2, y2 = [max(0, coord) for coord in b_box]
                
                # Dibujar bounding box y texto
                label_text = f'{cls_name} {conf:.2f}'
                color = (0, 255, 0)  # Verde
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                (w, h), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(display_frame, (x1, y1 - h - baseline - 5), (x1 + w, y1), (0,0,0), -1)
                cv2.putText(display_frame, label_text, (x1, y1 - baseline - 2), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        else:
            # Convertir a RGB para Tkinter/PIL
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
    else:
        # Si no hay frame procesado aún, solo convertir a RGB
        display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
    
    # Actualizar el frame en la GUI
    try:
        frame_resized = imutils.resize(display_frame, width=FRAME_WIDTH)
        img_pil = Image.fromarray(frame_resized)
        img_tk = ImageTk.PhotoImage(image=img_pil)
        if lblVideo:
            lblVideo.configure(image=img_tk)
            lblVideo.image = img_tk
    except Exception as e:
        logger.error(f"Error actualizando frame en GUI: {e}")
    
    # Programar la siguiente iteración
    if pantalla:
        pantalla.after(20, scanning_loop)

# --- Encapsular GUI en una clase ---
class AppGUI:
    """Clase que encapsula la interfaz gráfica de usuario para reducir el uso de variables globales."""
    
    def __init__(self, parent, config):
        """
        Inicializa la interfaz gráfica de usuario.
        
        Args:
            parent: Ventana raíz de Tkinter
            config: Objeto de configuración
        """
        self.parent = parent
        self.config = config
        
        # Estado interno (anteriormente variables globales)
        self.motor_busy = False
        self.last_detected_class_index = -1
        self.motor_thread = None
        self.processing_stats = {
            'frame_count': 0,
            'last_fps_time': time.time(),
            'fps': 0.0,
            'detection_counts': {class_name: 0 for class_name in CLASS_NAMES},
            'total_detections': 0,
        }
        
        # Elementos de la GUI
        self.lblVideo = None
        self.lblImgExample = None
        self.lblTxtExample = None
        self.lblMotorStatus = None
        self.lblFPS = None
        self.lblTotalCount = None
        self.class_count_labels = {}
        self.bin_level_labels = {}
        
        # Rutas a recursos gráficos desde config
        self.ui_assets_path = config.get('ui_assets.base_path', "ui_assets/")
        self.background_img_path = config.get('ui_assets.background', self.ui_assets_path + "Canva.png")
        self.example_img_paths = config.get('ui_assets.example_images', {
            'Metal': self.ui_assets_path + "metal.png",
            'Glass': self.ui_assets_path + "vidrio.png",
            'Plastic': self.ui_assets_path + "plastico.png",
            'Carton': self.ui_assets_path + "carton.png",
        })
        self.example_txt_paths = config.get('ui_assets.example_texts', {
            'Metal': self.ui_assets_path + "metaltxt.png",
            'Glass': self.ui_assets_path + "vidriotxt.png",
            'Plastic': self.ui_assets_path + "plasticotxt.png",
            'Carton': self.ui_assets_path + "cartontxt.png",
        })
        
        # Imágenes de ejemplo precargadas
        self.example_images = {}
        self.example_texts = {}
        
        # Setup inicial de la GUI
        self._setup_window()
        self._load_ui_assets()
    
    def _setup_window(self):
        """Configura la ventana principal de la aplicación."""
        # Configurar ventana principal
        window_title = self.config.get('window_title', "Cesto Inteligente")
        window_geometry = self.config.get('window_geometry', "1280x720")
        
        self.parent.title(window_title)
        self.parent.geometry(window_geometry)
        self.parent.resizable(False, False)  # Evitar redimensionamiento
        
        # Cargar y poner imagen de fondo
        try:
            bg_image = tk.PhotoImage(file=self.background_img_path)
            background_label = Label(self.parent, image=bg_image)
            background_label.place(x=0, y=0, relwidth=1, relheight=1)
            # Guardar referencia para evitar garbage collection
            self.parent.bg_image_ref = bg_image
        except Exception as e:
            logger.warning(f"ADVERTENCIA: No se pudo cargar la imagen de fondo '{self.background_img_path}': {e}")
        
        # Crear Labels para Video y Ejemplos
        self.lblVideo = Label(self.parent)
        self.lblVideo.place(x=320, y=180)  # Ajustar posición según tu fondo
        
        self.lblImgExample = Label(self.parent)  # Label para imagen de ejemplo
        self.lblImgExample.place(x=75, y=260)  # Ajustar posición
        
        self.lblTxtExample = Label(self.parent)  # Label para texto de ejemplo
        self.lblTxtExample.place(x=995, y=310)  # Ajustar posición
        
        # Crear paneles adicionales
        self.create_config_panel()
        self.create_status_panel()
    
    def _load_ui_assets(self):
        """Carga las imágenes de ejemplo desde las rutas especificadas."""
        logger.info("INFO: Cargando imágenes de ejemplo para la GUI...")
        for name, path in self.example_img_paths.items():
            try:
                img = cv2.imread(path)
                if img is not None:
                    self.example_images[name] = img
                else:
                    logger.warning(f"ADVERTENCIA: No se pudo cargar la imagen de ejemplo: {path}")
            except Exception as e:
                logger.error(f"ERROR: Cargando imagen {path}: {e}")
        
        for name, path in self.example_txt_paths.items():
            try:
                img = cv2.imread(path)
                if img is not None:
                    self.example_texts[name] = img
                else:
                    logger.warning(f"ADVERTENCIA: No se pudo cargar el texto de ejemplo: {path}")
            except Exception as e:
                logger.error(f"ERROR: Cargando texto {path}: {e}")
        logger.info("INFO: Carga de imágenes de ejemplo finalizada.")
    
    def display_example_images(self, class_name):
        """Muestra la imagen y texto de ejemplo para la clase dada."""
        img_to_show = self.example_images.get(class_name)
        txt_to_show = self.example_texts.get(class_name)
        
        # Mostrar imagen de ejemplo
        if img_to_show is not None and self.lblImgExample:
            try:
                img_rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)
                img_tk = ImageTk.PhotoImage(image=img_pil)
                self.lblImgExample.configure(image=img_tk)
                self.lblImgExample.image = img_tk  # Guardar referencia
            except Exception as e:
                logger.error(f"ERROR: Mostrando imagen de ejemplo para {class_name}: {e}")
        elif self.lblImgExample:
            self.lblImgExample.configure(image='')  # Limpiar si no hay imagen
        
        # Mostrar texto de ejemplo
        if txt_to_show is not None and self.lblTxtExample:
            try:
                txt_rgb = cv2.cvtColor(txt_to_show, cv2.COLOR_BGR2RGB)
                txt_pil = Image.fromarray(txt_rgb)
                txt_tk = ImageTk.PhotoImage(image=txt_pil)
                self.lblTxtExample.configure(image=txt_tk)
                self.lblTxtExample.image = txt_tk  # Guardar referencia
            except Exception as e:
                logger.error(f"ERROR: Mostrando texto de ejemplo para {class_name}: {e}")
        elif self.lblTxtExample:
            self.lblTxtExample.configure(image='')  # Limpiar si no hay texto
    
    def clear_example_images(self):
        """Limpia las etiquetas de imágenes de ejemplo en la GUI."""
        if self.lblImgExample:
            self.lblImgExample.configure(image='')
            self.lblImgExample.image = None
        if self.lblTxtExample:
            self.lblTxtExample.configure(image='')
            self.lblTxtExample.image = None
    
    def update_status_indicators(self, sensor_monitoring_active=False):
        """Actualiza los indicadores de estado en la interfaz de usuario."""
        # Actualizar indicador de estado del motor
        if self.lblMotorStatus:
            if self.motor_busy:
                self.lblMotorStatus.config(text="MOTOR: OCUPADO", fg="red", bg="#ffcccc")
            else:
                self.lblMotorStatus.config(text="MOTOR: LISTO", fg="green", bg="#ccffcc")
        
        # Actualizar contador de FPS
        if self.lblFPS:
            self.lblFPS.config(text=f"FPS: {self.processing_stats['fps']:.1f}")
        
        # Actualizar contador total
        if self.lblTotalCount:
            self.lblTotalCount.config(text=f"Total Clasificados: {self.processing_stats['total_detections']}")
        
        # Actualizar contadores por clase
        for class_name, label in self.class_count_labels.items():
            count = self.processing_stats['detection_counts'].get(class_name, 0)
            label.config(text=f"{class_name}: {count}")
        
        # Actualizar indicadores de nivel de llenado (si existen)
        if self.bin_level_labels and sensor_monitoring_active:
            try:
                # Obtener los niveles actuales (lectura única)
                bin_levels = sensor_controller.get_fill_levels(use_average=True, num_readings=1)
                
                # Actualizar cada etiqueta de nivel
                for bin_name, level in bin_levels.items():
                    if level is not None:
                        # Determinar color según nivel de llenado
                        if level > 80:
                            color = "#ff4444"  # Rojo (casi lleno)
                        elif level > 50:
                            color = "#ffaa44"  # Naranja (medio)
                        else:
                            color = "#44aa44"  # Verde (vacío)
                        
                        label = self.bin_level_labels[bin_name]
                        label.config(text=f"Nivel: {level:.1f}%", fg=color)
                    else:
                        label.config(text="Nivel: Error", fg="gray")
            except Exception as e:
                logger.error(f"Error al actualizar niveles de llenado: {e}")
    
    def create_status_panel(self):
        """Crea un panel de estado para mostrar información en tiempo real."""
        # Panel principal para estadísticas
        stats_frame = Frame(self.parent, bg='#f0f0f0', padx=10, pady=10, relief="ridge", bd=2)
        stats_frame.place(x=10, y=170, width=300, height=380)  # Aumentar altura para acomodar nuevos indicadores
        
        # Título del panel
        title_label = Label(stats_frame, text="ESTADO DEL SISTEMA", 
                            font=("Arial", 12, "bold"), bg='#f0f0f0')
        title_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        # Indicador de estado del motor
        self.lblMotorStatus = Label(stats_frame, text="MOTOR: LISTO", 
                                   font=("Arial", 10, "bold"), fg="green", bg="#ccffcc",
                                   width=20, height=2)
        self.lblMotorStatus.grid(row=1, column=0, columnspan=2, pady=10, padx=5)
        
        # Indicador de FPS
        self.lblFPS = Label(stats_frame, text="FPS: 0.0", font=("Arial", 10), bg='#f0f0f0')
        self.lblFPS.grid(row=2, column=0, columnspan=2, pady=5, sticky='w')
        
        # Contador total
        self.lblTotalCount = Label(stats_frame, text="Total Clasificados: 0", 
                                  font=("Arial", 10, "bold"), bg='#f0f0f0')
        self.lblTotalCount.grid(row=3, column=0, columnspan=2, pady=5, sticky='w')
        
        # Línea separadora
        separator = Frame(stats_frame, height=2, bg="gray")
        separator.grid(row=4, column=0, columnspan=2, sticky='ew', pady=8)
        
        # Contadores por clase
        self.class_count_labels = {}
        
        class_counter_title = Label(stats_frame, text="OBJETOS CLASIFICADOS", 
                                   font=("Arial", 10, "bold"), bg='#f0f0f0')
        class_counter_title.grid(row=5, column=0, columnspan=2, pady=5)
        
        for i, class_name in enumerate(CLASS_NAMES):
            count_label = Label(stats_frame, text=f"{class_name}: 0", 
                                font=("Arial", 9), bg='#f0f0f0')
            count_label.grid(row=6+i, column=0, columnspan=2, sticky='w', pady=2)
            self.class_count_labels[class_name] = count_label
        
        # Botón para reiniciar contadores
        reset_button = Button(
            stats_frame,
            text="Reiniciar Contadores",
            command=self.reset_counters
        )
        reset_button.grid(row=6+len(CLASS_NAMES), column=0, columnspan=2, pady=10)
        
        # Línea separadora para sección de niveles
        separator2 = Frame(stats_frame, height=2, bg="gray")
        separator2.grid(row=7+len(CLASS_NAMES), column=0, columnspan=2, sticky='ew', pady=8)
        
        # Sección para indicadores de nivel de llenado
        bin_level_title = Label(stats_frame, text="NIVEL DE LLENADO", 
                             font=("Arial", 10, "bold"), bg='#f0f0f0')
        bin_level_title.grid(row=8+len(CLASS_NAMES), column=0, columnspan=2, pady=5)
        
        # Crear indicadores de nivel para cada compartimento
        self.bin_level_labels = {}
        for i, class_name in enumerate(CLASS_NAMES):
            level_label = Label(stats_frame, text=f"Nivel: --", 
                             font=("Arial", 9), bg='#f0f0f0', fg="gray")
            level_label.grid(row=9+len(CLASS_NAMES)+i, column=0, columnspan=2, sticky='w', pady=2)
            self.bin_level_labels[class_name] = level_label
        
        return stats_frame
    
    def reset_counters(self):
        """Reinicia los contadores de detecciones."""
        self.processing_stats['detection_counts'] = {class_name: 0 for class_name in CLASS_NAMES}
        self.processing_stats['total_detections'] = 0
        self.update_status_indicators(sensor_monitoring_active)
        logger.info("Contadores reiniciados")
    
    def create_config_panel(self):
        """Crea un panel de configuración para ajustar parámetros en tiempo real."""
        global DROP_DELAY, MIN_CONFIDENCE  # Usar variables globales hasta refactor completo
        
        config_frame = Frame(self.parent, bg='#f0f0f0', padx=10, pady=10)
        config_frame.place(x=10, y=10, width=300, height=150)
        
        # Configuración de DROP_DELAY
        drop_delay_label = Label(config_frame, text="Tiempo de Caída (s):", bg='#f0f0f0')
        drop_delay_label.grid(row=0, column=0, sticky='w', pady=5)
        
        drop_delay_var = tk.DoubleVar(value=DROP_DELAY)
        drop_delay_scale = Scale(
            config_frame, 
            from_=0.5, 
            to=5.0, 
            resolution=0.1, 
            orient=HORIZONTAL, 
            variable=drop_delay_var,
            command=self.update_drop_delay
        )
        drop_delay_scale.grid(row=0, column=1, pady=5, padx=5)
        
        # Configuración de MIN_CONFIDENCE
        conf_label = Label(config_frame, text="Umbral de Confianza:", bg='#f0f0f0')
        conf_label.grid(row=1, column=0, sticky='w', pady=5)
        
        conf_var = tk.DoubleVar(value=MIN_CONFIDENCE)
        conf_scale = Scale(
            config_frame, 
            from_=0.1, 
            to=1.0, 
            resolution=0.05, 
            orient=HORIZONTAL, 
            variable=conf_var,
            command=self.update_confidence
        )
        conf_scale.grid(row=1, column=1, pady=5, padx=5)
        
        # Botón para guardar configuración
        save_button = Button(
            config_frame,
            text="Guardar Configuración",
            command=self.save_current_config
        )
        save_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        return config_frame
    
    def update_drop_delay(self, new_value):
        """Actualiza el tiempo de caída en tiempo real."""
        global DROP_DELAY
        DROP_DELAY = float(new_value)
        logger.info(f"Tiempo de caída actualizado a {DROP_DELAY} segundos")
    
    def update_confidence(self, new_value):
        """Actualiza el umbral de confianza en tiempo real."""
        global MIN_CONFIDENCE
        MIN_CONFIDENCE = float(new_value)
        logger.info(f"Umbral de confianza actualizado a {MIN_CONFIDENCE}")
    
    def save_current_config(self):
        """Guarda la configuración actual al archivo."""
        global config, DROP_DELAY, MIN_CONFIDENCE
        config.set('drop_delay', DROP_DELAY)
        config.set('min_confidence', MIN_CONFIDENCE)
        config.save()
        logger.info("Configuración guardada correctamente")
    
    def update_fill_indicators(self, levels):
        """
        Actualiza los indicadores visuales de nivel de llenado en la GUI.
        
        Args:
            levels (dict): Diccionario con los niveles de llenado por compartimento
        """
        # Actualizar cada etiqueta con su nivel correspondiente
        for bin_name, level in levels.items():
            if bin_name in self.bin_level_labels:
                label = self.bin_level_labels[bin_name]
                
                if level is not None:
                    # Determinar color según nivel de llenado
                    if level > 80:
                        color = "#ff4444"  # Rojo (casi lleno)
                    elif level > 50:
                        color = "#ffaa44"  # Naranja (medio)
                    else:
                        color = "#44aa44"  # Verde (vacío)
                    
                    label.config(text=f"Nivel: {level:.1f}%", fg=color)
                else:
                    label.config(text="Nivel: Error", fg="gray")
        
        # Nuevo: Actualizar adaptador web con niveles de llenado
        main_web_adapter.update_data(fill_levels=levels)
    
    def update_camera_frame(self, frame):
        """Actualiza el frame de la cámara en la GUI."""
        if self.lblVideo:
            try:
                frame_width = self.config.get('frame_width')
                frame_resized = imutils.resize(frame, width=frame_width)
                img_pil = Image.fromarray(frame_resized)
                img_tk = ImageTk.PhotoImage(image=img_pil)
                self.lblVideo.configure(image=img_tk)
                self.lblVideo.image = img_tk
            except Exception as e:
                logger.error(f"Error actualizando frame en GUI: {e}")
    
    def show_error_frame(self, message="ERROR DE CAMARA"):
        """Muestra un frame de error en la GUI."""
        if self.lblVideo:
            try:
                error_img = np.zeros((300, 400, 3), dtype=np.uint8)
                cv2.putText(error_img, message, (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                img_rgb = cv2.cvtColor(error_img, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)
                img_tk = ImageTk.PhotoImage(image=img_pil)
                self.lblVideo.configure(image=img_tk)
                self.lblVideo.image = img_tk
            except Exception as e:
                logger.error(f"Error mostrando frame de error: {e}")

    def handle_detection(self, best_detection, all_detections=None):
        """
        Callback que se llama cuando el procesador de frames tiene una detección.
        
        Args:
            best_detection: La mejor detección (mayor confianza)
            all_detections: Lista de todas las detecciones válidas
        """
        if best_detection:
            # Tenemos una detección
            cls_index = best_detection['cls_index']
            cls_name = best_detection['cls_name']
            
            # Mostrar la imagen de ejemplo asociada
            self.display_example_images(cls_name)
            
            # Si el motor no está ocupado y es una nueva clase, activar motor
            if not self.motor_busy and cls_index in TARGET_STEPS_MAP and cls_index != self.last_detected_class_index:
                self.motor_busy = True
                self.update_status_indicators(sensor_monitoring_active)
                target_position = TARGET_STEPS_MAP[cls_index]
                logger.info(f"Detección válida: '{cls_name}'. Iniciando motor hacia {target_position} pasos.")
                
                # Actualizar contadores
                self.processing_stats['detection_counts'][cls_name] = self.processing_stats['detection_counts'].get(cls_name, 0) + 1
                self.processing_stats['total_detections'] += 1
                self.update_status_indicators(sensor_monitoring_active)
                
                # Iniciar hilo del motor
                self.motor_thread = threading.Thread(
                    target=self.handle_motor_sequence,
                    args=(target_position, cls_name),
                    daemon=True
                )
                self.motor_thread.start()
                
                # Actualizar última clase
                self.last_detected_class_index = cls_index
                
                # Actualizar adaptador web
                detection_data = {
                    'class_name': cls_name,
                    'confidence': best_detection['conf']
                }
                # Actualizar adaptador web
                main_web_adapter.update_data(detection=detection_data)
        else:
            # No hay detección, limpiar si no hay motor activo
            if not self.motor_busy and self.last_detected_class_index != -1:
                self.last_detected_class_index = -1
                self.clear_example_images()

    def handle_motor_sequence(self, target_position, class_name):
        """
        Ejecuta la secuencia completa del motor en un hilo dedicado.
        Esto evita bloquear el hilo principal y la interfaz gráfica.
        """
        logger.info(f"THREAD: Iniciando secuencia de motor para '{class_name}' a {target_position} pasos.")
        try:
            # 1. Mover a la posición de la clase detectada
            logger.info(f"THREAD: Moviendo a posición {target_position}...")
            motor_controller.move_motor_to_position(target_position)
            logger.info(f"THREAD: Motor en posición {target_position}.")

            # 2. Esperar a que el objeto caiga
            logger.info(f"THREAD: Esperando {DROP_DELAY:.1f} segundos para que caiga el objeto...")
            time.sleep(DROP_DELAY)  # time.sleep() es seguro aquí (hilo separado)

            # 3. Volver a la posición HOME (si es diferente)
            if target_position != HOME_POSITION_STEPS:
                logger.info(f"THREAD: Volviendo a posición HOME ({HOME_POSITION_STEPS} pasos)...")
                motor_controller.move_motor_to_position(HOME_POSITION_STEPS)
                time.sleep(0.5)  # Pequeña pausa después de volver
                logger.info("THREAD: Motor en posición HOME.")
            else:
                logger.info("THREAD: Ya estaba en posición HOME, no se requiere retorno.")

            logger.info(f"THREAD: Secuencia de motor para '{class_name}' completada.")

        except Exception as e:
            logger.error(f"ERROR EN THREAD DEL MOTOR: {e}")
            # Intentar volver a HOME si falla en medio del movimiento (opcional)
            try:
                 logger.info("THREAD: Intentando volver a HOME después de error...")
                 motor_controller.move_motor_to_position(HOME_POSITION_STEPS)
            except Exception as e2:
                 logger.error(f"ERROR EN THREAD: No se pudo volver a HOME: {e2}")

        finally:
            # 4. ¡MUY IMPORTANTE! Liberar el flag para permitir nuevas detecciones.
            logger.info("THREAD: Liberando bandera 'motor_busy'.")
            self.motor_busy = False
            # Usar after para actualizar la UI desde el hilo principal
            if self.parent:
                self.parent.after(10, lambda: self.update_status_indicators(sensor_monitoring_active))
                
    def update_frame_stats(self):
        """Actualiza las estadísticas de procesamiento de frames (FPS)."""
        self.processing_stats['frame_count'] += 1
        current_time = time.time()
        time_diff = current_time - self.processing_stats['last_fps_time']
        
        # Actualizar FPS cada segundo
        if time_diff >= 1.0:
            self.processing_stats['fps'] = self.processing_stats['frame_count'] / time_diff
            self.processing_stats['last_fps_time'] = current_time
            self.processing_stats['frame_count'] = 0
            self.update_status_indicators(sensor_monitoring_active)
    
    def scanning_loop(self, cap, frame_processor, model):
        """
        Bucle principal para capturar y procesar frames de la cámara.
        
        Args:
            cap: Objeto de captura de OpenCV
            frame_processor: Procesador de frames
            model: Modelo YOLO 
        """
        # Variables de seguimiento para reintentos de cámara
        MAX_CAMERA_RETRIES = 5
        camera_retries = 0
        
        # Actualizar estadísticas de frames
        self.update_frame_stats()
        
        if cap is None or not cap.isOpened():
            logger.error("Cámara no disponible o cerrada. Intentando reconectar...")
            try:
                if cap is not None:
                    cap.release()  # Liberar recursos antes de intentar reconectar
                
                # Verificar si excedimos el número máximo de reintentos
                if camera_retries >= MAX_CAMERA_RETRIES:
                    logger.critical(f"Se alcanzó el máximo de {MAX_CAMERA_RETRIES} reintentos de reconexión de cámara. Deteniendo escaneo.")
                    if self.parent:
                        # Mostrar mensaje de error en la GUI
                        self.show_error_frame("ERROR DE CAMARA")
                        # Continuar el bucle sin intentar capturar frames
                        self.parent.after(100, lambda: self.scanning_loop(cap, frame_processor, model))
                    return
                
                # Intentar reconectar
                cap = cv2.VideoCapture(CAMERA_INDEX)
                if cap.isOpened():
                    logger.info("Cámara reconectada exitosamente.")
                    camera_retries = 0  # Reiniciar contador de reintentos si tuvimos éxito
                else:
                    camera_retries += 1
                    logger.warning(f"Reintento {camera_retries}/{MAX_CAMERA_RETRIES} fallido. Esperando antes de volver a intentar...")
                    time.sleep(1.0)  # Esperar antes de reintentar
                    if self.parent:
                        self.parent.after(100, lambda: self.scanning_loop(cap, frame_processor, model))
                    return
            except Exception as e:
                camera_retries += 1
                logger.error(f"Error al reconectar cámara: {e}. Reintento {camera_retries}/{MAX_CAMERA_RETRIES}")
                time.sleep(1.0)
                if self.parent:
                    self.parent.after(100, lambda: self.scanning_loop(cap, frame_processor, model))
                return
        
        # Capturar frame de la cámara
        ret, frame = cap.read()
        if not ret:
            logger.error("No se pudo capturar frame de la cámara.")
            camera_retries += 1
            if camera_retries >= MAX_CAMERA_RETRIES:
                logger.critical(f"Se alcanzó el máximo de {MAX_CAMERA_RETRIES} reintentos de captura de frame. Reconectando cámara...")
                # Resetear la cámara
                try:
                    if cap is not None:
                        cap.release()
                    cap = None  # Forzar reconexión en la próxima iteración
                except Exception as e:
                    logger.error(f"Error al liberar cámara para reconexión: {e}")
            
            time.sleep(0.5)
            if self.parent:
                self.parent.after(50, lambda: self.scanning_loop(cap, frame_processor, model))
            return
        
        # Resetear contador de reintentos si llegamos aquí (captura exitosa)
        camera_retries = 0
        
        # Añadir frame al buffer para procesamiento en segundo plano
        frame_processor.add_frame(frame)
        
        # Preparar frame para mostrar (sin anotaciones de detección)
        display_frame = frame.copy()
        
        # Usar las detecciones procesadas anteriormente en lugar de hacer re-inferencia
        if frame_processor.last_processed_frame is not None:
            # Obtener todas las detecciones ya procesadas
            all_detections = frame_processor.last_detections
            
            # Dibujar bounding boxes en el frame
            if all_detections:
                # Convertir a RGB para Tkinter/PIL
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                
                # Dibujar cada detección
                for detection in all_detections:
                    b_box = detection['box']
                    conf = detection['conf']
                    cls_name = detection['cls_name']
                    
                    x1, y1, x2, y2 = [max(0, coord) for coord in b_box]
                    
                    # Dibujar bounding box y texto
                    label_text = f'{cls_name} {conf:.2f}'
                    color = (0, 255, 0)  # Verde
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                    (w, h), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(display_frame, (x1, y1 - h - baseline - 5), (x1 + w, y1), (0,0,0), -1)
                    cv2.putText(display_frame, label_text, (x1, y1 - baseline - 2), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            else:
                # Convertir a RGB para Tkinter/PIL
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        else:
            # Si no hay frame procesado aún, solo convertir a RGB
            display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        
        # Actualizar el frame en la GUI
        self.update_camera_frame(display_frame)
        
        # Programar la siguiente iteración
        if self.parent:
            self.parent.after(20, lambda: self.scanning_loop(cap, frame_processor, model))

# --- Función Principal de la Aplicación ---

def main_app():
    """Inicializa la aplicación, carga recursos, configura la GUI y arranca el bucle."""
    global cap, model, pantalla, frame_processor, sensor_monitoring_active
    global motor_busy  # Motor sigue siendo global por ahora
    
    setup_successful = False # Flag para controlar limpieza de GPIO
    sensors_setup_successful = False # Flag para controlar limpieza de sensores
    pantalla = None # Asegurar que pantalla es None al inicio
    gui = None  # La instancia de la clase GUI

    try:
        # Inicializar primero el adaptador web
        logger.info("Iniciando servidor web adapter para comunicación con el backend...")
        main_web_adapter.start_server()
        logger.info(f"Servidor web adapter iniciado en {main_web_adapter.HOST}:{main_web_adapter.PORT}")
        
        # Actualizar estado inicial
        main_web_adapter.update_data(system_status="active")
        
        # --- 1. Inicializar GPIO para el Motor ---
        logger.info("INFO: Inicializando GPIO para control del motor...")
        if not motor_controller.setup_gpio():
            # setup_gpio ya debería imprimir un error específico
            raise RuntimeError("Fallo al inicializar GPIO. ¿Ejecutando en Raspberry Pi con permisos (sudo)?")
        logger.info("INFO: GPIO inicializado correctamente.")
        setup_successful = True # Marcar que GPIO se configuró
        
        # --- 1.1 Inicializar sensores ultrasónicos ---
        logger.info("INFO: Inicializando sensores de nivel de llenado...")
        if not sensor_controller.setup_sensors():
            logger.warning("ADVERTENCIA: No se pudieron configurar los sensores de nivel. La función de monitoreo estará desactivada.")
        else:
            sensors_setup_successful = True
            logger.info("INFO: Sensores de nivel inicializados correctamente.")

        # --- 2. Configurar Ventana Principal (GUI con Tkinter) ---
        logger.info("INFO: Creando ventana principal de la GUI...")
        pantalla = tk.Tk()
        # Inicializar la GUI encapsulada en la clase AppGUI
        gui = AppGUI(pantalla, config)
        logger.info("INFO: GUI creada.")

        # --- 3. Cargar Modelo YOLO ---
        logger.info(f"INFO: Cargando modelo YOLO desde '{MODEL_PATH}'...")
        try:
            model = YOLO(MODEL_PATH)
            # Opcional: hacer una inferencia dummy para calentar/verificar
            # model(np.zeros((480, 640, 3)), verbose=False)
            logger.info("INFO: Modelo YOLO cargado exitosamente.")
        except Exception as e:
            raise RuntimeError(f"Error CRÍTICO al cargar el modelo YOLO desde '{MODEL_PATH}': {e}")

        # --- 5. Inicializar Cámara ---
        logger.info(f"INFO: Inicializando cámara (índice {CAMERA_INDEX})...")
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            raise IOError(f"Error CRÍTICO: No se puede abrir la cámara con índice {CAMERA_INDEX}. Verifica conexión y permisos.")
        logger.info("INFO: Cámara inicializada.")

        # --- 6. Actualizar funciones para usar la GUI encapsulada ---
        # Actualizar el callback de detección para usar la instancia gui
        def adapted_detection_callback(best_detection, all_detections=None):
            gui.handle_detection(best_detection, all_detections)
            gui.update_status_indicators(sensor_monitoring_active)
        
        # Iniciar el procesador de frames con el callback adaptado
        logger.info("INFO: Iniciando procesador de frames...")
        frame_processor.start_processing(model, MIN_CONFIDENCE, adapted_detection_callback)
        
        logger.info("INFO: Iniciando bucle principal de escaneo y detección...")
        gui.scanning_loop(cap, frame_processor, model)

        # --- 7. Iniciar monitoreo de niveles de llenado ---
        if sensors_setup_successful:
            logger.info("INFO: Iniciando monitoreo de niveles de llenado...")
            sensor_monitoring_active = sensor_controller.start_continuous_monitoring(
                callback=gui.update_fill_indicators,
                interval=10.0  # Actualizar cada 10 segundos
            )
            if sensor_monitoring_active:
                logger.info("INFO: Monitoreo de niveles iniciado correctamente.")
            else:
                logger.warning("ADVERTENCIA: No se pudo iniciar el monitoreo de niveles.")

        # --- 8. Iniciar Bucle Principal de Tkinter ---
        # Esto mantiene la ventana abierta y procesa eventos
        pantalla.mainloop()

        # Nuevo: Actualizar estado de cierre
        main_web_adapter.update_data(system_status="inactive")

    except Exception as e:
        logger.critical(f"\nERROR CRÍTICO EN LA APLICACIÓN: {e}")
        # Nuevo: Actualizar estado de error
        main_web_adapter.update_data(system_status="error")
        # No es necesario mostrar un mensaje de error adicional ya que tenemos el logger

    finally:
        # Limpiar recursos y cerrar conexiones
        logger.info("INFO: Realizando limpieza de recursos...")
        
        try:
            # Detener el procesamiento de video si está activo
            if frame_processor and frame_processor.is_running:
                logger.info("INFO: Deteniendo procesamiento de video...")
                frame_processor.stop_processing()
        except Exception as proc_e:
            logger.error(f"ERROR: Durante la limpieza del procesador de video: {proc_e}")
            
        try:
            # Limpiar recursos de GPIO (motor)
            logger.info("INFO: Limpiando recursos de GPIO...")
            motor_controller.cleanup_gpio()
        except Exception as gpio_e:
            logger.error(f"ERROR: Durante la limpieza de GPIO: {gpio_e}")
            
        try:
            # Detener monitoreo de sensores y limpiar
            logger.info("INFO: Limpiando recursos de sensores...")
            sensor_controller.cleanup_sensors()
        except Exception as sensor_e:
            logger.error(f"ERROR: Durante la limpieza de sensores: {sensor_e}")
        
        # Liberar la cámara
        try:
            if cap is not None:
                logger.info("INFO: Liberando recursos de cámara...")
                cap.release()
                logger.info("INFO: Cámara liberada correctamente.")
        except Exception as cam_e:
            logger.error(f"ERROR: Durante la liberación de la cámara: {cam_e}")

        # Detener el servidor web adapter
        logger.info("Deteniendo servidor web adapter...")
        main_web_adapter.stop_server()
        logger.info("Servidor web adapter detenido")

        logger.info("INFO: Aplicación cerrada.")

# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    logger.info("=============================================")
    logger.info(" Iniciando Aplicación Cesto Inteligente ")
    logger.info("=============================================")
    main_app()
    logger.info("Aplicación finalizada.")
    logger.info("=============================================")