// Configuración
const API_BASE_URL = '/api';
const UPDATE_INTERVAL = 5000; // Intervalo de actualización en milisegundos
const SOCKET_URL = window.location.origin;

// Variables globales
let socket = null;
let updateTimer = null;
let countdownInterval = null;
let nextUpdateTime = null;

// Mapeo de nombres en inglés a español
const WASTE_TYPES_MAP = {
    'Metal': 'Metal',
    'Glass': 'Vidrio',
    'Plastic': 'Plástico',
    'Carton': 'Cartón'
};

// Iconos para cada tipo de residuo
const WASTE_ICONS_MAP = {
    'Metal': 'fa-bolt',
    'Glass': 'fa-wine-glass-alt',
    'Plastic': 'fa-flask',
    'Carton': 'fa-box'
};

// Elementos DOM
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const refreshButton = document.getElementById('refresh-button');
const nextUpdateElement = document.getElementById('next-update');
const toast = document.getElementById('toast');
const toastMessage = document.querySelector('.toast-message');
const toastClose = document.querySelector('.toast-close');

// --- Funciones de inicialización ---

// Inicializar la aplicación
function initApp() {
    // Registrar event listeners
    refreshButton.addEventListener('click', forceUpdate);
    toastClose.addEventListener('click', hideToast);
    
    // Intentar conectar WebSocket
    connectWebSocket();
    
    // Obtener datos iniciales
    fetchDashboardData();
    
    // Iniciar temporizador de actualización
    startUpdateTimer();
}

// Conectar al WebSocket para actualizaciones en tiempo real
function connectWebSocket() {
    try {
        // Actualizar estado de conexión
        setConnectionStatus('connecting', 'Conectando...');
        
        // Inicializar Socket.IO
        socket = io(SOCKET_URL);
        
        // Manejar eventos
        socket.on('connect', handleSocketConnect);
        socket.on('disconnect', handleSocketDisconnect);
        socket.on('connect_error', handleSocketError);
        socket.on('data_update', handleDataUpdate);
        socket.on('connection_error', handleConnectionError);
    } catch (error) {
        console.error('Error conectando WebSocket:', error);
        setConnectionStatus('disconnected', 'Error al conectar');
        showToast('Error al conectar con el servidor. Reintentando...', 'error');
    }
}

// --- Manejadores de eventos Socket.IO ---

function handleSocketConnect() {
    console.log('WebSocket conectado');
    setConnectionStatus('connected', 'Conectado');
    showToast('Conexión establecida con el servidor', 'success');
}

function handleSocketDisconnect() {
    console.log('WebSocket desconectado');
    setConnectionStatus('disconnected', 'Desconectado');
    showToast('Conexión perdida con el servidor. Reintentando...', 'error');
    
    // Reintentar conexión después de un tiempo
    setTimeout(connectWebSocket, 5000);
}

function handleSocketError(error) {
    console.error('Error en WebSocket:', error);
    setConnectionStatus('disconnected', 'Error de conexión');
    showToast('Error de conexión con el servidor', 'error');
}

function handleDataUpdate(data) {
    console.log('Actualizando datos');
    // Cuando recibimos notificación de actualización, obtenemos los datos más recientes
    fetchDashboardData();
}

function handleConnectionError(error) {
    console.error('Error de conexión con main.py:', error);
    showToast('Error de conexión con el sistema Cesto Inteligente', 'error');
}

// --- Funciones de actualización de datos ---

// Forzar actualización manual
function forceUpdate() {
    refreshButton.classList.add('spinning');
    
    // Si hay un socket conectado, solicitar actualización
    if (socket && socket.connected) {
        socket.emit('request_update');
    } else {
        // Si no hay socket, usar fetch
        fetchDashboardData();
    }
    
    // Reiniciar temporizador
    startUpdateTimer();
    
    // Quitar clase spinning después de un segundo
    setTimeout(() => {
        refreshButton.classList.remove('spinning');
    }, 1000);
}

// Obtener datos del dashboard desde la API
async function fetchDashboardData() {
    try {
        const response = await fetch(`${API_BASE_URL}/dashboard`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Actualizar la UI con los nuevos datos
            updateDashboard(data.data);
            setConnectionStatus('connected', 'Conectado');
        } else {
            console.error('Error en respuesta API:', data);
            showToast('Error al obtener datos del servidor', 'error');
        }
    } catch (error) {
        console.error('Error obteniendo datos:', error);
        setConnectionStatus('disconnected', 'Error al obtener datos');
        showToast('Error al comunicarse con el servidor', 'error');
    }
}

// Actualizar toda la UI con los datos recibidos
function updateDashboard(data) {
    // Actualizar niveles de llenado
    if (data.fill_levels) {
        updateFillLevels(data.fill_levels);
    }
    
    // Actualizar estadísticas
    if (data.statistics) {
        updateStatistics(data.statistics);
    }
    
    // Actualizar estado del sistema
    if (data.system_status) {
        updateSystemStatus(data.system_status);
    }
    
    // Actualizar última detección
    if (data.detection) {
        updateLastDetection(data.detection);
    }
    
    // Actualizar última actualización
    const lastUpdate = document.getElementById('last-update');
    const now = new Date();
    lastUpdate.textContent = now.toLocaleTimeString();
}

// Actualizar los niveles de llenado
function updateFillLevels(levels) {
    for (const [compartment, level] of Object.entries(levels)) {
        const lowerName = compartment.toLowerCase();
        const fillBar = document.getElementById(`${lowerName}-fill`);
        const percentText = document.getElementById(`${lowerName}-percentage`);
        
        if (fillBar && percentText) {
            // Actualizar altura de la barra
            fillBar.style.height = `${level}%`;
            
            // Actualizar texto de porcentaje
            percentText.textContent = `${Math.round(level)}%`;
            
            // Establecer color según nivel
            if (level > 80) {
                fillBar.style.backgroundColor = 'var(--error-color)';
            } else if (level > 50) {
                fillBar.style.backgroundColor = 'var(--warning-color)';
            } else {
                fillBar.style.backgroundColor = `var(--${lowerName}-color)`;
            }
        }
    }
}

// Actualizar las estadísticas
function updateStatistics(stats) {
    let totalItems = 0;
    
    // Actualizar contadores individuales
    for (const [wasteType, count] of Object.entries(stats)) {
        const lowerName = wasteType.toLowerCase();
        const countElement = document.getElementById(`${lowerName}-count`);
        
        if (countElement) {
            countElement.textContent = count;
        }
        
        totalItems += count;
    }
    
    // Actualizar total
    const totalElement = document.getElementById('total-items');
    if (totalElement) {
        totalElement.textContent = totalItems;
    }
}

// Actualizar el estado del sistema
function updateSystemStatus(status) {
    const statusElement = document.getElementById('system-status');
    const messageElement = document.getElementById('status-message');
    
    if (statusElement) {
        // Mapear estado a texto amigable en español
        let statusText = status.status || 'unknown';
        let displayStatus = 'Desconocido';
        
        switch (statusText) {
            case 'active':
                displayStatus = 'Activo';
                break;
            case 'inactive':
                displayStatus = 'Inactivo';
                break;
            case 'error':
                displayStatus = 'Error';
                break;
            case 'starting':
                displayStatus = 'Iniciando';
                break;
            default:
                displayStatus = statusText.charAt(0).toUpperCase() + statusText.slice(1);
        }
        
        statusElement.textContent = displayStatus;
    }
    
    if (messageElement && status.message) {
        messageElement.textContent = status.message;
    }
}

// Actualizar información de la última detección
function updateLastDetection(detection) {
    if (!detection || !detection.class_name) {
        return;
    }
    
    const detectedItem = document.getElementById('detected-item');
    const wasteType = detection.class_name;
    const confidence = detection.confidence;
    
    if (detectedItem) {
        // Remover clases previas
        detectedItem.className = 'detected-item';
        
        // Agregar clase para el tipo de residuo
        detectedItem.classList.add(wasteType.toLowerCase());
        
        // Actualizar contenido
        const iconElement = detectedItem.querySelector('.detection-icon i');
        const classElement = detectedItem.querySelector('.detection-class');
        const confidenceElement = detectedItem.querySelector('.detection-confidence');
        
        if (iconElement) {
            iconElement.className = `fas ${WASTE_ICONS_MAP[wasteType] || 'fa-question-circle'}`;
        }
        
        if (classElement) {
            classElement.textContent = WASTE_TYPES_MAP[wasteType] || wasteType;
        }
        
        if (confidenceElement && confidence) {
            confidenceElement.textContent = `Confianza: ${Math.round(confidence * 100)}%`;
        }
    }
}

// --- Funciones auxiliares ---

// Establecer estado de conexión
function setConnectionStatus(state, text) {
    statusIndicator.className = 'status-dot';
    statusIndicator.classList.add(state);
    statusText.textContent = text;
}

// Iniciar temporizador de actualización
function startUpdateTimer() {
    // Limpiar temporizadores existentes
    if (updateTimer) {
        clearTimeout(updateTimer);
    }
    
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    
    // Configurar próxima actualización
    nextUpdateTime = Date.now() + UPDATE_INTERVAL;
    
    // Iniciar el intervalo para actualizar la cuenta regresiva
    updateCountdown();
    countdownInterval = setInterval(updateCountdown, 1000);
    
    // Configurar el temporizador para la próxima actualización
    updateTimer = setTimeout(() => {
        fetchDashboardData();
        startUpdateTimer();
    }, UPDATE_INTERVAL);
}

// Actualizar cuenta regresiva
function updateCountdown() {
    const now = Date.now();
    const remaining = Math.max(0, nextUpdateTime - now);
    const seconds = Math.ceil(remaining / 1000);
    
    nextUpdateElement.textContent = `${seconds}s`;
    
    if (seconds <= 0) {
        // Actualización en progreso
        nextUpdateElement.textContent = 'Actualizando...';
    }
}

// Mostrar mensaje toast
function showToast(message, type = 'info') {
    // Configurar mensaje y tipo
    toastMessage.textContent = message;
    
    // Remover clases previas
    toast.className = 'toast';
    
    // Agregar tipo
    toast.classList.add(type);
    
    // Mostrar toast
    setTimeout(() => {
        toast.classList.remove('hidden');
    }, 10);
    
    // Ocultar automáticamente después de 5 segundos
    setTimeout(hideToast, 5000);
}

// Ocultar mensaje toast
function hideToast() {
    toast.classList.add('hidden');
}

// Inicializar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', initApp); 