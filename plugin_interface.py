from abc import ABC, abstractmethod
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QGraphicsItem
from PySide6.QtCore import QObject, Signal, QPointF
import ezdxf

class PluginSignalEmitter(QObject):
    """QObject非継承クラスでもSignalを扱えるようにするエミッター"""
    parameters_changed = Signal()

class ShapePluginInterface(ABC):
    """すべての図形プラグインが継承すべき抽象基底クラス"""

    def __init__(self) -> None:
        self.signals = PluginSignalEmitter()

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """UIに表示するプラグイン名"""
        pass

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """設定保存用のユニークID"""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """パラメータ調整用GUIウィジェットを生成して返す"""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """指定されたパラメータに基づきQGraphicsItemを生成して返す"""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """ezdxfのモデルスペース(msp)に図形エンティティを追加する"""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """現在のGUI入力値を辞書型で取得する"""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """外部から読み込んだパラメータ辞書をGUIに反映する"""
        pass