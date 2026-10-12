# DrawLayout

**DrawLayout** is an extensible, **2D CAD Design System Framework** built with **PySide6**. By utilizing a robust plugin architecture, it allows developers to dynamically integrate new shapes and functionalities into the application without modifying the core codebase.

## 🚀 Key Features

- **Dynamic Plugin System**: Easily add new geometric shapes (e.g., circles, polygons, custom paths) by simply dropping Python files into the `plugin/` folder.
- **Interactive Parameter Adjustment**: Each plugin can define its own GUI widgets, allowing users to modify dimensions and attributes in real-time via a dedicated sidebar.
- **Multi-Format Export**: Seamlessly export your designs as:
  - **SVG**: For high-quality vector graphics.
  - **DXF**: The industry standard for CAD software (powered by `ezdxf`).
- **Project Management**: Save and load project states, including all placed elements and their specific parameters, using JSON files.
- **Advanced Graphics Handling**: Powered by `QGraphicsScene`, providing native support for selecting, moving, zooming, and panning objects within a 2D workspace.

## 🛠 Tech Stack

- **Language**: Python 3.x
- **GUI Framework**: PySide6 (Qt for Python)
- **CAD Engine**: ezdxf (for DXF generation)
- **Data Format**: JSON (Configuration)

## 📂 Directory Structure

```text
app/
├── main.py                  # Application entry point & Main window
├── plugin_interface.py     # Plugin base class (ShapePluginInterface)
├── plugin_manager.py       # Dynamic plugin loader
├── export_manager.py       # SVG/DXF export management class
└── plugin/                 # Plugin storage folder
    ├── __init__.py
    └── rectangle_plugin.py  # Sample plugin (Rectangle)
```

## 🔧 Setup & Installation

### Prerequisites
- Python 3.8 or higher installed on your system.

### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/DrawLayout.git
   cd DrawLayout
   ```
2. Install the required dependencies:
   ```bash
   pip install PySide6 ezdxf
   ```

### Running the Application
```bash
python app/main.py
```

## 🏗 Architecture Overview

The system is designed with **Loose Coupling** in mind to ensure scalability and ease of maintenance:

1.  **`ShapePluginInterface`**: An abstract base class that defines the contract for all shape plugins. It abstracts GUI generation, graphics item creation, and DXF export logic.
2.  **`PluginManager`**: Uses `pkgutil` and `importlib` to scan the `plugin/` directory at runtime. It automatically detects and instantiates any class that implements the `ShapePluginInterface`.
3.  **`ExportManager`**: Handles the transformation of scene data into files. For DXF specifically, it delegates the entity creation logic back to the individual plugins to ensure complex shapes are exported correctly.

## EXTENDING (How to add a Plugin)

To add a new shape to the system, follow these steps:

1.  Create a new Python file in `app/plugin/` (e.g., `circle_plugin.py`).
2.  Define a class that inherits from `ShapePluginInterface`.
3.  Implement the following methods:
    - `plugin_name`: The name displayed in the UI dropdown.
    - `plugin_id`: A unique string identifier for configuration saving.
    - `create_parameter_widget()`: Return a widget (e.g., `QDoubleSpinBox`) for user inputs.
    - `generate_graphics_item()`: Create and return the object to be rendered in the scene.
    - `export_to_dxf()`: Define how the shape should be drawn into the `ezdxf` modelspace.

