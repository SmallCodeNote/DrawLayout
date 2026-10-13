### Directory Structure

```text
app/
├── main.py                  # Application entry point / Main window
├── plugin_interface.py     # Base class for plugins (ShapePluginInterface)
├── plugin_manager.py       # Dynamic plugin loader
├── export_manager.py       # SVG/DXF output management class
└── plugin/                 # Plugin storage folder
    ├── __init__.py
    ├── circle_plugin.py
    ├── drawing_frame_plugin.py
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
    """An emitter that allows Signals to be handled even if not inheriting from QObject."""
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
        """A unique ID for saving settings."""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """Generates and returns the GUI widget for parameter adjustment."""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a QGraphicsItem based on specified parameters."""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds the shape entity to the model space (msp) of ezdxf."""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """Retrieves current GUI input values as a dictionary."""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Reflect external parameter dictionaries onto the GUI."""
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
    """Manages automatic dynamic detection and loading of plugins from the 'plugin' folder."""

    def __init__(self, plugin_folder: str = "plugin") -> None:
        self.plugin_folder = Path(plugin_folder)
        self.plugins: Dict[str, ShapePluginInterface] = {}
        self.ensure_plugin_folder()

    def ensure_plugin_folder(self) -> None:
        """Creates the plugin folder if it does not exist."""
        if not self.plugin_folder.exists():
            self.plugin_folder.mkdir(parents=True, exist_ok=True)
            # Generates __init__.py for package definition
            init_file = self.plugin_folder / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def discover_plugins(self) -> Dict[str, ShapePluginInterface]:
        """Scans the plugin folder and instantiates classes implementing ShapePluginInterface."""
        self.plugins.clear()
        
        # Searches for modules within the 'plugin' directory
        for _, module_name, is_pkg in pkgutil.iter_modules([str(self.plugin_folder)]):
            if is_pkg:
                continue
            
            full_module_name = f"{self.plugin_folder.name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # Scans classes within the module
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
from typing import Any, List
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene
import ezdxf

class ExportManager:
    """Manages exporting to SVG and DXF files."""

    @staticmethod
    def export_to_svg(scene: QGraphicsScene, file_path: str) -> bool:
        """Outputs the content of a QGraphicsScene as an SVG file."""
        try:
            generator = QSvgGenerator()
            generator.setFileName(file_path)
            
            rect = scene.sceneRect()
            generator.setSize(rect.size().toSize())
            generator.setViewBox(rect)

            painter = QPainter(generator)
            scene.render(painter)
            painter.end()
            return True
        except Exception as e:
            print(f"SVG Export Error: {e}")
            return False

    @staticmethod
    def export_to_dxf(elements: list, plugin_manager: Any, file_path: str, pixel_scale: float = 2.83, scene_height: float = 1500.0) -> bool:
        """Outputs a DXF file from the list of placed elements (considering Y-axis inversion)."""
        try:
            doc = ezdxf.new(dxfversion="R2010")
            msp = doc.modelspace()

            for elem in elements:
                plugin_id = elem.get("plugin_id")
                params = elem.get("params", {})
                pos = elem.get("position")  # QPointF or [x, y]
                
                if pos:
                    x_px = pos.x() if hasattr(pos, "x") else pos[0]
                    y_px = pos.y() if hasattr(pos, "y") else pos[1]
                    
                   # X remains the same, Y is inverted from Qt (top-origin) to DXF (bottom-origin)
                    x_mm = x_px / pixel_scale
                    y_mm = (scene_height - y_px) / pixel_scale
                    
                    position_mm = QPointF(x_mm, y_mm)
                else:
                    position_mm = QPointF(0, 0)

                plugin = plugin_manager.plugins.get(plugin_id)
                if plugin and hasattr(plugin, "export_to_dxf"):
                    plugin.export_to_dxf(msp, params, position_mm)

            doc.saveas(file_path)
            return True
        except Exception as e:
            print(f"DXF Export Error: {e}")
            return False
```

---

### 4-1. `plugin/circle_plugin.py` (Sample Plugin - Circle)

```python
from typing import Dict, Any
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QGraphicsItem, 
    QGraphicsEllipseItem, QDialog, QVBoxLayout, QDialogButtonBox
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen, QColor, QMouseEvent
import ezdxf

from plugin_interface import ShapePluginInterface

class EditableCircleItem(QGraphicsEllipseItem):
    """A custom circular item that allows editing the diameter parameter via double-click."""

    def __init__(self, x: float, y: float, w: float, h: float, plugin: 'CirclePlugin', params: Dict[str, Any]) -> None:
        super().__init__(x, y, w, h)
        self.plugin = plugin
        self.params = params
        
        # Selection and movement flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        pen = QPen(QColor(0, 120, 215), 2.0)
        self.setPen(pen)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Displays a separate diameter editing dialog on double-click."""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing")
        dialog.resize(300, 120)
        
        layout = QVBoxLayout(dialog)

        # Creates form and spin box for the dialog
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        spin_dia = QDoubleSpinBox()
        spin_dia.setRange(0.1, 5000.0)
        spin_dia.setValue(float(self.params.get("diameter", 80.0)))
        spin_dia.setSuffix(" mm")

        form_layout.addRow("Diameter:", spin_dia) # Translated label
        layout.addWidget(form_widget)

        # OK / Cancel buttons for the dialog
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Executes the dialog, and if accepted, updates parameters and redraw shape
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_diameter = spin_dia.value()
            new_params = {"diameter": new_diameter}
            self.params = new_params
            self.setData(1, new_params)  # Update metadata
            
            # Updates the circle size (specified as a rectangle where width and height are equal to diameter)
            self.setRect(-new_diameter / 2.0, -new_diameter / 2.0, new_diameter, new_diameter)

        super().mouseDoubleClickEvent(event)


class CirclePlugin(ShapePluginInterface):
    """A shape plugin that draws a circle by specifying its diameter."""

    def __init__(self) -> None:
        super().__init__()
        self._spin_diameter: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Circle" # Translated name

    @property
    def plugin_id(self) -> str:
        return "std.circle"

    def create_parameter_widget(self) -> QWidget:
        """Creates the parameter adjustment UI for the main screen."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self._spin_diameter = QDoubleSpinBox()
        self._spin_diameter.setRange(0.1, 5000.0)
        self._spin_diameter.setValue(80.0)
        self._spin_diameter.setSuffix(" mm")
        self._spin_diameter.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        layout.addRow("Diameter:", self._spin_diameter) # Translated label

        return widget

    def generate_graphics_item(self, params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> QGraphicsItem:
        """Generates a circle item reflecting the specified scale factor."""
        dia_real = float(params.get("diameter", 80.0))
        dia = dia_real * drawing_scale * pixel_scale

        item = EditableCircleItem(-dia / 2.0, -dia / 2.0, dia, dia, self, params)
        return item

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds a circle entity to the ezdxf model space."""
        dia = float(params.get("diameter", 80.0))
        radius = dia / 2.0
        cx, cy = position.x(), position.y()

        # Specifies center coordinates and radius for the circle
        msp.add_circle((cx, cy), radius)

    def get_current_parameters(self) -> Dict[str, Any]:
        return {
            "diameter": self._spin_diameter.value() if self._spin_diameter else 80.0,
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        if self._spin_diameter and "diameter" in params:
            self._spin_diameter.setValue(float(params["diameter"]))
```

---

### 4-2. `plugin/drawing_frame_plugin.py` (Sample Plugin - Drawing Frame)

```python
from typing import Dict, Any, Tuple
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QLineEdit, QGraphicsItem, 
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItemGroup,
    QDialog, QVBoxLayout, QDialogButtonBox
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen, QColor, QMouseEvent
import ezdxf

from plugin_interface import ShapePluginInterface

class EditableDrawingFrameGroup(QGraphicsItemGroup):
    """A custom drawing frame group that allows editing paper size, orientation, title, and scale via double-click."""

    def __init__(self, plugin: 'DrawingFramePlugin', params: Dict[str, Any]) -> None:
        super().__init__()
        self.plugin = plugin
        self.params = params
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Displays a dialog for editing paper settings and scale on double-click."""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing")
        dialog.resize(320, 240)
        
        layout = QVBoxLayout(dialog)
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        # 1. Paper Size selection
        combo_size = QComboBox()
        combo_size.addItems(["A4", "A3"])
        current_size = self.params.get("size", "A4")
        idx = combo_size.findText(current_size)
        if idx >= 0:
            combo_size.setCurrentIndex(idx)

        # 2. Orientation selection
        combo_orient = QComboBox()
        combo_orient.addItems(["Landscape", "Portrait"]) # Translated options
        current_orient = self.params.get("orientation", "Landscape")
        idx2 = combo_orient.findText(current_orient)
        if idx2 >= 0:
            combo_orient.setCurrentIndex(idx2)

        # 3. Title information input
        line_title = QLineEdit()
        line_title.setText(self.params.get("title", "2D Drawing Layout")) # Translated default title

        # 4. Scale selection (Scale Factor)
        combo_scale = QComboBox()
        combo_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        current_scale = self.params.get("scale", "1:1")
        idx3 = combo_scale.findText(current_scale)
        if idx3 >= 0:
            combo_scale.setCurrentIndex(idx3)

        form_layout.addRow("Paper Size:", combo_size) # Translated label
        form_layout.addRow("Orientation:", combo_orient) # Translated label
        form_layout.addRow("Title:", line_title) # Translated label
        form_layout.addRow("Scale (Ratio):", combo_scale) # Translated label
        layout.addWidget(form_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = {
                "size": combo_size.currentText(),
                "orientation": combo_orient.currentText(),
                "title": line_title.text() or "2D Drawing Layout",
                "scale": combo_scale.currentText()
            }
            self.params = new_params
            self.setData(1, new_params)  # Update metadata
            
            # Synchronize with the main window's scale combobox
            scene = self.scene()
            if scene and hasattr(scene, "views") and scene.views():
                main_win = scene.views()[0].parent()
                if hasattr(main_win, "combo_main_scale"):
                    idx_main = main_win.combo_main_scale.findText(new_params["scale"])
                    if idx_main >= 0:
                        main_win.combo_main_scale.blockSignals(True)
                        main_win.combo_main_scale.setCurrentIndex(idx_main)
                        main_win.combo_main_scale.blockSignals(False)

            # Clear existing child items
            scene_ptr = self.scene()
            for child in self.childItems():
                self.removeFromGroup(child)
                if scene_ptr:
                    scene_ptr.removeItem(child)
            
            # Regenerate parts with new parameters (using default pixel scale)
            width, height = self.plugin._get_dimensions(new_params)
            
            frame = QGraphicsRectItem(0, 0, width, height)
            frame.setPen(QPen(QColor(100, 100, 100), 1.5, Qt.PenStyle.DashLine))
            self.addToGroup(frame)

            tb_w, tb_h = 240.0, 70.0
            tb_x = width - tb_w - 20
            tb_y = height - tb_h - 20
            
            title_box = QGraphicsRectItem(tb_x, tb_y, tb_w, tb_h)
            title_box.setPen(QPen(QColor(50, 50, 50), 1))
            self.addToGroup(title_box)

            size_str = new_params["size"]
            orient_str = new_params["orientation"]
            title_str = new_params["title"]
            scale_str = new_params["scale"]
            
            text_item = QGraphicsTextItem(f"Title: {title_str}\nSize: {size_str} ({orient_str})\nScale: {scale_str}") # Translated text content
            text_item.setPos(tb_x + 5, tb_y + 5)
            text_item.setDefaultTextColor(QColor(30, 30, 30))
            self.addToGroup(text_item)

        super().mouseDoubleClickEvent(event)


class DrawingFramePlugin(ShapePluginInterface):
    """A plugin that generates a drawing frame and title block by selecting paper size, orientation, title, and scale."""

    PAGE_SIZES = {
        "A4": (210.0, 297.0),
        "A3": (297.0, 420.0),
    }

    def __init__(self) -> None:
        super().__init__()
        self._combo_size: QComboBox | None = None
        self._combo_orientation: QComboBox | None = None
        self._line_title: QLineEdit | None = None
        self._combo_scale: QComboBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Drawing Frame" # Translated name

    @property
    def plugin_id(self) -> str:
        return "std.drawing_frame"

    def create_parameter_widget(self) -> QWidget:
        """Creates the parameter adjustment UI for the main screen."""
        widget = QWidget()
        layout = QFormLayout(widget)

        self._combo_size = QComboBox()
        self._combo_size.addItems(["A4", "A3"])
        self._combo_size.currentIndexChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._combo_orientation = QComboBox()
        # Translated options for orientation in the UI
        self._combo_orientation.addItems(["Landscape", "Portrait"]) 
        self._combo_orientation.currentIndexChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._line_title = QLineEdit()
        self._line_title.setText("2D Drawing Layout") # Translated default title
        self._line_title.textChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._combo_scale = QComboBox()
        self._combo_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        self._combo_scale.currentIndexChanged.connect(lambda: self.signals.parameters_changed.emit())

        layout.addRow("Paper Size:", self._combo_size) # Translated label
        layout.addRow("Orientation:", self._combo_orientation) # Translated label
        layout.addRow("Title:", self._line_title) # Translated label
        layout.addRow("Scale (Ratio):", self._combo_scale) # Translated label

        return widget

    def _get_dimensions(self, params: Dict[str, Any], pixel_scale: float = 2.83) -> Tuple[float, float]:
        """Calculates the screen-based pixel size by multiplying the actual dimensions (mm) of the paper with the pixel scale."""
        size_str = params.get("size", "A4")
        orient_str = params.get("orientation", "Landscape") # Normalized orientation string
        
        base_w, base_h = self.PAGE_SIZES.get(size_str, (210.0, 297.0))
        
        if "Portrait" in orient_str: # Check for Portrait instead of Japanese '横'/'縦' if the UI is translated
            return base_w * pixel_scale, base_h * pixel_scale
        else:
            # Landscape orientation (Width = Height side)
            return base_h * pixel_scale, base_w * pixel_scale

    def generate_graphics_item(self, params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> QGraphicsItem:
        """Generates an editable custom drawing frame group."""
        width, height = self._get_dimensions(params, pixel_scale)
        group = EditableDrawingFrameGroup(self, params)
        
        # 1. Paper outer boundary (frame)
        frame = QGraphicsRectItem(0, 0, width, height)
        frame.setPen(QPen(QColor(100, 100, 100), 1.5, Qt.PenStyle.DashLine))
        group.addToGroup(frame)

        # 2. Title block frame
        tb_w, tb_h = 240.0, 70.0
        tb_x = width - tb_w - 20
        tb_y = height - tb_h - 20
        
        title_box = QGraphicsRectItem(tb_x, tb_y, tb_w, tb_h)
        title_box.setPen(QPen(QColor(50, 50, 50), 1))
        group.addToGroup(title_box)

        # 3. Text content
        size_str = params.get("size", "A4")
        orient_str = params.get("orientation", "Landscape") # Normalized orientation string
        title_str = params.get("title", "2D Drawing Layout")
        scale_str = params.get("scale", "1:1")
        
        text_item = QGraphicsTextItem(f"Title: {title_str}\nSize: {size_str} ({orient_str})\nScale: {scale_str}") # Translated text content
        text_item.setPos(tb_x + 5, tb_y + 5)
        text_item.setDefaultTextColor(QColor(30, 30, 30))
        group.addToGroup(text_item)

        return group

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Generates the drawing frame and title block text in real dimensions (mm) for DXF output."""
        size_str = params.get("size", "A4")
        orient_str = params.get("orientation", "Landscape") # Normalized orientation string
        title_str = params.get("title", "2D Drawing Layout")
        scale_str = params.get("scale", "1:1")
        
        base_w, base_h = self.PAGE_SIZES.get(size_str, (210.0, 297.0))
        
        if "Portrait" in orient_str:
            w_mm, h_mm = base_w, base_h  # Width=short side, Height=long side
        else:
            w_mm, h_mm = base_h, base_w  # Width=long side, Height=short side

        x, y = position.x(), position.y()
        
        # 1. Paper outer boundary (polyline)
        x1, y1 = x, y
        x2, y2 = x + w_mm, y
        x3, y3 = x + w_mm, y - h_mm
        x4, y4 = x, y - h_mm

        points = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
        msp.add_lwpolyline(points, close=True)

        # 2. Title block frame (approximate size/position based on mm conversion from preview px)
        tb_w, tb_h = 85.0, 25.0  
        tb_x = x + w_mm - tb_w - 10
        tb_y = y - h_mm + 10     # Slightly above the bottom edge of the frame
        
        tb_points = [
            (tb_x, tb_y + tb_h),
            (tb_x + tb_w, tb_y + tb_h),
            (tb_x + tb_w, tb_y),
            (tb_x, tb_y)
        ]
        msp.add_lwpolyline(tb_points, close=True)

        # 3. Adding text (ezdxf.add_text)
        text_style = {"height": 3.5, "layer": "0"}  # Character height 3.5mm
        
        msp.add_text(f"Title: {title_str}", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 17)) # Translated text content
        msp.add_text(f"Size: {size_str} ({orient_str})", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 10)) # Translated text content
        msp.add_text(f"Scale: {scale_str}", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 3)) # Translated text content

    def get_current_parameters(self) -> Dict[str, Any]:
        return {
            "size": self._combo_size.currentText() if self._combo_size else "A4",
            "orientation": self._combo_orientation.currentText() if self._combo_orientation else "Landscape", # Normalized orientation string
            "title": self._line_title.text() if self._line_title else "2D Drawing Layout",
            "scale": self._combo_scale.currentText() if self._combo_scale else "1:1",
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        if self._combo_size and "size" in params:
            idx = self._combo_size.findText(params["size"])
            if idx >= 0:
                self._combo_size.setCurrentIndex(idx)
        if self._combo_orientation and "orientation" in params:
            # Handle both Japanese/English versions of orientation input for robustness
            target = params["orientation"] if any(o in target for o in ["Landscape", "Portrait"]) else "Landscape" # Fallback logic based on expected values
            idx = self._combo_orientation.findText(target) 
            if idx >= 0:
                self._combo_orientation.setCurrentIndex(idx)
        if self._line_title and "title" in params:
            self._line_title.setText(params["title"])
        if self._combo_scale and "scale" in params:
            idx = self._combo_scale.findText(params["scale"])
            if idx >= 0:
                self._combo_scale.setCurrentIndex(idx)
```

---

### 4-3. `plugin/rectangle_plugin.py` (Sample Plugin - Rectangle)

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
    """A custom rectangular item that opens a parameter editing dialog on double-click."""

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
        """Displays a separate parameter editing dialog on double-click."""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing") # Translated title
        dialog.resize(300, 150)
        
        layout = QVBoxLayout(dialog)

        # Creates form and spin boxes for the dialog
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

        form_layout.addRow("Width:", spin_w) # Translated label
        form_layout.addRow("Height:", spin_h) # Translated label
        layout.addWidget(form_widget)

        # OK / Cancel buttons for the dialog
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Executes the dialog, and if accepted, updates parameters and redraw shape
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = {
                "width": spin_w.value(),
                "height": spin_h.value()
            }
            self.params = new_params
            self.setData(1, new_params)  # Update metadata

            # Updates the rectangle size and shape
            w = float(new_params["width"])
            h = float(new_params["height"])
            self.setRect(-w / 2.0, -h / 2.0, w, h)

        super().mouseDoubleClickEvent(event)


class RectanglePlugin(ShapePluginInterface):
    """A sample shape plugin that draws a rectangle."""

    def __init__(self) -> None:
        super().__init__()
        self._spin_width: QDoubleSpinBox | None = None
        self._spin_height: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Rectangle" # Translated name

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

        layout.addRow("Width:", self._spin_width) # Translated label
        layout.addRow("Height:", self._spin_height) # Translated label

        return widget

    def generate_graphics_item(self, params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> QGraphicsItem:
        w_real = float(params.get("width", 100.0))
        h_real = float(params.get("height", 60.0))

        # Preview screen size = Real dimensions (mm) * Drawing Scale * px/mm scale factor
        w = w_real * drawing_scale * pixel_scale
        h = h_real * drawing_scale * pixel_scale

        item = EditableRectItem(-w / 2.0, -h / 2.0, w, h, self, params)
        return item

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        w = float(params.get("width", 100.0))
        h = float(params.get("height", 60.0))
        cx, cy = position.x(), position.y()

        # Adjust coordinates for DXF model space (assuming center-based preview)
        x1, y1 = cx - w / 2.0, cy - h / 2.0 # Bottom Left in Qt view coords if Y is inverted later by export_manager
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

### 5. `main.py` (Main Window / Entry Point)

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
    """A custom QGraphicsView equipped with zoom, pan, and Delete key functionality."""

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
    """The main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("2D CAD Design System - PySide6") # Translated title
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

        # 0. Drawing overall settings group (Scale & Pixel Scale Factor)
        group_drawing = QGroupBox("Drawing Overall Settings") # Translated title
        drawing_layout = QVBoxLayout(group_drawing)
        
        # Drawing scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Drawing Scale:")) # Translated label
        self.combo_main_scale = QComboBox()
        self.combo_main_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        self.combo_main_scale.currentIndexChanged.connect(self._on_drawing_setting_changed)
        scale_layout.addWidget(self.combo_main_scale)
        drawing_layout.addLayout(scale_layout)

        # Pixel scale factor (px/mm)
        px_layout = QHBoxLayout()
        px_layout.addWidget(QLabel("Display Multiplier (px/mm):")) # Translated label
        self.spin_px_scale = QDoubleSpinBox()
        self.spin_px_scale.setRange(0.5, 20.0)
        self.spin_px_scale.setSingleStep(0.1)
        self.spin_px_scale.setValue(2.83)  # Initial value
        self.spin_px_scale.valueChanged.connect(self._on_drawing_setting_changed)
        px_layout.addWidget(self.spin_px_scale)
        drawing_layout.addLayout(px_layout)

        left_layout.addWidget(group_drawing)

        # 1. Plugin selection group
        group_plugin = QGroupBox("Shape / Layout Plugins") # Translated title
        plugin_layout = QVBoxLayout(group_plugin)
        self.combo_plugins = QComboBox()
        self.combo_plugins.currentIndexChanged.connect(self._on_plugin_changed)
        plugin_layout.addWidget(self.combo_plugins)

        self.param_widget_container = QWidget()
        self.param_widget_layout = QVBoxLayout(self.param_widget_container)
        plugin_layout.addWidget(self.param_widget_container)

        self.btn_add_shape = QPushButton("Add / Update Drawing") # Translated button text
        self.btn_add_shape.clicked.connect(self._add_shape_to_scene)
        plugin_layout.addWidget(self.btn_add_shape)
        left_layout.addWidget(group_plugin)

        # 2. Configuration save/load group
        group_config = QGroupBox("Project Management (JSON)") # Translated title
        config_layout = QVBoxLayout(group_config)
        self.btn_save_config = QPushButton("Save Settings (JSON)") # Translated button text
        self.btn_save_config.clicked.connect(self._save_config)
        self.btn_load_config = QPushButton("Load Settings (JSON)") # Translated button text
        self.btn_load_config.clicked.connect(self._load_config)
        config_layout.addWidget(self.btn_save_config)
        config_layout.addWidget(self.btn_load_config)
        left_layout.addWidget(group_config)

        # 3. Export group
        group_export = QGroupBox("Drawing Output") # Translated title
        export_layout = QVBoxLayout(group_export)
        self.btn_export_svg = QPushButton("Export to SVG File") # Translated button text
        self.btn_export_svg.clicked.connect(self._export_svg)
        self.btn_export_dxf = QPushButton("Export to DXF File") # Translated button text
        self.btn_export_dxf.clicked.connect(self._export_dxf)
        export_layout.addWidget(self.btn_export_svg)
        export_layout.addWidget(self.btn_export_dxf)
        left_layout.addWidget(group_export)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # -------------------- Central Preview Screen --------------------
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 2000, 1500) # Initial scene dimensions

        self.view = CustomGraphicsView(self.scene, self)
        main_layout.addWidget(self.view)

    def _populate_plugins(self) -> None:
        """Populates the plugin selection dropdown menu."""
        self.combo_plugins.clear()
        for plugin_id, plugin in self.plugin_manager.plugins.items():
            # Stores (Plugin Name, Plugin ID)
            self.combo_plugins.addItem(plugin.plugin_name, userData=plugin_id)

    def _on_plugin_changed(self) -> None:
        """Switches the parameter widget when a new plugin is selected."""
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
        """Calculates the drawing scale factor (e.g., 1/2 for 1:2)."""
        scale_str = self.combo_main_scale.currentText()
        try:
            parts = scale_str.split(":")
            if len(parts) == 2:
                return float(parts[0]) / float(parts[1])
        except (ValueError, ZeroDivisionError):
            pass
        return 1.0

    def _getPixelScale(self) -> float:
        """Retrieves the pixel-to-real unit scale factor (px/mm)."""
        return self.spin_px_scale.value()

    def _on_drawing_setting_changed(self) -> None:
        """Redraws all shapes to synchronize with changes in drawing scale or display multiplier."""
        drawing_scale = self._getDrawingScaleFactor()
        pixel_scale = self._getPixelScale()
        scale_str = self.combo_main_scale.currentText()

        for item in self.placed_items:
            plugin_id = item.data(0)
            params = item.data(1)
            plugin = self.plugin_manager.plugins.get(plugin_id)
            if plugin and params:
                pos = item.pos()
                
                # Update scale parameter for the frame if it's changed globally
                if plugin_id == "std.drawing_frame":
                    params["scale"] = scale_str

                self.scene.removeItem(item) # Remove old item
                
                new_item = plugin.generate_graphics_item(
                    params, drawing_scale=drawing_scale, pixel_scale=pixel_scale
                )
                new_item.setData(0, plugin_id)
                new_item.setData(1, params)
                new_item.setPos(pos) # Maintain original position
                
                self.scene.addItem(new_item)
                idx = self.placed_items.index(item)
                self.placed_items[idx] = new_item

    def _init_default_frame(self) -> None:
        """Initializes a default drawing frame upon startup."""
        frame_plugin = self.plugin_manager.plugins.get("std.drawing_frame")
        if frame_plugin:
            params = {"size": "A4", "orientation": "Landscape", "title": "2D Drawing Layout", "scale": "1:1"}
            frame_plugin.set_parameters(params)
            item = frame_plugin.generate_graphics_item(
                params, drawing_scale=1.0, pixel_scale=self._getPixelScale()
            )
            item.setData(0, "std.drawing_frame")
            item.setData(1, params)
            item.setPos(50, 50) # Default position
            self.scene.addItem(item)
            self.placed_items.append(item)

    def _add_shape_to_scene(self) -> None:
        """Adds a new shape to the scene based on selected plugin parameters."""
        plugin_id = self.combo_plugins.currentData()
        plugin = self.plugin_manager.plugins.get(plugin_id)
        if not plugin:
            return

        params = plugin.get_current_parameters()
        # Ensure the frame's scale reflects global settings when adding/updating it
        if plugin_id == "std.drawing_frame":
            params["scale"] = self.combo_main_scale.currentText()

        drawing_scale = self._getDrawingScaleFactor()
        pixel_scale = self._getPixelScale()

        item = plugin.generate_graphics_item(
            params, drawing_scale=drawing_scale, pixel_scale=pixel_scale
        )
        
        item.setData(0, plugin_id) # Plugin ID stored as data(0)
        item.setData(1, params)    # Parameters stored as data(1)

        item.setPos(200, 200) # Default placement for new items
        self.scene.addItem(item)
        self.placed_items.append(item)

    def _collect_placed_elements(self) -> List[Dict[str, Any]]:
        """Collect data (ID, parameters, position) from all placed items."""
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
        """Saves the current scene configuration to a JSON file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Configuration", "config.json", "JSON Files (*.json)")
        if not file_path:
            return

        data = []
        for elem in self._collect_placed_elements():
            data.append({
                "plugin_id": elem["plugin_id"],
                "params": elem["params"],
                "position": [elem["x"], elem["y"]] # Store position as list for JSON serialization
            })

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Success", "Configuration saved to JSON.") # Translated message
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}") # Translated message

    def _load_config(self) -> None:
        """Loads a scene configuration from a JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Configuration", "config.json", "JSON Files (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Clear existing items before loading new ones
            for item in self.placed_items:
                if item.scene():
                    self.scene.removeItem(item)
            self.placed_items.clear()

            # Load global drawing frame settings first (to update scale combobox)
            for node in data:
                if node.get("plugin_id") == "std.drawing_frame":
                    p = node.get("params", {})
                    s_str = p.get("scale", "1:1")
                    idx = self.combo_main_scale.findText(s_str)
                    if idx >= 0:
                        self.combo_main_scale.blockSignals(True)
                        self.combo_main_scale.setCurrentIndex(idx)
                        self.combo_main_scale.blockSignals(False)

            drawing_scale = self._getDrawingScaleFactor()
            pixel_scale = self._getPixelScale()

            # Recreate all items from the loaded data
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
        """Exports the current scene content to an SVG file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "SVG Export", "drawing.svg", "SVG Files (*.svg)")
        if file_path:
            if ExportManager.export_to_svg(self.scene, file_path):
                QMessageBox.information(self, "Success", "SVG export complete.") # Translated message
            else:
                QMessageBox.critical(self, "Error", "Failed to export SVG.") # Translated message

    def _export_dxf(self) -> None:
        """Exports all placed items into a DXF file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "DXF Export", "drawing.dxf", "DXF Files (*.dxf)")
        if file_path:
            elements = self._collect_placed_elements()
            scene_height = self.scene.sceneRect().height()  # Get the overall scene height
            
            if ExportManager.export_to_dxf(elements, self.plugin_manager, file_path, pixel_scale=self._getPixelScale(), scene_height=scene_height):
                QMessageBox.information(self, "Success", "DXF export complete.") # Translated message
            else:
                QMessageBox.critical(self, "Error", "Failed to export DXF.") # Translated message


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
```
