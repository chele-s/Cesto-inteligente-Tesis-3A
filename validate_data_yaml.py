#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# validate_data_yaml.py - Herramienta para validar la configuración del dataset
# Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
# Fecha: Abril de 2024
# Descripción: Verifica la validez del archivo data.yaml, incluyendo rutas,
#              estructura de clases y consistencia con el proyecto.
# -----------------------------------------------------------------------------

import os
import sys
import yaml
import argparse
import logging
import glob

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('validate_data_yaml')

def parse_arguments():
    """Procesa los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description='Validador de estructura y consistencia de data.yaml')
    
    parser.add_argument(
        '--yaml', type=str, default='./dataset_basura/data.yaml',
        help='Ruta al archivo data.yaml (default: ./dataset_basura/data.yaml)')
    
    parser.add_argument(
        '--check-paths', action='store_true',
        help='Verificar existencia de rutas de imágenes y etiquetas')
    
    parser.add_argument(
        '--check-labels', action='store_true',
        help='Verificar contenido de archivos de etiquetas')
    
    return parser.parse_args()

def load_yaml(yaml_path):
    """Carga un archivo YAML y valida su estructura básica."""
    try:
        if not os.path.exists(yaml_path):
            logger.error(f"El archivo {yaml_path} no existe")
            return None
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        return data
    
    except Exception as e:
        logger.error(f"Error al cargar {yaml_path}: {e}")
        return None

def validate_basic_structure(data):
    """Verifica que el YAML contenga los campos requeridos y tengan formato correcto."""
    # Campos requeridos para YOLOv8
    required_fields = ['train', 'val', 'nc', 'names']
    
    # Verificar presencia de campos requeridos
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        logger.error(f"Campos requeridos faltantes: {', '.join(missing_fields)}")
        return False
    
    # Verificar número de clases
    if not isinstance(data['nc'], int) or data['nc'] < 1:
        logger.error(f"El campo 'nc' debe ser un número entero positivo (actual: {data['nc']})")
        return False
    
    # Verificar lista de nombres
    if not isinstance(data['names'], list):
        logger.error("El campo 'names' debe ser una lista")
        return False
    
    # Verificar coherencia entre nc y names
    if len(data['names']) != data['nc']:
        logger.error(f"La cantidad de nombres de clases ({len(data['names'])}) no coincide con 'nc' ({data['nc']})")
        return False
    
    # Verificar que no haya nombres duplicados
    if len(set(data['names'])) != len(data['names']):
        logger.error("Hay nombres de clases duplicados en 'names'")
        return False
    
    # Verificar que los campos de rutas sean strings
    for path_field in ['train', 'val', 'test']:
        if path_field in data and not isinstance(data[path_field], str):
            logger.error(f"El campo '{path_field}' debe ser una cadena de texto")
            return False
    
    logger.info("✅ La estructura básica del archivo YAML es correcta")
    return True

def validate_dataset_paths(data, base_dir='.'):
    """Verifica que las rutas a imágenes y etiquetas existan."""
    result = True
    
    # Construir rutas absolutas desde la ubicación del archivo YAML
    paths_to_check = {
        'Entrenamiento (imágenes)': os.path.join(base_dir, data['train']),
        'Validación (imágenes)': os.path.join(base_dir, data['val'])
    }
    
    # Añadir ruta de test si existe
    if 'test' in data and data['test']:
        paths_to_check['Test (imágenes)'] = os.path.join(base_dir, data['test'])
    
    # Verificar las rutas de imágenes
    for desc, path in paths_to_check.items():
        if not os.path.exists(path):
            logger.error(f"❌ La ruta para {desc} no existe: {path}")
            result = False
        else:
            # Contar imágenes
            img_extensions = ('*.jpg', '*.jpeg', '*.png', '*.bmp')
            image_files = []
            for ext in img_extensions:
                image_files.extend(glob.glob(os.path.join(path, ext)))
            
            if not image_files:
                logger.warning(f"⚠️ No se encontraron imágenes en la ruta para {desc}: {path}")
                result = False
            else:
                logger.info(f"✅ {desc}: {len(image_files)} imágenes encontradas en {path}")
    
    # Verificar rutas de etiquetas (deben seguir la estructura estándar de YOLO)
    for dataset_type in ['train', 'val']:
        img_path = os.path.join(base_dir, data[dataset_type])
        
        # La ruta de etiquetas debe estar al mismo nivel que la de imágenes
        # reemplazando 'images' por 'labels'
        label_path = img_path.replace('/images/', '/labels/')
        if label_path == img_path:  # Si no se pudo reemplazar
            label_path = os.path.join(os.path.dirname(os.path.dirname(img_path)), 'labels', os.path.basename(img_path))
        
        if not os.path.exists(label_path):
            logger.error(f"❌ La ruta para etiquetas de {dataset_type} no existe: {label_path}")
            result = False
        else:
            # Contar archivos de etiquetas
            label_files = glob.glob(os.path.join(label_path, '*.txt'))
            if not label_files:
                logger.warning(f"⚠️ No se encontraron archivos de etiquetas en {label_path}")
                result = False
            else:
                logger.info(f"✅ Etiquetas de {dataset_type}: {len(label_files)} archivos encontrados en {label_path}")
    
    return result

def validate_label_files(data, base_dir='.', max_samples=10):
    """Verifica una muestra de archivos de etiquetas para confirmar su formato y clases."""
    result = True
    
    # Construir ruta a etiquetas de entrenamiento
    train_img_path = os.path.join(base_dir, data['train'])
    train_label_path = train_img_path.replace('/images/', '/labels/')
    if train_label_path == train_img_path:
        train_label_path = os.path.join(os.path.dirname(os.path.dirname(train_img_path)), 'labels', os.path.basename(train_img_path))
    
    # Verificar si la ruta existe
    if not os.path.exists(train_label_path):
        logger.error(f"No se puede validar etiquetas: ruta {train_label_path} no existe")
        return False
    
    # Obtener lista de archivos de etiquetas
    label_files = glob.glob(os.path.join(train_label_path, '*.txt'))
    if not label_files:
        logger.error(f"No se encontraron archivos de etiquetas en {train_label_path}")
        return False
    
    # Limitar a un máximo de muestras
    samples = label_files[:min(max_samples, len(label_files))]
    logger.info(f"Validando {len(samples)} archivos de etiquetas...")
    
    # Conjunto para almacenar clases encontradas
    classes_found = set()
    
    # Revisar cada archivo de muestra
    for label_file in samples:
        try:
            with open(label_file, 'r') as f:
                lines = f.readlines()
            
            if not lines:
                logger.warning(f"⚠️ Archivo de etiquetas vacío: {os.path.basename(label_file)}")
                continue
            
            for i, line in enumerate(lines):
                parts = line.strip().split()
                
                # Verificar formato: debe tener 5 valores (clase, x, y, w, h)
                if len(parts) != 5:
                    logger.error(f"❌ Formato inválido en {os.path.basename(label_file)}, línea {i+1}: {line.strip()}")
                    result = False
                    continue
                
                # Verificar que la clase sea un entero no negativo
                try:
                    class_idx = int(parts[0])
                    classes_found.add(class_idx)
                    
                    if class_idx < 0 or class_idx >= data['nc']:
                        logger.error(f"❌ Índice de clase inválido en {os.path.basename(label_file)}, línea {i+1}: {class_idx}")
                        result = False
                    
                    # Verificar que las coordenadas sean números entre 0 y 1
                    for j in range(1, 5):
                        val = float(parts[j])
                        if val < 0 or val > 1:
                            logger.warning(f"⚠️ Valor fuera de rango [0,1] en {os.path.basename(label_file)}, línea {i+1}, valor {j}: {val}")
                
                except ValueError:
                    logger.error(f"❌ Error de formato en {os.path.basename(label_file)}, línea {i+1}: {line.strip()}")
                    result = False
        
        except Exception as e:
            logger.error(f"Error al procesar {label_file}: {e}")
            result = False
    
    # Verificar que se hayan encontrado todas las clases
    if classes_found:
        logger.info(f"Clases encontradas en las etiquetas: {sorted(classes_found)}")
        
        missing_classes = [i for i in range(data['nc']) if i not in classes_found]
        if missing_classes:
            logger.warning(f"⚠️ Algunas clases no aparecen en la muestra de etiquetas: {missing_classes}")
            # No fallamos aquí porque puede ser que solo no aparezcan en la muestra
    else:
        logger.error("❌ No se encontraron clases válidas en los archivos de etiquetas")
        result = False
    
    return result

def main():
    """Función principal."""
    args = parse_arguments()
    
    # Cargar y validar el archivo YAML
    logger.info(f"Validando archivo: {args.yaml}")
    data = load_yaml(args.yaml)
    if data is None:
        return 1
    
    # Validar estructura básica
    if not validate_basic_structure(data):
        logger.error("Validación básica fallida. Corrige los errores antes de continuar.")
        return 1
    
    # Obtener directorio base (donde está el archivo YAML)
    base_dir = os.path.dirname(os.path.abspath(args.yaml))
    
    # Validar rutas de dataset si se solicitó
    if args.check_paths:
        logger.info("Validando rutas del dataset...")
        if not validate_dataset_paths(data, base_dir):
            logger.warning("Algunas rutas del dataset no son válidas.")
        else:
            logger.info("✅ Todas las rutas del dataset son válidas.")
    
    # Validar archivos de etiquetas si se solicitó
    if args.check_labels:
        logger.info("Validando archivos de etiquetas...")
        if not validate_label_files(data, base_dir):
            logger.warning("Se encontraron problemas en los archivos de etiquetas.")
        else:
            logger.info("✅ Muestra de archivos de etiquetas válida.")
    
    # Imprimir resumen
    logger.info("\n---- RESUMEN DE VALIDACIÓN ----")
    logger.info(f"Archivo: {args.yaml}")
    logger.info(f"Número de clases: {data['nc']}")
    logger.info(f"Clases: {', '.join(data['names'])}")
    logger.info(f"Dataset de entrenamiento: {data['train']}")
    logger.info(f"Dataset de validación: {data['val']}")
    if 'test' in data and data['test']:
        logger.info(f"Dataset de test: {data['test']}")
    
    logger.info("Validación completada.")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 