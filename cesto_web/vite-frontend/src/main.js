// Importaciones
import anime from 'animejs'
import { io } from 'socket.io-client';

// Configuración global
const WEBSOCKET_URL = 'http://localhost:5000';
const ANIMATION_DURATION = 800;
const ANIMATION_EASING = 'easeOutElastic(1, .5)';
const UPDATE_INTERVAL = 10000;

// Estado de la aplicación
const appState = {
  fillLevels: {
    metal: 0,
    glass: 0,
    plastic: 0,
    carton: 0
  },
  statistics: {
    metal: 0,
    glass: 0,
    plastic: 0,
    carton: 0,
    total: 0
  },
  lastDetection: {
    class: null,
    confidence: 0,
    timestamp: null
  },
  systemStatus: {
    status: 'disconnected',
    lastUpdate: null,
    message: 'No hay conexión'
  },
  darkMode: true,
  focusedBinType: null, // 'metal', 'glass', etc. or null
  binOrder: ['metal', 'glass', 'plastic', 'carton'] // Define order for navigation
};

// Variable global para la animación de las olas
let waveAnimation = null;

// --- Helper para hover ---
function addHoverEffect(selector, animationProps) {
  document.querySelectorAll(selector).forEach(el => {
    let anim;
    el.addEventListener('mouseenter', () => {
      anim = anime({
        targets: el,
        ...animationProps,
        duration: 300,
        easing: 'easeOutQuad'
      });
    });
    el.addEventListener('mouseleave', () => {
      if (anim) {
        // Animar de vuelta a la normalidad puede ser complejo si hay transforms previos.
        // Una forma simple es usar scale/translateY relativos o revertir/buscar el inicio.
        // Para simplicidad, animamos a los valores por defecto.
        anime({
          targets: el,
          scale: 1,
          translateY: 0, // Asegurarse de volver a 0 si se usa translateY
          // ... otros props a resetear si es necesario
          duration: 200,
          easing: 'easeOutQuad'
        });
      }
    });
  });
}
// --- Fin Helper para hover ---

// Elementos DOM
const elements = {
  // loading: document.getElementById('loading'), // Comentado o eliminado
  themeToggle: document.getElementById('theme-toggle'),
  header: document.getElementById('header'),
  mainContainer: document.getElementById('main-container'),
  sections: document.querySelectorAll('.dashboard-section'),
  footer: document.getElementById('footer'),
  
  // Llenado de bines
  binFills: {
    metal: document.getElementById('metal-fill'),
    glass: document.getElementById('glass-fill'),
    plastic: document.getElementById('plastic-fill'),
    carton: document.getElementById('carton-fill')
  },
  binPercentages: {
    metal: document.getElementById('metal-percentage'),
    glass: document.getElementById('glass-percentage'),
    plastic: document.getElementById('plastic-percentage'),
    carton: document.getElementById('carton-percentage')
  },
  
  // Detección
  detectionIcon: document.getElementById('detection-icon'),
  detectionClass: document.getElementById('detection-class'),
  detectionConfidence: document.getElementById('detection-confidence'),
  confidenceBar: document.getElementById('confidence-bar'),
  detectionIconInner: document.getElementById('detection-icon-inner'),
  
  // Estadísticas
  counts: {
    metal: document.getElementById('metal-count'),
    glass: document.getElementById('glass-count'),
    plastic: document.getElementById('plastic-count'),
    carton: document.getElementById('carton-count')
  },
  
  // Estado del sistema
  systemStatus: document.getElementById('system-status'),
  lastUpdate: document.getElementById('last-update'),
  statusMessage: document.getElementById('status-message'),

  // Vista Pantalla Completa
  fullscreenView: document.getElementById('fullscreen-fill-levels'),
  closeFullscreenBtn: document.getElementById('close-fullscreen-btn'),
  fullscreenBinsContainer: document.querySelector('.fullscreen-bins-container'),
  fullscreenBins: document.querySelectorAll('.fullscreen-bin'), // Get all bin containers
  prevBinBtn: document.getElementById('prev-bin-btn'),
  nextBinBtn: document.getElementById('next-bin-btn'),
  // Apuntar a los paths de las olas SVG
  fullscreenBinFills: {
    metal: document.getElementById('wave-metal'),
    glass: document.getElementById('wave-glass'),
    plastic: document.getElementById('wave-plastic'),
    carton: document.getElementById('wave-carton')
  },
  fullscreenBinPercentages: {
    metal: document.getElementById('fullscreen-metal-percentage'),
    glass: document.getElementById('fullscreen-glass-percentage'),
    plastic: document.getElementById('fullscreen-plastic-percentage'),
    carton: document.getElementById('fullscreen-carton-percentage')
  }
};

// Inicializar Socket.io
let socket;

function initSocketConnection() {
  socket = io(WEBSOCKET_URL, {
    reconnectionAttempts: 5,
    timeout: 10000
  });
  
  // Eventos de Socket.io
  socket.on('connect', () => {
    console.log('Conectado al servidor');
    updateSystemStatus('connected', 'Conectado al servidor');
    
    // Solicitar datos iniciales
    socket.emit('getData');
  });
  
  socket.on('disconnect', () => {
    console.log('Desconectado del servidor');
    updateSystemStatus('disconnected', 'Desconectado del servidor');
  });
  
  socket.on('error', (error) => {
    console.error('Error de conexión:', error);
    updateSystemStatus('error', 'Error de conexión');
  });
  
  // Eventos de datos
  socket.on('fillLevels', (data) => {
    updateFillLevels(data);
  });
  
  socket.on('statistics', (data) => {
    updateStatistics(data);
  });
  
  socket.on('detection', (data) => {
    updateDetection(data);
  });
  
  socket.on('systemStatus', (data) => {
    updateSystemStatus(data.status, data.message);
  });
}

// Actualizar niveles de llenado
function updateFillLevels(data) {
  const { metal, glass, plastic, carton } = data;
  
  // Actualizar estado
  appState.fillLevels = { metal, glass, plastic, carton };
  
  // Animar las barras de llenado (Dashboard)
  Object.keys(appState.fillLevels).forEach(type => {
    const value = appState.fillLevels[type];
    const percentage = Math.round(value);
    
    // Animar la altura y opacidad de la barra (Dashboard)
    anime({
      targets: elements.binFills[type],
      height: `${percentage}%`,
      opacity: [0.5, 1],
      duration: ANIMATION_DURATION,
      easing: ANIMATION_EASING
    });
    
    // Actualizar el texto de porcentaje con contador (Dashboard)
    const percentageElement = elements.binPercentages[type];
    anime({
      targets: {value: parseInt(percentageElement.textContent.replace('%', '') || 0)}, // Parse current value or default to 0
      value: percentage,
      round: 1,
      duration: ANIMATION_DURATION,
      easing: 'linear',
      update: function(anim) {
        percentageElement.textContent = Math.round(anim.animatables[0].target.value) + '%';
      }
    });
    
    // Animar el icono del cesto correspondiente (Dashboard)
    const iconElement = elements.binFills[type].closest('.bin').querySelector('.bin-icon i');
    if (iconElement) {
      anime({
        targets: iconElement,
        scale: [1, 1.3, 1], // Efecto de pulso
        duration: 600,
        easing: 'easeOutElastic(1, .6)'
      });
    }

    // Añadir clase de alerta si el nivel es alto (Dashboard)
    const binElement = elements.binFills[type].closest('.bin');
    if (percentage > 80) {
        binElement.classList.add('alert-high'); // Asegúrate de tener estilos CSS para .alert-high en .bin
    } else {
        binElement.classList.remove('alert-high');
    }
  });

  // Actualizar también la vista fullscreen si está visible
  if (elements.fullscreenView.classList.contains('visible')) {
    updateFullscreenFillView(appState.fillLevels);
  }
  
  // Actualizar timestamp
  appState.systemStatus.lastUpdate = new Date();
  displayTimestamp();
}

// Actualizar estadísticas
function updateStatistics(data) {
  const { metal, glass, plastic, carton, total } = data;
  
  // Guardar estado anterior para animación
  const prevStats = { ...appState.statistics };
  
  // Actualizar estado
  appState.statistics = { metal, glass, plastic, carton, total };
  
  // Animar los contadores
  Object.keys(elements.counts).forEach(type => {
    const prevValue = prevStats[type];
    const newValue = appState.statistics[type];
    
    anime({
      targets: {value: prevValue},
      value: newValue,
      round: 1,
      duration: ANIMATION_DURATION,
      easing: 'easeOutElastic(1, .7)',
      update: function(anim) {
        elements.counts[type].textContent = Math.round(anim.animatables[0].target.value);
      },
      complete: function() {
        const statItem = elements.counts[type].closest('.stat-item');
        if (statItem) {
          statItem.classList.add('highlight-update');
          setTimeout(() => statItem.classList.remove('highlight-update'), 600);
        }
      }
    });
    
    // Efecto de pulso al actualizar
    anime({
      targets: elements.counts[type],
      scale: [1, 1.2, 1],
      duration: 600,
      easing: 'easeInOutQuad'
    });
  });
}

// Actualizar detección
function updateDetection(data) {
  if (!data) return;
  
  const { class: detectedClass, confidence } = data;
  const detectionContainer = document.getElementById('detection-container');
  const detectionElements = '#detection-container > *'; // Selector for children
  
  // Check if container exists
  if (!detectionContainer) {
      console.warn('Detection container not found, skipping update.');
      return;
  }

  // 1. Cancelar animaciones previas en los elementos de detección
  anime.remove([detectionElements, detectionContainer, elements.confidenceBar, elements.detectionIconInner]);
  
  // Actualizar estado
  appState.lastDetection = {
    class: detectedClass,
    confidence: confidence,
    timestamp: new Date()
  };
  
  // Actualizar icono según la clase detectada
  let iconClass = 'fas fa-question-circle';
  switch (detectedClass.toLowerCase()) {
    case 'metal':
      iconClass = 'fas fa-bolt';
      break;
    case 'glass':
      iconClass = 'fas fa-wine-glass-alt';
      break;
    case 'plastic':
      iconClass = 'fas fa-flask';
      break;
    case 'carton':
      iconClass = 'fas fa-box';
      break;
  }
  
  // Animar el cambio de detección
  // Primero, animar la salida del contenido anterior si existe
  anime({
    targets: detectionElements, // Animar hijos
    opacity: [1, 0],
    translateY: [0, 10],
    duration: 300,
    easing: 'easeInQuad',
    complete: function() {
      // 2. Verificar si el contenedor todavía existe antes de modificarlo
      if (!detectionContainer) return; 

      // Actualizar contenido después de ocultar
      // Usar la referencia segura a detectionIconInner
      elements.detectionIconInner.className = iconClass; // Update only the <i> class
      elements.detectionClass.textContent = detectedClass;
      elements.detectionConfidence.textContent = `Confianza: ${Math.round(confidence * 100)}%`;
      
      // Animar la entrada del nuevo contenido
      anime({
        targets: detectionElements,
        opacity: [0, 1],
        translateY: [10, 0],
        duration: 400,
        easing: 'easeOutQuad',
        delay: anime.stagger(50) // Escalonar la aparición de icono e info
      });

      // Animar la barra de confianza
      anime({
        targets: elements.confidenceBar,
        width: `${confidence * 100}%`,
        duration: ANIMATION_DURATION,
        easing: 'easeOutQuad'
      });
      
      // Animar el icono (rotación) - Usar referencia directa
      anime({
        targets: elements.detectionIconInner,
        rotate: '1turn',
        duration: 800,
        easing: 'easeOutCirc'
      });

      // Cambiar el color del contenedor según el tipo de material
      // Usar la referencia segura a detectionContainer
      detectionContainer.classList.remove('metal', 'glass', 'plastic', 'carton'); // Safe now due to check above
      if (detectedClass) {
        detectionContainer.classList.add(detectedClass.toLowerCase());
      }
    }
  });
  
  // Animar el borde del contenedor de la sección
  anime({
    targets: detectionContainer.closest('.dashboard-section'), // Target the parent section
    borderColor: ['var(--border-color)', 'var(--secondary-color)', 'var(--border-color)'], // Flash border
    duration: 1000,
    easing: 'easeInOutSine'
  });
}

// Actualizar estado del sistema
function updateSystemStatus(status, message) {
  // Actualizar estado
  appState.systemStatus.status = status;
  appState.systemStatus.message = message;
  appState.systemStatus.lastUpdate = new Date();
  
  // Actualizar elementos DOM
  elements.systemStatus.textContent = getStatusText(status);
  elements.statusMessage.textContent = message;
  
  // Cambiar la clase según el estado
  elements.systemStatus.className = 'info-value';
  elements.systemStatus.classList.add(`status-${status}`);
  
  // Mostrar timestamp
  displayTimestamp();
}

// Formatear y mostrar timestamp
function displayTimestamp() {
  if (!appState.systemStatus.lastUpdate) return;
  
  const date = appState.systemStatus.lastUpdate;
  const options = { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit',
    hour12: false 
  };
  const timeString = date.toLocaleTimeString('es-ES', options);
  
  // Animate timestamp update
  anime({
    targets: elements.lastUpdate,
    opacity: [0, 1],
    translateY: [-5, 0],
    duration: 500,
    easing: 'easeOutQuad',
    begin: function() {
      elements.lastUpdate.textContent = timeString; // Update text at animation start
    }
  });
}

// Obtener texto de estado
function getStatusText(status) {
  switch (status) {
    case 'connected':
      return 'Conectado';
    case 'disconnected':
      return 'Desconectado';
    case 'error':
      return 'Error';
    default:
      return 'Desconocido';
  }
}

// --- Intersection Observer Setup ---
function setupScrollAnimations() {
    const sections = document.querySelectorAll('.dashboard-section');
    if (!sections.length) return { observer: null, sections: [] }; // Exit if no sections found

    const observerOptions = {
        root: null, // Use the viewport as the root
        rootMargin: '0px 0px -10% 0px', // Trigger a bit before element is fully in/out view from bottom
        threshold: 0.1 // Trigger when 10% is visible
    };

    const observerCallback = (entries, observer) => {
        entries.forEach(entry => {
            const target = entry.target;
            // OPTIMIZATION: Find children only if intersecting to avoid unnecessary queries
            // const children = target.querySelectorAll('.card-title, .bins-container > *, .detection-container > *, .stats-grid > *, .info-container > *');

            // Cancel any ongoing animations on this target // and its children
            // anime.remove([target, ...children]); // Removing children animation cancel here for simplicity
            anime.remove(target); 

            if (entry.isIntersecting) {
                // Find children just before animating in
                const children = target.querySelectorAll('.card-title, .bins-container > *, .detection-container > *, .stats-grid > *, .info-container > *');
                anime.remove([...children]); // Cancel any pending animations on children before starting new ones

                // --- Animate In --- 
                anime({
                    targets: target,
                    opacity: [0, 1],
                    translateY: [80, 0], // Start further down
                    scale: [0.95, 1], // Subtle scale up
                    rotateX: [-20, 0], // Subtle rotation
                    duration: 1200,
                    easing: 'easeOutExpo', // Smoother easing
                });
                
                anime({
                  targets: children,
                  opacity: [0, 1],
                  translateY: [30, 0],
                  scale: [0.9, 1],
                  delay: anime.stagger(80, { start: 150 }), 
                  duration: 1000,
                  easing: 'easeOutExpo'
                });
                // Optionally unobserve after first animation to prevent re-triggering
                // observer.unobserve(target); 

            } else {
                 // Find children just before animating out (if animating children out)
                const children = target.querySelectorAll('.card-title, .bins-container > *, .detection-container > *, .stats-grid > *, .info-container > *');
                anime.remove([...children]); // Cancel child animations too

                // --- Animate Out --- 
                // Set immediate initial state for exit if needed (though typically we animate from current)
                anime({
                    targets: target,
                    opacity: [target.style.opacity || 1, 0], // Animate from current opacity to 0
                    translateY: [0, -60], // Move up slightly on exit
                    scale: 0.95,
                    rotateX: 10, // Slight tilt out
                    duration: 600,
                    easing: 'easeInQuad' // Faster exit easing
                });

                // Optionally animate children out too, or let them disappear with the parent
                anime({
                    targets: children,
                    opacity: 0,
                    translateY: -20,
                    scale: 0.95,
                    duration: 400,
                    delay: anime.stagger(40), // Faster stagger out
                    easing: 'easeInQuad'
                });
            }
        });
    };

    const observer = new IntersectionObserver(observerCallback, observerOptions);

    sections.forEach(section => {
        // Initial state: Set opacity to 0, transform as needed for entry animation start
        section.style.opacity = '0'; 
        // We set the starting translateY/scale/rotate in the 'Animate In' part now
        section.style.transform = 'translateY(80px) scale(0.95) rotateX(-20deg)'; // Set initial transform explicitly
        
        // Set initial state for children too
        section.querySelectorAll('.card-title, .bins-container > *, .detection-container > *, .stats-grid > *, .info-container > *').forEach(child => {
           child.style.opacity = '0';
           child.style.transform = 'translateY(30px) scale(0.9)'; // Set initial child transform
        });
         
        // DO NOT observe yet, observer.observe(section);
    });

    // Return observer and sections to start observing later
    return { observer, sections }; 
}

// Alternar tema
function toggleTheme() {
  const html = document.documentElement;
  appState.darkMode = !appState.darkMode;
  const iconElement = elements.themeToggle.querySelector('i');
  
  if (appState.darkMode) {
    html.classList.add('dark-mode');
    iconElement.className = 'fas fa-sun'; // Update class directly
  } else {
    html.classList.remove('dark-mode');
    iconElement.className = 'fas fa-moon'; // Update class directly
  }
  
  // Animar el cambio de tema (body)
  anime({
    targets: 'body',
    opacity: [0.8, 1],
    duration: 500,
    easing: 'easeOutQuad'
  });

  // Animar el icono del toggle
  anime({
    targets: iconElement,
    rotate: [0, 360],
    scale: [1, 1.3, 1],
    duration: 600,
    easing: 'easeInOutSine'
  });
}

// Animaciones iniciales
function runEntryAnimations() {
  // Animar el header
  anime({
    targets: elements.header,
    translateY: [-50, 0],
    opacity: [0, 1],
    duration: 1000,
    easing: 'easeOutQuad'
  });
  
  // Animar el footer
  anime({
    targets: elements.footer,
    translateY: [20, 0],
    opacity: [0, 1],
    duration: 1000,
    delay: 1200,
    easing: 'easeOutQuad'
  });
}

// Cargar datos simulados (para desarrollo)
function loadMockData() {
  // Simulación de datos para desarrollo
  const mockFillLevels = {
    metal: 65,
    glass: 30,
    plastic: 85,
    carton: 45
  };
  
  const mockStatistics = {
    metal: 42,
    glass: 28,
    plastic: 65,
    carton: 33,
    total: 168
  };
  
  const mockDetection = {
    class: 'Plastic',
    confidence: 0.89,
    timestamp: new Date() // Add timestamp for consistency
  };
  
  // Usar setTimeout para simular delay de red
  // Update mock data calls to prevent rapid consecutive updates in dev
  if (!window.mockUpdateTimeout) {
    window.mockUpdateTimeout = true;
    setTimeout(() => {
      updateFillLevels(mockFillLevels);
      updateStatistics(mockStatistics);
      updateDetection(mockDetection);
      window.mockUpdateTimeout = false; // Allow next update
    }, 2000); // Increase delay slightly
  }
}

// --- Fullscreen View Logic ---

// Actualizar vista de pantalla completa (llamado por updateFillLevels o al abrir)
function updateFullscreenFillView(data) {
  // SVG ViewBox Height (definido en el HTML como 100)
  const svgHeight = 100;

  Object.keys(data).forEach(type => {
    const value = data[type];
    const percentage = Math.round(value);
    const targetY = svgHeight * (1 - percentage / 100);

    // console.log(`Updating ${type}: ${percentage}% -> targetY: ${targetY}`); // Log para depuración
    // Asegurarse que el elemento existe - TARGET THE GROUP NOW
    const waveGroupElement = elements.fullscreenBinFills[type]; 
    if (!waveGroupElement) return;

    // Animar posición vertical de la ola SVG - ANIMATE THE GROUP
    anime({
      targets: waveGroupElement,
      // Animar el atributo transform para mover la ola verticalmente
      translateY: targetY,
      duration: ANIMATION_DURATION + 200,
      easing: 'easeOutElastic(1, .6)' // Un easing más "líquido"
    });

    // Actualizar porcentaje con contador (Fullscreen)
    const percentageElement = elements.fullscreenBinPercentages[type];
    anime({
       targets: {value: parseInt(percentageElement.textContent.replace('%', '') || 0)}, // Parse current value or default to 0
      value: percentage,
      round: 1,
      duration: ANIMATION_DURATION + 200,
      easing: 'linear',
      update: function(anim) {
        percentageElement.textContent = Math.round(anim.animatables[0].target.value) + '%';
      }
    });
     // Añadir clase de alerta si el nivel es alto (Fullscreen)
    const fullscreenBinElement = elements.fullscreenBinFills[type].closest('.fullscreen-bin');
    if (percentage > 80) {
        fullscreenBinElement.classList.add('alert-high'); // Asegúrate de tener estilos CSS para .alert-high en .fullscreen-bin
    } else {
        fullscreenBinElement.classList.remove('alert-high');
    }
  });
}

// Iniciar animación continua de las olas
function startWaveAnimation() {
  if (waveAnimation) {
    waveAnimation.pause(); // Pausa si ya existe
  }
  waveAnimation = anime({
    targets: '.wave-fill', // TARGET THE INNER PATH
    // Animar el atributo 'd' para simular movimiento
    // Usaremos una animación más simple: mover horizontalmente
    translateX: [
      { value: -10, duration: 1500, easing: 'easeInOutSine' }, // Mover a la izquierda
      { value: 10, duration: 1500, easing: 'easeInOutSine' },  // Mover a la derecha
    ],
    loop: true,
    direction: 'alternate',
    delay: anime.stagger(200) // Desfasar ligeramente las olas
  });
}

// Detener animación continua de las olas
function stopWaveAnimation() {
  if (waveAnimation) {
    waveAnimation.pause();
    // Opcional: resetear translateX si es necesario
    // anime({ targets: '.wave-fill', translateX: 0, duration: 100 });
  }
}

// Enfocar un cesto específico
function focusOnBin(type, direction = 'none') { // direction: 'from-right', 'from-left', 'none'
  if (!type || !elements.fullscreenBinsContainer) return;
  
  const previouslyFocused = appState.focusedBinType;
  appState.focusedBinType = type;
  elements.fullscreenView.classList.add('focused');

  // Seleccionar el bin a enfocar y los otros
  const targetBin = elements.fullscreenView.querySelector(`.fullscreen-bin[data-type="${type}"]`);
  const otherBins = Array.from(elements.fullscreenBins).filter(bin => bin.dataset.type !== type);
  
  if (!targetBin) return;

  // Get container dimensions for centering
  const container = elements.fullscreenBinsContainer;
  const containerRect = container.getBoundingClientRect();
  const targetRect = targetBin.getBoundingClientRect(); // Get initial rect *before* potential style changes

  // Calculate center position relative to the container's top-left
  // Adjust if container has padding or borders influencing child positions
  const targetCenterX = (containerRect.width / 2) - (targetRect.width / 2);
  const targetCenterY = (containerRect.height / 2) - (targetRect.height / 2); // Remove incorrect adjustment
  
  // Store original position for unfocus
  if (!targetBin.dataset.originalTransform) {
      targetBin.dataset.originalTransform = targetBin.style.transform || '';
      targetBin.dataset.originalOpacity = targetBin.style.opacity || '';
  }

  const tl = anime.timeline({
    easing: 'easeInOutExpo', // Base easing
    duration: 800 // Slightly longer duration for smoother feel
  });

  // 1. Animar salida de los otros cestos (o del previamente enfocado)
  let exitAnimationConfig = {
      targets: [], // Defined below
      scale: 0.3, // Shrink more
      opacity: 0,
      rotate: (el, i) => { 
          const elType = el.dataset.type;
          const typeIndex = appState.binOrder.indexOf(type);
          const elIndex = appState.binOrder.indexOf(elType);
          return elIndex < typeIndex ? -65 : 65; // Rotate further based on position
      },
      skewX: (el, i) => { 
          const elType = el.dataset.type;
          const typeIndex = appState.binOrder.indexOf(type);
          const elIndex = appState.binOrder.indexOf(elType);
          return elIndex < typeIndex ? -20 : 20; // More skew
      },
      // Use translateX relative to viewport width for more consistent exit
      translateX: (el, i) => { 
          const elType = el.dataset.type;
          const typeIndex = appState.binOrder.indexOf(type);
          const elIndex = appState.binOrder.indexOf(elType);
          return elIndex < typeIndex ? '-100vw' : '100vw'; // Move off screen
      },
      easing: 'easeInCirc', // Sharper exit
      duration: 600,
      delay: anime.stagger(60),
      complete: (anim) => {
          anim.animatables.forEach(a => {
              const el = a.target;
              const elType = el.dataset.type;
              const typeIndex = appState.binOrder.indexOf(type);
              const elIndex = appState.binOrder.indexOf(elType);
              el.classList.add(elIndex < typeIndex ? 'hidden-left' : 'hidden-right');
              // Ensure position is reset if it was absolute (relevant for unfocus)
              el.style.position = ''; 
              el.style.left = '';
              el.style.top = '';
          });
      }
  };

  if (previouslyFocused && previouslyFocused !== type) {
      const prevBin = elements.fullscreenView.querySelector(`.fullscreen-bin[data-type="${previouslyFocused}"]`);
      if (prevBin) {
          exitAnimationConfig.targets = prevBin;
          // Animate previous bin out based on the direction the new one is coming from
          exitAnimationConfig.translateX = direction === 'from-right' ? '-100vw' : '100vw';
          exitAnimationConfig.rotate = direction === 'from-right' ? -65 : 65;
          exitAnimationConfig.skewX = direction === 'from-right' ? -20 : 20;
          tl.add(exitAnimationConfig);
      }
  } else {
      // If coming from general view, animate all others out
      exitAnimationConfig.targets = otherBins;
      tl.add(exitAnimationConfig);
  }

  // 2. Preparar y animar entrada del cesto enfocado al CENTRO
  targetBin.classList.remove('hidden-left', 'hidden-right');
  targetBin.classList.add('focused');
  
  // Set position absolute BEFORE animating position properties
  targetBin.style.position = 'absolute'; 
  
  // Get initial position for animation start (relative to container)
  // Reset temporary inline styles before getting offset (important for navigation)
  if (direction !== 'none') {
      // Force removal of properties potentially set by previous animations or hidden states
      targetBin.style.position = ''; // Ensure it's not absolute when calculating offset
      targetBin.style.left = '';
      targetBin.style.top = '';
      targetBin.style.transform = ''; // Clear potential interfering transforms
      targetBin.style.opacity = ''; // Reset opacity too
  }
  const initialLeft = targetBin.offsetLeft;
  const initialTop = targetBin.offsetTop;

  tl.add({
    targets: targetBin,
    // Animate left/top for centering
    left: [initialLeft + 'px', targetCenterX + 'px'], // Animate from current pos to center X
    top: [initialTop + 'px', targetCenterY + 'px'],   // Animate from current pos to center Y
    // Override translateX/Y used for exit/entry positioning
    translateX: ['0%', '0%'], // Ensure no lingering translateX 
    translateY: ['0%', '0%'], // Ensure no lingering translateY
    scale: [direction !== 'none' ? 0.6 : 1, 1.45], // Start smaller if navigating, end larger
    opacity: [direction !== 'none' ? 0 : 1, 1],
    rotate: [direction === 'from-right' ? 45 : (direction === 'from-left' ? -45 : 0), 0],
    skewX: [direction === 'from-right' ? 15 : (direction === 'from-left' ? -15 : 0), 0],
    easing: 'easeOutElastic(1.1, .6)', // More elastic entry
    duration: 900 // Longer entry animation
  }, previouslyFocused ? '-=450' : '-=500'); // Adjust overlap timing

  // 3. Animar entrada de las flechas 
  if (!elements.prevBinBtn.style.opacity || parseFloat(elements.prevBinBtn.style.opacity) === 0) {
      tl.add({
          targets: [elements.prevBinBtn, elements.nextBinBtn],
          opacity: [0, 0.8],
          scale: [0.5, 1],
          delay: anime.stagger(100)
      }, '-=600'); // Overlap more with bin animation
   }
}

// Volver a la vista general de todos los cestos
function unfocusAllBins() {
  if (!appState.focusedBinType) return; // Ya está desenfocado

  const currentlyFocusedBin = elements.fullscreenView.querySelector(`.fullscreen-bin[data-type="${appState.focusedBinType}"]`);
  if (!currentlyFocusedBin) {
      appState.focusedBinType = null;
      elements.fullscreenView.classList.remove('focused');
      return; // No bin found to unfocus
  }
  
  // Store original position details from dataset IF they exist
  const originalTransform = currentlyFocusedBin.dataset.originalTransform || '';
  const originalOpacity = currentlyFocusedBin.dataset.originalOpacity || '';
  delete currentlyFocusedBin.dataset.originalTransform;
  delete currentlyFocusedBin.dataset.originalOpacity;

  appState.focusedBinType = null;
  elements.fullscreenView.classList.remove('focused');

  const tl = anime.timeline({
    easing: 'easeInOutExpo',
    duration: 700 // Slightly longer duration
  });

  // 1. Animar salida del cesto enfocado y flechas
  tl.add({
      targets: [elements.prevBinBtn, elements.nextBinBtn],
      opacity: [0.8, 0],
      scale: [1, 0.5],
      pointerEvents: 'none',
      duration: 400
    })
    .add({
      targets: currentlyFocusedBin,
      // Animate transform properties back to default
      scale: [1.45, 1], 
      opacity: [1, 1], 
      rotate: 0,
      skewX: 0,
      // REMOVE left/top animation - let flexbox handle repositioning after reset
      // left: [currentlyFocusedBin.style.left, '0px'], 
      // top: [currentlyFocusedBin.style.top, '0px'],   
      translateX: '0%', // Ensure transform is cleared visually during animation
      translateY: '0%',
      easing: 'easeOutCirc', 
      duration: 650, 
      complete: () => { 
          currentlyFocusedBin.classList.remove('focused'); 
          // Reset all potentially interfering inline styles forcefully
          currentlyFocusedBin.style.position = '';
          currentlyFocusedBin.style.left = '';
          currentlyFocusedBin.style.top = '';
          currentlyFocusedBin.style.transform = ''; // Clear transform completely 
          currentlyFocusedBin.style.opacity = ''; // Clear opacity 
      }
    }, '-=300'); // Overlap slightly with arrows disappearing

  // 2. Animar entrada de todos los demás cestos
  const binsToUnhide = elements.fullscreenView.querySelectorAll('.fullscreen-bin.hidden-left, .fullscreen-bin.hidden-right');
  binsToUnhide.forEach(bin => {
      bin.classList.remove('hidden-left', 'hidden-right');
      // Reset styles potentially set by exit animation before starting entry
      bin.style.position = ''; // Ensure relative positioning restored
      bin.style.left = '';
      bin.style.top = '';
      bin.style.transform = ''; // Clear transform from hidden state
      bin.style.opacity = 0; // Start hidden before fade-in
  });
  
  tl.add({
      targets: binsToUnhide,
      scale: [0.6, 1], // Start slightly smaller
      opacity: [0, 1],
      translateX: ['0%', '0%'], // Ensure they end up in their flex positions
      rotate: [-15, 0], // Subtle rotation in
      // No skew needed for return?
      easing: 'easeOutElastic(1, .8)', // Elastic return
      delay: anime.stagger(100), // Stagger their return
      duration: 800
  }, '-=500'); // Overlap significantly with the focused one moving back
}

// Navegar entre cestos enfocados
function navigateBins(step) { // step = 1 (next) or -1 (prev)
  if (!appState.focusedBinType) return; // No hay nada enfocado para navegar

  const currentIndex = appState.binOrder.indexOf(appState.focusedBinType);
  let nextIndex = (currentIndex + step + appState.binOrder.length) % appState.binOrder.length;
  const nextType = appState.binOrder[nextIndex];
  
  focusOnBin(nextType, step === 1 ? 'from-right' : 'from-left');
}

// Abrir vista de pantalla completa
function openFullscreenFillView() {
  console.log('Opening fullscreen view...');
  // Asegurar que no esté en modo enfocado al abrir
  unfocusAllBins(); // Llama a esto para resetear si estaba enfocado
  elements.fullscreenView.classList.add('visible');
  elements.fullscreenBins.forEach(bin => {
      bin.classList.remove('focused', 'hidden-left', 'hidden-right');
      bin.style.transform = ''; // Reset transform potentially set by unfocus
      bin.style.opacity = ''; // Reset opacity
  });
  updateFullscreenFillView(appState.fillLevels); 

  const tl = anime.timeline({
    easing: 'easeOutExpo',
    duration: 750
  });

  tl
    .add({
      targets: elements.fullscreenView,
      opacity: [0, 1],
      duration: 500 
    })
    .add({
      targets: elements.fullscreenView.querySelector('h2'),
      translateY: [-20, 0],
      opacity: [0, 1]
    }, '-=300') 
    .add({
      targets: elements.closeFullscreenBtn,
      scale: [0.5, 1],
      opacity: [0, 1]
    }, '-=500') 
    .add({
        targets: '.fullscreen-bin', // Animar entrada inicial
        translateY: [50, 0],
        opacity: [0, 1],
        scale: [0.8, 1],
        delay: anime.stagger(100) 
    }, '-=500'); 

  startWaveAnimation();
}

// Cerrar vista de pantalla completa
function closeFullscreenFillView() {
  console.log('Closing fullscreen view...');
  stopWaveAnimation();
  // Asegurarse de quitar el foco antes de cerrar
  unfocusAllBins(); 

  const tl = anime.timeline({
    easing: 'easeInExpo', 
    duration: 500,
    // Añadir un pequeño delay para permitir que unfocusAllBins termine si se llamó justo antes
    // delay: appState.focusedBinType ? 100 : 0 
  });

  tl
    .add({
      // Animar salida de los bins visibles (estado general)
      targets: elements.fullscreenBinsContainer.querySelectorAll('.fullscreen-bin:not(.hidden-left):not(.hidden-right)'),
      translateY: [0, 50],
      opacity: [1, 0],
      scale: [1, 0.8],
      delay: anime.stagger(80, {direction: 'reverse'}) 
    })
    .add({
      targets: [elements.fullscreenView.querySelector('h2'), elements.closeFullscreenBtn],
      translateY: [0, -20],
      opacity: [1, 0],
    }, '-=300') 
    .add({
      targets: elements.fullscreenView,
      opacity: [1, 0],
      duration: 400,
      complete: function() {
        elements.fullscreenView.classList.remove('visible');
        elements.fullscreenView.classList.remove('focused'); // Doble check
        // Resetear estado visual y lógico
        appState.focusedBinType = null;
        elements.fullscreenBins.forEach(bin => {
            bin.classList.remove('focused', 'hidden-left', 'hidden-right');
            bin.style.transform = ''; // Reset styles
            bin.style.opacity = '';
        });
        // Resetear flechas
        elements.prevBinBtn.style.opacity = 0;
        elements.nextBinBtn.style.opacity = 0;
        elements.prevBinBtn.style.pointerEvents = 'none';
        elements.nextBinBtn.style.pointerEvents = 'none';
        
        // Resetear porcentajes
        Object.values(elements.fullscreenBinPercentages).forEach(el => el.textContent = '0%');
      }
    }, '-=200'); 
}

// --- Fin Fullscreen View Logic ---

// --- Intro Animation --- 
function runIntroAnimation(onCompleteCallback) { // Accept a callback
    const overlay = document.getElementById('entry-animation-overlay');
    if (!overlay) {
        console.warn('Entry animation overlay not found. Skipping intro.');
        runEntryAnimations(); // Run main animations directly if overlay is missing
        if (onCompleteCallback) onCompleteCallback(); // Call callback immediately
        return;
    }

    const tl = anime.timeline({
        easing: 'easeOutExpo', // A nice default easing
        duration: 1000, // Default duration for steps
        complete: function() {
            // Animation complete: Fade out overlay and run main animations
            anime({
                targets: overlay,
                opacity: [1, 0],
                duration: 500,
                easing: 'easeOutQuad',
                complete: function() {
                    overlay.style.pointerEvents = 'none';
                    overlay.style.display = 'none'; // Hide completely
                    runEntryAnimations(); // Start the main page animations
                    if (onCompleteCallback) onCompleteCallback(); // Execute the callback
                }
            });
        }
    });

    // Staggered animation for SVG parts
    tl.add({
        targets: '#entry-cesto-svg .entry-part',
        opacity: [0, 1],
        scale: [0.5, 1],
        translateY: ['+=50', 0], // Adjust based on CSS initial positions
        delay: anime.stagger(150)
    })
    // Animate wave fill specifically (scaleY)
    .add({
        targets: '#entry-wave-group',
        scaleY: [0, 1],
        opacity: [0, 1], // Ensure opacity is animated too
        easing: 'easeOutElastic(1, .6)'
    }, '-=800') // Overlap slightly
    // Animate icon group slightly differently (e.g., rotate)
    .add({
        targets: '#entry-icon-group',
        scale: [0, 1.1, 1],
        rotate: [-45, 0],
        opacity: [0, 1],
    }, '-=900')
    // Animate text
    .add({
        targets: '#entry-title, #entry-subtitle',
        opacity: [0, 1],
        translateX: [-50, 0],
        delay: anime.stagger(100, {start: 200}) // Stagger title and subtitle
    }, '-=1000') // Start text animation earlier
    // Optional: Animate decorative lines
    .add({
        targets: '.entry-line',
        opacity: [0, 0.1],
        duration: 1500,
    }, 0); // Start animating lines early
}
// --- End Intro Animation ---

// Inicializador
function init() {
  console.log('Inicializando aplicación...');
  
  // Prepare scroll animations but don't start observing yet
  const { observer, sections } = setupScrollAnimations();
  
  // Run Intro Animation FIRST and pass a callback to start observing
  runIntroAnimation(() => {
      // This code runs AFTER the intro animation AND overlay fade-out are complete
      console.log('Intro complete. Starting section observation.');
      if (observer && sections.length > 0) {
          sections.forEach(section => {
              observer.observe(section);
          });
      } else {
          console.log('No observer or sections found to observe.');
      }
  });
  
  // Ocultar pantalla de carga después de un momento <-- Lógica eliminada
  /* setTimeout(() => {
    anime({
      targets: elements.loading, // elements.loading ya no existe
      opacity: [1, 0],
      duration: 800,
      easing: 'easeOutQuad',
      complete: function() {
        // elements.loading.style.display = 'none'; // elements.loading ya no existe
        runEntryAnimations(); // <-- MOVED to intro animation complete callback
      }
    });
  }, 1500); */
  
  // Ejecutar animaciones de entrada directamente <-- REMOVED, now called by intro complete
  // runEntryAnimations();

  // Asignar eventos
  elements.themeToggle.addEventListener('click', toggleTheme);
  elements.closeFullscreenBtn.addEventListener('click', closeFullscreenFillView);
  elements.prevBinBtn.addEventListener('click', () => navigateBins(-1));
  elements.nextBinBtn.addEventListener('click', () => navigateBins(1));

  // Listeners para enfocar cestos
  elements.fullscreenBins.forEach(bin => {
    bin.addEventListener('click', () => {
      const type = bin.dataset.type;
      if (appState.focusedBinType === type) {
        // Si se hace clic en el ya enfocado, volver a la vista general
        unfocusAllBins();
      } else if (!appState.focusedBinType) {
         // Si no hay ninguno enfocado, enfocar el clicado
         focusOnBin(type);
      } 
      // Si ya hay uno enfocado y se clicka OTRO, las flechas se encargan
    });
  });

  // Listener para abrir la vista fullscreen
  const fillLevelsSection = document.getElementById('fill-levels');
  if (fillLevelsSection) {
    fillLevelsSection.addEventListener('click', openFullscreenFillView);
    // Opcional: Añadir un estilo cursor pointer a la sección en CSS
    fillLevelsSection.style.cursor = 'pointer'; 
  }
  
  // Añadir efectos hover
  addHoverEffect('.stat-item', { scale: 1.08 });
  addHoverEffect('.bin', { scale: 1.05, translateY: -5 });
  addHoverEffect('.dashboard-section', { translateY: -8 });

  // Iniciar conexión WebSocket
  try {
    initSocketConnection();
  } catch (error) {
    console.error('Error al iniciar WebSocket:', error);
    updateSystemStatus('error', 'Error al iniciar WebSocket');
    
    // Usar datos simulados si no hay conexión
    loadMockData();
  }
  
  // Configurar intervalo de actualización
  setInterval(() => {
    if (socket && socket.connected) {
      socket.emit('getData');
    } else {
      // Si no hay conexión, actualizar con datos simulados para demostración
      loadMockData();
    }
  }, UPDATE_INTERVAL);
}

// Iniciar la aplicación cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  init();
  // setupScrollAnimations(); // Call the scroll setup <-- MOVED inside init structure
});