### Directory Structure

```text
app/
├── main.py                  # Application entry point / Main window
├── plugin_interface.py     # Plugin base class (ShapePluginInterface)
├── plugin_manager.py       # Dynamic plugin loader
├── export_manager.py       # SVG/DXF output management class
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
    """Emitter to handle Signals even in classes that do not inherit from QObject."""
    parameters_changed = Signal()

class ShapePluginInterface(ABC):
    """Abstract base class that all shape plugins must inherit from."""

    def __init__(self) -> None:
        self.signals = PluginSignalEmitter()

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """The name of the plugin displayed in the UI."""
        pass

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """A unique ID for configuration saving."""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """Generates and returns a GUI widget for parameter adjustment."""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a QGraphicsItem based on specified parameters."""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds a shape entity to the ezdxf model space (msp)."""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """Retrieves current GUI input values as a dictionary."""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Reflect an external parameter dictionary in the GUI."""
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
    """Management class that automatically discovers and loads plugins from the 'plugin' folder."""

    def __init__(self, plugin_folder: str = "plugin") -> None:
        self.plugin_folder = Path(plugin_folder)
        self.plugins: Dict[str, ShapePluginInterface] = {}
        self.ensure_plugin_folder()

    def ensure_plugin_folder(self) -> None:
        """Creates the plugin folder if it does not exist."""
        if not self.plugin_folder.exists():
            self.plugin_folder.mkdir(parents=True, exist_ok=True)
            # Generate __init__.py for packaging
            init_file = self.plugin_folder / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def discover_plugins(self) -> Dict[str, ShapePluginInterface]:
        """Scans modules within the 'plugin' folder and instantiates classes implementing ShapePluginInterface."""
        self.plugins.clear()
        
        # Scan modules under the plugin directory
        for _, module_name, is_pkg in pkgutil.iter_modules([str(self.plugin_folder)]):
            if is_pkg:
                continue
            
            full_module_name = f"{self.plugin_folder.name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # Scan classes in the module
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

### 3. `export_manager.py` (SVG / DXF Export Module)

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
    """Class responsible for exporting drawing elements to SVG and DXF files."""

    @staticmethod
    def export_to_svg(scene: QGraphicsScene, file_path: str) -> bool:
        """Outputs the content of QGraphicsScene as an SVG file."""
        try:
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            
            # Set scene boundary size as output range
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
            print(f"[ERROR] Failed to write SVG: {e}")
            return False

    @staticmethod
    def export_to_dxf(placed_elements: List[Dict[str, Any]], plugin_manager: PluginManager, file_path: str) -> bool:
        """Exports a DXF file using ezdxf from the data of placed shape objects."""
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
                    # Call the DXF output process in the plugin
                    plugin.export_to_dxf(msp, params, position)

            doc.saveas(file_path)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write DXF: {e}")
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
    """Custom rectangle item that opens a parameter editing dialog on double click."""

    def __init__(self, x: float, y: float, w: float, h: float, plugin: 'RectanglePlugin', params: Dict[str, Any]) -> None:
        super().__init__(x, y, w, h)
        self.plugin = plugin
        self.params = params
        
        # Selection/Movement flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        pen = QPen(QColor(0, 120, 215), 2.0)
        self.setPen(pen)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Displays an independent parameter editing dialog upon double-clicking."""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing")
        dialog.resize(300, 150)
        
        layout = QVBoxLayout(dialog)

        # Create form and spin boxes for the dialog individually
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

        # Execute the dialog and update parameters if OK is clicked
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = {
                "width": spin_w.value(),
                "height": spin_h.value()
            }
            self.params = new_params
            self.setData(1, new_params)  # Update metadata as well
            
            # Update the size and shape of the rectangle
            w = float(new_params["width"])
            h = float(new_params["height"])
            self.setRect(-w / 2.0, -h / 2.0, w, h)

        super().mouseDoubleClickEvent(event)


class RectanglePlugin(ShapePluginInterface):
    """Sample shape plugin that draws a rectangle."""

    def __init__(self) -> None:
        super().__init__()
        self._spin_width: QDoubleSpinBox | None = None
        self._spin_height: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Rectangle" # Translated from "矩形 (Rectangle)"

    @property
    def plugin_id(self) -> str:
        return "std.rectangle"

    def create_parameter_widget(self) -> QWidget:
        """Creates the parameter adjustment UI for the main screen."""
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

        layout.addRow("Width:", self._spin_width) # Translated from "幅 (Width):"
        layout.addRow("Height:", self._spin_height) # Translated from "高さ (Height):"

        return widget

    def generate_graphics_item(self, params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> QGraphicsItem:
        w_real = float(params.get("width", 100.0))
        h_real = float(params.get("height", 60.0))

        # Preview screen size = Real dimensions (mm) * Drawing scale * px/mm scale
        w = w_real * drawing_scale * pixel_scale
        h = h_real * drawing_scale * pixel_scale

        item = EditableRectItem(-w / 2.0, -h / 2.0, w, h, self, params)
        return item

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Generates LWPOLYLINE suitable for ezdxf."""
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

### 5. `main.py` (Main Screen / Entry Point)

```python
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsScene, QGraphicsView,
    QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QFileDialog,
    QMessageBox, QGroupBox, QGraphicsItem, QLabel, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QWheelEvent, QKeyEvent

from plugin_manager import PluginManager
from export_manager import ExportManager

class CustomGraphicsView(QGraphicsView):
    """Custom QGraphicsView equipped with zoom, pan, and Delete key functionality."""

    def __init__(self, scene: QGraphicsScene, main_window: 'MainWindow') -> None:
        super().__init__(scene)
        self.main_window = main_window
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event: QWheelEvent) -> None:
        zoom_factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(zoom_factor, zoom_factor)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                if item in self.main_window.placed_items:
                    self.main_window.placed_items.remove(item)
                self.scene().removeItem(item)
            event.accept()
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("2D CAD Design System - PySide6")
        self.resize(1280, 800)

        self.plugin_manager = PluginManager()
        self.plugin_manager.discover_plugins()
        self.placed_items: List[QGraphicsItem] = []

        self._setup_ui()
        self._populate_plugins()
        self._init_default_frame()

    def _setup_ui(self) -> None:
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # -------------------- Left Operation Panel --------------------
        left_panel = QWidget()
        left_panel.setFixedWidth(340)
        left_layout = QVBoxLayout(left_panel)

        # 0. Drawing Overall Settings Group (Scale & Pixel Scale Factor)
        group_drawing = QGroupBox("Drawing Overall Settings") # Translated from "図面全体の設定"
        drawing_layout = QVBoxLayout(group_drawing)
        
        # Drawing Scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Drawing Scale:")) # Translated from "図面縮尺:"
        self.combo_main_scale = QComboBox()
        self.combo_main_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        self.combo_main_scale.currentIndexChanged.connect(self._on_drawing_setting_changed)
        scale_layout.addWidget(self.combo_main_scale)
        drawing_layout.addLayout(scale_layout)

        # Pixel Scale Factor (px/mm)
        px_layout = QHBoxLayout()
        px_layout.addWidget(QLabel("Display Multiplier (px/mm):")) # Translated from "表示倍率 (px/mm):"
        self.spin_px_scale = QDoubleSpinBox()
        self.spin_px_scale.setRange(0.5, 20.0)
        self.spin_px_scale.setSingleStep(0.1)
        self.spin_px_scale.setValue(2.83)  # Initial value
        self.spin_px_scale.valueChanged.connect(self._on_drawing_setting_changed)
        px_layout.addWidget(self.spin_px_scale)
        drawing_layout.addLayout(px_layout)

        left_layout.addWidget(group_drawing)

        # 1. Plugin Selection Group
        group_plugin = QGroupBox("Shape/Layout Plugins") # Translated from "図形・レイアウトプラグイン"
        plugin_layout = QVBoxLayout(group_plugin)
        self.combo_plugins = QComboBox()
        self.combo_plugins.currentIndexChanged.connect(self._on_plugin_changed)
        plugin_layout.addWidget(self.combo_plugins)

        self.param_widget_container = QWidget()
        self.param_widget_layout = QVBoxLayout(self.param_widget_container)
        plugin_layout.addWidget(self.param_widget_container)

        self.btn_add_shape = QPushButton("Add to Drawing / Update") # Translated from "図面に追加 / 更新"
        self.btn_add_shape.clicked.connect(self._add_shape_to_scene)
        plugin_layout.addWidget(self.btn_add_shape)
        left_layout.addWidget(group_plugin)

        # 2. Configuration Save/Load Group
        group_config = QGroupBox("Project Management (JSON)") # Translated from "プロジェクト管理 (JSON)"
        config_layout = QVBoxLayout(group_config)
        self.btn_save_config = QPushButton("Save Settings (JSON)") # Translated from "設定保存 (JSON)"
        self.btn_save_config.clicked.connect(self._save_config)
        self.btn_load_config = QPushButton("Load Settings (JSON)") # Translated from "設定読み込み (JSON)"
        self.btn_load_config.clicked.connect(self._load_config)
        config_layout.addWidget(self.btn_save_config)
        config_layout.addWidget(self.btn_load_config)
        left_layout.addWidget(group_config)

        # 3. Export Group
        group_export = QGroupBox("Drawing Output") # Translated from "図面出力"
        export_layout = QVBoxLayout(group_export)
        self.btn_export_svg = QPushButton("Export to SVG File") # Translated from "SVGファイルへ出力"
        self.btn_export_svg.clicked.connect(self._export_svg)
        self.btn_export_dxf = QPushButton("Export to DXF File") # Translated from "DXFファイルへ出力"
        self.btn_export_dxf.clicked.connect(self._export_dxf)
        export_layout.addWidget(self.btn_export_svg)
        export_layout.addWidget(self.btn_export_dxf)
        left_layout.addWidget(group_export)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # -------------------- Central Preview Area --------------------
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 2000, 1500)

        self.view = CustomGraphicsView(self.scene, self)
        main_layout.addWidget(self.view)

    def _populate_plugins(self) -> None:
        self.combo_plugins.clear()
        for plugin_id, plugin in self.plugin_manager.plugins.items():
            self.combo_plugins.addItem(plugin.plugin_name, userData=plugin_id)

    def _on_plugin_changed(self) -> None:
        # Clear existing widgets in the container (reverse iteration to handle parent changes safely)
        for i in reversed(range(self.param_widget_layout.count())):
            widget = self.param_widget_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        plugin_id = self.combo_plugins.currentData()
        if plugin_id in self.plugin_manager.plugins:
            plugin = self.plugin_manager.plugins[plugin_id]
            widget = plugin.create_parameter_widget()
            self.param_widget_layout.addWidget(widget)

    def _getDrawingScaleFactor(self) -> float:
        """Calculates the drawing scale factor."""
        scale_str = self.combo_main_scale.currentText()
        try:
            parts = scale_str.split(":")
            if len(parts) == 2:
                return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            pass
        return 1.0

    def _getPixelScale(self) -> float:
        """Gets the pixel-to-real dimension scale factor (px/mm)."""
        return self.spin_px_scale.value()

    def _on_drawing_setting_changed(self) -> None:
        """Redraw and synchronize all shapes when the scale or display multiplier is changed."""
        drawing_scale = self._getDrawingScaleFactor()
        pixel_scale = self._getPixelScale()
        scale_str = self.combo_main_scale.currentText()

        for item in self.placed_items:
            plugin_id = item.data(0)
            params = item.data(1)
            plugin = self.plugin_manager.plugins.get(plugin_id)
            if plugin and params:
                pos = item.pos()
                
                if plugin_id == "std.drawing_frame":
                    params["scale"] = scale_str

                self.scene.removeItem(item)
                
                new_item = plugin.generate_graphics_item(
                    params, drawing_scale=drawing_scale, pixel_scale=pixel_scale
                )
                new_item.setData(0, plugin_id)
                new_item.setData(1, params)
                new_item.setPos(pos)
                
                self.scene.addItem(new_item)
                idx = self.placed_items.index(item)
                self.placed_items[idx] = new_item

    def _init_default_frame(self) -> None:
        frame_plugin = self.plugin_manager.plugins.get("std.drawing_frame")
        if frame_plugin:
            params = {"size": "A4", "orientation": "Landscape", "title": "2D Drawing Layout", "scale": "1:1"} # Translated orientation
            frame_plugin.set_parameters(params)
            item = frame_plugin.generate_graphics_item(
                params, drawing_scale=1.0, pixel_scale=self._getPixelScale()
            )
            item.setData(0, "std.drawing_frame")
            item.setData(1, params)
            item.setPos(50, 50)
            self.scene.addItem(item)
            self.placed_items.append(item)

    def _add_shape_to_scene(self) -> None:
        plugin_id = self.combo_plugins.currentData()
        plugin = self.plugin_manager.plugins.get(plugin_id)
        if not plugin:
            return

        params = plugin.get_current_parameters()
        if plugin_id == "std.drawing_frame":
            params["scale"] = self.combo_main_scale.currentText()

        drawing_scale = self._getDrawingScaleFactor()
        pixel_scale = self._getPixelScale()

        item = plugin.generate_graphics_item(
            params, drawing_scale=drawing_scale, pixel_scale=pixel_scale
        )
        
        item.setData(0, plugin_id)
        item.setData(1, params)

        item.setPos(200, 200)
        self.scene.addItem(item)
        self.placed_items.append(item)

    def _collect_placed_elements(self) -> List[Dict[str, Any]]:
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
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Settings", "config.json", "JSON Files (*.json)") # Translated title
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
            QMessageBox.information(self, "Success", "Configuration saved to JSON.") # Translated message
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}") # Translated message

    def _load_config(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Settings", "config.json", "JSON Files (*.json)") # Translated title
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in self.placed_items:
                if item.scene():
                    self.scene.removeItem(item)
            self.placed_items.clear()

            # Handle drawing frame scale setting first
            frame_config = next((node for node in data if node.get("plugin_id") == "std.drawing_frame"), None)
            if frame_config:
                p = frame_config.get("params", {})
                s_str = p.get("scale", "1:1")
                idx = self.combo_main_scale.findText(s_str)
                if idx >= 0:
                    self.combo_main_scale.blockSignals(True)
                    self.combo_main_scale.setCurrentIndex(idx)
                    self.combo_main_scale.blockSignals(False)

            drawing_scale = self._getDrawingScaleFactor()
            pixel_scale = self._getPixelScale()

            for node in data:
                plugin_id = node.get("plugin_id")
                params = node.get("params", {})
                pos_list = node.get("position", [200, 200])

                plugin = self.plugin_manager.plugins.get(plugin_id)
                if plugin:
                    item = plugin.generate_graphics_item(
                        params, drawing_scale=drawing_scale, pixel_scale=pixel_scale
                    )
                    item.setData(0, plugin_id)
                    item.setData(1, params)
                    item.setPos(pos_list[0], pos_list[1])
                    self.scene.addItem(item)
                    self.placed_items.append(item)

            QMessageBox.information(self, "Success", "Configuration restored.") # Translated message
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load configuration: {e}") # Translated message

    def _export_svg(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Save SVG Output", "drawing.svg", "SVG Files (*.svg)") # Translated title
        if file_path:
            if ExportManager.export_to_svg(self.scene, file_path):
                QMessageBox.information(self, "Success", "SVG export completed successfully.") # Translated message
            else:
                QMessageBox.critical(self, "Error", "Failed to export SVG.") # Translated message

    def _export_dxf(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Save DXF Output", "drawing.dxf", "DXF Files (*.dxf)") # Translated title
        if file_path:
            elements = self._collect_placed_elements()
            if ExportManager.export_to_dxf(elements, self.plugin_manager, file_path):
                QMessageBox.information(self, "Success", "DXF export completed successfully.") # Translated message
            else:
                QMessageBox.critical(self, "Error", "Failed to export DXF.") # Translated message


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```
