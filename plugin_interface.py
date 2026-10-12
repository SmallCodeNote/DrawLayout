from abc import ABC, abstractmethod
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QGraphicsItem
from PySide6.QtCore import QObject, Signal, QPointF
import ezdxf

class PluginSignalEmitter(QObject):
    """Emitter to handle Signals even in classes that do not inherit from QObject"""
    parameters_changed = Signal()

class ShapePluginInterface(ABC):
    """Abstract base class that all shape plugins must inherit from"""

    def __init__(self) -> None:
        self.signals = PluginSignalEmitter()

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Plugin name to display in the UI"""
        pass

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique ID for saving configurations"""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """Generates and returns a GUI widget for parameter adjustment"""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a QGraphicsItem based on the specified parameters"""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds shape entities to the ezdxf modelspace (msp)"""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """Retrieves current GUI input values as a dictionary"""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Reflects the parameter dictionary loaded from external sources onto the GUI"""
        pass
