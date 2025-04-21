#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# sensor_controller.py - Módulo para control de sensores ultrasónicos HC-SR04
# Autor(es): Gabriel Calderón, Elias Bautista, Cristian Hernandez
# Fecha: Abril de 2024
# Descripción: Control de los sensores ultrasónicos (HC-SR04) para medir el 
#              nivel de llenado de cada compartimento del Cesto Inteligente.
# -----------------------------------------------------------------------------

import RPi.GPIO as GPIO
import time
import logging
import threading
import statistics
import json
import os

# Obtener logger configurado en main.py
logger = logging.getLogger(__name__)

# --- Configuración por defecto ---
# Mapeo: Nombre_Compartimento -> (TRIG_PIN, ECHO_PIN)
DEFAULT_SENSOR_PINS = {
    'Metal':   (23, 24),  # Ejemplo: GPIO 23 para TRIG, GPIO 24 para ECHO
    'Glass':   (25, 8),
    'Plastic': (7, 12),
    'Carton':  (1, 18)
}

# --- Parámetros Físicos y Constantes ---
DEFAULT_BIN_DEPTH_CM = 50.0  # Profundidad total del compartimento en cm
DEFAULT_SOUND_SPEED = 34300  # Velocidad del sonido en cm/s a 20°C
DEFAULT_READINGS_PER_MEASUREMENT = 3  # Número de lecturas a promediar
DEFAULT_STABILIZATION_TIME = 0.5  # Tiempo de estabilización en segundos
DEFAULT_MEASUREMENT_TIMEOUT = 0.5  # Tiempo máximo para una medición en segundos
DEFAULT_READING_INTERVAL = 0.1  # Tiempo entre lecturas consecutivas

# --- Variables Globales ---
sensor_pins = DEFAULT_SENSOR_PINS.copy()
bin_depth_cm = DEFAULT_BIN_DEPTH_CM
sound_speed = DEFAULT_SOUND_SPEED
readings_per_measurement = DEFAULT_READINGS_PER_MEASUREMENT
is_monitoring = False
monitoring_thread = None
fill_level_cache = {}  # Caché de las últimas mediciones
use_temperature_compensation = False
current_temperature = 20.0  # Temperatura por defecto en grados Celsius

# --- Funciones de Configuración ---

def load_config(config_file='config.json'):
    """
    Carga la configuración desde un archivo JSON.
    
    Args:
        config_file (str): Ruta al archivo de configuración.
        
    Returns:
        bool: True si la configuración se cargó correctamente, False en caso contrario.
    """
    global sensor_pins, bin_depth_cm, sound_speed, readings_per_measurement, use_temperature_compensation, current_temperature
    
    try:
        if not os.path.exists(config_file):
            logger.warning(f"Archivo de configuración {config_file} no encontrado. Usando valores por defecto.")
            return False
            
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        if 'sensors' in config:
            sensor_config = config['sensors']
            
            if 'pins' in sensor_config:
                sensor_pins = sensor_config['pins']
                
            if 'bin_depth_cm' in sensor_config:
                bin_depth_cm = float(sensor_config['bin_depth_cm'])
                
            if 'sound_speed' in sensor_config:
                sound_speed = float(sensor_config['sound_speed'])
                
            if 'readings_per_measurement' in sensor_config:
                readings_per_measurement = int(sensor_config['readings_per_measurement'])
            
            if 'use_temperature_compensation' in sensor_config:
                use_temperature_compensation = bool(sensor_config['use_temperature_compensation'])
                
            if 'default_temperature_c' in sensor_config:
                current_temperature = float(sensor_config['default_temperature_c'])
                if use_temperature_compensation:
                    # Actualizar velocidad del sonido basado en la temperatura
                    sound_speed = calculate_sound_speed(current_temperature)
                
        logger.info(f"Configuración cargada desde {config_file}")
        logger.info(f"Usando compensación de temperatura: {use_temperature_compensation}")
        if use_temperature_compensation:
            logger.info(f"Temperatura: {current_temperature}°C, Velocidad del sonido: {sound_speed} cm/s")
        return True
        
    except Exception as e:
        logger.error(f"Error al cargar configuración: {e}")
        return False

def calculate_sound_speed(temperature_c=20):
    """
    Calcula la velocidad del sonido ajustada por temperatura.
    
    Args:
        temperature_c (float): Temperatura en grados Celsius.
        
    Returns:
        float: Velocidad del sonido en cm/s.
    """
    # Fórmula para velocidad del sonido en función de la temperatura (aproximación)
    # v = 331.3 + 0.606 * T (m/s) -> convertida a cm/s
    return (331.3 + 0.606 * temperature_c) * 100

def set_temperature(temperature_c):
    """
    Actualiza la temperatura ambiente y recalcula la velocidad del sonido.
    
    Args:
        temperature_c (float): Temperatura en grados Celsius.
    
    Returns:
        float: Nueva velocidad del sonido calculada.
    """
    global current_temperature, sound_speed, use_temperature_compensation
    
    if not use_temperature_compensation:
        logger.debug("Compensación de temperatura desactivada, ignorando cambio de temperatura.")
        return sound_speed
        
    current_temperature = temperature_c
    sound_speed = calculate_sound_speed(temperature_c)
    logger.info(f"Temperatura actualizada a {temperature_c}°C, nueva velocidad del sonido: {sound_speed} cm/s")
    return sound_speed

def setup_sensors(force_mode=False):
    """
    Configura los pines GPIO para todos los sensores.
    
    Args:
        force_mode (bool): Si es True, fuerza el modo BCM incluso si ya está configurado.
        
    Returns:
        bool: True si la configuración fue exitosa, False en caso contrario.
    """
    try:
        # Intentar establecer el modo BCM si es necesario
        if force_mode or GPIO.getmode() is None:
            GPIO.setmode(GPIO.BCM)
        elif GPIO.getmode() != GPIO.BCM:
            logger.warning("GPIO ya inicializado en un modo distinto a BCM. Puede causar conflictos.")
            return False
            
        # Configurar cada sensor
        for name, (trig_pin, echo_pin) in sensor_pins.items():
            # Limpiar configuración previa si existe
            GPIO.setup(trig_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(echo_pin, GPIO.IN)
            logger.info(f"Sensor '{name}' configurado: TRIG={trig_pin}, ECHO={echo_pin}")
            
        # Breve pausa para estabilización
        logger.info(f"Esperando {DEFAULT_STABILIZATION_TIME}s para estabilización de sensores...")
        time.sleep(DEFAULT_STABILIZATION_TIME)
        
        # Verificar sensores haciendo una lectura inicial
        for name, (trig_pin, echo_pin) in sensor_pins.items():
            distance = get_distance_cm(trig_pin, echo_pin)
            if distance is None:
                logger.warning(f"Sensor '{name}' no responde en la prueba inicial")
            else:
                logger.debug(f"Sensor '{name}' responde correctamente: {distance:.1f}cm")
                
        return True
        
    except Exception as e:
        logger.error(f"Error configurando sensores GPIO: {e}")
        return False

# --- Funciones de Medición ---

def get_distance_cm(trig_pin, echo_pin, timeout=DEFAULT_MEASUREMENT_TIMEOUT, retries=1):
    """
    Mide la distancia para un sensor específico.
    
    Args:
        trig_pin (int): Pin GPIO conectado al TRIG del sensor.
        echo_pin (int): Pin GPIO conectado al ECHO del sensor.
        timeout (float): Tiempo máximo de espera para la medición en segundos.
        retries (int): Número de intentos si falla la medición.
        
    Returns:
        float or None: Distancia en cm o None si error.
    """
    for attempt in range(retries + 1):
        try:
            # Asegurar que TRIG esté bajo antes de iniciar
            GPIO.output(trig_pin, GPIO.LOW)
            time.sleep(0.00002)  # Pequeña pausa para asegurar estado bajo
            
            # Enviar pulso TRIG (10µs)
            GPIO.output(trig_pin, GPIO.HIGH)
            time.sleep(0.00001)  # 10 microsegundos exactos
            GPIO.output(trig_pin, GPIO.LOW)
            
            # Variables para medir tiempo
            start_loop_time = time.time()
            pulse_start_time = None
            pulse_end_time = None
            
            # Esperar a que ECHO suba (tiempo inicial)
            while GPIO.input(echo_pin) == GPIO.LOW:
                pulse_start_time = time.time()
                if pulse_start_time - start_loop_time > timeout:
                    if attempt < retries:
                        continue  # Reintentar
                    logger.debug(f"Timeout esperando inicio de pulso ECHO en pin {echo_pin}")
                    return None
                    
            # Esperar a que ECHO baje (tiempo final)
            while GPIO.input(echo_pin) == GPIO.HIGH:
                pulse_end_time = time.time()
                # Si el objeto está muy cerca, el pulso puede ser muy largo
                if pulse_end_time - pulse_start_time > timeout:
                    logger.debug(f"Pulso ECHO muy largo en pin {echo_pin} (posible objeto muy cerca)")
                    return 2.0  # Objeto muy cercano al sensor
                    
            # Calcular duración y distancia
            if pulse_start_time is not None and pulse_end_time is not None:
                pulse_duration = pulse_end_time - pulse_start_time
                distance = (pulse_duration * sound_speed) / 2  # Dividir por 2 (ida y vuelta)
                return distance
                
        except Exception as e:
            logger.error(f"Error en medición de distancia (pin {echo_pin}): {e}")
            
        # Pequeña pausa entre intentos
        time.sleep(0.05)
        
    return None  # Fallaron todos los intentos

def get_avg_distance(trig_pin, echo_pin, num_readings=3):
    """
    Obtiene un promedio de múltiples lecturas de distancia para mayor precisión.
    
    Args:
        trig_pin (int): Pin GPIO conectado al TRIG del sensor.
        echo_pin (int): Pin GPIO conectado al ECHO del sensor.
        num_readings (int): Número de lecturas a promediar.
        
    Returns:
        float or None: Distancia promedio en cm o None si todas las lecturas fallaron.
    """
    readings = []
    
    for _ in range(num_readings):
        distance = get_distance_cm(trig_pin, echo_pin, retries=1)
        if distance is not None:
            readings.append(distance)
        time.sleep(0.05)  # Pequeña pausa entre lecturas
        
    if not readings:
        return None
        
    # Si tenemos suficientes lecturas, eliminar valores atípicos
    if len(readings) >= 3:
        # Usar mediana para filtrar valores extremos
        return statistics.median(readings)
    
    # De lo contrario, usar promedio simple
    return sum(readings) / len(readings)

def calculate_fill_percentage(distance):
    """
    Calcula el porcentaje de llenado a partir de la distancia medida.
    
    Args:
        distance (float): Distancia en cm desde el sensor hasta el contenido.
        
    Returns:
        float: Porcentaje de llenado (0-100%).
    """
    if distance is None:
        return None
        
    # Calcular espacio vacío y luego llenado
    empty_space = max(0, min(distance, bin_depth_cm))
    filled_space = bin_depth_cm - empty_space
    fill_percentage = max(0, min(100, (filled_space / bin_depth_cm) * 100))
    
    return round(fill_percentage, 1)

def get_fill_levels(use_average=True, num_readings=None):
    """
    Obtiene el nivel de llenado (0-100%) para cada compartimento.
    
    Args:
        use_average (bool): Si True, utiliza un promedio de varias lecturas.
        num_readings (int): Número de lecturas a promediar (si None, usa el valor global).
        
    Returns:
        dict: Diccionario con el porcentaje de llenado para cada compartimento.
    """
    global fill_level_cache
    
    # Usar valor global si no se especifica
    if num_readings is None:
        num_readings = readings_per_measurement
        
    fill_levels = {}
    
    for name, (trig_pin, echo_pin) in sensor_pins.items():
        try:
            # Obtener distancia (simple o promediada)
            if use_average and num_readings > 1:
                distance = get_avg_distance(trig_pin, echo_pin, num_readings)
            else:
                distance = get_distance_cm(trig_pin, echo_pin)
                
            # Calcular porcentaje de llenado
            fill_percentage = calculate_fill_percentage(distance)
            
            if fill_percentage is not None:
                fill_levels[name] = fill_percentage
                fill_level_cache[name] = fill_percentage  # Actualizar caché
                logger.debug(f"Sensor '{name}': Dist={distance:.1f}cm, Llenado={fill_percentage:.1f}%")
            else:
                # Usar último valor válido de caché si disponible
                if name in fill_level_cache:
                    fill_levels[name] = fill_level_cache[name]
                    logger.warning(f"Usando valor en caché para sensor '{name}': {fill_levels[name]}%")
                else:
                    fill_levels[name] = None
                    logger.warning(f"No se pudo leer el sensor '{name}' y no hay valores en caché")
                    
            time.sleep(DEFAULT_READING_INTERVAL)  # Pausa entre lecturas de sensores
            
        except Exception as e:
            logger.error(f"Error obteniendo nivel para '{name}': {e}")
            fill_levels[name] = None
            
    return fill_levels

# --- Monitoreo Continuo ---

def start_continuous_monitoring(callback=None, interval=5.0):
    """
    Inicia un hilo de monitoreo continuo que mide los niveles periódicamente.
    
    Args:
        callback (callable): Función a llamar con los resultados de cada medición.
        interval (float): Intervalo entre mediciones en segundos.
        
    Returns:
        bool: True si el monitoreo se inició correctamente.
    """
    global is_monitoring, monitoring_thread
    
    if is_monitoring:
        logger.warning("El monitoreo continuo ya está activo")
        return False
        
    def monitoring_loop():
        global is_monitoring
        logger.info(f"Iniciando monitoreo continuo cada {interval} segundos")
        while is_monitoring:
            try:
                levels = get_fill_levels(use_average=True)
                
                # Llamar callback si existe
                if callback and callable(callback):
                    callback(levels)
                    
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error en ciclo de monitoreo: {e}")
                time.sleep(1)  # Pausa corta en caso de error
                
        logger.info("Monitoreo continuo detenido")
    
    # Configurar y comenzar hilo
    is_monitoring = True
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()
    
    return True

def stop_continuous_monitoring():
    """
    Detiene el hilo de monitoreo continuo.
    
    Returns:
        bool: True si el monitoreo se detuvo correctamente.
    """
    global is_monitoring, monitoring_thread
    
    if not is_monitoring:
        logger.warning("El monitoreo continuo no está activo")
        return False
        
    is_monitoring = False
    
    # Esperar a que el hilo termine (timeout)
    if monitoring_thread:
        monitoring_thread.join(timeout=2.0)
        
    monitoring_thread = None
    return True

# --- Limpieza ---

def cleanup_sensors():
    """
    Libera los recursos usados por los sensores.
    Esta función es segura de llamar incluso si los pines serán limpiados en main.py
    """
    # Detener monitoreo si está activo
    if is_monitoring:
        stop_continuous_monitoring()
        
    # No es necesario limpiar los pines individualmente,
    # ya que GPIO.cleanup() en main.py se ocupará de eso
    logger.info("Recursos de sensores liberados.")

# --- Código de prueba (se ejecuta solo si se llama directamente) ---
if __name__ == '__main__':
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    def print_levels(levels):
        """Imprime los niveles de llenado en formato legible."""
        for name, percentage in levels.items():
            print(f"{name}: {percentage:.1f}% lleno")
    
    # Probar configuración y medición
    print("=== Iniciando prueba de sensores ultrasónicos ===")
    try:
        # Cargar configuración si existe
        load_config()
        
        # Probar efecto de la temperatura
        if use_temperature_compensation:
            print(f"\nPrueba de compensación de temperatura:")
            print(f"Temperatura actual: {current_temperature}°C, velocidad del sonido: {sound_speed} cm/s")
            for test_temp in [10, 15, 20, 25, 30]:
                new_speed = set_temperature(test_temp)
                print(f"A {test_temp}°C -> Velocidad del sonido: {new_speed} cm/s")
        
        if setup_sensors():
            # Modo de prueba 1: Lectura única
            print("\n--- Modo de prueba 1: Lectura única ---")
            levels = get_fill_levels(use_average=True, num_readings=5)
            print_levels(levels)
            
            # Modo de prueba 2: Monitoreo continuo
            print("\n--- Modo de prueba 2: Monitoreo continuo (Ctrl+C para detener) ---")
            start_continuous_monitoring(callback=print_levels, interval=3.0)
            
            # Mantener ejecución hasta Ctrl+C
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nMonitoreo detenido por usuario.")
                stop_continuous_monitoring()
                
        else:
            print("Error al configurar sensores.")
            
    except Exception as e:
        print(f"Error durante la prueba: {e}")
        
    finally:
        # Limpiar recursos
        GPIO.cleanup()
        print("\n=== Prueba finalizada ===")