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
