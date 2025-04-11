#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
app.py - Servidor backend para el Cesto Inteligente
Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
Fecha: Abril de 2024
"""

import os
import socket
import json
import threading
import time
import logging
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import requests

# Importar módulos del proyecto
import config
import database
from api import api_bp

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('app')

# Crear la aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['DEBUG'] = config.DEBUG

# Inicializar SocketIO para comunicaciones en tiempo real
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Registrar blueprint de la API
app.register_blueprint(api_bp)

# Variable global para el estado de la conexión
connection_state = {
    'main_py_connected': False,
    'last_update': None,
    'error_message': None
}

# Rutas básicas
@app.route('/')
def index():
    return render_template('index.html')

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Ruta no encontrada", "status": 404}), 404

# Función para obtener datos del script main.py
def get_data_from_main():
    """
    Intenta obtener datos del script main.py
    El script main.py debería exponer un servidor de sockets simple que devuelva
    JSON con los datos actuales del sistema.
    """
    try:
        # Crear un socket cliente
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(5)  # Timeout de 5 segundos
        
        # Conectar al servidor en main.py
        client_socket.connect((config.MAIN_PY_HOST, config.MAIN_PY_PORT))
        
        # Enviar comando para solicitar datos
        client_socket.send(b'GET_DATA')
        
        # Recibir respuesta
        response = b''
        chunk = client_socket.recv(4096)
        while chunk:
            response += chunk
            try:
                # Intentar recibir más datos con un timeout corto
                client_socket.settimeout(0.5)
                chunk = client_socket.recv(4096)
            except socket.timeout:
                # No hay más datos para recibir
                break
        
        # Cerrar conexión
        client_socket.close()
        
        # Decodificar respuesta JSON
        if response:
            data = json.loads(response.decode('utf-8'))
            return data, None
        else:
            return None, "Respuesta vacía de main.py"
            
    except socket.timeout:
        return None, "Timeout al conectar con main.py"
    except socket.error as e:
        return None, f"Error de conexión: {e}"
    except json.JSONDecodeError as e:
        return None, f"Error al decodificar JSON: {e}"
    except Exception as e:
        return None, f"Error inesperado: {e}"

# Función para el hilo de actualización de datos
def update_data_thread():
    """
    Hilo que periódicamente obtiene datos de main.py y actualiza la base de datos
    """
    global connection_state
    
    db = database.get_db()
    
    while True:
        try:
            # Obtener datos de main.py
            data, error = get_data_from_main()
            
            if data is not None:
                # Actualizar estado de conexión
                connection_state['main_py_connected'] = True
                connection_state['last_update'] = time.time()
                connection_state['error_message'] = None
                
                # Actualizar estado del sistema en la base de datos
                db.update_system_status("active", "Sistema funcionando correctamente")
                
                # Procesar datos de niveles de llenado
                if 'fill_levels' in data:
                    for compartment, level in data['fill_levels'].items():
                        db.insert_fill_level(compartment, level)
                
                # Procesar datos de la última detección
                if 'detection' in data and data['detection']:
                    waste_type = data['detection'].get('class_name')
                    confidence = data['detection'].get('confidence')
                    if waste_type and confidence:
                        db.insert_detection(waste_type, confidence)
                
                # Emitir evento de actualización a clientes conectados
                socketio.emit('data_update', {
                    'success': True,
                    'timestamp': time.time()
                })
                
                logger.info("Datos actualizados desde main.py")
            else:
                # Actualizar estado de conexión
                connection_state['main_py_connected'] = False
                connection_state['error_message'] = error
                
                # Actualizar estado del sistema en la base de datos
                db.update_system_status("error", f"Error de conexión con main.py: {error}")
                
                # Emitir evento de error a clientes conectados
                socketio.emit('connection_error', {
                    'error': error,
                    'timestamp': time.time()
                })
                
                logger.warning(f"Error obteniendo datos: {error}")
        
        except Exception as e:
            logger.error(f"Error en el hilo de actualización: {e}")
            
        # Esperar hasta la próxima actualización
        time.sleep(config.UPDATE_INTERVAL)

# Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    """Manejar conexión de cliente WebSocket"""
    logger.info(f"Cliente WebSocket conectado: {request.sid}")
    # Enviar estado actual al cliente recién conectado
    emit('connection_status', connection_state)

@socketio.on('request_update')
def handle_update_request():
    """Forzar una actualización inmediata de datos cuando el cliente lo solicita"""
    try:
        # Obtener datos actualizados de la base de datos
        db = database.get_db()
        
        # Construir respuesta con datos actuales
        fill_levels = db.get_latest_fill_levels()
        statistics = db.get_statistics()
        system_status = db.get_system_status()
        
        # Emitir datos actualizados solo al cliente que lo solicitó
        emit('data_update', {
            'success': True,
            'data': {
                'fill_levels': fill_levels,
                'statistics': statistics,
                'system_status': system_status
            },
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"Error al procesar solicitud de actualización: {e}")
        emit('error', {'message': str(e)})

# Iniciar la aplicación
if __name__ == '__main__':
    try:
        # Verificar acceso a la base de datos
        db = database.get_db()
        if db:
            logger.info("Conexión a la base de datos establecida")
            
            # Configurar estado inicial del sistema
            db.update_system_status("starting", "Iniciando servidor backend")
        
        # Iniciar hilo de actualización
        update_thread = threading.Thread(target=update_data_thread, daemon=True)
        update_thread.start()
        logger.info(f"Hilo de actualización iniciado con intervalo de {config.UPDATE_INTERVAL} segundos")
        
        # Iniciar servidor web
        logger.info(f"Iniciando servidor Flask en el puerto {config.PORT}")
        socketio.run(app, host='0.0.0.0', port=config.PORT)
        
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {e}")
    finally:
        # Cerrar conexión a la base de datos
        if 'db' in locals() and db:
            db.close() 