# Documentación: Módulo Motor Controller

## Descripción General

El módulo `motor_controller.py` proporciona una interfaz para controlar un motor paso a paso conectado a una Raspberry Pi a través de un driver A4988. Este módulo es parte fundamental del Cesto Inteligente y se encarga de mover físicamente el mecanismo de separación de residuos según la clasificación realizada por el sistema de visión por computadora.

## Requisitos

- Raspberry Pi (cualquier modelo con pines GPIO)
- Driver A4988 para motor paso a paso
- Motor paso a paso bipolar (como NEMA17)
- Biblioteca RPi.GPIO instalada
- Permisos de superusuario para acceder al GPIO

## Diagrama de Conexión

```
Raspberry Pi                A4988               Motor Paso a Paso
-----------                ------               ----------------
      GPIO20 ------> DIR     DIR  ----
      GPIO21 ------> STEP    STEP ----         [Conexiones del
      GPIO16 ------> ENABLE  ENABLE            motor según
      GND    ------> GND     GND                documentación
      5V     ------> VDD     VDD                del fabricante]
                            VMOT ---- Fuente de alimentación externa (8-35V)
                            
                            [MS1/MS2/MS3 - Configuración de microstepping]
```

**Nota importante**: El driver A4988 requiere una fuente de alimentación externa para el motor (VMOT). No conecte VMOT a la Raspberry Pi, ya que excede sus capacidades de corriente.

## Configuración

Las constantes de configuración en la parte superior del archivo determinan el comportamiento del motor:

- `DIR_PIN` (20): Pin GPIO conectado al pin DIR del A4988
- `STEP_PIN` (21): Pin GPIO conectado al pin STEP del A4988
- `ENABLE_PIN` (16): Pin GPIO conectado al pin ENABLE del A4988
- `USE_ENABLE` (True): Habilita/deshabilita el uso del pin ENABLE
- `STEP_DELAY` (0.005): Tiempo entre pulsos STEP (segundos), controla la velocidad del motor

## API de Funciones

### `setup_gpio()`

**Descripción**:  
Inicializa los pines GPIO necesarios para controlar el motor. Esta función debe llamarse al inicio del programa antes de intentar mover el motor.

**Parámetros**:  
Ninguno

**Retorno**:  
- `True`: Si la configuración fue exitosa
- `False`: Si hubo algún error durante la configuración

**Ejemplo**:
```python
import motor_controller

if motor_controller.setup_gpio():
    print("Motor listo para usar")
else:
    print("Error configurando el motor")
```

**Efectos Secundarios**:
- Configura los pines GPIO en modo BCM
- Inicializa el contador de pasos a 0
- Deshabilita el driver A4988 si USE_ENABLE está activo

### `move_motor_to_position(target_steps)`

**Descripción**:  
Mueve el motor desde su posición actual hasta la posición objetivo especificada en pasos.

**Parámetros**:  
- `target_steps` (int): Posición de destino en número de pasos desde la posición inicial (0)

**Retorno**:  
Ninguno

**Ejemplo**:
```python
# Mover a posición 100 pasos
motor_controller.move_motor_to_position(100)

# Volver a posición 0
motor_controller.move_motor_to_position(0)

# Mover a posición negativa (dirección opuesta)
motor_controller.move_motor_to_position(-50)
```

**Efectos Secundarios**:
- Actualiza el contador interno de pasos (`current_motor_steps`)
- Habilita el driver A4988 durante el movimiento (si USE_ENABLE es True)
- Bloquea la ejecución hasta completar el movimiento (operación síncrona)

### `cleanup_gpio()`

**Descripción**:  
Libera los recursos GPIO utilizados por el controlador del motor. Debe llamarse al finalizar el programa para una limpieza adecuada.

**Parámetros**:  
Ninguno

**Retorno**:  
Ninguno

**Ejemplo**:
```python
try:
    # Código del programa
    motor_controller.move_motor_to_position(100)
finally:
    # Asegurar que siempre se limpien los recursos
    motor_controller.cleanup_gpio()
```

**Efectos Secundarios**:
- Deshabilita el driver del motor (si USE_ENABLE está activo)
- Libera todos los pines GPIO utilizados

## Consideraciones Importantes

1. **Seguridad**:
   - El motor mantiene su posición (holding torque) después de moverse.
   - Para ahorrar energía y evitar calentamiento, puedes descomentar la línea que deshabilita el driver después del movimiento en la función `move_motor_to_position()`.

2. **Microstepping**:
   - El módulo no configura el microstepping por software. Debes establecerlo mediante los pines MS1, MS2 y MS3 del A4988 según la documentación del driver.
   - Recuerda ajustar TARGET_STEPS_MAP en main.py si cambias la configuración de microstepping.

3. **Homing**:
   - Este módulo no implementa un procedimiento de "homing" con interruptores de límite.
   - Se asume que la posición inicial (0) es la correcta al iniciar el programa.
   - Para implementar homing, necesitarías añadir interruptores de límite y modificar `setup_gpio()`.

4. **Suavidad del Movimiento**:
   - Para movimientos más suaves, reduce `STEP_DELAY` o implementa ramping (aceleración/desaceleración).
   - El valor óptimo de `STEP_DELAY` depende del motor, voltaje y carga.

5. **Debugging**:
   - Si el motor produce ruido pero no se mueve, verifica:
     - El voltaje en VMOT (¿suficiente corriente?)
     - Los ajustes de corriente en el potenciómetro del A4988
     - Las conexiones del motor
   - Si el motor vibra o pierde pasos, aumenta `STEP_DELAY`

## Integración con main.py

En el programa principal (main.py), el módulo se utiliza dentro de un hilo dedicado para evitar bloquear la interfaz gráfica:

```python
# Ejemplo simplificado de main.py
import threading
import motor_controller

# Configuración inicial
motor_controller.setup_gpio()

# Función para ejecutar en un hilo separado
def move_motor_thread(position):
    motor_controller.move_motor_to_position(position)
    
# Crear e iniciar el hilo
motor_thread = threading.Thread(target=move_motor_thread, args=(100,), daemon=True)
motor_thread.start()

# Al finalizar el programa
motor_controller.cleanup_gpio()
``` 