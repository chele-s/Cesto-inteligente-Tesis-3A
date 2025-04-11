# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# TrashDetect.py - Script para Detección de Residuos con YOLOv8
# Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
# Fecha: Abril de 2024
# Descripción: Utiliza un modelo YOLOv8 entrenado para detectar tipos de
#              residuos (Metal, Vidrio, Plástico, Cartón) utilizando
#              la cámara en tiempo real.
# -----------------------------------------------------------------------------

import os
import sys
import cv2
import math
import argparse
import yaml
import logging
import time
from pathlib import Path
from ultralytics import YOLO

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('TrashDetect')

# Valores por defecto
DEFAULT_MODEL_PATH = 'models/best.pt'
DEFAULT_CAMERA_INDEX = 0
DEFAULT_CAMERA_WIDTH = 1280
DEFAULT_CAMERA_HEIGHT = 720
DEFAULT_CONFIDENCE = 0.45
DEFAULT_DATA_YAML = 'dataset_basura/data.yaml'


def parse_arguments():
    """
    Parsea los argumentos de línea de comandos para configurar la detección.
    """
    parser = argparse.ArgumentParser(description='Detección de residuos en tiempo real con YOLOv8')
    
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_PATH,
                        help=f'Ruta al modelo YOLOv8 (default: {DEFAULT_MODEL_PATH})')
    parser.add_argument('--camera', type=int, default=DEFAULT_CAMERA_INDEX,
                        help=f'Índice de la cámara a usar (default: {DEFAULT_CAMERA_INDEX})')
    parser.add_argument('--width', type=int, default=DEFAULT_CAMERA_WIDTH,
                        help=f'Ancho de la captura de cámara (default: {DEFAULT_CAMERA_WIDTH})')
    parser.add_argument('--height', type=int, default=DEFAULT_CAMERA_HEIGHT,
                        help=f'Alto de la captura de cámara (default: {DEFAULT_CAMERA_HEIGHT})')
    parser.add_argument('--conf', type=float, default=DEFAULT_CONFIDENCE,
                        help=f'Umbral de confianza para detecciones (default: {DEFAULT_CONFIDENCE})')
    parser.add_argument('--data', type=str, default=DEFAULT_DATA_YAML,
                        help=f'Archivo data.yaml con nombres de clases (default: {DEFAULT_DATA_YAML})')
    
    return parser.parse_args()


def load_class_names(yaml_path):
    """
    Carga los nombres de clases desde el archivo data.yaml.
    Si no puede cargar el archivo, devuelve una lista predeterminada.
    """
    default_classes = ['Metal', 'Glass', 'Plastic', 'Carton']
    
    if not os.path.exists(yaml_path):
        logger.warning(f"Archivo {yaml_path} no encontrado. Usando nombres de clases por defecto.")
        return default_classes
    
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            if 'names' in data and isinstance(data['names'], list):
                logger.info(f"Clases cargadas de {yaml_path}: {data['names']}")
                return data['names']
            else:
                logger.warning(f"Formato incorrecto en {yaml_path}. Usando nombres de clases por defecto.")
                return default_classes
    except Exception as e:
        logger.error(f"Error al cargar {yaml_path}: {e}")
        return default_classes


def setup_camera(camera_index, width, height):
    """
    Configura la cámara con los parámetros especificados.
    Devuelve el objeto de captura o None si falla.
    """
    try:
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error(f"No se pudo abrir la cámara con índice {camera_index}")
            return None
        
        # Establecer resolución (puede no funcionar en todas las cámaras)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        
        # Verificar la resolución real (puede diferir de la solicitada)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(f"Cámara inicializada. Resolución: {actual_width}x{actual_height}")
        
        return cap
    
    except Exception as e:
        logger.error(f"Error al configurar la cámara: {e}")
        return None


def load_model(model_path):
    """
    Carga el modelo YOLO desde la ruta especificada.
    Devuelve el modelo o None si falla.
    """
    if not os.path.exists(model_path):
        logger.error(f"No se encontró el modelo en {model_path}")
        return None
    
    try:
        logger.info(f"Cargando modelo desde {model_path}...")
        model = YOLO(model_path)
        logger.info("Modelo cargado correctamente")
        return model
    
    except Exception as e:
        logger.error(f"Error al cargar el modelo: {e}")
        return None


def process_frame(frame, model, class_names, min_confidence):
    """
    Procesa un frame con el modelo YOLO.
    Devuelve el frame con anotaciones y la mejor detección.
    """
    if frame is None or model is None:
        return frame, None
    
    # Hacer una copia del frame original
    annotated_frame = frame.copy()
    best_detection = None
    
    try:
        # Inferencia
        results = model(frame, stream=True, verbose=False)
        
        for res in results:
            boxes = res.boxes
            for box in boxes:
                # Obtener confianza
                conf = float(box.conf[0])
                
                # Filtrar por umbral de confianza
                if conf < min_confidence:
                    continue
                
                # Obtener índice de clase
                cls_idx = int(box.cls[0])
                
                # Verificar si el índice de clase es válido
                if cls_idx < 0 or cls_idx >= len(class_names):
                    logger.warning(f"Índice de clase inválido: {cls_idx}")
                    continue
                
                # Obtener clase
                cls_name = class_names[cls_idx]
                
                # Obtener coordenadas del bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Asegurar que las coordenadas estén dentro de los límites del frame
                height, width = frame.shape[:2]
                x1 = max(0, min(x1, width - 1))
                y1 = max(0, min(y1, height - 1))
                x2 = max(0, min(x2, width - 1))
                y2 = max(0, min(y2, height - 1))
                
                # Guardar la mejor detección (mayor confianza)
                if best_detection is None or conf > best_detection['conf']:
                    best_detection = {
                        'box': (x1, y1, x2, y2),
                        'conf': conf,
                        'cls_idx': cls_idx,
                        'cls_name': cls_name
                    }
                
                # Dibujar bounding box y etiqueta
                color = (0, 0, 255)  # Rojo (BGR)
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                
                # Preparar texto de etiqueta
                label_text = f'{cls_name} {int(conf * 100)}%'
                
                # Dibujar fondo para el texto
                (text_width, text_height), baseline = cv2.getTextSize(
                    label_text, cv2.FONT_HERSHEY_COMPLEX, 1, 2
                )
                cv2.rectangle(
                    annotated_frame, 
                    (x1, y1 - 20 - text_height), 
                    (x1 + text_width, y1), 
                    (0, 0, 0), 
                    -1
                )
                
                # Dibujar texto
                cv2.putText(
                    annotated_frame, 
                    label_text, 
                    (x1, y1 - 20), 
                    cv2.FONT_HERSHEY_COMPLEX, 
                    1, 
                    color, 
                    2
                )
        
        # Mostrar información de la mejor detección (solo para depuración)
        if best_detection:
            logger.debug(
                f"Mejor detección: {best_detection['cls_name']} "
                f"(Conf: {best_detection['conf']:.2f})"
            )
        
        return annotated_frame, best_detection
    
    except Exception as e:
        logger.error(f"Error procesando frame: {e}")
        return frame, None


def calculate_fps(start_time, frame_count):
    """
    Calcula los FPS basado en el tiempo transcurrido y el número de frames.
    """
    elapsed_time = time.time() - start_time
    if elapsed_time > 0:
        return frame_count / elapsed_time
    return 0


def main():
    """Función principal del programa."""
    # Parsear argumentos de línea de comandos
    args = parse_arguments()
    
    # Cargar nombres de clases desde data.yaml
    class_names = load_class_names(args.data)
    
    # Cargar modelo YOLOv8
    model = load_model(args.model)
    if model is None:
        return 1
    
    # Configurar cámara
    cap = setup_camera(args.camera, args.width, args.height)
    if cap is None:
        return 1
    
    # Variables para mostrar FPS
    start_time = time.time()
    frame_count = 0
    fps = 0
    
    # Crear ventana
    window_name = "Waste Detect"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    logger.info("Iniciando bucle de detección. Presiona 'ESC' o 'q' para salir.")
    
    try:
        # Bucle principal
        while True:
            # Capturar frame
            ret, frame = cap.read()
            if not ret:
                logger.error("Error al capturar frame. Comprueba la conexión de la cámara.")
                # Intentar reconectarse a la cámara
                time.sleep(1.0)
                cap = setup_camera(args.camera, args.width, args.height)
                if cap is None:
                    break
                continue
            
            # Procesar frame
            annotated_frame, detection = process_frame(frame, model, class_names, args.conf)
            
            # Calcular FPS cada 10 frames
            frame_count += 1
            if frame_count % 10 == 0:
                fps = calculate_fps(start_time, frame_count)
                # Resetear para el siguiente cálculo
                start_time = time.time()
                frame_count = 0
            
            # Mostrar FPS en el frame
            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),  # Verde
                2
            )
            
            # Mostrar el frame
            cv2.imshow(window_name, annotated_frame)
            
            # Comprobar tecla presionada (ESC o q para salir)
            key = cv2.waitKey(1)
            if key == 27 or key == ord('q'):  # ESC o 'q'
                logger.info("Saliendo por petición del usuario.")
                break
    
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado (Ctrl+C). Saliendo...")
    
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
    
    finally:
        # Liberar recursos
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        logger.info("Recursos liberados. Programa finalizado.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())