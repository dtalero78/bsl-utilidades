# BSL Chat - iOS App

Native iOS application for BSL Chat using SwiftUI.

## Requirements

- macOS with Xcode 15.0 or later
- iOS 15.0+ deployment target
- CocoaPods installed (`sudo gem install cocoapods`)
- Apple Developer account for TestFlight deployment

## Setup Instructions

### 1. Install CocoaPods Dependencies

```bash
cd ios/BSLChat
pod install
```

### 2. Open Workspace in Xcode

**IMPORTANT:** After running `pod install`, you MUST open the `.xcworkspace` file, NOT the `.xcodeproj` file.

```bash
open BSLChat.xcworkspace
```

### 3. Configure Signing

1. Open the project in Xcode
2. Select the BSLChat target
3. Go to "Signing & Capabilities" tab
4. Select your Development Team
5. Xcode will automatically manage provisioning profiles

### 4. Build and Run

1. Select a simulator or connected device
2. Press `Cmd + R` to build and run
3. For physical device testing, you may need to trust the developer certificate in Settings

## Project Structure

```
BSLChat/
├── Core/
│   ├── Network/       # API client, networking layer
│   ├── Models/        # Data models (Conversation, Message, etc.)
│   └── Services/      # Business logic services
├── Features/
│   ├── Conversations/ # Conversations list screen
│   └── Chat/          # Chat screen with messages
├── Shared/            # Shared UI components, utilities
└── Resources/         # Assets, fonts, etc.
```

## Dependencies

- **Alamofire** (~> 5.8): HTTP networking
- **Socket.IO-Client-Swift** (~> 16.1.0): WebSocket for real-time messaging
- **SDWebImage** (~> 5.18): Async image loading and caching

## Backend Integration

The app connects to the Flask backend at:
- Production: `https://bsl-utilidades-yp78a.ondigitalocean.app`
- Endpoint: `/twilio-chat`

All API endpoints are defined in `Core/Network/APIClient.swift`.

## Development Phases

- [x] **Phase 1**: Backend code restructuring
- [x] **Phase 2**: iOS project base setup with SwiftUI ← Current
- [ ] **Phase 3**: Networking layer with Alamofire
- [ ] **Phase 4**: Conversations list implementation
- [ ] **Phase 5**: Chat screen implementation
- [ ] **Phase 6**: Additional features (offline mode, media, etc.)
- [ ] **Phase 7**: Testing and TestFlight deployment

## TestFlight Deployment

Coming in Phase 7. Will include instructions for:
- Archive and export
- App Store Connect upload
- TestFlight beta testing

## Rollback Strategy

If any issues occur during development:

```bash
# Return to stable version
git checkout v1.0-stable

# Or reset the feature branch
git checkout feature/ios-app
git reset --hard v1.0-stable
```

The tag `v1.0-stable` represents the last known working state before iOS development started.
