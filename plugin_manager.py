import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type
from plugin_interface import ShapePluginInterface

class PluginManager:
    """Manages automatic dynamic detection and loading of plugins from the 'plugin' folder."""

    def __init__(self, plugin_folder: str = "plugin") -> None:
        self.plugin_folder = Path(plugin_folder)
        self.plugins: Dict[str, ShapePluginInterface] = {}
        self.ensure_plugin_folder()

    def ensure_plugin_folder(self) -> None:
        """Creates the plugin folder if it does not exist."""
        if not self.plugin_folder.exists():
            self.plugin_folder.mkdir(parents=True, exist_ok=True)
            # Generates __init__.py for package definition
            init_file = self.plugin_folder / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def discover_plugins(self) -> Dict[str, ShapePluginInterface]:
        """Scans the plugin folder and instantiates classes implementing ShapePluginInterface."""
        self.plugins.clear()
        
        # Searches for modules within the 'plugin' directory
        for _, module_name, is_pkg in pkgutil.iter_modules([str(self.plugin_folder)]):
            if is_pkg:
                continue
            
            full_module_name = f"{self.plugin_folder.name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # Scans classes within the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ShapePluginInterface) and 
                        attr is not ShapePluginInterface):
                        
                        instance = attr()
                        self.plugins[instance.plugin_id] = instance
            except Exception as e:
                print(f"[ERROR] Failed to load plugin module '{module_name}': {e}")
                
        return self.plugins
