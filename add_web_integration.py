#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para integrar el adaptador web con main.py

Este archivo muestra un ejemplo de cómo modificar main.py para
comunicarse con el backend web. Debes agregar este código en main.py
en las ubicaciones apropiadas.
"""

# --- INSTRUCCIONES DE INTEGRACIÓN ---
# 
# 1. Importar el adaptador web al principio de main.py
# Agrega estas líneas después de importar otros módulos:

# Importar el adaptador web para comunicación con el backend
import main_web_adapter

# 2. Iniciar el servidor web adapter en main_app() antes del bucle principal
# Agrega estas líneas en la función main_app() antes del bucle principal:

# Iniciar el servidor web adapter
logger.info("Iniciando servidor web adapter para comunicación con el backend...")
main_web_adapter.start_server()
logger.info(f"Servidor web adapter iniciado en {main_web_adapter.HOST}:{main_web_adapter.PORT}")

# 3. Actualizar los datos del adaptador web cuando haya cambios
# Agrega estas líneas en lugares donde haya cambios de estado importantes:

# 3.1 En la función where detection_callback actualiza la información de detección:
if detection_result and 'class_name' in detection_result:
    # Preparar datos para el adaptador web
    detection_data = {
        'class_name': detection_result['class_name'],
        'confidence': detection_result['confidence']
    }
    # Actualizar adaptador web
    main_web_adapter.update_data(detection=detection_data)

# 3.2 En la función update_fill_indicators para actualizar niveles de llenado:
def update_fill_indicators(levels):
    # Código existente...
    
    # Actualizar adaptador web
    main_web_adapter.update_data(fill_levels=levels)
    
# 3.3 Al iniciar o detener el sistema, actualizar el estado:
# Al iniciar:
main_web_adapter.update_data(system_status="active")

# Al detectar errores:
main_web_adapter.update_data(system_status="error")

# Al finalizar:
main_web_adapter.update_data(system_status="inactive")

# 4. Detener el servidor web adapter al finalizar en main_app
# Agrega estas líneas al final de main_app() o en un bloque finally:

# Detener el servidor web adapter
logger.info("Deteniendo servidor web adapter...")
main_web_adapter.stop_server()
logger.info("Servidor web adapter detenido")

# --- FIN DE LAS INSTRUCCIONES DE INTEGRACIÓN ---

# --- EJEMPLO DE INTEGRACIÓN COMPLETA EN MAIN.PY ---
"""
Ejemplo de cómo podría verse la integración en main.py:

def main_app():
    try:
        # Inicialización existente...
        
        # Iniciar servidor web adapter
        logger.info("Iniciando servidor web adapter para comunicación con el backend...")
        main_web_adapter.start_server()
        logger.info(f"Servidor web adapter iniciado en {main_web_adapter.HOST}:{main_web_adapter.PORT}")
        
        # Actualizar estado inicial
        main_web_adapter.update_data(system_status="active")
        
        # Bucle principal existente...
        
    except Exception as e:
        logger.error(f"Error en aplicación principal: {e}")
        main_web_adapter.update_data(system_status="error")
        
    finally:
        # Limpieza existente...
        
        # Detener servidor web adapter
        logger.info("Deteniendo servidor web adapter...")
        main_web_adapter.stop_server()
        logger.info("Servidor web adapter detenido")
"""

# NOTA: Este archivo es solo un ejemplo de integración.
# No ejecutes este archivo directamente, sino integra su contenido
# en las ubicaciones apropiadas dentro de main.py 