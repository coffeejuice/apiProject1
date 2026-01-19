# Client Context: CardMix (Block Editor)

This document provides essential context for coding agents working on the CardMix project.

## Project Overview
**CardMix** is a Qt Quick-based application designed for editing "cards" that contain nested "cells". It uses a hierarchical data model implemented in C++ and exposed to QML. The application is built with Qt 6.8 and C++20.

## Architecture & Data Flow

### Data Models (C++)
- **`CardModel`**: A `QAbstractListModel` that manages a collection of cards.
    - Roles: `cardType` (enum), `cellModel` (pointer to a `CellModel`).
    - Card Types: `IMAGE`, `GRAPHIC`, `DOCUMENT`, `BLOCK`, `HEAT`, `UPSET`, `DRAW`.
- **`CellModel`**: A `QAbstractListModel` managed within each card.
    - Roles: `angleValue` (String), `heightValue` (String).

### UI Integration
- The `CardModel` is instantiated in `main.cpp` and set as an initial property of the QML engine.
- QML components consume these models to build the nested interface.

## Visual Layout & UI Components

### 1. Main Window (`Main.qml`)
- The entry point, setting up the 1000x800 window and hosting the `CardView`.

### 2. Card Management View (`CardView.qml`)
- **Side Panel (Left)**: A `Column` containing "Append Card" and "Remove Card" buttons.
- **Main Area (Right)**: A `ListView` that occupies the remaining space.
- **Card Selection**: Uses `DelegateChooser` to select the appropriate delegate based on the card's type (currently most map to `Draw.qml`).

### 3. Card Delegate (`Draw.qml`)
- Acts as the container for cells within a card.
- **Local Toolbar**: Buttons to add/remove cells (`+` / `-`).
- **Content Area**: Uses a `Flow` layout to wrap cells horizontally.
- **Repeater**: Iterates over the `cellModel` role of the current card to create `Cell` instances.

### 4. Cell Component (`Cell.qml`)
- Displays cell data in a row: `( [Angle] °) [Height] →`.
- Uses `EditText.qml` for editable values.

### 5. Custom Controls (`EditText.qml`)
- A wrapper around `TextField`.
- Features a dynamic border that highlights on focus or hover.
- Implements auto-sizing based on content width.

## Qt Quick Features Used
- **Models & Views**: `ListView`, `Repeater`, `DelegateChooser`, `DelegateChoice`.
- **Layouts**: `Column`, `Row`, `RowLayout`, `Flow`, `anchors`.
- **Interactivity**: `Button`, `TextField`, `Keys` (Return/Enter handling).
- **Styling**: `Rectangle` with custom borders and transparency, `qputenv("QT_QUICK_CONTROLS_STYLE", "Windows")` in `main.cpp`.
- **C++ Integration**: `QML_ELEMENT`, `QML_UNCREATABLE`, `setInitialProperties`, custom Roles.

## File Structure Highlights
- `main.cpp`: Application initialization and C++ model injection.
- `CardView.qml`: Main UI structure (Sidebar + List).
- `Draw.qml`: Card-level container and flow logic.
- `Cell.qml` / `EditText.qml`: Low-level data entry components.
- `cardmodel.h/cpp` & `cellmodel.h/cpp`: The core C++ data structures.
- `card_delegates/`: Directory intended for specialized card type delegates (e.g., `Card_Document.qml`, `Card_BaseLayout.qml`).

## Development Guidelines
- **Nested Models**: When adding items to a card, you are interacting with the `CellModel` nested inside a `CardModel` index.
- **Flow Layout**: The cell display uses `Flow`, meaning items wrap automatically based on the available width of the `CardView`.
- **Types**: Always check the `cardType` role when modifying card-specific behavior.
