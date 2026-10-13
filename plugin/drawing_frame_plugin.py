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
        combo_orient.addItems(["Landscape", "Portrait"])
        current_orient = self.params.get("orientation", "Landscape")
        idx2 = combo_orient.findText(current_orient)
        if idx2 >= 0:
            combo_orient.setCurrentIndex(idx2)

        # 3. Title information input
        line_title = QLineEdit()
        line_title.setText(self.params.get("title", "2D Drawing Layout"))

        # 4. Scale selection (Scale Factor)
        combo_scale = QComboBox()
        combo_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        current_scale = self.params.get("scale", "1:1")
        idx3 = combo_scale.findText(current_scale)
        if idx3 >= 0:
            combo_scale.setCurrentIndex(idx3)

        form_layout.addRow("Paper Size:", combo_size)
        form_layout.addRow("Orientation:", combo_orient)
        form_layout.addRow("Title:", line_title)
        form_layout.addRow("Scale (Ratio):", combo_scale)
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
            
            text_item = QGraphicsTextItem(f"Title: {title_str}\nSize: {size_str} ({orient_str})\nScale: {scale_str}")
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
        return "Drawing Frame"

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
        self._combo_orientation.addItems(["Landscape", "Portrait"]) 
        self._combo_orientation.currentIndexChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._line_title = QLineEdit()
        self._line_title.setText("2D Drawing Layout")
        self._line_title.textChanged.connect(lambda: self.signals.parameters_changed.emit())

        self._combo_scale = QComboBox()
        self._combo_scale.addItems(["1:1", "1:2", "1:5", "1:10", "2:1", "5:1"])
        self._combo_scale.currentIndexChanged.connect(lambda: self.signals.parameters_changed.emit())

        layout.addRow("Paper Size:", self._combo_size)
        layout.addRow("Orientation:", self._combo_orientation)
        layout.addRow("Title:", self._line_title)
        layout.addRow("Scale (Ratio):", self._combo_scale)

        return widget

    def _get_dimensions(self, params: Dict[str, Any], pixel_scale: float = 2.83) -> Tuple[float, float]:
        """Calculates the screen-based pixel size by multiplying the actual dimensions (mm) of the paper with the pixel scale."""
        size_str = params.get("size", "A4")
        orient_str = params.get("orientation", "Landscape") 
        
        base_w, base_h = self.PAGE_SIZES.get(size_str, (210.0, 297.0))
        
        if "Portrait" in orient_str: 
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
        orient_str = params.get("orientation", "Landscape") 
        title_str = params.get("title", "2D Drawing Layout")
        scale_str = params.get("scale", "1:1")
        
        text_item = QGraphicsTextItem(f"Title: {title_str}\nSize: {size_str} ({orient_str})\nScale: {scale_str}") 
        text_item.setPos(tb_x + 5, tb_y + 5)
        text_item.setDefaultTextColor(QColor(30, 30, 30))
        group.addToGroup(text_item)

        return group

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Generates the drawing frame and title block text in real dimensions (mm) for DXF output."""
        size_str = params.get("size", "A4")
        orient_str = params.get("orientation", "Landscape") 
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
        
        msp.add_text(f"Title: {title_str}", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 17))
        msp.add_text(f"Size: {size_str} ({orient_str})", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 10))
        msp.add_text(f"Scale: {scale_str}", dxfattribs=text_style).set_placement((tb_x + 3, tb_y + 3))

    def get_current_parameters(self) -> Dict[str, Any]:
        return {
            "size": self._combo_size.currentText() if self._combo_size else "A4",
            "orientation": self._combo_orientation.currentText() if self._combo_orientation else "Landscape", 
            "title": self._line_title.text() if self._line_title else "2D Drawing Layout",
            "scale": self._combo_scale.currentText() if self._combo_scale else "1:1",
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        if self._combo_size and "size" in params:
            idx = self._combo_size.findText(params["size"])
            if idx >= 0:
                self._combo_size.setCurrentIndex(idx)
        if self._combo_orientation and "orientation" in params:
            target = params["orientation"] if any(o in target for o in ["Landscape", "Portrait"]) else "Landscape"
            idx = self._combo_orientation.findText(target) 
            if idx >= 0:
                self._combo_orientation.setCurrentIndex(idx)
        if self._line_title and "title" in params:
            self._line_title.setText(params["title"])
        if self._combo_scale and "scale" in params:
            idx = self._combo_scale.findText(params["scale"])
            if idx >= 0:
                self._combo_scale.setCurrentIndex(idx)
