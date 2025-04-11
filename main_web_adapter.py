#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
main_web_adapter.py - Adaptador para exponer datos del Cesto Inteligente al backend web
Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
Fecha: Abril de 2024

Este módulo crea un servidor de socket simple que se ejecuta junto con main.py
para proporcionar datos al backend web. Debe importarse desde main.py.

Uso:
1. Importar este módulo desde main.py
2. Iniciar el servidor con start_server()
3. Actualizar los datos con update_data() cada vez que haya cambios
"""

import socket
import threading
import json
import logging
import time

# Obtener logger configurado en main.py (o crear uno nuevo si se ejecuta independientemente)
try:
    from __main__ import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger('main_web_adapter')

# Configuración del servidor
HOST = '127.0.0.1'
PORT = 5001
MAX_CONNECTIONS = 5
SOCKET_TIMEOUT = 5.0  # segundos

# Datos del sistema (serán actualizados por main.py)
system_data = {
    'fill_levels': {
        'Metal': 0.0,
        'Glass': 0.0,
        'Plastic': 0.0,
        'Carton': 0.0
    },
    'detection': None,
    'system_status': 'inactive',
    'timestamp': time.time()
}

# Flag para controlar el hilo del servidor
server_running = False
server_thread = None
server_socket = None

def update_data(fill_levels=None, detection=None, system_status=None):
    """
    Actualiza los datos del sistema que serán enviados al backend.
    
    Args:
        fill_levels (dict): Diccionario con niveles de llenado por compartimento
        detection (dict): Información sobre la última detección
        system_status (str): Estado actual del sistema
    """
    global system_data
    
    # Actualizar solo los datos proporcionados
    if fill_levels is not None:
        system_data['fill_levels'] = fill_levels
    
    if detection is not None:
        system_data['detection'] = detection
    
    if system_status is not None:
        system_data['system_status'] = system_status
    
    # Actualizar timestamp
    system_data['timestamp'] = time.time()
    
    logger.debug("Datos actualizados para el backend")

def handle_client(client_socket):
    """
    Maneja una conexión cliente.
    
    Args:
        client_socket: Socket de conexión con el cliente
    """
    try:
        # Recibir comando del cliente
        data = client_socket.recv(1024)
        if not data:
            return
            
        command = data.decode('utf-8')
        
        # Procesar comando
        if command == 'GET_DATA':
            # Enviar datos actuales
            response = json.dumps(system_data)
            client_socket.sendall(response.encode('utf-8'))
            logger.debug("Datos enviados al cliente")
        else:
            # Comando desconocido
            response = json.dumps({'error': 'Comando desconocido'})
            client_socket.sendall(response.encode('utf-8'))
            logger.warning(f"Comando desconocido recibido: {command}")
    
    except Exception as e:
        logger.error(f"Error en manejo de cliente: {e}")
    
    finally:
        # Cerrar conexión
        client_socket.close()

def server_loop():
    """
    Bucle principal del servidor.
    """
    global server_running, server_socket
    
    try:
        # Crear socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(MAX_CONNECTIONS)
        server_socket.settimeout(SOCKET_TIMEOUT)
        
        logger.info(f"Servidor web adapter iniciado en {HOST}:{PORT}")
        
        while server_running:
            try:
                # Esperar conexión
                client_socket, addr = server_socket.accept()
                logger.debug(f"Conexión aceptada desde {addr}")
                
                # Manejar cliente en un hilo separado
                client_thread = threading.Thread(target=handle_client, args=(client_socket,), daemon=True)
                client_thread.start()
                
            except socket.timeout:
                # Timeout de accept(), continuar bucle
                continue
            except Exception as e:
                if server_running:
                    logger.error(f"Error en bucle del servidor: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error al iniciar servidor web adapter: {e}")
    
    finally:
        if server_socket:
            server_socket.close()
            logger.info("Servidor web adapter detenido")

def start_server():
    """
    Inicia el servidor web adapter en un hilo separado.
    """
    global server_running, server_thread
    
    if server_running:
        logger.warning("El servidor web adapter ya está en ejecución")
        return False
    
    server_running = True
    server_thread = threading.Thread(target=server_loop, daemon=True)
    server_thread.start()
    
    logger.info("Hilo del servidor web adapter iniciado")
    return True

def stop_server():
    """
    Detiene el servidor web adapter.
    """
    global server_running, server_thread, server_socket
    
    if not server_running:
        logger.warning("El servidor web adapter no está en ejecución")
        return False
    
    server_running = False
    
    # Si hay un socket activo, cerrar para desbloquear accept()
    if server_socket:
        try:
            server_socket.close()
        except Exception as e:
            logger.error(f"Error al cerrar socket del servidor: {e}")
    
    # Esperar a que el hilo termine
    if server_thread:
        server_thread.join(timeout=5.0)
        if server_thread.is_alive():
            logger.warning("El hilo del servidor no terminó correctamente")
    
    logger.info("Servidor web adapter detenido")
    return True

# Si se ejecuta como script independiente, iniciar servidor de prueba
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger('main_web_adapter')
    
    print("=== Inicio de prueba del adaptador web ===")
    print("Este módulo debe importarse desde main.py")
    print("Ejecutando servidor de prueba...")
    
    try:
        # Crear datos de prueba
        test_data = {
            'fill_levels': {
                'Metal': 25.5,
                'Glass': 10.0,
                'Plastic': 75.2,
                'Carton': 45.8
            },
            'detection': {
                'class_name': 'Plastic',
                'confidence': 0.85
            },
            'system_status': 'active'
        }
        
        # Actualizar datos con valores de prueba
        update_data(**test_data)
        
        # Iniciar servidor
        start_server()
        
        print(f"Servidor de prueba iniciado en {HOST}:{PORT}")
        print("Presione Ctrl+C para detener...")
        
        # Mantener el servidor en ejecución
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDeteniendo servidor...")
        
    except Exception as e:
        print(f"Error en prueba: {e}")
    
    finally:
        # Detener servidor
        stop_server()
        print("=== Fin de prueba ===") 