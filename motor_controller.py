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

# Variable global para rastrear la posición actual del motor (en pasos desde el inicio)
# Se asume que el motor empieza en la posición 0 al llamar a setup_gpio()
current_motor_steps = 0

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
    
    Raises:
        No lanza excepciones, pero errores de GPIO pueden ocurrir en la ejecución.
    
    Examples:
        >>> move_motor_to_position(100)  # Mover a posición 100
        >>> move_motor_to_position(0)    # Volver a posición inicial
    """
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

# --- Función adicional para ramping (aceleración/desaceleración) ---
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
        Esta es una función experimental. Ajustar parámetros según el motor usado.
    """
    global current_motor_steps
    
    # Esta función es experimental y está comentada por defecto
    # Para utilizarla, descomentar y añadir la implementación de ramping
    logger.warning("La función move_motor_with_ramping es experimental y no está implementada")
    # Implementación básica: usar move_motor_to_position estándar
    move_motor_to_position(target_steps)

# --- Código de prueba (opcional) ---
# Si ejecutas este archivo directamente, puedes probar las funciones.
if __name__ == '__main__':
    # Configurar logging básico para pruebas
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()
    
    logger.info("=== Iniciando prueba del controlador de motor ===")
    if setup_gpio():
        try:
            logger.info("Moviendo a 50 pasos...")
            move_motor_to_position(50)
            time.sleep(1)

            logger.info("Moviendo a 0 pasos...")
            move_motor_to_position(0)
            time.sleep(1)

            logger.info("Moviendo a -50 pasos (dirección inversa)...")
            move_motor_to_position(-50)
            time.sleep(1)

            logger.info("Volviendo a posición 0...")
            move_motor_to_position(0)
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Prueba interrumpida por el usuario (Ctrl+C).")
        finally:
            cleanup_gpio()
    else:
        logger.error("No se pudo iniciar la prueba debido a un error de configuración de GPIO.")
    
    logger.info("=== Prueba finalizada ===")