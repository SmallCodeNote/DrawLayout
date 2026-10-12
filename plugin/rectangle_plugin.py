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
