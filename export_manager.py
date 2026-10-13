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
