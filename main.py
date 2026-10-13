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
