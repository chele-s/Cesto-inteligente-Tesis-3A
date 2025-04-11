from flask import Blueprint, jsonify
from datetime import datetime
import database

# Crear un Blueprint para las rutas de la API
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Formatear timestamp para JSON
def format_timestamp(timestamp):
    if timestamp is None:
        return None
    if isinstance(timestamp, datetime):
        return timestamp.isoformat()
    return timestamp

# Ruta para obtener los niveles de llenado de todos los compartimentos
@api_bp.route('/fill-levels', methods=['GET'])
def get_fill_levels():
    db = database.get_db()
    levels = db.get_latest_fill_levels()
    
    # Si no hay datos, devolver valores por defecto
    if not levels:
        levels = {
            'Metal': 0.0,
            'Glass': 0.0,
            'Plastic': 0.0,
            'Carton': 0.0
        }
    
    return jsonify({
        'success': True,
        'data': levels,
        'timestamp': format_timestamp(datetime.now())
    })

# Ruta para obtener las estadísticas de clasificación
@api_bp.route('/statistics', methods=['GET'])
def get_statistics():
    db = database.get_db()
    stats = db.get_statistics()
    
    # Si no hay datos, devolver valores por defecto
    if not stats:
        stats = {
            'Metal': 0,
            'Glass': 0,
            'Plastic': 0,
            'Carton': 0
        }
    
    return jsonify({
        'success': True,
        'data': stats,
        'timestamp': format_timestamp(datetime.now())
    })

# Ruta para obtener el estado del sistema
@api_bp.route('/system-status', methods=['GET'])
def get_system_status():
    db = database.get_db()
    status = db.get_system_status()
    
    # Formatear timestamp
    if 'timestamp' in status:
        status['timestamp'] = format_timestamp(status['timestamp'])
    
    return jsonify({
        'success': True,
        'data': status
    })

# Ruta para obtener todos los datos del sistema (dashboard)
@api_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    db = database.get_db()
    
    # Obtener todos los datos relevantes
    fill_levels = db.get_latest_fill_levels()
    statistics = db.get_statistics()
    system_status = db.get_system_status()
    
    # Formatear timestamp del estado del sistema
    if 'timestamp' in system_status:
        system_status['timestamp'] = format_timestamp(system_status['timestamp'])
    
    # Si no hay datos, proporcionar valores por defecto
    if not fill_levels:
        fill_levels = {
            'Metal': 0.0,
            'Glass': 0.0,
            'Plastic': 0.0,
            'Carton': 0.0
        }
    
    if not statistics:
        statistics = {
            'Metal': 0,
            'Glass': 0,
            'Plastic': 0,
            'Carton': 0
        }
    
    # Calcular totales
    total_items = sum(statistics.values())
    
    # Crear respuesta
    response = {
        'success': True,
        'data': {
            'fill_levels': fill_levels,
            'statistics': statistics,
            'system_status': system_status,
            'totals': {
                'items_classified': total_items
            }
        },
        'timestamp': format_timestamp(datetime.now())
    }
    
    return jsonify(response) 