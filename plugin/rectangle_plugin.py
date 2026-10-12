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
    """ダブルクリックでパラメータ編集ダイアログを開けるカスタム矩形アイテム"""

    def __init__(self, x: float, y: float, w: float, h: float, plugin: 'RectanglePlugin', params: Dict[str, Any]) -> None:
        super().__init__(x, y, w, h)
        self.plugin = plugin
        self.params = params
        
        # 選択・移動フラグ
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        pen = QPen(QColor(0, 120, 215), 2.0)
        self.setPen(pen)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """ダブルクリック時に独立したパラメータ編集ダイアログを表示する"""
        dialog = QDialog()
        dialog.setWindowTitle(f"{self.plugin.plugin_name} - パラメータ編集")
        dialog.resize(300, 150)
        
        layout = QVBoxLayout(dialog)

        # ダイアログ用のフォームとスピンボックスを個別に作成
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

        form_layout.addRow("幅 (Width):", spin_w)
        form_layout.addRow("高さ (Height):", spin_h)
        layout.addWidget(form_widget)

        # OK / キャンセルボタン
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # ダイアログを実行し、OKならパラメータを更新して形状を再描画
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_params = {
                "width": spin_w.value(),
                "height": spin_h.value()
            }
            self.params = new_params
            self.setData(1, new_params)  # メタデータも更新
            
            # 矩形のサイズ・形状を更新
            w = float(new_params["width"])
            h = float(new_params["height"])
            self.setRect(-w / 2.0, -h / 2.0, w, h)

        super().mouseDoubleClickEvent(event)


class RectanglePlugin(ShapePluginInterface):
    """矩形を描画するサンプル図形プラグイン"""

    def __init__(self) -> None:
        super().__init__()
        self._spin_width: QDoubleSpinBox | None = None
        self._spin_height: QDoubleSpinBox | None = None

    @property
    def plugin_name(self) -> str:
        return "矩形 (Rectangle)"

    @property
    def plugin_id(self) -> str:
        return "std.rectangle"

    def create_parameter_widget(self) -> QWidget:
        """メイン画面用のパラメータ調整UIを作成"""
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

        layout.addRow("幅 (Width):", self._spin_width)
        layout.addRow("高さ (Height):", self._spin_height)

        return widget

    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """ダブルクリック対応のカスタム矩形アイテムを生成して返す"""
        w = float(params.get("width", 100.0))
        h = float(params.get("height", 60.0))

        item = EditableRectItem(-w / 2.0, -h / 2.0, w, h, self, params)
        return item

    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """ezdxf向けLWPOLYLINEの生成"""
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