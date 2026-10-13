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

        form_layout.addRow("Diameter:", spin_dia)
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
        return "Circle"

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

        layout.addRow("Diameter:", self._spin_diameter)

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
