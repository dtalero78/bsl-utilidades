# iOS App Setup - IMPORTANTE

## Estado Actual

El proyecto iOS base ha sido creado con la siguiente estructura:

```
ios/BSLChat/
├── Podfile                  # Definición de dependencias
├── BSLChat.xcodeproj/       # Proyecto Xcode
└── BSLChat/
    ├── BSLChatApp.swift     # Entry point de la app
    ├── ContentView.swift    # Vista inicial
    ├── Info.plist           # Configuración de la app
    ├── Core/                # Networking, Models, Services
    ├── Features/            # Conversations, Chat screens
    ├── Shared/              # Componentes compartidos
    └── Resources/           # Assets, imágenes
```

## Próximos Pasos (MANUAL)

### 1. Instalar Dependencias CocoaPods

Antes de abrir el proyecto en Xcode, debes instalar las dependencias:

```bash
cd ios/BSLChat
pod install
```

**IMPORTANTE:** Este comando puede tardar varios minutos la primera vez, ya que debe clonar el repositorio completo de especificaciones de CocoaPods (~3GB).

Si encuentras errores de codificación, asegúrate de tener UTF-8 configurado:

```bash
export LANG=en_US.UTF-8
pod install
```

### 2. Abrir en Xcode

**CRÍTICO:** Después de `pod install`, SIEMPRE abre el archivo `.xcworkspace`, NO el `.xcodeproj`:

```bash
open BSLChat.xcworkspace
```

### 3. Configurar Signing & Capabilities

1. Abre el proyecto en Xcode
2. Selecciona el target "BSLChat" en el navegador de proyecto
3. Ve a la pestaña "Signing & Capabilities"
4. Selecciona tu "Team" (Apple Developer account)
5. Xcode gestionará automáticamente los provisioning profiles

### 4. Build y Run

- Selecciona un simulador (iPhone 15, iPhone 14, etc.) o dispositivo físico conectado
- Presiona `Cmd + R` para compilar y ejecutar
- Si usas dispositivo físico, puede que necesites confiar en el certificado de desarrollador en Ajustes

## Dependencias Instaladas

El Podfile incluye:

- **Alamofire** (~> 5.8): Cliente HTTP para networking
- **Socket.IO-Client-Swift** (~> 16.1.0): WebSocket para mensajería en tiempo real
- **SDWebImage** (~> 5.18): Carga y caché de imágenes

## Solución de Problemas

### Error: "No such file 'Alamofire/Alamofire-Swift.h'"
- Significa que no ejecutaste `pod install` o abriste el `.xcodeproj` en lugar del `.xcworkspace`
- Solución: Cierra Xcode, ejecuta `pod install`, abre `.xcworkspace`

### Error: "Xcode requires a development team"
- Solución: Ve a Signing & Capabilities y selecciona tu equipo de desarrollo

### Error: "Unable to install pods"
- Puede ser problema de red o caché de CocoaPods
- Solución:
  ```bash
  pod cache clean --all
  pod deintegrate
  pod install
  ```

## Estado de Desarrollo

- ✅ Fase 1: Backend restructurado
- ✅ Fase 2: Proyecto iOS base creado (estructura completa)
- ⏸️  **Pendiente**: `pod install` (requiere conexión estable + ~5-10 min primera vez)
- ⏳ Fase 3: Networking layer (siguiente paso)
- ⏳ Fase 4-7: Features, testing, TestFlight

## Rollback

Si algo sale mal:

```bash
git checkout v1.0-stable
```

El tag `v1.0-stable` contiene el último estado estable antes del desarrollo iOS.
