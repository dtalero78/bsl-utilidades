# App Móvil BSL Chat

La aplicación móvil de BSL Chat ha sido movida a un repositorio separado para mejor organización y mantenimiento.

## Repositorio de la App Móvil

**URL:** (Se creará en GitHub como repositorio separado)

**Nombre del repositorio:** `bsl-chat-mobile`

## Arquitectura

```
Repositorio Backend (este):
├── backend/              # Flask API, WebSocket, servicios
│   ├── descargar_bsl.py
│   ├── static/
│   └── templates/
└── MOBILE_APP.md        # Este archivo

Repositorio Mobile (separado):
├── App.tsx              # React Native + Expo
├── src/
│   ├── screens/         # Conversaciones, Chat
│   ├── services/        # API client, WebSocket
│   ├── components/      # UI components
│   └── types/           # TypeScript types
├── app.json             # Expo config
└── package.json
```

## Por Qué Repositorios Separados

1. **Simplicidad**: Cada repo tiene su propio `node_modules/`, evita conflictos
2. **Deploy Independiente**: Backend y mobile se pueden deployar por separado
3. **Espacio en Disco**: node_modules de React Native es muy pesado (~1.5GB)
4. **Clean Git History**: Commits del mobile no mezclan con commits del backend
5. **CI/CD**: Pipelines separados para cada plataforma

## Conexión entre Backend y Mobile

La app móvil se conecta al backend a través de:
- **REST API**: `https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat/api`
- **WebSocket**: Socket.IO en el mismo dominio

## Testing con Expo Go

1. En el repo mobile, ejecuta: `npm start`
2. Escanea el QR code con Expo Go en tu iPhone
3. La app se carga instantáneamente

## Deploy a TestFlight

Se usará **EAS Build** (servicio de Expo):
```bash
eas build --platform ios
eas submit --platform ios
```

No requiere Xcode, todo se hace en la nube.

---

**Fecha de separación:** 2025-11-18
**Razón:** Facilitar desarrollo sin Xcode + mejor organización
