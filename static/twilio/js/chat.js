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
let socket = null; // Socket.IO connection

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

    // Limpiar cache antiguo de fotos de perfil
    limpiarCacheFotosPerfil();

    // Cargar conversaciones
    cargarConversaciones();

    // Inicializar WebSocket con Socket.IO
    console.log('🔌 Conectando a WebSocket...');
    socket = io('/twilio-chat', {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5
    });

    // Event: Conexión exitosa
    socket.on('connect', () => {
        console.log('✅ WebSocket conectado');
    });

    // Event: Desconexión
    socket.on('disconnect', () => {
        console.log('❌ WebSocket desconectado');
    });

    // Event: Nuevo mensaje con queue y throttling
    socket.on('new_message', (data) => {
        console.log('📨 Nuevo mensaje recibido vía WebSocket:', data);
        agregarMensajeACola(data);
    });

    // Event: Error
    socket.on('error', (error) => {
        console.error('❌ Error de WebSocket:', error);
    });

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
// CONVERSATIONS LOADING
// ============================================================================

async function cargarConversaciones() {
    const listContainer = document.getElementById('conversationsList');

    try {
        console.log('Loading conversations...');

        // Mostrar indicador de carga
        listContainer.innerHTML = `
            <div class="loading">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Cargando conversaciones...</p>
            </div>
        `;

        const response = await fetch(`${API_BASE}/api/conversaciones`);
        const data = await response.json();

        if (data.success) {
            conversaciones = data.conversaciones;
            renderizarConversaciones();
            console.log(`✅ Loaded ${data.total} conversations (showing ${data.count})`);

            // Mostrar mensaje si hay más conversaciones
            if (data.has_more) {
                console.log(`ℹ️ Hay ${data.total - data.count} conversaciones más disponibles`);
            }
        } else {
            console.error('Error loading conversations:', data.error);
            mostrarError('Error al cargar conversaciones');
            listContainer.innerHTML = `
                <div class="loading">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Error al cargar conversaciones</p>
                    <button onclick="cargarConversaciones()" style="margin-top: 10px; padding: 8px 16px; cursor: pointer;">
                        Reintentar
                    </button>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error fetching conversations:', error);
        mostrarError('Error de conexión');
        listContainer.innerHTML = `
            <div class="loading">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Error de conexión</p>
                <button onclick="cargarConversaciones()" style="margin-top: 10px; padding: 8px 16px; cursor: pointer;">
                    Reintentar
                </button>
            </div>
        `;
    }
}

// ============================================================================
// PROFILE PICTURE CACHE
// ============================================================================

function obtenerFotoPerfilCached(numero, profilePictureUrl) {
    if (!profilePictureUrl) return null;

    const cacheKey = `profile_pic_${numero}`;
    const cacheTimeKey = `profile_pic_time_${numero}`;
    const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 horas en milisegundos

    try {
        // Verificar si existe en cache
        const cached = localStorage.getItem(cacheKey);
        const cacheTime = localStorage.getItem(cacheTimeKey);

        if (cached && cacheTime) {
            const age = Date.now() - parseInt(cacheTime);

            // Si el cache es válido (menos de 24 horas)
            if (age < CACHE_DURATION) {
                return cached;
            }
        }

        // Guardar nuevo valor en cache
        localStorage.setItem(cacheKey, profilePictureUrl);
        localStorage.setItem(cacheTimeKey, Date.now().toString());

        return profilePictureUrl;
    } catch (e) {
        // Si falla localStorage (cuota excedida, etc), retornar URL sin cache
        console.warn('Error usando cache de fotos:', e);
        return profilePictureUrl;
    }
}

function limpiarCacheFotosPerfil() {
    // Limpiar fotos de perfil con más de 7 días
    const MAX_AGE = 7 * 24 * 60 * 60 * 1000; // 7 días

    try {
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);

            if (key && key.startsWith('profile_pic_time_')) {
                const cacheTime = parseInt(localStorage.getItem(key));
                const age = Date.now() - cacheTime;

                if (age > MAX_AGE) {
                    const numero = key.replace('profile_pic_time_', '');
                    localStorage.removeItem(`profile_pic_${numero}`);
                    localStorage.removeItem(key);
                    console.log(`♻️ Cache limpiado para ${numero}`);
                }
            }
        }
    } catch (e) {
        console.warn('Error limpiando cache:', e);
    }
}

// ============================================================================
// CONVERSATIONS RENDERING
// ============================================================================

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
        html += crearElementoConversacion(numero, conversacion);
    }

    listContainer.innerHTML = html;
}

function crearElementoConversacion(numero, conversacion) {
    const lastMessage = getLastMessage(conversacion);
    const nombre = conversacion.nombre || conversacion.wix_data?.nombre || formatPhoneNumber(numero);
    const preview = conversacion.last_message || (lastMessage ? truncateText(lastMessage.body || lastMessage.mensaje, 50) : 'Sin mensajes');
    const time = conversacion.last_message_time ? formatTime(conversacion.last_message_time) : (lastMessage ? formatTime(lastMessage.date_sent || lastMessage.timestamp) : '');
    const isActive = conversacionActual === numero ? 'active' : '';

    // Determinar la clase de avatar según la fuente
    const source = conversacion.source || 'twilio';
    const avatarClass = source === 'whapi' ? 'avatar-whapi' : (source === 'both' ? 'avatar-both' : 'avatar-twilio');

    // Obtener foto de perfil con cache
    const profilePicture = obtenerFotoPerfilCached(numero, conversacion.profile_picture);
    const avatarContent = profilePicture
        ? `<img src="${profilePicture}" alt="${nombre}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
           <i class="fas fa-user" style="display: none;"></i>`
        : `<i class="fas fa-user"></i>`;

    return `
        <div class="conversation-item ${isActive}" data-numero="${numero}" onclick="abrirConversacion('${numero}')">
            <div class="conversation-avatar ${avatarClass}">
                ${avatarContent}
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

function actualizarConversacion(numero) {
    const conversacion = conversaciones[numero];
    if (!conversacion) return;

    const listContainer = document.getElementById('conversationsList');
    const existingItem = listContainer.querySelector(`[data-numero="${numero}"]`);

    // Crear nuevo elemento HTML
    const nuevoElemento = crearElementoConversacion(numero, conversacion);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = nuevoElemento;
    const nuevoItem = tempDiv.firstElementChild;

    if (existingItem) {
        // Actualizar elemento existente
        existingItem.replaceWith(nuevoItem);

        // Mover al inicio si es necesario (nuevo mensaje)
        const primerElemento = listContainer.firstElementChild;
        if (primerElemento !== nuevoItem) {
            listContainer.insertBefore(nuevoItem, primerElemento);
        }
    } else {
        // Insertar nuevo elemento al inicio
        listContainer.insertBefore(nuevoItem, listContainer.firstElementChild);
    }
}

// ============================================================================
// CONVERSATION HANDLING
// ============================================================================

async function abrirConversacion(numero) {
    try {
        conversacionActual = numero;

        // Update UI
        updateActiveConversation(numero);

        // Mobile: Show chat area and hide sidebar
        mostrarChatEnMobil();

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

function mostrarChatEnMobil() {
    // Solo en móvil (pantallas < 768px)
    if (window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        const chatArea = document.querySelector('.chat-area');

        if (sidebar) sidebar.classList.add('hidden');
        if (chatArea) chatArea.classList.add('active');
    }
}

function volverALista() {
    // Volver a la lista de conversaciones (móvil)
    const sidebar = document.querySelector('.sidebar');
    const chatArea = document.querySelector('.chat-area');

    if (sidebar) sidebar.classList.remove('hidden');
    if (chatArea) chatArea.classList.remove('active');

    // Limpiar conversación actual
    conversacionActual = null;
}

function renderizarChat(numero, data) {
    const chatHeader = document.getElementById('chatHeader');
    const messagesContainer = document.getElementById('messagesContainer');

    // Update header
    const nombre = data.wix_data?.nombre || formatPhoneNumber(numero);
    const stopBot = data.wix_data?.stopBot ? '(Bot detenido)' : '(Bot activo)';

    // Obtener foto de perfil de la conversación actual
    const conversacion = conversaciones[numero];
    const profilePicture = conversacion?.profile_picture;
    const avatarContent = profilePicture
        ? `<img src="${profilePicture}" alt="${nombre}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
           <i class="fas fa-user" style="display: none;"></i>`
        : `<i class="fas fa-user"></i>`;

    chatHeader.innerHTML = `
        <button class="btn-back-mobile" onclick="volverALista()" title="Volver">
            <i class="fas fa-arrow-left"></i>
        </button>
        <div class="chat-contact" onclick="toggleContactInfo()">
            <div class="chat-avatar">
                ${avatarContent}
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

    console.log(`📊 Renderizando chat - Total mensajes: ${allMessages.length}`);
    console.log(`📨 Twilio messages:`, data.twilio_messages?.length || 0);
    console.log(`📨 Data recibida:`, data);

    // Render messages
    let messagesHtml = '';
    allMessages.forEach(msg => {
        messagesHtml += renderizarMensaje(msg);
    });

    messagesContainer.innerHTML = messagesHtml;
    console.log(`✅ Mensajes renderizados en el DOM`);

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
            status: msg.status,
            media_url: msg.media_url,
            media_type: msg.media_type,
            media_mime: msg.media_mime,
            media_count: msg.media_count
        });
    });

    // Sort by timestamp
    merged.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    return merged;
}

function renderizarMensaje(msg) {
    const direction = msg.direction === 'outbound' ? 'outbound' : 'inbound';

    // Debug: Ver qué timestamp estamos recibiendo
    console.log(`📅 Mensaje timestamp:`, msg.timestamp, `Body:`, msg.body?.substring(0, 20) || '(media)');

    const time = formatTime(msg.timestamp);
    const statusIcon = getStatusIcon(msg.status);

    // Renderizar contenido según el tipo
    let messageContent = '';

    if (msg.media_url && msg.media_type) {
        // Renderizar media según el tipo
        messageContent = renderizarMedia(msg.media_url, msg.media_type, msg.media_mime);

        // Agregar caption/body si existe
        if (msg.body) {
            messageContent += `<div class="message-caption">${escapeHtml(msg.body)}</div>`;
        }
    } else if (msg.body) {
        // Mensaje de texto normal - detectar URLs y hacerlas clickeables
        messageContent = convertirUrlsALinks(escapeHtml(msg.body));
    } else {
        messageContent = '<span class="media-placeholder">📎 Archivo adjunto</span>';
    }

    return `
        <div class="message ${direction}">
            <div class="message-bubble">
                <div class="message-text">${messageContent}</div>
                <div class="message-footer">
                    <span class="message-time">${time}</span>
                    ${direction === 'outbound' ? `<span class="message-status">${statusIcon}</span>` : ''}
                </div>
            </div>
        </div>
    `;
}

function renderizarMedia(url, type, mime) {
    if (!url) return '<span class="media-placeholder">📎 Archivo adjunto</span>';

    switch (type) {
        case 'image':
        case 'sticker':
            return `<img src="${url}" alt="Imagen" class="message-image" onclick="abrirMediaModal('${url}', 'image')" loading="lazy">`;

        case 'video':
            return `<video controls class="message-video" preload="metadata">
                <source src="${url}" type="${mime || 'video/mp4'}">
                Tu navegador no soporta videos.
            </video>`;

        case 'audio':
            return `<audio controls class="message-audio" preload="metadata">
                <source src="${url}" type="${mime || 'audio/ogg'}">
                Tu navegador no soporta audio.
            </audio>`;

        case 'document':
            return `<a href="${url}" target="_blank" class="message-document">
                <i class="fas fa-file-alt"></i> Ver documento
            </a>`;

        default:
            return `<a href="${url}" target="_blank" class="message-document">
                <i class="fas fa-paperclip"></i> Ver archivo
            </a>`;
    }
}

function convertirUrlsALinks(text) {
    // Regex para detectar URLs
    const urlRegex = /(https?:\/\/[^\s<]+)/g;
    return text.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
}

function abrirMediaModal(url, type) {
    const modal = document.getElementById('mediaModal');
    if (!modal) return;

    const modalContent = modal.querySelector('.modal-content') || modal;

    if (type === 'image') {
        modalContent.innerHTML = `
            <span class="close-modal" onclick="closeMediaModal()">&times;</span>
            <img src="${url}" style="max-width: 90vw; max-height: 90vh; object-fit: contain;">
        `;
    }

    modal.style.display = 'flex';
}

// ============================================================================
// SLASH COMMANDS (Atajos de texto)
// ============================================================================

const SLASH_COMMANDS = {
    '/a': '...transfiriendo con asesor',

    '/c': `Bancolombia
Cuenta de Ahorros 442 9119 2456
Cédula: 79 981 585

Daviplata: 3014400818
Nequi: 3008021701`,

    '/l': `La persona que va a hacer el examen debe diligenciar el siguiente link:

https://bsl-plataforma.com/nuevaorden1.html`,

    '/2': `Agendar tu teleconsulta es muy fácil:

📅 Diligencia tus datos y escoge la hora que te convenga

👂👀 Realiza las pruebas de audición y visión necesarias desde tu celular o computador.

📱 El médico se comunicará contigo a través de WhatsApp video.

💵 Paga después de la consulta usando Bancolombia, Nequi, o Daviplata (46.000).

¡Listo! Descarga inmediatamente tu certificado

Para comenzar:

https://bsl-plataforma.com/nuevaorden1.html`
};

function expandirComando(texto) {
    // Verificar si el texto es exactamente un comando
    const textoLimpio = texto.trim().toLowerCase();
    if (SLASH_COMMANDS[textoLimpio]) {
        return SLASH_COMMANDS[textoLimpio];
    }
    return texto;
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
    let mensaje = messageInput.value.trim();

    if (!mensaje) {
        return;
    }

    // Expandir comandos slash
    mensaje = expandirComando(mensaje);

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

            // Actualizar contador de mensajes para detectar nuevos correctamente
            lastMessageCount++;

            // Actualizar preview en la lista de conversaciones
            if (conversaciones[conversacionActual]) {
                conversaciones[conversacionActual].last_message = mensaje.substring(0, 50);
                conversaciones[conversacionActual].last_message_time = new Date().toISOString();
                actualizarConversacion(conversacionActual);
            }

            // Refresh conversation after a short delay (silencioso para no reemplazar todo)
            setTimeout(() => {
                actualizarConversacionActualSilencioso();
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

// Variable para timeout de debouncing
let searchTimeout;

function filtrarConversaciones() {
    // Cancelar búsqueda anterior si existe
    clearTimeout(searchTimeout);

    // Esperar 300ms después del último keypress
    searchTimeout = setTimeout(() => {
        const searchInput = document.getElementById('searchInput');
        const filter = searchInput.value.toLowerCase();
        const items = document.querySelectorAll('.conversation-item');

        items.forEach(item => {
            const nombre = item.querySelector('.conversation-name')?.textContent.toLowerCase() || '';
            const numero = item.getAttribute('data-numero') || '';

            if (nombre.includes(filter) || numero.includes(filter)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }, 300);
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
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
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
    // Si el backend ya envía last_message_time, usarlo directamente
    if (conversacion.last_message_time) {
        return conversacion.last_message_time;
    }
    // Fallback: buscar en los mensajes
    const lastMsg = getLastMessage(conversacion);
    return lastMsg ? (lastMsg.date_sent || lastMsg.timestamp) : new Date(0);
}

// ============================================================================
// WEBSOCKET MESSAGE QUEUE (Throttling)
// ============================================================================

let messageQueue = [];
let isProcessingQueue = false;

function agregarMensajeACola(data) {
    messageQueue.push(data);
    console.log(`📥 Mensaje agregado a cola (${messageQueue.length} pendientes)`);
    procesarColaMensajes();
}

async function procesarColaMensajes() {
    // Si ya estamos procesando o no hay mensajes, salir
    if (isProcessingQueue || messageQueue.length === 0) {
        return;
    }

    isProcessingQueue = true;
    console.log('⚙️ Iniciando procesamiento de cola de mensajes');

    while (messageQueue.length > 0) {
        const data = messageQueue.shift();
        console.log(`⚡ Procesando mensaje (${messageQueue.length} restantes)`);

        try {
            await handleNewMessage(data);
        } catch (error) {
            console.error('❌ Error procesando mensaje de cola:', error);
        }

        // Throttle: esperar 100ms entre mensajes
        if (messageQueue.length > 0) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }

    isProcessingQueue = false;
    console.log('✅ Cola de mensajes procesada completamente');
}

// ============================================================================
// WEBSOCKET MESSAGE HANDLING
// ============================================================================

async function handleNewMessage(data) {
    console.log('📨 Procesando nuevo mensaje:', data);

    try {
        // Reproducir sonido de notificación
        if (audioPermitido && notificationSound) {
            notificationSound.play().catch(e => console.log('No se pudo reproducir sonido:', e));
        }

        // Mostrar notificación del navegador
        if ('Notification' in window && Notification.permission === 'granted' && document.hidden) {
            const notification = new Notification('Nuevo mensaje de WhatsApp', {
                body: `${data.body?.substring(0, 50) || '(media)'}`,
                icon: '/static/images/whatsapp-icon.png',
                tag: `msg-${data.numero}`
            });

            notification.onclick = function() {
                window.focus();
                abrirConversacion(data.numero);
                notification.close();
            };
        }

        // Actualizar la conversación en memoria inmediatamente
        if (conversaciones[data.numero]) {
            console.log('⚡ Actualizando conversación en memoria');
            conversaciones[data.numero].last_message = data.body?.substring(0, 50) || '(media)';
            conversaciones[data.numero].last_message_time = new Date().toISOString();

            // Actualizar solo este elemento en el DOM (optimización)
            actualizarConversacion(data.numero);
        } else {
            console.log('🆕 Nueva conversación detectada, recargando lista completa');
            cargarConversacionesSilencioso();
        }

        // Si estamos viendo la conversación del mensaje, actualízala también
        if (conversacionActual === data.numero) {
            console.log('🔄 Actualizando conversación actual con nuevo mensaje');
            actualizarConversacionActualSilencioso();
        }

        // Incrementar contador de no leídos si el usuario no está viendo
        if (document.hidden) {
            unreadMessages++;
            startTitleBlink(data.body);
        }
    } catch (error) {
        console.error('❌ Error manejando mensaje nuevo:', error);
    }
}

// ============================================================================
// CLEANUP
// ============================================================================

window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    if (socket) {
        socket.disconnect();
    }
});
