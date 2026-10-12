### Directory Structure

```text
app/
├── main.py                  # Application entry point / Main window
├── plugin_interface.py     # Plugin base class (ShapePluginInterface)
├── plugin_manager.py       # Dynamic plugin loader
├── export_manager.py       # SVG/DXF export management class
└── plugin/                 # Plugin storage folder
    ├── __init__.py
    └── rectangle_plugin.py  # Sample plugin (Rectangle)

```

---

### 1. `plugin_interface.py` (Plugin Base Class)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QGraphicsItem
from PySide6.QtCore import QObject, Signal, QPointF
import ezdxf

class PluginSignalEmitter(QObject):
    """Emitter to handle Signals even in classes that do not inherit from QObject"""
    parameters_changed = Signal()

class ShapePluginInterface(ABC):
    """Abstract base class that all shape plugins must inherit from"""

    def __init__(self) -> None:
        self.signals = PluginSignalEmitter()

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Plugin name to display in the UI"""
        pass

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique ID for saving configurations"""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """Generates and returns a GUI widget for parameter adjustment"""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a QGraphicsItem based on the specified parameters"""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds shape entities to the ezdxf modelspace (msp)"""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """Retrieves current GUI input values as a dictionary"""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Reflects the parameter dictionary loaded from external sources onto the GUI"""
        pass

```

---

### 2. `plugin_manager.py` (Dynamic Plugin Loader)

```python
import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type
from plugin_interface import ShapePluginInterface

class PluginManager:
    """Management class that automatically detects and loads plugins from the 'plugin' folder"""

    def __init__(self, plugin_folder: str = "plugin") -> None:
        self.plugin_folder = Path(plugin_folder)
        self.plugins: Dict[str, ShapePluginInterface] = {}
        self.ensure_plugin_folder()

    def ensure_plugin_folder(self) -> None:
        """Creates the plugin folder if it does not exist"""
        if not self.plugin_folder.exists():
            self.plugin_folder.mkdir(parents=True, exist_ok=True)
            # Generate __init__.py for packaging
            init_file = self.plugin_folder / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def discover_plugins(self) -> Dict[str, ShapePluginInterface]:
        """Scans modules in the plugin folder and instantiates classes that implement ShapePluginInterface"""
        self.plugins.clear()
        
        # Explore modules under the plugin directory
        for _, module_name, is_pkg in pkgutil.iter_modules([str(self.plugin_folder)]):
            if is_pkg:
                continue
            
            full_module_name = f"{self.plugin_folder.name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # Iterate through classes within the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ShapePluginInterface) and 
                        attr is not ShapePluginInterface):
                        
                        instance = attr()
                        self.plugins[instance.plugin_id] = instance
            except Exception as e:
                print(f"[ERROR] Failed to load plugin module '{module_name}': {e}")
                
        return self.plugins

```

---

### 3. `export_manager.py` (SVG / DXF Export Section)

```python
from pathlib import Path
from typing import List, Dict, Any
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtCore import QSize, QRectF
from PySide6.QtGui import QPainter
import ezdxf

from plugin_manager import PluginManager

class ExportManager:
    """Class responsible for exporting drawing elements to SVG and DXF files"""

    @staticmethod
    def export_to_svg(scene: QGraphicsScene, file_path: str) -> bool:
        """Outputs the rendering content of a QGraphicsScene as an SVG file"""
        try:
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            
            # Set the scene's boundary size as the output range
            scene_rect = scene.sceneRect()
            generator.setSize(QSize(int(scene_rect.width()), int(scene_rect.height())))
            generator.setViewBox(QRectF(0, 0, scene_rect.width(), scene_rect.height()))
            generator.setTitle("2D CAD Drawing Output")
            generator.setDescription("Generated by PySide6 SVG Export Manager")

            painter = QPainter()
            if painter.begin(generator):
                scene.render(painter)
                painter.end()
                return True
            return False
        except Exception as e:
            print(f"[ERROR] Failed to export SVG: {e}")
            return False

    @staticmethod
    def export_to_dxf(placed_elements: List[Dict[str, Any]], plugin_manager: PluginManager, file_path: str) -> bool:
        """Outputs a DXF file using ezdxf from the data of each placed shape object"""
        try:
            # Generate DXF R2010 document
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()

            for elem in placed_elements:
                plugin_id = elem.get("plugin_id")
                params = elem.get("params", {})
                position = elem.get("position")  # QPointF

                plugin = plugin_manager.plugins.get(plugin_id)
                if plugin and position:
                    # Call the DXF export process on the plugin side
                    plugin.export_to_dxf(msp, params, position)

            doc.saveas(file_path)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to export DXF: {e}")
            return False

```

---

### 4. `plugin/rectangle_plugin.py` (Sample Plugin)

```python
from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QGraphicsItem, 
    QGraphicsRectItem, QDialog, QVBoxLayout, QDialogButtonBox
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen, QColor, QMouseEvent
import ezdxf

from plugin_interface import ShapePluginInterface

class EditableRectItem(QGraphicsRectItem):
    """Custom rectangle item that opens a parameter editing dialog on double-click"""

    def __init__(self, x: float, y: float, w: float, h: float, plugin: 'RectanglePlugin', params: Dict[str, Any]) -> None:
        super().__init__(x, y, w, h)
        self.plugin = plugin
        self.params = params
        
        # Selection and movement flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        pen = QPen(QColor(0, 120, 215), 2.0)
        self.setPen(pen)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Displays an independent parameter editing dialog upon double-click"""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing")
        dialog.resize(300, 150)
        
        layout = QVBoxLayout(dialog)

        # Individually create the form and spin boxes for the dialog
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        spin_w = QDoubleSpinBox()
        spin_w.setRange(1.0, 5000.0)
        spin_w.setValue(float(self.params.get("width", 100.0)))
        spin_w.setSuffix(" mm")

        spin_h = QDoubleSpinBox()
        spin_h.setRange(1.0, 5000.0)
        spin_h.setValue(float(self.params.get("height", 60.0)))
        spin_h.setSuffix(" mm")

        form_layout.addRow("Width:", spin_w)
        form_layout.addRow("Height:", spin_h)
        layout.addWidget(form_widget)

        # OK / Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Execute the dialog; if accepted, update parameters and redraw the shape
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = {
                "width": spin_w.value(),
                "height": spin_h.value()
            }
            self.params = new_params
            self.setData(1, new_params)  # Update metadata as well
            
            # Update rectangle size and shape
            w = float(new_params["width"])
            h = float(new_params["height"])
            self.setRect(-w / 2.0, -h / 2.0, w, h)

        super().mouseDoubleClickEvent(event)


class RectanglePlugin(ShapePluginInterface):
    """Sample shape plugin that draws a rectangle"""

    def __init__(self) -> None:
        super().__init__()
        self._spin_width: QDoubleSpinBox | None = None
        self._spin_height: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Rectangle"

    @property
    def plugin_id(self) -> str:
        return "std.rectangle"

    def create_parameter_widget(self) -> QWidget:
        """Creates parameter adjustment UI for the main screen"""
        widget = QWidget()
        layout = QFormLayout(widget)

        self._spin_width = QDoubleSpinBox()
        self._spin_width.setRange(1.0, 5000.0)
        self._spin_width.setValue(100.0)
        self._spin_width.setSuffix(" mm")
        self._spin_width.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._spin_height = QDoubleSpinBox()
        self._spin_height.setRange(1.0, 5000.0)
        self._spin_height.setValue(60.0)
        self._spin_height.setSuffix(" mm")
        self._spin_height.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        layout.addRow("Width:", self._spin_width)
        layout.addRow("Height:", self._spin_height)

        return widget

    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a custom rectangle item that supports double-clicking"""
        w = float(params.get("width", 100.0))
        h = float(params.get("height", 60.0))

        item = EditableRectItem(-w / 2.0, -h / 2.0, w, h, self, params)
        return item

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Generation of LWPOLYLINE for ezdxf"""
        w = float(params.get("width", 100.0))
        h = float(params.get("height", 60.0))
        cx, cy = position.x(), position.y()

        x1, y1 = cx - w / 2.0, cy - h / 2.0
        x2, y2 = cx + w / 2.0, cy - h / 2.0
        x3, y3 = cx + w / 2.0, cy + h / 2.0
        x4, y4 = cx - w / 2.0, cy + h / 2.0

        points = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
        msp.add_lwpolyline(points, close=True)

    def get_current_parameters(self) -> Dict[str, Any]:
        return {
            "width": self._spin_width.value() if self._spin_width else 100.0,
            "height": self._spin_height.value() if self._spin_height else 60.0,
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        if self._spin_width and "width" in params:
            self._spin_width.setValue(float(params["width"]))
        if self._spin_height and "height" in params:
            self._spin_height.setValue(float(params["height"]))

```

---

### 5. `main.py` (Main Window & Entry Point)

```python
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsScene, QGraphicsView,
    QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QFileDialog,
    QMessageBox, QGroupBox, QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QWheelEvent, QPen, QColor, QBrush

from plugin_manager import PluginManager
from export_manager import ExportManager

class CustomGraphicsView(QGraphicsView):
    """Custom QGraphicsView with zoom and pan functions"""

    def __init__(self, scene: QGraphicsScene) -> None:
        super().__init__(scene)
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in/out with the mouse wheel"""
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(zoom_factor, zoom_factor)


class MainWindow(QMainWindow):
    """Application main window"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("2D CAD Design System - PySide6")
        self.resize(1280, 800)

        # Plugin manager and data management
        self.plugin_manager = PluginManager()
        self.plugin_manager.discover_plugins()
        self.placed_items: List[QGraphicsItem] = []  # List of plugin items on the scene

        self._setup_ui()
        self._populate_plugins()

    def _setup_ui(self) -> None:
        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # -------------------- Left Operation Panel --------------------
        left_panel = QWidget()
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(left_panel)

        # 1. Plugin Selection Group
        group_plugin = QGroupBox("Shape Plugins")
        plugin_layout = QVBoxLayout(group_plugin)
        self.combo_plugins = QComboBox()
        self.combo_plugins.currentIndexChanged.connect(self._on_plugin_changed)
        plugin_layout.addWidget(self.combo_plugins)

        # Dynamic parameter GUI insertion area
        self.param_widget_container = QWidget()
        self.param_widget_layout = QVBoxLayout(self.param_widget_container)
        plugin_layout.addWidget(self.param_widget_container)

        self.btn_add_shape = QPushButton("Add to Drawing")
        self.btn_add_shape.clicked.connect(self._add_shape_to_scene)
        plugin_layout.addWidget(self.btn_add_shape)
        left_layout.addWidget(group_plugin)

        # 2. Configuration Save/Load Group
        group_config = QGroupBox("Project Management (JSON)")
        config_layout = QVBoxLayout(group_config)
        self.btn_save_config = QPushButton("Save Config (JSON)")
        self.btn_save_config.clicked.connect(self._save_config)
        self.btn_load_config = QPushButton("Load Config (JSON)")
        self.btn_load_config.clicked.connect(self._load_config)
        config_layout.addWidget(self.btn_save_config)
        config_layout.addWidget(self.btn_load_config)
        left_layout.addWidget(group_config)

        # 3. Export Group
        group_export = QGroupBox("Drawing Output")
        export_layout = QVBoxLayout(group_export)
        self.btn_export_svg = QPushButton("Export to SVG File")
        self.btn_export_svg.clicked.connect(self._export_svg)
        self.btn_export_dxf = QPushButton("Export to DXF File")
        self.btn_export_dxf.clicked.connect(self._export_dxf)
        export_layout.addWidget(self.btn_export_svg)
        export_layout.addWidget(self.btn_export_dxf)
        left_layout.addWidget(group_export)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # -------------------- Center Preview Screen --------------------
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 800, 600)
        self._init_drawing_frame()

        self.view = CustomGraphicsView(self.scene)
        main_layout.addWidget(self.view)

    def _init_drawing_frame(self) -> None:
        """Draw the drawing frame (e.g., A4 frame, title area)"""
        # Outer Frame
        frame = QGraphicsRectItem(0, 0, 800, 600)
        frame.setPen(QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine))
        self.scene.addItem(frame)

        # Title Block Area
        title_box = QGraphicsRectItem(550, 520, 240, 70)
        title_box.setPen(QPen(QColor(50, 50, 50), 1))
        self.scene.addItem(title_box)

        title_text = QGraphicsTextItem("Project: 2D CAD Title Block\nScale: 1:1")
        title_text.setPos(555, 525)
        self.scene.addItem(title_text)

    def _populate_plugins(self) -> None:
        """Set loaded plugins into the combo box"""
        self.combo_plugins.clear()
        for plugin_id, plugin in self.plugin_manager.plugins.items():
            self.combo_plugins.addItem(plugin.plugin_name, userData=plugin_id)

    def _on_plugin_changed(self) -> None:
        """Switching process for selected plugin"""
        # Clear UI
        for i in reversed(range(self.param_widget_layout.count())):
            widget = self.param_widget_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        plugin_id = self.combo_plugins.currentData()
        if plugin_id in self.plugin_manager.plugins:
            plugin = self.plugin_manager.plugins[plugin_id]
            widget = plugin.create_parameter_widget()
            self.param_widget_layout.addWidget(widget)

    def _add_shape_to_scene(self) -> None:
        """Add the shape of the currently selected plugin to the center of the Scene"""
        plugin_id = self.combo_plugins.currentData()
        plugin = self.plugin_manager.plugins.get(plugin_id)
        if not plugin:
            return

        params = plugin.get_current_parameters()
        item = plugin.generate_graphics_item(params)
        
        # Retain internal data meta-tags
        item.setData(0, plugin_id)
        item.setData(1, params)

        # Place near the center of the Scene
        item.setPos(400, 300)
        self.scene.addItem(item)
        self.placed_items.append(item)

    def _collect_placed_elements(self) -> List[Dict[str, Any]]:
        """Collect valid shape element data placed on the scene"""
        elements = []
        for item in self.placed_items:
            if item.scene() == self.scene:
                plugin_id = item.data(0)
                params = item.data(1)
                pos = item.pos()
                elements.append({
                    "plugin_id": plugin_id,
                    "params": params,
                    "position": pos,
                    "x": pos.x(),
                    "y": pos.y()
                })
        return elements

    def _save_config(self) -> None:
        """Output current placement data to config.json"""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Config", "config.json", "JSON Files (*.json)")
        if not file_path:
            return

        data = []
        for elem in self._collect_placed_elements():
            data.append({
                "plugin_id": elem["plugin_id"],
                "params": elem["params"],
                "position": [elem["x"], elem["y"]]
            })

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Done", "Configuration saved to JSON.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _load_config(self) -> None:
        """Restore placement state from config.json"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Config", "config.json", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Remove current shapes
            for item in self.placed_items:
                if item.scene():
                    self.scene.removeItem(item)
            self.placed_items.clear()

            # Restore drawing
            for node in data:
                plugin_id = node.get("plugin_id")
                params = node.get("params", {})
                pos_list = node.get("position", [400, 300])

                plugin = self.plugin_manager.plugins.get(plugin_id)
                if plugin:
                    item = plugin.generate_graphics_item(params)
                    item.setData(0, plugin_id)
                    item.setData(1, params)
                    item.setPos(pos_list[0], pos_list[1])
                    self.scene.addItem(item)
                    self.placed_items.append(item)

            QMessageBox.information(self, "Done", "Configuration restored.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    def _export_svg(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "SVG Export", "drawing.svg", "SVG Files (*.svg)")
        if file_path:
            if ExportManager.export_to_svg(self.scene, file_path):
                QMessageBox.information(self, "Success", "SVG export completed.")
            else:
                QMessageBox.critical(self, "Error", "Failed to export SVG.")

    def _export_dxf(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "DXF Export", "drawing.dxf", "DXF Files (*.dxf)")
        if file_path:
            elements = self._collect_placed_elements()
            if ExportManager.export_to_dxf(elements, self.plugin_manager, file_path):
                QMessageBox.information(self, "Success", "DXF export completed.")
            else:
                QMessageBox.critical(self, "Error", "Failed to export DXF.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

```