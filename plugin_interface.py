from abc import ABC, abstractmethod
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QGraphicsItem
from PySide6.QtCore import QObject, Signal, QPointF
import ezdxf

class PluginSignalEmitter(QObject):
    """An emitter that allows Signals to be handled even if not inheriting from QObject."""
    parameters_changed = Signal()

class ShapePluginInterface(ABC):
    """Abstract base class that all shape plugins must inherit from."""

    def __init__(self) -> None:
        self.signals = PluginSignalEmitter()

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """The name of the plugin displayed in the UI."""
        pass

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """A unique ID for saving settings."""
        pass

    @abstractmethod
    def create_parameter_widget(self) -> QWidget:
        """Generates and returns the GUI widget for parameter adjustment."""
        pass

    @abstractmethod
    def generate_graphics_item(self, params: Dict[str, Any]) -> QGraphicsItem:
        """Generates and returns a QGraphicsItem based on specified parameters."""
        pass

    @abstractmethod
    def export_to_dxf(self, msp: Any, params: Dict[str, Any], position: QPointF) -> None:
        """Adds the shape entity to the model space (msp) of ezdxf."""
        pass

    @abstractmethod
    def get_current_parameters(self) -> Dict[str, Any]:
        """Retrieves current GUI input values as a dictionary."""
        pass

    @abstractmethod
    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Reflect external parameter dictionaries onto the GUI."""
        pass
