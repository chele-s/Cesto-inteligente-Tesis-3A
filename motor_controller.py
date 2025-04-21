# -*- coding: utf-8 -*-
"""
Módulo para controlar un motor paso a paso usando un driver A4988
conectado a los pines GPIO de una Raspberry Pi.

Este módulo forma parte del sistema Cesto Inteligente y proporciona las funciones 
necesarias para mover el mecanismo de separación a las posiciones correspondientes 
a cada tipo de residuo detectado.

Autor: Gabriel Calderón, Elias Bautista, Cristian Hernandez
Licencia: MIT
Versión: 1.1
"""

import RPi.GPIO as GPIO
import time
import logging
import json
import os

# Obtener logger configurado en main.py
logger = logging.getLogger()

# --- Configuración del Motor Paso a Paso ---
# ¡¡¡ADVERTENCIA!!! CAMBIA ESTOS PINES SEGÚN TU CONEXIÓN REAL
DIR_PIN = 20    # Pin de Dirección
STEP_PIN = 21   # Pin de Pasos
ENABLE_PIN = 16 # Pin de Habilitación (opcional)
USE_ENABLE = True # Poner a False si no usas el pin ENABLE (y conectas ENABLE del A4988 a GND)

# Control de velocidad (delay entre pulsos STEP - menor delay = mayor velocidad)
# Experimenta con este valor. Demasiado bajo puede hacer perder pasos.
STEP_DELAY = 0.005 # segundos

# Parámetros de ramping - se actualizarán desde config.json si está disponible
USE_RAMPING = True
RAMPING_START_DELAY = 0.01
RAMPING_MIN_DELAY = 0.001
RAMPING_ACCEL_STEPS = 20

# Variable global para rastrear la posición actual del motor (en pasos desde el inicio)
# Se asume que el motor empieza en la posición 0 al llamar a setup_gpio()
current_motor_steps = 0

def load_motor_config(config_file='config.json'):
    """
    Carga la configuración del motor desde un archivo JSON.
    
    Args:
        config_file (str): Ruta al archivo de configuración.
        
    Returns:
        bool: True si la configuración se cargó correctamente, False en caso contrario.
    """
    global STEP_DELAY, USE_RAMPING, RAMPING_START_DELAY, RAMPING_MIN_DELAY, RAMPING_ACCEL_STEPS
    
    try:
        if not os.path.exists(config_file):
            logger.warning(f"Archivo de configuración {config_file} no encontrado. Usando valores por defecto para el motor.")
            return False
            
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        if 'motor' in config:
            motor_config = config['motor']
            
            if 'step_delay' in motor_config:
                STEP_DELAY = float(motor_config['step_delay'])
                
            if 'use_ramping' in motor_config:
                USE_RAMPING = bool(motor_config['use_ramping'])
                
            if 'ramping_start_delay' in motor_config:
                RAMPING_START_DELAY = float(motor_config['ramping_start_delay'])
                
            if 'ramping_min_delay' in motor_config:
                RAMPING_MIN_DELAY = float(motor_config['ramping_min_delay'])
                
            if 'ramping_accel_steps' in motor_config:
                RAMPING_ACCEL_STEPS = int(motor_config['ramping_accel_steps'])
                
        logger.info(f"Configuración del motor cargada desde {config_file}")
        logger.info(f"Usando ramping: {USE_RAMPING}")
        if USE_RAMPING:
            logger.info(f"Parámetros de ramping: start_delay={RAMPING_START_DELAY}, min_delay={RAMPING_MIN_DELAY}, accel_steps={RAMPING_ACCEL_STEPS}")
        return True
        
    except Exception as e:
        logger.error(f"Error al cargar configuración del motor: {e}")
        return False

def setup_gpio():
    """
    Configura los pines GPIO necesarios para el control del motor.
    
    Esta función debe llamarse una vez al inicio del programa principal
    antes de intentar usar cualquier otra función del módulo. Configura
    los pines en modo BCM e inicializa la posición del motor a 0.
    
    Returns:
        bool: True si la configuración fue exitosa, False en caso contrario.
    
    Raises:
        No lanza excepciones, captura errores internamente.
    
    Note:
        Requiere privilegios de superusuario (sudo) en Raspberry Pi.
    """
    global current_motor_steps
    try:
        # Cargar configuración del motor
        load_motor_config()
        
        GPIO.setmode(GPIO.BCM) # Usar numeración BCM
        GPIO.setup(DIR_PIN, GPIO.OUT)
        GPIO.setup(STEP_PIN, GPIO.OUT)
        GPIO.output(STEP_PIN, GPIO.LOW) # Asegurar que el pin STEP empiece en bajo

        if USE_ENABLE:
            GPIO.setup(ENABLE_PIN, GPIO.OUT)
            GPIO.output(ENABLE_PIN, GPIO.HIGH) # Empezar con el driver deshabilitado (HIGH lo deshabilita en A4988)

        current_motor_steps = 0 # Asumir posición inicial 0
        logger.info("GPIO configurado para motor paso a paso.")
        return True

    except Exception as e:
        logger.error(f"Error al configurar GPIO: {e}")
        logger.error("Asegúrate de ejecutar como superusuario (sudo) si es necesario y que RPi.GPIO está instalado.")
        return False


def move_motor_to_position(target_steps):
    """
    Mueve el motor desde su posición actual a la posición objetivo.
    
    Esta función genera los pulsos necesarios para mover el motor paso a paso
    desde su posición actual hasta la posición especificada. La función es
    bloqueante y no retorna hasta completar el movimiento.
    
    Args:
        target_steps (int): La posición final deseada, en número de pasos
                           desde la posición inicial (0). Puede ser positivo
                           o negativo para controlar la dirección.
    
    Returns:
        None
    
    Note:
        Si USE_RAMPING está activado, utilizará move_motor_with_ramping para el movimiento.
    """
    # Si está habilitado el ramping, usar esa función en su lugar
    if USE_RAMPING:
        move_motor_with_ramping(target_steps, RAMPING_START_DELAY, RAMPING_MIN_DELAY, RAMPING_ACCEL_STEPS)
        return
    
    global current_motor_steps
    global STEP_DELAY

    if target_steps == current_motor_steps:
        logger.info(f"Motor ya en la posición {target_steps}. No se requiere movimiento.")
        return # Ya estamos en la posición deseada

    logger.debug(f"Moviendo motor de {current_motor_steps} a {target_steps} pasos.")

    # Habilitar driver si se usa el pin ENABLE
    if USE_ENABLE:
        GPIO.output(ENABLE_PIN, GPIO.LOW) # LOW habilita el A4988
        time.sleep(0.01) # Pequeña pausa para asegurar que el driver esté listo

    # Calcular pasos y dirección
    steps_to_move = target_steps - current_motor_steps
    # La dirección depende de tu cableado, podrías necesitar invertir GPIO.HIGH/GPIO.LOW
    direction = GPIO.HIGH if steps_to_move > 0 else GPIO.LOW
    GPIO.output(DIR_PIN, direction)
    time.sleep(0.01) # Pausa para que la dirección se establezca

    # Generar pulsos STEP
    abs_steps = abs(steps_to_move)
    for i in range(abs_steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(STEP_DELAY)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(STEP_DELAY)
        
        # Reportar progreso cada 25 pasos o en el último paso
        if i % 25 == 0 or i == abs_steps - 1:
            progress = (i + 1) / abs_steps * 100
            logger.debug(f"Progreso del movimiento: {progress:.1f}% ({i+1}/{abs_steps} pasos)")

    current_motor_steps = target_steps # Actualizar la posición actual registrada
    logger.info(f"Motor movido a la posición {current_motor_steps}.")

    # Decidir si deshabilitar el motor para ahorrar energía o mantenerlo habilitado
    # para que mantenga la posición (holding torque). Por defecto, lo dejamos habilitado.
    # if USE_ENABLE:
    #     GPIO.output(ENABLE_PIN, GPIO.HIGH) # Deshabilitar driver

def move_motor_with_ramping(target_steps, start_delay=0.01, min_delay=0.001, accel_steps=20):
    """
    Mueve el motor con rampa de aceleración/desaceleración para movimiento suave.
    
    Esta función avanzada implementa un perfil de velocidad trapezoidal para
    reducir vibraciones y mejorar la precisión del movimiento, especialmente
    para desplazamientos largos.
    
    Args:
        target_steps (int): Posición objetivo en pasos desde el cero
        start_delay (float): Delay inicial entre pulsos (segundos)
        min_delay (float): Delay mínimo (velocidad máxima) entre pulsos
        accel_steps (int): Número de pasos para aceleración/desaceleración
    
    Returns:
        None
    
    Note:
        Esta es una función avanzada que reduce la pérdida de pasos y las vibraciones.
    """
    global current_motor_steps
    
    if target_steps == current_motor_steps:
        logger.info(f"Motor ya en la posición {target_steps}. No se requiere movimiento.")
        return  # Ya estamos en la posición deseada
    
    logger.debug(f"Moviendo motor con ramping de {current_motor_steps} a {target_steps} pasos.")
    
    # Habilitar driver si se usa el pin ENABLE
    if USE_ENABLE:
        GPIO.output(ENABLE_PIN, GPIO.LOW)  # LOW habilita el A4988
        time.sleep(0.01)  # Pequeña pausa para asegurar que el driver esté listo
    
    # Calcular pasos y dirección
    steps_to_move = target_steps - current_motor_steps
    direction = GPIO.HIGH if steps_to_move > 0 else GPIO.LOW
    GPIO.output(DIR_PIN, direction)
    time.sleep(0.01)  # Pausa para que la dirección se establezca
    
    abs_steps = abs(steps_to_move)
    
    # Verificar que los pasos de aceleración sean razonables
    if accel_steps * 2 > abs_steps:
        accel_steps = abs_steps // 4  # Limitar al 25% del recorrido para aceleración y otro 25% para desaceleración
        logger.debug(f"Ajustando accel_steps a {accel_steps} para un movimiento de {abs_steps} pasos")
    
    # Generar perfil de velocidad trapezoidal
    for i in range(abs_steps):
        # Calcular el delay actual basado en la fase (aceleración, velocidad constante, desaceleración)
        if i < accel_steps:  # Fase de aceleración
            current_delay = start_delay - (i * (start_delay - min_delay) / accel_steps)
        elif i >= (abs_steps - accel_steps):  # Fase de desaceleración
            idx = abs_steps - i  # Pasos restantes
            current_delay = start_delay - (idx * (start_delay - min_delay) / accel_steps)
        else:  # Fase de velocidad constante
            current_delay = min_delay
        
        # Asegurar que el delay no sea menor que el mínimo permitido
        current_delay = max(current_delay, min_delay)
        
        # Generar pulso
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(current_delay)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(current_delay)
        
        # Reportar progreso cada 25 pasos o en el último paso
        if i % 25 == 0 or i == abs_steps - 1:
            progress = (i + 1) / abs_steps * 100
            logger.debug(f"Progreso del movimiento con ramping: {progress:.1f}% ({i+1}/{abs_steps} pasos)")
    
    current_motor_steps = target_steps  # Actualizar la posición actual registrada
    logger.info(f"Motor movido con ramping a la posición {current_motor_steps}.")

def cleanup_gpio():
    """
    Libera los recursos GPIO utilizados por el controlador del motor.
    
    Esta función debe llamarse al finalizar el programa principal para
    asegurar una liberación adecuada de los recursos. Deshabilita el
    motor y libera todos los pines GPIO utilizados.
    
    Returns:
        None
    
    Raises:
        No lanza excepciones, captura errores internamente.
    
    Note:
        Es importante llamar a esta función en un bloque finally para
        garantizar su ejecución incluso si ocurren errores.
    """
    try:
        # Opcional: Mover a una posición 'segura' o 'home' antes de limpiar
        # move_motor_to_position(0)
        # time.sleep(0.5)

        # Deshabilitar motor si se usa ENABLE
        if USE_ENABLE:
             GPIO.output(ENABLE_PIN, GPIO.HIGH)

        GPIO.cleanup()
        logger.info("GPIO limpiado correctamente.")
    except Exception as e:
        logger.error(f"Error durante la limpieza de GPIO: {e}")

# --- Código de prueba (opcional) ---
if __name__ == "__main__":
    # Configurar logging básico (en la aplicación principal se configurará más completo)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Cargar configuración
    load_motor_config()
    
    print("=== Test de Control de Motor Paso a Paso ===")
    try:
        if setup_gpio():
            print("\n1. Movimiento Simple (sin ramping)")
            USE_RAMPING = False  # Desactivar ramping temporalmente
            
            print("\nMoviendo a posición 50...")
            move_motor_to_position(50)
            time.sleep(1)
            
            print("\nVolviendo a posición 0...")
            move_motor_to_position(0)
            time.sleep(1)
            
            # Probar ramping si está disponible
            print("\n2. Movimiento con Ramping")
            USE_RAMPING = True
            
            print("\nMoviendo a posición 100 con ramping...")
            move_motor_to_position(100)
            time.sleep(1)
            
            print("\nVolviendo a posición 0 con ramping...")
            move_motor_to_position(0)
        else:
            print("Error al configurar GPIO. No se puede proceder con la prueba.")
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por usuario")
    finally:
        # Siempre limpiar GPIO al terminar
        cleanup_gpio()
        print("\n=== Test finalizado ===")