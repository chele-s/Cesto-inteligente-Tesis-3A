# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# train_yolo.py - Script para Entrenar el Modelo YOLOv8
# Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
# Fecha: Abril de 2024
# Descripción: Carga un modelo base YOLOv8, lo entrena con un dataset
#              personalizado (definido en data.yaml) para la detección
#              de residuos (Metal, Vidrio, Plástico, Cartón), y guarda
#              el modelo entrenado ('best.pt').
# -----------------------------------------------------------------------------

import os
import sys
import torch
from ultralytics import YOLO
import datetime # Para nombres de experimento únicos
import argparse
import logging
import yaml
import platform

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('train_yolo')

def parse_arguments():
    """
    Parsea los argumentos de línea de comandos para configurar el entrenamiento.
    """
    parser = argparse.ArgumentParser(description='Entrenamiento de YOLOv8 para detección de residuos')
    
    # Argumentos principales
    parser.add_argument('--data', type=str, default='./DATASET_basura/data.yaml',
                        help='Ruta al archivo data.yaml')
    parser.add_argument('--model', type=str, default='yolov8n.pt',
                        help='Modelo base a utilizar (yolov8n.pt, yolov8s.pt, etc.)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Número de épocas de entrenamiento')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='Tamaño de las imágenes para entrenamiento')
    parser.add_argument('--batch', type=int, default=16,
                        help='Tamaño del batch (-1 para auto)')
    
    # Argumentos de proyecto
    parser.add_argument('--project', type=str, default='CestoInteligente_Train',
                        help='Nombre del proyecto')
    parser.add_argument('--name', type=str, default=None,
                        help='Nombre del experimento (por defecto se genera automáticamente)')
    
    # Argumentos avanzados
    parser.add_argument('--workers', type=int, default=4,
                        help='Número de workers para carga de datos')
    parser.add_argument('--patience', type=int, default=25,
                        help='Épocas para early stopping')
    parser.add_argument('--device', type=str, default='',
                        help='Dispositivo (cuda, cpu, mps o "" para auto)')
    parser.add_argument('--resume', action='store_true',
                        help='Reanudar entrenamiento desde último checkpoint')
    parser.add_argument('--resume_path', type=str, default=None,
                        help='Ruta específica al archivo .pt para reanudar')
    
    return parser.parse_args()

def normalize_path(path):
    """
    Normaliza las rutas para manejar problemas con espacios en nombre de directorios.
    """
    # Reemplazar posibles espacios con guiones bajos para mayor compatibilidad
    normalized = path.replace(' ', '_')
    
    # En Windows, asegurarse de usar / en lugar de \
    if platform.system() == 'Windows':
        normalized = normalized.replace('\\', '/')
    
    return normalized

def validate_data_yaml(data_path):
    """
    Valida la estructura del archivo data.yaml y verifica las rutas
    """
    try:
        # Normalizar la ruta antes de abrirla
        normalized_path = normalize_path(data_path)
        
        with open(normalized_path, 'r') as f:
            data_config = yaml.safe_load(f)
        
        # Verificar campos requeridos
        required_keys = ['train', 'val', 'nc', 'names']
        for key in required_keys:
            if key not in data_config:
                logger.error(f"El archivo data.yaml no contiene la clave requerida '{key}'")
                return False
        
        # Verificar tipo de datos para nc
        if not isinstance(data_config['nc'], int):
            logger.error("El número de clases (nc) debe ser un entero")
            return False
            
        # Verificar coherencia entre nc y names
        if not isinstance(data_config['names'], list) or len(data_config['names']) != data_config['nc']:
            logger.error(f"La lista 'names' debe tener exactamente {data_config['nc']} elementos")
            return False
            
        # Verificar nombres duplicados
        if len(set(data_config['names'])) != len(data_config['names']):
            logger.error("Hay nombres de clases duplicados en 'names'")
            return False
            
        logger.info(f"Archivo data.yaml válido con {data_config['nc']} clases: {data_config['names']}")
        
        # Verificar existencia de rutas de entrenamiento y validación
        base_dir = os.path.dirname(os.path.abspath(normalized_path))
        
        # Normalizar también las rutas dentro del YAML
        train_path = os.path.join(base_dir, normalize_path(data_config['train']))
        val_path = os.path.join(base_dir, normalize_path(data_config['val']))
        
        if not os.path.exists(train_path):
            logger.warning(f"La ruta de entrenamiento no existe: {train_path}")
            # No fallamos aquí, solo advertimos
        else:
            logger.info(f"Ruta de entrenamiento verificada: {train_path}")
            
        if not os.path.exists(val_path):
            logger.warning(f"La ruta de validación no existe: {val_path}")
            # No fallamos aquí, solo advertimos
        else:
            logger.info(f"Ruta de validación verificada: {val_path}")
        
        # Verificar rutas de etiquetas (opcional)
        train_labels_path = train_path.replace('/images/', '/labels/')
        val_labels_path = val_path.replace('/images/', '/labels/')
        
        if not os.path.exists(train_labels_path):
            logger.warning(f"La ruta de etiquetas de entrenamiento podría no existir: {train_labels_path}")
        else:
            logger.info(f"Ruta de etiquetas de entrenamiento verificada: {train_labels_path}")
            
        if not os.path.exists(val_labels_path):
            logger.warning(f"La ruta de etiquetas de validación podría no existir: {val_labels_path}")
        else:
            logger.info(f"Ruta de etiquetas de validación verificada: {val_labels_path}")
            
        # Si hay parámetros adicionales en data.yaml, mostrarlos como información
        additional_params = {k: v for k, v in data_config.items() 
                            if k not in required_keys and k != 'test'}
        if additional_params:
            logger.info(f"Parámetros adicionales en data.yaml: {additional_params}")
            
        return True
    except Exception as e:
        logger.error(f"Error al validar data.yaml: {e}")
        return False

def train_waste_detector(args):
    """
    Configura y ejecuta el proceso de entrenamiento del modelo YOLOv8
    para la detección de residuos.
    """
    logger.info("--- Iniciando Script de Entrenamiento YOLOv8 ---")

    # --- 1. Configuración del Entrenamiento ---

    # --- Configuración Básica ---
    MODEL_NAME = args.model
    DATA_CONFIG_PATH = normalize_path(args.data)  # Normalizar la ruta
    EPOCHS = args.epochs
    IMAGE_SIZE = args.imgsz
    BATCH_SIZE = args.batch
    PROJECT_NAME = args.project
    
    # Crear un nombre de experimento único con fecha y hora si no se proporciona
    if args.name:
        EXPERIMENT_NAME = args.name
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        EXPERIMENT_NAME = f'{MODEL_NAME.split(".")[0]}_epochs{EPOCHS}_{timestamp}'
    
    # Hiperparámetros avanzados
    NUM_WORKERS = args.workers
    PATIENCE = args.patience
    RESUME_TRAINING = args.resume
    RESUME_PATH = args.resume_path

    # --- Configuración de Aumento de Datos (Data Augmentation) ---
    AUGMENT_PARAMS = {
        'degrees': 15.0,      # Rotación aleatoria (+/- grados)
        'translate': 0.1,   # Traslación aleatoria (+/- fracción de imagen)
        'scale': 0.4,       # Escalado aleatorio (+/- factor) - Aumentado un poco
        'shear': 5.0,       # Corte aleatorio (+/- grados)
        'perspective': 0.0, # Perspectiva aleatoria (normalmente 0.0 para detección)
        'flipud': 0.3,      # Probabilidad de volteo vertical
        'fliplr': 0.5,      # Probabilidad de volteo horizontal (muy útil)
        'mosaic': 0.8,      # Probabilidad de aumento Mosaico (combina 4 imgs) - Puede desactivarse al final (mosaic=0.0)
        'mixup': 0.1,       # Probabilidad de MixUp (mezcla 2 imgs y etiquetas)
        'copy_paste': 0.1   # Probabilidad de Copy-Paste (copia y pega objetos)
    }

    # --- Opciones Adicionales ---
    SAVE_PERIOD = -1        # Guardar checkpoint cada N épocas (-1 para desactivar, solo guarda 'best' y 'last')
    PLOTS = True            # Generar gráficos de resultados (curvas, matrices de confusión) al final.

    # --- 2. Verificación de Archivos y Entorno ---

    # Verificar que el archivo data.yaml existe
    abs_data_path = os.path.abspath(DATA_CONFIG_PATH)
    if not os.path.exists(DATA_CONFIG_PATH):
        logger.error(f"¡ERROR FATAL! No se encontró el archivo de configuración del dataset en: '{abs_data_path}'")
        logger.error("Asegúrate de que la ruta sea correcta y el archivo exista antes de continuar.")
        logger.error(f"Asegúrate de que la carpeta DATASET_basura existe (sin espacios en el nombre)")
        return # Salir si no se encuentra el archivo
    else:
        logger.info(f"Usando archivo de configuración del dataset: '{abs_data_path}'")
        
    # Validar estructura del archivo data.yaml
    if not validate_data_yaml(DATA_CONFIG_PATH):
        logger.error("El archivo data.yaml no tiene el formato correcto.")
        return

    # Determinar el dispositivo a usar
    device = args.device
    if not device:  # Si no se especificó, detectar automáticamente
        if torch.cuda.is_available():
            device = 'cuda'
            logger.info("GPU CUDA detectada. Usando GPU para el entrenamiento.")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = 'mps'
            logger.info("Apple MPS detectado. Usando GPU para el entrenamiento.")
        else:
            device = 'cpu'
            logger.warning("No se detectó GPU compatible (CUDA/MPS). Usando CPU para el entrenamiento (será MUCHO más lento).")

    # --- 3. Cargar el Modelo Base ---
    logger.info(f"Cargando modelo base YOLOv8: '{MODEL_NAME}'...")
    try:
        model = YOLO(MODEL_NAME)
        logger.info("Modelo base cargado correctamente.")
    except Exception as e:
        logger.error(f"¡ERROR FATAL! No se pudo cargar el modelo base '{MODEL_NAME}': {e}")
        return

    # --- 4. Iniciar el Entrenamiento ---
    logger.info("\n--- Iniciando Proceso de Entrenamiento ---")
    logger.info(f"   Proyecto: {PROJECT_NAME}")
    logger.info(f"   Experimento: {EXPERIMENT_NAME}")
    logger.info(f"   Dispositivo: {device}")
    logger.info(f"   Épocas: {EPOCHS}")
    logger.info(f"   Tamaño Imagen: {IMAGE_SIZE}x{IMAGE_SIZE}")
    logger.info(f"   Batch Size: {BATCH_SIZE}")
    logger.info(f"   Workers: {NUM_WORKERS}")
    logger.info(f"   Paciencia (Early Stopping): {PATIENCE}")
    logger.info("----------------------------------------")

    # Determinar si se continúa desde un checkpoint específico o se usa 'resume'
    resume_config = False
    if RESUME_TRAINING:
        if RESUME_PATH:
            if os.path.exists(RESUME_PATH):
                logger.info(f"Reanudando entrenamiento desde: {RESUME_PATH}")
                model = YOLO(RESUME_PATH)
                resume_config = False  # Ya cargamos el modelo específico, no necesitamos resume=True
            else:
                logger.error(f"No se encontró el archivo de checkpoint: {RESUME_PATH}")
                return
        else:
            logger.info("Reanudando desde el último checkpoint disponible")
            resume_config = True  # Usar resume=True para que YOLO busque el último checkpoint

    try:
        results = model.train(
            # --- Argumentos Principales ---
            data=DATA_CONFIG_PATH,
            epochs=EPOCHS,
            imgsz=IMAGE_SIZE,
            batch=BATCH_SIZE,
            workers=NUM_WORKERS,
            device=device,
            project=PROJECT_NAME,
            name=EXPERIMENT_NAME,

            # --- Control del Entrenamiento ---
            patience=PATIENCE,
            resume=resume_config,

            # --- Aumento de Datos ---
            degrees=AUGMENT_PARAMS['degrees'],
            translate=AUGMENT_PARAMS['translate'],
            scale=AUGMENT_PARAMS['scale'],
            shear=AUGMENT_PARAMS['shear'],
            perspective=AUGMENT_PARAMS['perspective'],
            flipud=AUGMENT_PARAMS['flipud'],
            fliplr=AUGMENT_PARAMS['fliplr'],
            mosaic=AUGMENT_PARAMS['mosaic'],
            mixup=AUGMENT_PARAMS['mixup'],
            copy_paste=AUGMENT_PARAMS['copy_paste'],

            # --- Opciones Adicionales ---
            save_period=SAVE_PERIOD,
            plots=PLOTS, # Generar gráficos al final
            val=True     # Realizar validación después de cada época (¡Importante!)
        )

        logger.info("\n--- Entrenamiento Completado Exitosamente ---")
        # La ruta exacta se guarda en results.save_dir
        save_directory = os.path.join('runs', 'detect', PROJECT_NAME, EXPERIMENT_NAME)
        logger.info(f"Resultados y modelo 'best.pt' guardados en: {os.path.abspath(save_directory)}")
        logger.info("El archivo 'best.pt' es el que debes copiar a la carpeta 'models/' de tu Raspberry Pi.")
        logger.info("\nPara visualizar los resultados detallados (gráficos, métricas):")
        logger.info(f"1. Abre una terminal.")
        logger.info(f"2. Navega a la carpeta '{PROJECT_NAME}' (donde está '{EXPERIMENT_NAME}').")
        logger.info(f"3. Ejecuta: tensorboard --logdir ./{EXPERIMENT_NAME}")
        logger.info("4. Abre tu navegador web en la dirección que te indique TensorBoard (usualmente http://localhost:6006/).")

    except Exception as e:
        logger.error(f"\n¡ERROR FATAL durante el entrenamiento!: {e}")
        import traceback
        traceback.print_exc() # Imprimir el traceback completo para más detalles
        logger.error("Verifica la configuración, las rutas del dataset, la instalación de librerías y la memoria disponible.")

# --- Punto de Entrada del Script ---
if __name__ == "__main__":
    args = parse_arguments()
    # Llamar a la función principal de entrenamiento
    train_waste_detector(args)
    logger.info("\n--- Script de Entrenamiento Finalizado ---")