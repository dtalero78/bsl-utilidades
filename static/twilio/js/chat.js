// ============================================================================
// Twilio-BSL WhatsApp Chat Interface - JavaScript
// Real-time chat functionality with Wix integration
// ============================================================================

// Global state
let conversaciones = {};
let conversacionActual = null;
let autoRefreshInterval = null;
let isLoadingMessages = false;
let lastMessageCount = 0;
let notificationSound = null;
let audioPermitido = false; // Flag para saber si el usuario ya interactuó
let unreadMessages = 0; // Contador de mensajes no leídos
let originalTitle = 'Twilio-BSL WhatsApp Chat'; // Título original
let titleBlinkInterval = null; // Intervalo para parpadeo del título
let eventSource = null; // SSE connection
let sseConnected = false; // Estado de conexión SSE
let sseReconnectAttempts = 0; // Intentos de reconexión
const MAX_SSE_RECONNECT_ATTEMPTS = 5; // Máximo de intentos antes de usar fallback

// API Configuration
const API_BASE = window.API_BASE || window.location.origin;

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Twilio-BSL Chat initialized');

    // Inicializar sonido de notificación
    inicializarSonidoNotificacion();

    // Mostrar banner de permisos de audio
    const audioBanner = document.getElementById('audioBanner');
    if (audioBanner) {
        // Mostrar banner después de 2 segundos
        setTimeout(() => {
            if (!audioPermitido) {
                audioBanner.style.display = 'block';
            }
        }, 2000);
    }

    // Habilitar audio después de la primera interacción del usuario
    const habilitarAudio = () => {
        if (!audioPermitido) {
            audioPermitido = true;
            console.log('✅ Audio habilitado después de interacción del usuario');

            // Ocultar banner
            if (audioBanner) {
                audioBanner.style.display = 'none';
            }

            // Reproducir el sonido de notificación como prueba
            if (notificationSound && notificationSound.play) {
                console.log('🎵 Reproduciendo sonido de prueba...');
                notificationSound.play().then(() => {
                    console.log('🎵 Audio context desbloqueado - sonido de prueba exitoso');
                }).catch((e) => {
                    console.error('❌ Error al reproducir sonido de prueba:', e);
                });
            }
        }
    };

    // Escuchar múltiples eventos de interacción
    document.addEventListener('click', habilitarAudio, { once: false });
    document.addEventListener('keydown', habilitarAudio, { once: false });
    document.addEventListener('touchstart', habilitarAudio, { once: false });

    // Banner clickeable para habilitar audio
    if (audioBanner) {
        audioBanner.addEventListener('click', habilitarAudio);
    }

    // Cargar conversaciones
    cargarConversaciones();

    // Conectar SSE para notificaciones en tiempo real
    console.log('🔌 Iniciando conexión SSE...');
    conectarSSE();

    // Fallback polling cada 60 segundos (solo si SSE falla completamente)
    console.log('⏰ Configurando fallback polling cada 60 segundos...');
    autoRefreshInterval = setInterval(() => {
        // Solo hacer polling si SSE no está conectado
        if (!sseConnected) {
            console.log(`⏰ Fallback polling ejecutándose... (SSE desconectado)`);
            if (conversacionActual) {
                console.log('🔄 Actualizando conversación actual...');
                actualizarConversacionActualSilencioso();
            } else {
                console.log('📋 Actualizando lista de conversaciones...');
                cargarConversacionesSilencioso();
            }
        }
    }, 60000); // 60 segundos = fallback solo si SSE falla

    // Auto-expand textarea
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }

    // Page Visibility API - Detectar cuando el usuario vuelve a la pestaña
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            console.log('👁️ Usuario regresó a la pestaña - Actualizando inmediatamente...');

            // Detener parpadeo del título
            stopTitleBlink();

            // Resetear contador de no leídos
            unreadMessages = 0;

            // Actualizar inmediatamente
            if (conversacionActual) {
                actualizarConversacionActualSilencioso();
            } else {
                cargarConversacionesSilencioso();
            }
        } else {
            console.log('👁️ Usuario salió de la pestaña - Continuando en segundo plano...');
        }
    });

    // Solicitar permisos de notificación del navegador
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission().then(permission => {
            console.log('🔔 Permiso de notificaciones:', permission);
        });
    }
});

// ============================================================================
// TITLE NOTIFICATION (like WhatsApp Web)
// ============================================================================

function startTitleBlink(messagePreview) {
    // Si ya está parpadeando, no iniciar otro
    if (titleBlinkInterval) return;

    let showingNew = true;
    titleBlinkInterval = setInterval(() => {
        if (showingNew) {
            document.title = `(${unreadMessages}) Nuevo mensaje - ${messagePreview.substring(0, 30)}`;
        } else {
            document.title = originalTitle;
        }
        showingNew = !showingNew;
    }, 1000); // Parpadear cada segundo
}

function stopTitleBlink() {
    if (titleBlinkInterval) {
        clearInterval(titleBlinkInterval);
        titleBlinkInterval = null;
    }
    document.title = originalTitle;
}

// ============================================================================
// NOTIFICATION SOUND
// ============================================================================

function inicializarSonidoNotificacion() {
    // Usar Web Audio API directamente (más confiable que CDN)
    try {
        notificationSound = crearSonidoWebAudio();
        console.log('Sonido de notificación inicializado con Web Audio API');
    } catch (e) {
        console.warn('No se pudo inicializar el sonido de notificación:', e);
    }
}

function crearSonidoWebAudio() {
    // Crear un sonido de notificación tipo WhatsApp con Web Audio API
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        return {
            play: function() {
                return new Promise((resolve, reject) => {
                    try {
                        // Primer tono (más agudo)
                        const osc1 = audioContext.createOscillator();
                        const gain1 = audioContext.createGain();

                        osc1.connect(gain1);
                        gain1.connect(audioContext.destination);

                        osc1.frequency.value = 800; // Fa
                        osc1.type = 'sine';

                        gain1.gain.setValueAtTime(0, audioContext.currentTime);
                        gain1.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.02);
                        gain1.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.15);

                        osc1.start(audioContext.currentTime);
                        osc1.stop(audioContext.currentTime + 0.15);

                        // Segundo tono (más grave) - como WhatsApp
                        const osc2 = audioContext.createOscillator();
                        const gain2 = audioContext.createGain();

                        osc2.connect(gain2);
                        gain2.connect(audioContext.destination);

                        osc2.frequency.value = 600; // Re
                        osc2.type = 'sine';

                        gain2.gain.setValueAtTime(0, audioContext.currentTime + 0.1);
                        gain2.gain.linearRampToValueAtTime(0.3, audioContext.currentTime + 0.12);
                        gain2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);

                        osc2.start(audioContext.currentTime + 0.1);
                        osc2.stop(audioContext.currentTime + 0.3);

                        // Resolver después de que termine el sonido
                        setTimeout(() => resolve(), 350);
                    } catch (e) {
                        reject(e);
                    }
                });
            },
            currentTime: undefined, // Para compatibilidad con Audio()
            volume: 0.5 // Para compatibilidad
        };
    } catch (e) {
        console.warn('Web Audio API no disponible:', e);
        return null;
    }
}

function reproducirSonidoNotificacion() {
    if (!notificationSound) {
        console.warn('⚠️ notificationSound no está inicializado');
        return;
    }

    if (!audioPermitido) {
        console.warn('⚠️ Audio no permitido aún. El usuario debe interactuar primero con la página.');
        return;
    }

    try {
        console.log('🔔 Reproduciendo sonido de notificación...');

        notificationSound.play().then(() => {
            console.log('✅ Sonido reproducido exitosamente');
        }).catch(e => {
            console.error('❌ Error al reproducir sonido:', e);
        });
    } catch (e) {
        console.error('❌ Error al reproducir sonido:', e);
    }
}

// ============================================================================
// SSE (Server-Sent Events) Real-Time Notifications
// ============================================================================

function conectarSSE() {
    try {
        console.log('🔌 Conectando a SSE endpoint...');

        // Cerrar conexión anterior si existe
        if (eventSource) {
            eventSource.close();
        }

        // Crear nueva conexión EventSource
        eventSource = new EventSource(`${API_BASE}/events`);

        eventSource.onopen = function() {
            console.log('✅ SSE conectado exitosamente');
            sseConnected = true;
            sseReconnectAttempts = 0;
        };

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log('📨 SSE mensaje recibido:', data);

                if (data.event === 'connected') {
                    console.log(`✅ SSE suscriptor ID: ${data.subscriber_id}`);
                } else if (data.event === 'keepalive') {
                    console.log('💓 SSE keepalive recibido');
                }
            } catch (e) {
                console.error('❌ Error procesando mensaje SSE:', e);
            }
        };

        // Escuchar eventos personalizados
        eventSource.addEventListener('new_message', function(event) {
            try {
                const messageData = JSON.parse(event.data);
                console.log('📬 Nuevo mensaje SSE:', messageData);

                // Manejar nuevo mensaje
                manejarNuevoMensajeSSE(messageData);
            } catch (e) {
                console.error('❌ Error procesando new_message:', e);
            }
        });

        eventSource.onerror = function(error) {
            console.error('❌ Error SSE:', error);
            sseConnected = false;

            // Intentar reconectar con backoff exponencial
            sseReconnectAttempts++;
            if (sseReconnectAttempts < MAX_SSE_RECONNECT_ATTEMPTS) {
                const delay = Math.min(1000 * Math.pow(2, sseReconnectAttempts), 30000);
                console.log(`🔄 Reintentando SSE en ${delay}ms (intento ${sseReconnectAttempts}/${MAX_SSE_RECONNECT_ATTEMPTS})`);
                setTimeout(conectarSSE, delay);
            } else {
                console.log('⚠️ Máximo de reintentos SSE alcanzado. Usando fallback polling.');
                eventSource.close();
            }
        };

    } catch (error) {
        console.error('❌ Error fatal conectando SSE:', error);
        sseConnected = false;
    }
}

function manejarNuevoMensajeSSE(messageData) {
    console.log('🔔 Procesando nuevo mensaje desde SSE:', messageData);

    // Si estamos viendo esta conversación, agregar el mensaje directamente
    if (conversacionActual && conversacionActual === messageData.numero) {
        console.log('👁️ Mensaje es para la conversación actual - Agregando mensaje directamente...');
        agregarMensajeAlChat(messageData);
    } else {
        // Actualizar solo el preview en la lista de conversaciones
        console.log('📋 Actualizando preview de conversación...');
        actualizarPreviewConversacion(messageData);
    }

    // Reproducir sonido de notificación
    if (audioPermitido) {
        console.log('🔔 Reproduciendo sonido de notificación...');
        reproducirSonidoNotificacion();
    }

    // Incrementar contador de mensajes no leídos
    unreadMessages++;

    // Si el usuario NO está en la pestaña, iniciar parpadeo del título
    if (document.hidden) {
        console.log('📋 Usuario en otra pestaña - Iniciando parpadeo del título');
        startTitleBlink(messageData.body);
    }

    // Mostrar notificación del navegador
    mostrarNotificacionNavegador('Nuevo mensaje de WhatsApp', messageData.body || '(mensaje)');
}

function agregarMensajeAlChat(messageData) {
    /**
     * Agrega un mensaje nuevo directamente al DOM sin recargar toda la conversación
     */
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) return;

    // Crear objeto de mensaje compatible con renderizarMensaje()
    const nuevoMensaje = {
        sid: messageData.message_sid,
        direction: 'inbound',
        body: messageData.body,
        timestamp: messageData.timestamp,
        status: 'received'
    };

    // Agregar el mensaje al DOM
    messagesContainer.innerHTML += renderizarMensaje(nuevoMensaje);

    // Incrementar contador de mensajes
    lastMessageCount++;

    // Auto-scroll al fondo
    scrollToBottom();

    console.log('✅ Mensaje agregado directamente al chat');
}

function actualizarPreviewConversacion(messageData) {
    /**
     * Actualiza solo el preview de la conversación en la lista sin recargar todo
     */
    const numero = messageData.numero;

    // Buscar el item de conversación en el DOM
    const conversationItems = document.querySelectorAll('.conversation-item');
    let conversationItem = null;

    for (const item of conversationItems) {
        if (item.onclick && item.onclick.toString().includes(numero)) {
            conversationItem = item;
            break;
        }
    }

    if (conversationItem) {
        // Actualizar el preview y timestamp
        const previewElement = conversationItem.querySelector('.conversation-preview');
        const timeElement = conversationItem.querySelector('.conversation-time');

        if (previewElement) {
            previewElement.textContent = truncateText(messageData.body || '(media)', 50);
        }

        if (timeElement) {
            timeElement.textContent = formatTime(messageData.timestamp);
        }

        // Mover la conversación al tope de la lista
        const conversationsList = document.getElementById('conversationsList');
        if (conversationsList) {
            conversationsList.insertBefore(conversationItem, conversationsList.firstChild);
        }

        console.log('✅ Preview de conversación actualizado');
    } else {
        // Si no existe la conversación, recargar la lista completa (nuevo contacto)
        console.log('⚠️ Conversación no encontrada - Recargando lista...');
        cargarConversacionesSilencioso();
    }
}

// ============================================================================
// CONVERSATIONS LOADING
// ============================================================================

async function cargarConversaciones() {
    try {
        console.log('Loading conversations...');
        const response = await fetch(`${API_BASE}/api/conversaciones`);
        const data = await response.json();

        if (data.success) {
            conversaciones = data.conversaciones;
            renderizarConversaciones();
            console.log(`Loaded ${data.total} conversations`);
        } else {
            console.error('Error loading conversations:', data.error);
            mostrarError('Error al cargar conversaciones');
        }
    } catch (error) {
        console.error('Error fetching conversations:', error);
        mostrarError('Error de conexión');
    }
}

function renderizarConversaciones() {
    const listContainer = document.getElementById('conversationsList');

    if (Object.keys(conversaciones).length === 0) {
        listContainer.innerHTML = `
            <div class="loading">
                <i class="fab fa-whatsapp"></i>
                <p>No hay conversaciones disponibles</p>
            </div>
        `;
        return;
    }

    let html = '';

    // Sort conversations by last message time
    const sortedConversaciones = Object.entries(conversaciones).sort((a, b) => {
        const lastMsgA = getLastMessageTime(a[1]);
        const lastMsgB = getLastMessageTime(b[1]);
        return new Date(lastMsgB) - new Date(lastMsgA);
    });

    for (const [numero, conversacion] of sortedConversaciones) {
        const lastMessage = getLastMessage(conversacion);
        const nombre = conversacion.nombre || conversacion.wix_data?.nombre || formatPhoneNumber(numero);
        const preview = lastMessage ? truncateText(lastMessage.body || lastMessage.mensaje, 50) : 'Sin mensajes';
        const time = lastMessage ? formatTime(lastMessage.date_sent || lastMessage.timestamp) : '';
        const initial = nombre.charAt(0).toUpperCase();
        const isActive = conversacionActual === numero ? 'active' : '';

        html += `
            <div class="conversation-item ${isActive}" onclick="abrirConversacion('${numero}')">
                <div class="conversation-avatar">
                    <i class="fas fa-user"></i>
                </div>
                <div class="conversation-info">
                    <div class="conversation-header">
                        <span class="conversation-name">${nombre}</span>
                        <span class="conversation-time">${time}</span>
                    </div>
                    <div class="conversation-preview">${preview}</div>
                </div>
            </div>
        `;
    }

    listContainer.innerHTML = html;
}

// ============================================================================
// CONVERSATION HANDLING
// ============================================================================

async function abrirConversacion(numero) {
    try {
        conversacionActual = numero;

        // Update UI
        updateActiveConversation(numero);

        // Load conversation details
        const response = await fetch(`${API_BASE}/api/conversacion/${numero}`);
        const data = await response.json();

        if (data.success) {
            renderizarChat(numero, data);
            mostrarInputArea();

            // Inicializar contador de mensajes para detectar nuevos
            const allMessages = mergeMessages(data.twilio_messages || [], data.wix_data?.mensajes || []);
            lastMessageCount = allMessages.length;
            console.log(`Conversación cargada: ${lastMessageCount} mensajes`);
        } else {
            console.error('Error loading conversation:', data.error);
            mostrarError('Error al cargar conversación');
        }
    } catch (error) {
        console.error('Error opening conversation:', error);
        mostrarError('Error de conexión');
    }
}

function renderizarChat(numero, data) {
    const chatHeader = document.getElementById('chatHeader');
    const messagesContainer = document.getElementById('messagesContainer');

    // Update header
    const nombre = data.wix_data?.nombre || formatPhoneNumber(numero);
    const stopBot = data.wix_data?.stopBot ? '(Bot detenido)' : '(Bot activo)';

    chatHeader.innerHTML = `
        <div class="chat-contact" onclick="toggleContactInfo()">
            <div class="chat-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="chat-contact-info">
                <h3>${nombre}</h3>
                <p>${formatPhoneNumber(numero)} ${stopBot}</p>
            </div>
        </div>
        <div class="chat-actions">
            <button onclick="actualizarConversacionActual()" title="Actualizar">
                <i class="fas fa-sync-alt"></i>
            </button>
            <button onclick="toggleContactInfo()" title="Información">
                <i class="fas fa-info-circle"></i>
            </button>
        </div>
    `;

    // Merge and sort messages from both sources
    const allMessages = mergeMessages(data.twilio_messages, data.wix_data?.mensajes || []);

    // Render messages
    let messagesHtml = '';
    allMessages.forEach(msg => {
        messagesHtml += renderizarMensaje(msg);
    });

    messagesContainer.innerHTML = messagesHtml;

    // Scroll to bottom
    scrollToBottom();
}

function mergeMessages(twilioMessages, wixMessages = []) {
    // SOLO Twilio - sin Wix
    const merged = [];

    // Add Twilio messages
    twilioMessages.forEach(msg => {
        merged.push({
            sid: msg.sid,
            type: 'twilio',
            direction: msg.direction,
            body: msg.body,
            timestamp: msg.date_sent,
            status: msg.status
        });
    });

    // Sort by timestamp
    merged.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    return merged;
}

function renderizarMensaje(msg) {
    const direction = msg.direction === 'outbound' ? 'outbound' : 'inbound';
    const time = formatTime(msg.timestamp);
    const statusIcon = getStatusIcon(msg.status);

    return `
        <div class="message ${direction}">
            <div class="message-bubble">
                <div class="message-text">${escapeHtml(msg.body)}</div>
                <div class="message-footer">
                    <span class="message-time">${time}</span>
                    ${direction === 'outbound' ? `<span class="message-status">${statusIcon}</span>` : ''}
                </div>
            </div>
        </div>
    `;
}

// ============================================================================
// MESSAGE SENDING
// ============================================================================

async function enviarMensaje() {
    if (!conversacionActual) {
        mostrarError('Selecciona una conversación primero');
        return;
    }

    const messageInput = document.getElementById('messageInput');
    const mensaje = messageInput.value.trim();

    if (!mensaje) {
        return;
    }

    try {
        // Disable send button
        const btnSend = document.querySelector('.btn-send');
        btnSend.disabled = true;

        // Format phone number for Twilio
        const toNumber = conversacionActual.startsWith('+') ? conversacionActual : `+${conversacionActual}`;

        const response = await fetch(`${API_BASE}/api/enviar-mensaje`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to: toNumber,
                message: mensaje
            })
        });

        const data = await response.json();

        if (data.success) {
            // Clear input
            messageInput.value = '';
            messageInput.style.height = 'auto';

            // Add message to UI immediately
            const messagesContainer = document.getElementById('messagesContainer');
            messagesContainer.innerHTML += renderizarMensaje({
                direction: 'outbound',
                body: mensaje,
                timestamp: new Date().toISOString(),
                status: 'sent'
            });

            scrollToBottom();

            // Refresh conversation after a short delay
            setTimeout(() => {
                actualizarConversacionActual();
            }, 2000);
        } else {
            console.error('Error sending message:', data.error);
            mostrarError('Error al enviar mensaje');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        mostrarError('Error de conexión');
    } finally {
        // Re-enable send button
        const btnSend = document.querySelector('.btn-send');
        btnSend.disabled = false;
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        enviarMensaje();
    }
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function actualizarConversacionActual() {
    if (conversacionActual) {
        abrirConversacion(conversacionActual);
    }
}

async function actualizarConversacionActualSilencioso() {
    console.log(`🔧 actualizarConversacionActualSilencioso llamada. conversacionActual=${conversacionActual}, isLoadingMessages=${isLoadingMessages}`);

    if (!conversacionActual || isLoadingMessages) {
        console.log('⚠️ No se actualizará: conversacionActual vacía o ya cargando');
        return;
    }

    try {
        isLoadingMessages = true;
        console.log(`📡 Fetching conversación ${conversacionActual}...`);
        const response = await fetch(`${API_BASE}/api/conversacion/${conversacionActual}`);
        const data = await response.json();
        console.log(`📡 Respuesta recibida:`, data.success ? 'success' : 'error');

        if (data.success) {
            const messagesContainer = document.getElementById('messagesContainer');
            const currentScrollHeight = messagesContainer.scrollHeight;
            const currentScrollTop = messagesContainer.scrollTop;
            const isAtBottom = (messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight) < 100;

            // Merge and render messages
            const allMessages = mergeMessages(data.twilio_messages || [], data.wix_data?.mensajes || []);

            console.log(`🔍 Verificando mensajes: lastCount=${lastMessageCount}, currentCount=${allMessages.length}`);

            // Verificar si hay mensajes nuevos ENTRANTES (no salientes)
            if (allMessages.length > lastMessageCount) {
                const newMessagesCount = allMessages.length - lastMessageCount;
                console.log(`📨 ${newMessagesCount} mensaje(s) nuevo(s) detectado(s)`);

                // Verificar si el último mensaje es ENTRANTE (inbound)
                const lastMessage = allMessages[allMessages.length - 1];
                console.log(`📩 Último mensaje:`, {
                    direction: lastMessage.direction,
                    body: lastMessage.body ? lastMessage.body.substring(0, 50) : 'N/A'
                });

                if (lastMessage.direction === 'inbound') {
                    console.log(`🔔 Es un mensaje ENTRANTE - Reproduciendo sonido...`);

                    // Incrementar contador de no leídos
                    unreadMessages++;

                    // Reproducir sonido (siempre, incluso en background)
                    reproducirSonidoNotificacion();

                    // Si el usuario NO está en la pestaña, iniciar parpadeo del título
                    if (document.hidden) {
                        console.log('📋 Usuario en otra pestaña - Iniciando parpadeo del título');
                        startTitleBlink(lastMessage.body);
                    }

                    // Mostrar notificación del navegador (especialmente útil cuando estás en otra pestaña)
                    mostrarNotificacionNavegador('Nuevo mensaje', lastMessage.body);
                } else {
                    console.log(`📤 Es un mensaje SALIENTE - No reproducir sonido`);
                }

                // Solo agregar los mensajes NUEVOS (no re-renderizar todo)
                console.log(`➕ Agregando solo ${newMessagesCount} mensaje(s) nuevo(s) al DOM`);
                for (let i = lastMessageCount; i < allMessages.length; i++) {
                    messagesContainer.innerHTML += renderizarMensaje(allMessages[i]);
                }

                lastMessageCount = allMessages.length;

                // Auto-scroll si estaba al fondo
                if (isAtBottom) {
                    scrollToBottom();
                }
            } else {
                console.log(`✓ No hay mensajes nuevos (${allMessages.length})`);
                // No hacer nada, no re-renderizar
            }
        }
    } catch (error) {
        console.error('Error en actualización silenciosa:', error);
    } finally {
        isLoadingMessages = false;
    }
}

async function cargarConversacionesSilencioso() {
    try {
        const response = await fetch(`${API_BASE}/api/conversaciones`);
        const data = await response.json();

        if (data.success) {
            conversaciones = data.conversaciones;
            renderizarConversaciones();
        }
    } catch (error) {
        console.error('Error cargando conversaciones:', error);
    }
}

function mostrarNotificacionNavegador(titulo, mensaje) {
    if (!('Notification' in window)) return;

    if (Notification.permission === 'granted') {
        new Notification(titulo, {
            body: mensaje.substring(0, 100),
            icon: '/static/images/whatsapp-icon.png',
            tag: 'twilio-bsl-notification'
        });
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(titulo, {
                    body: mensaje.substring(0, 100)
                });
            }
        });
    }
}

function mostrarInputArea() {
    const inputArea = document.getElementById('messageInputArea');
    inputArea.style.display = 'block';
}

function updateActiveConversation(numero) {
    const items = document.querySelectorAll('.conversation-item');
    items.forEach(item => {
        item.classList.remove('active');
    });

    const activeItem = Array.from(items).find(item =>
        item.onclick.toString().includes(numero)
    );
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

function scrollToBottom() {
    const container = document.getElementById('messagesContainer');
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 100);
}

function filtrarConversaciones() {
    const searchInput = document.getElementById('searchInput');
    const filter = searchInput.value.toLowerCase();
    const items = document.querySelectorAll('.conversation-item');

    items.forEach(item => {
        const nombre = item.querySelector('.conversation-name').textContent.toLowerCase();
        const numero = item.onclick.toString();

        if (nombre.includes(filter) || numero.includes(filter)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function toggleContactInfo() {
    const contactInfo = document.getElementById('contactInfo');
    if (contactInfo.style.display === 'none') {
        contactInfo.style.display = 'flex';
        // Load contact details
        if (conversacionActual && conversaciones[conversacionActual]) {
            renderContactInfo(conversaciones[conversacionActual]);
        }
    } else {
        contactInfo.style.display = 'none';
    }
}

function renderContactInfo(conversacion) {
    const contactDetails = document.getElementById('contactDetails');
    const wixData = conversacion.wix_data || {};

    contactDetails.innerHTML = `
        <div style="padding: 16px;">
            <h4>Detalles del Contacto</h4>
            <p><strong>Nombre:</strong> ${wixData.nombre || 'N/A'}</p>
            <p><strong>Teléfono:</strong> ${formatPhoneNumber(conversacion.numero)}</p>
            <p><strong>Bot:</strong> ${wixData.stopBot ? 'Detenido' : 'Activo'}</p>
            <p><strong>Observaciones:</strong> ${wixData.observaciones || 'Ninguna'}</p>
        </div>
    `;
}

function closeMediaModal() {
    document.getElementById('mediaModal').style.display = 'none';
}

function mostrarError(mensaje) {
    // Simple alert for now - can be replaced with toast notification
    alert(mensaje);
}

function formatPhoneNumber(numero) {
    // Format phone number for display
    numero = numero.replace('whatsapp:', '').replace('+', '');
    if (numero.length === 12 && numero.startsWith('57')) {
        return `+57 ${numero.substr(2, 3)} ${numero.substr(5, 3)} ${numero.substr(8, 4)}`;
    }
    return `+${numero}`;
}

function formatTime(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    // If today, show time
    if (diff < 86400000 && now.getDate() === date.getDate()) {
        return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    }

    // If yesterday
    if (diff < 172800000 && now.getDate() - date.getDate() === 1) {
        return 'Ayer';
    }

    // Otherwise show date
    return date.toLocaleDateString('es-CO', { day: '2-digit', month: '2-digit' });
}

function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function getStatusIcon(status) {
    switch (status) {
        case 'delivered':
        case 'sent':
            return '<i class="fas fa-check-double delivered"></i>';
        case 'read':
            return '<i class="fas fa-check-double read"></i>';
        default:
            return '<i class="fas fa-check"></i>';
    }
}

function getLastMessage(conversacion) {
    const twilioMessages = conversacion.twilio_messages || [];
    const wixMessages = conversacion.wix_data?.mensajes || [];

    const allMessages = [...twilioMessages, ...wixMessages];

    if (allMessages.length === 0) return null;

    return allMessages.sort((a, b) => {
        const timeA = new Date(a.date_sent || a.timestamp);
        const timeB = new Date(b.date_sent || b.timestamp);
        return timeB - timeA;
    })[0];
}

function getLastMessageTime(conversacion) {
    const lastMsg = getLastMessage(conversacion);
    return lastMsg ? (lastMsg.date_sent || lastMsg.timestamp) : new Date(0);
}

// ============================================================================
// CLEANUP
// ============================================================================

window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (eventSource) {
        console.log('🔌 Cerrando conexión SSE...');
        eventSource.close();
    }
});
