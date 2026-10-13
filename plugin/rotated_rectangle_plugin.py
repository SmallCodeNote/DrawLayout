from typing import Dict, Any, Tuple
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QGraphicsItem, 
    QGraphicsPolygonItem, QGraphicsLineItem, QGraphicsTextItem,
    QDialog, QVBoxLayout, QDialogButtonBox, QStyle
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPen, QColor, QMouseEvent, QPolygonF, QPainter
import math
import ezdxf

from plugin_interface import ShapePluginInterface

class DraggableTextItem(QGraphicsTextItem):
    """A text item that can be freely moved by dragging with the mouse."""

    def __init__(self, text: str, parent: QGraphicsItem = None) -> None:
        super().__init__(text, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class EditableRotatedRectItem(QGraphicsPolygonItem):
    """An item that displays the main rotated rectangle centered at a fixed point and draws dimension lines/auxiliary lines clearly outside."""

    def __init__(self, plugin: 'RotatedRectanglePlugin', params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> None:
        super().__init__()
        self.plugin = plugin
        self.params = params
        self.drawing_scale = drawing_scale
        self.pixel_scale = pixel_scale
        
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        self.child_lines = []
        self.child_texts = []
        
        # Ensure drawing is executed upon initialization
        self.update_geometry_and_content()

    def paint(self, painter: QPainter, option: Any, widget: QWidget = None) -> None:
        # Prevent the display of Qt's standard "selection bounding box" (dashed border)
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def update_geometry_and_content(self) -> None:
        """Construct the rectangle body and external dimension lines/texts based on parameters."""
        # Clear existing child items
        for line in self.child_lines:
            if line.scene():
                line.scene().removeItem(line)
        self.child_lines.clear()

        for t_item in self.child_texts:
            if t_item.scene():
                t_item.scene().removeItem(t_item)
        self.child_texts.clear()

        w_real = float(self.params.get("width", 100.0))
        h_real = float(self.params.get("height", 50.0))
        angle_deg = float(self.params.get("angle", 30.0))

        w = w_real * self.drawing_scale * self.pixel_scale
        h = h_real * self.drawing_scale * self.pixel_scale
        rad = math.radians(angle_deg)

        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        hw, hh = w / 2.0, h / 2.0
        
        # Four vertices relative to center (0,0)
        # 0: bottom-left, 1: bottom-right, 2: top-right, 3: top-left
        local_p0 = QPointF(-hw * cos_a + hh * sin_a, -hw * sin_a - hh * cos_a)
        local_p1 = QPointF(hw * cos_a + hh * sin_a, hw * sin_a - hh * cos_a)
        local_p2 = QPointF(hw * cos_a - hh * sin_a, hw * sin_a + hh * cos_a)
        local_p3 = QPointF(-hw * cos_a - hh * sin_a, -hw * sin_a + hh * cos_a)

        # 1. Draw the outline of the rotated rectangle (transparent interior)
        polygon = QPolygonF([local_p0, local_p1, local_p2, local_p3])
        self.setPolygon(polygon)
        self.setPen(QPen(QColor(20, 20, 20), 1.5))
        self.setBrush(Qt.BrushStyle.NoBrush)

        # 2. Draw the preview of dimension lines/auxiliary lines (placed outside reliably)
        # Ensure correct direction for outward normal vector
        offset = 25.0
        nx, ny = sin_a, -cos_a  # Outward normal direction for base edge (p0-p1)

        dim_p0 = QPointF(local_p0.x() + nx * offset, local_p0.y() + ny * offset)
        dim_p1 = QPointF(local_p1.x() + nx * offset, local_p1.y() + ny * offset)

        dim_pen = QPen(QColor(100, 100, 100), 0.8, Qt.PenStyle.DashLine)
        ext1 = QGraphicsLineItem(local_p0.x(), local_p0.y(), dim_p0.x() + nx * 5, dim_p0.y() + ny * 5, self)
        ext2 = QGraphicsLineItem(local_p1.x(), local_p1.y(), dim_p1.x() + nx * 5, dim_p1.y() + ny * 5, self)
        ext1.setPen(dim_pen)
        ext2.setPen(dim_pen)
        self.child_lines.extend([ext1, ext2])

        main_dim_pen = QPen(QColor(40, 40, 40), 1.0)
        dim_line = QGraphicsLineItem(dim_p0.x(), dim_p0.y(), dim_p1.x(), dim_p1.y(), self)
        dim_line.setPen(main_dim_pen)
        self.child_lines.append(dim_line)

        text_l1 = DraggableTextItem(f"L1: {w_real}mm", self)
        text_l1.setDefaultTextColor(QColor(20, 20, 20))
        mid_x = (dim_p0.x() + dim_p1.x()) / 2.0 + nx * 4
        mid_y = (dim_p0.y() + dim_p1.y()) / 2.0 + ny * 4
        text_l1.setPos(mid_x - 15, mid_y - 10)
        self.child_texts.append(text_l1)

        # Dimension line for the other side L2 (right side / outward offset)
        offset_h = 25.0
        nx_h, ny_h = cos_a, sin_a  # Outward normal direction for edge (p1-p2)

        dim_q0 = QPointF(local_p1.x() + nx_h * offset_h, local_p1.y() + ny_h * offset_h)
        dim_q1 = QPointF(local_p2.x() + nx_h * offset_h, local_p2.y() + ny_h * offset_h)

        ext_h1 = QGraphicsLineItem(local_p1.x(), local_p1.y(), dim_q0.x() + nx_h * 5, dim_q0.y() + ny_h * 5, self)
        ext_h2 = QGraphicsLineItem(local_p2.x(), local_p2.y(), dim_q1.x() + nx_h * 5, dim_q1.y() + ny_h * 5, self)
        ext_h1.setPen(dim_pen)
        ext_h2.setPen(dim_pen)
        self.child_lines.extend([ext_h1, ext_h2])

        dim_line_h = QGraphicsLineItem(dim_q0.x(), dim_q0.y(), dim_q1.x(), dim_q1.y(), self)
        dim_line_h.setPen(main_dim_pen)
        self.child_lines.append(dim_line_h)

        text_l2 = DraggableTextItem(f"L2: {h_real}mm", self)
        text_l2.setDefaultTextColor(QColor(20, 20, 20))
        mid_hx = (dim_q0.x() + dim_q1.x()) / 2.0 + nx_h * 4
        mid_hy = (dim_q0.y() + dim_q1.y()) / 2.0 + ny_h * 4
        text_l2.setPos(mid_hx - 15, mid_hy - 10)
        self.child_texts.append(text_l2)

        # Angle display text
        text_ang = DraggableTextItem(f"{angle_deg}°", self)
        text_ang.setDefaultTextColor(QColor(0, 100, 180))
        text_ang.setPos(local_p0.x() - 10, local_p0.y() - 20)
        self.child_texts.append(text_ang)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - Parameter Editing")
        dialog.resize(300, 220)
        
        layout = QVBoxLayout(dialog)
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        spin_width = QDoubleSpinBox()
        spin_width.setRange(1.0, 5000.0)
        spin_width.setValue(float(self.params.get("width", 100.0)))

        spin_height = QDoubleSpinBox()
        spin_height.setRange(1.0, 5000.0)
        spin_height.setValue(float(self.params.get("height", 50.0)))

        spin_angle = QDoubleSpinBox()
        spin_angle.setRange(-360.0, 360.0)
        spin_angle.setValue(float(self.params.get("angle", 30.0)))

        form_layout.addRow("Base Edge Length (mm):", spin_width)
        form_layout.addRow("Other Side Length (mm):", spin_height)
        form_layout.addRow("Angle (degrees):", spin_angle)
        layout.addWidget(form_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.params = {
                "width": spin_width.value(),
                "height": spin_height.value(),
                "angle": spin_angle.value()
            }
            self.setData(1, self.params)
            self.update_geometry_and_content()

        super().mouseDoubleClickEvent(event)


class RotatedRectanglePlugin(ShapePluginInterface):
    """Rotated Rectangle Plugin"""

    def __init__(self) -> None:
        super().__init__()
        self._spin_width: QDoubleSpinBox | None = None
        self._spin_height: QDoubleSpinBox | None = None
        self._spin_angle: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "Rotated Rectangle"

    @property
    def plugin_id(self) -> str:
        return "std.rotated_rectangle"

    def create_parameter_widget(self) -> QWidget:
        widget = QWidget()
        layout = QFormLayout(widget)

        self._spin_width = QDoubleSpinBox()
        self._spin_width.setRange(1.0, 5000.0)
        self._spin_width.setValue(100.0)
        self._spin_width.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._spin_height = QDoubleSpinBox()
        self._spin_height.setRange(1.0, 5000.0)
        self._spin_height.setValue(50.0)
        self._spin_height.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._spin_angle = QDoubleSpinBox()
        self._spin_angle.setRange(-360.0, 360.0)
        self._spin_angle.setValue(30.0)
        self._spin_angle.valueChanged.connect(lambda: self.signals.parameters_changed.emit())

        layout.addRow("Base Edge Length (mm):", self._spin_width)
        layout.addRow("Other Side Length (mm):", self._spin_height)
        layout.addRow("Angle (degrees):", self._spin_angle)

        return widget

    def generate_graphics_item(self, params: Dict[str, Any], drawing_scale: float = 1.0, pixel_scale: float = 2.83) -> QGraphicsItem:
        return EditableRotatedRectItem(self, params, drawing_scale=drawing_scale, pixel_scale=pixel_scale)

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """DXF Export: Outputs the rotated rectangle polyline and dimension text based on center coordinates."""
        w = float(params.get("width", 100.0))
        h = float(params.get("height", 50.0))
        angle_deg = float(params.get("angle", 30.0))
        rad = math.radians(angle_deg)

        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        cx, cy = position.x(), position.y()
        hw, hh = w / 2.0, h / 2.0

        local_pts = [
            (-hw * cos_a + hh * sin_a, -hw * sin_a - hh * cos_a),
            (hw * cos_a + hh * sin_a, hw * sin_a - hh * cos_a),
            (hw * cos_a - hh * sin_a, hw * sin_a + hh * cos_a),
            (-hw * cos_a - hh * sin_a, -hw * sin_a + hh * cos_a)
        ]
        pts_global = [(cx + px, cy + py) for px, py in local_pts]

        # 1. Output the polyline of the rotated rectangle body
        msp.add_lwpolyline(pts_global, close=True)

        # 2. Output dimension text
        text_style = {"height": 3.0, "layer": "0"}
        msp.add_text(f"L1 = {w}mm", dxfattribs=text_style).set_placement((cx - 15, cy - 5))
        msp.add_text(f"L2 = {h}mm", dxfattribs=text_style).set_placement((cx + 10, cy + 5))
        msp.add_text(f"Angle = {angle_deg}deg", dxfattribs=text_style).set_placement((cx, cy + 15))

    def get_current_parameters(self) -> Dict[str, Any]:
        return {
            "width": self._spin_width.value() if self._spin_width else 100.0,
            "height": self._spin_height.value() if self._spin_height else 50.0,
            "angle": self._spin_angle.value() if self._spin_angle else 30.0,
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        if self._spin_width and "width" in params:
            self._spin_width.setValue(float(params["width"]))
        if self._spin_height and "height" in params:
            self._spin_height.setValue(float(params["height"]))
        if self._spin_angle and "angle" in params:
            self._spin_angle.setValue(float(params["angle"]))
