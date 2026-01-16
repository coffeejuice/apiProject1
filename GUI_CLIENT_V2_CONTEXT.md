# 🤖 GUI_CLIENT_V2_CONTEXT: Technical Blueprint

High-performance, QML-based desktop client implementing a modular, block-based workspace.

## 🏛 Architecture: MVVM+S
The client follows a strict **Model-View-ViewModel + Service** pattern.

### 1. View (Declarative UI)
- **Engine**: Qt Quick / QML.
- **Root**: `resources/qml/Main.qml`.
- **Logic**: UI components link to ViewModels via property bindings and slots.
- **Dynamic Loading**: Uses `Loader` in `Main.qml` to instantiate block components based on path provided by ViewModels.

### 2. ViewModel (Python Bridge)
- **Base Class**: `app.viewmodels.block.BlockViewModel` (Inherits `QObject`).
- **Communication**: Uses PySide6 `Property`, `Signal`, and `Slot`.
- **State Management**:
    - `DocumentListViewModel`: Manages global document navigation.
    - `ProcessViewModel`: Manages the active document state and block list.
    - `BlockViewModel`: Individual block state (data, type, UI path).
    - `AuthViewModel`: Manages authentication state (login/logout) and user credentials.

### 3. Service (Backend Integration)
- **ApiClient**: Cleaned-up wrapper for the Techno-Notion API.
- **BlockRegistry**: Static registry mapping `BlockType` (API) -> `ViewModel` class + `QML` path.

## 🖼 GUI Layout Description
The interface uses a responsive layout managed by `Main.qml`.

### 1. Left Pane (Authentication & Navigation)
Stacked vertically in a `ColumnLayout`:
- **LoginPane** (`LoginPane.qml`): Top-aligned fixed-height pane (~250px). Contains high-contrast credential fields and login logic.
- **Document List** (`Sidebar.qml`): Fills remaining space. Uses a **Flow Layout** inside a ScrollView to display documents as wrapping cards or tags.

### 2. Editor Workspace (Right)
- **Component**: Central `Rectangle` in `Main.qml`.
- **Structure**: 
    - **Header**: Displays the current document title (bound to `processViewModel.title`).
    - **Card View**: Replaces the standard list. Uses `CardView.qml` (ListView) to display blocks.
    - **Card Delegate**: Each block is wrapped in `Draw.qml`, which provides a local toolbar and `Flow` layout context.
    - **Styled Inputs**: Text fields use `EditText.qml`, a custom wrapper with dynamic borders.
    - **Creation Tool**: An "+ Add New Card" button is pinned to the bottom of the list.

## 🧩 Extendability (Plugin System)
To add a new block type (e.g., "Image"):
1. **VM**: Create `ImageBlockViewModel` in `block.py`.
2. **UI**: Create `ImageBlock.qml` in `resources/qml/blocks/`.
3. **Registry**: Add `BlockRegistry.register("image", "blocks/ImageBlock.qml", ImageBlockViewModel)`.
*The core editor will automatically detect and render the new type.*

## 📂 Directory Map
- `app/api/`: Request logic and token handling.
- `app/core/`: Registry and configuration singletons.
- `app/viewmodels/`: Python bridge logic.
- `resources/qml/`: UI assets.
  - `components/`: Shell UI (Sidebar, Toolbars).
  - `blocks/`: Modular content blocks.
  - `Theme.qml`: Global style singleton (`pragma Singleton`).

## ⚠️ Development Guardrails
1. **Bindable Properties**: Every `Property` MUST have a `notify` signal (e.g., `textChanged`). Failure causes "non-bindable properties" console warnings and breaks reactivity.
2. **NoneType Control**: Shiboken (C++ bridge) cannot convert Python `None` to specific C++ types (int, bool). Use safe defaults (e.g., `-1` for IDs, `""` for strings).
3. **Import System**:
    - `main.py` adds `resources/qml` to `engine.addImportPath`.
    - Components in subdirs (like `blocks/`) MUST `import ".."` to access the `Theme` singleton or other peer components.
4. **Style**: `QT_QUICK_CONTROLS_STYLE` is set to `Fusion` in `main.py` to allow custom control styling (backgrounds, borders).

## 🚀 Key Entry Points
- **Entry**: `main.py` (Bootstraps API client, ViewModels, and QML Engine).
- **Theme**: `resources/qml/Theme.qml` (Source of truth for colors/spacing).
- **Core Editor**: `resources/qml/Main.qml` (The `Repeater` + `Loader` pattern).
