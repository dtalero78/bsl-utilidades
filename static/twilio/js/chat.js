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

// API Configuration
const API_BASE = window.API_BASE || window.location.origin;

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Twilio-BSL Chat initialized');

    // Inicializar sonido de notificación
    inicializarSonidoNotificacion();

    // Cargar conversaciones
    cargarConversaciones();

    // Auto-refresh cada 5 segundos (como WhatsApp)
    autoRefreshInterval = setInterval(() => {
        if (conversacionActual) {
            actualizarConversacionActualSilencioso();
        } else {
            cargarConversacionesSilencioso();
        }
    }, 5000); // 5 segundos = actualización casi en tiempo real

    // Auto-expand textarea
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }
});

// ============================================================================
// NOTIFICATION SOUND
// ============================================================================

function inicializarSonidoNotificacion() {
    // Crear sonido de notificación simple
    try {
        notificationSound = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+DyvmwhBTGH0fPTgjMGHm7A7+OZSA0PVq3o7qlXFglCn+Dyg==');
        notificationSound.volume = 0.3;
    } catch (e) {
        console.warn('No se pudo inicializar el sonido de notificación');
    }
}

function reproducirSonidoNotificacion() {
    if (notificationSound && document.hidden) {
        // Solo reproducir si la ventana no está visible
        try {
            notificationSound.play().catch(e => console.log('No se pudo reproducir sonido'));
        } catch (e) {
            console.log('No se pudo reproducir sonido');
        }
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
    if (!conversacionActual || isLoadingMessages) return;

    try {
        isLoadingMessages = true;
        const response = await fetch(`${API_BASE}/api/conversacion/${conversacionActual}`);
        const data = await response.json();

        if (data.success) {
            const messagesContainer = document.getElementById('messagesContainer');
            const currentScrollHeight = messagesContainer.scrollHeight;
            const currentScrollTop = messagesContainer.scrollTop;
            const isAtBottom = (messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight) < 100;

            // Merge and render messages
            const allMessages = mergeMessages(data.twilio_messages || [], data.wix_data?.mensajes || []);

            // Verificar si hay mensajes nuevos
            if (allMessages.length > lastMessageCount) {
                console.log(`📨 Nuevo mensaje detectado (${allMessages.length - lastMessageCount} nuevo(s))`);
                reproducirSonidoNotificacion();

                // Mostrar notificación del navegador
                mostrarNotificacionNavegador('Nuevo mensaje', allMessages[allMessages.length - 1].body);
            }

            lastMessageCount = allMessages.length;

            // Renderizar mensajes
            let messagesHtml = '';
            allMessages.forEach(msg => {
                messagesHtml += renderizarMensaje(msg);
            });

            messagesContainer.innerHTML = messagesHtml;

            // Mantener scroll position a menos que esté al fondo
            if (isAtBottom) {
                scrollToBottom();
            } else {
                messagesContainer.scrollTop = currentScrollTop;
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
});
