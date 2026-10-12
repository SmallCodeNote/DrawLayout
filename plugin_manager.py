import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type
from plugin_interface import ShapePluginInterface

class PluginManager:
    """plugin フォルダからプラグインを自動動的検出・ロードする管理クラス"""

    def __init__(self, plugin_folder: str = "plugin") -> None:
        self.plugin_folder = Path(plugin_folder)
        self.plugins: Dict[str, ShapePluginInterface] = {}
        self.ensure_plugin_folder()

    def ensure_plugin_folder(self) -> None:
        """プラグインフォルダが存在しない場合は作成する"""
        if not self.plugin_folder.exists():
            self.plugin_folder.mkdir(parents=True, exist_ok=True)
            # パッケージ化のための __init__.py を生成
            init_file = self.plugin_folder / "__init__.py"
            if not init_file.exists():
                init_file.touch()

    def discover_plugins(self) -> Dict[str, ShapePluginInterface]:
        """pluginフォルダ内のモジュールを走査し、ShapePluginInterfaceを実装したクラスをインスタンス化する"""
        self.plugins.clear()
        
        # plugin ディレクトリ配下のモジュールを探索
        for _, module_name, is_pkg in pkgutil.iter_modules([str(self.plugin_folder)]):
            if is_pkg:
                continue
            
            full_module_name = f"{self.plugin_folder.name}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                # モジュール内のクラスを走査
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, ShapePluginInterface) and 
                        attr is not ShapePluginInterface):
                        
                        instance = attr()
                        self.plugins[instance.plugin_id] = instance
            except Exception as e:
                print(f"[ERROR] プラグインモジュール '{module_name}' のロードに失敗しました: {e}")
                
        return self.plugins