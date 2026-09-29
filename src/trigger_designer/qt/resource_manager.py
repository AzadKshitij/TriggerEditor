import os
import sys
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from PIL import Image, ImageQt
from qtpy.QtCore import QSettings, Qt
from qtpy.QtGui import QColor, QPixmap, QImage, QPainter
from qtpy.QtSvg import QSvgRenderer

import orjson as json

logger = logger.bind(resource_manager=True)


def _bundle_base() -> Path:
    # ponytail: _MEIPASS/_internal is read-only under Program Files; writes go to user scope
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "trigger_designer"
    return Path(__file__).parents[1]


def _writable_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Trigger Designer"
        return Path.home() / ".trigger_designer"
    return _bundle_base()


class ResourceManager:
    _map: dict = {}
    _cache: dict[str, Any] = {}
    _initialized: bool = False
    _res_folder: Path = _bundle_base()

    def __init__(self) -> None:
        """Load JSON resource map"""

        if not ResourceManager._initialized:
            self.load_resource_map()
            ResourceManager._initialized = True

    def load_resource_map(self) -> None:
        """Load JSON resource map"""
        logger.debug("Loading resource map")
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            ResourceManager._res_folder = _bundle_base()
        with open(Path(__file__).parent / "resources.json", encoding="utf-8") as f:
            # Read file content as string first
            content = f.read()
            ResourceManager._map = json.loads(content)
            logger.info(
                f"{self.__class__.__name__} Loaded {len(ResourceManager._map.items())} resources"
            )
            # logger.info(
            #     f"{self.__class__.__name__} Resources: {ResourceManager._map.items()}")

    def load_theme(self, theme_file: str = "dark") -> str:
        """To load theme.json file.

        Args:
            theme_file (str): Theme file name.

        Raises:
            AttributeError: _description_

        Returns:
            str: will return theme in qss format.
        """
        print(
            "🐍 File: qt/resource_manager.py:43 | load_resource_map ~ theme_file",
            theme_file,
        )

        try:
            with open(
                ResourceManager._res_folder
                / "resources/qt/themes"
                / f"{theme_file}.json",
                encoding="utf-8",
                mode="r",
            ) as f:
                print(
                    "🐍 File: qt/resource_manager.py:57 | load_theme ~ theme_file",
                    theme_file,
                )
                # Read file content as string first
                content = f.read()
                theme_variables: dict = json.loads(content)

            with open(
                ResourceManager._res_folder / "resources/qt/themes" / f"base.qss",
                encoding="utf-8",
                mode="r",
            ) as f:
                theme_qss = f.read()

            if theme_qss and theme_variables:
                theme_qss = theme_qss.format(**theme_variables)
        except FileNotFoundError:
            print("Error: File not found.")
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in file.")

        except Exception as e:
            logger.error(e)

        # Save this theme to a file (best-effort: bundle may be read-only)
        try:
            with open(
                str(
                    ResourceManager._res_folder
                    / "resources/qt/themes/runtime_theme.qss"
                ),
                "w",
            ) as f:
                f.write(theme_qss)
        except OSError:
            try:
                fallback = _writable_dir() / "runtime_theme.qss"
                fallback.parent.mkdir(parents=True, exist_ok=True)
                fallback.write_text(theme_qss)
            except OSError as exc:
                logger.warning(f"Unable to cache runtime theme: {exc}")

        return theme_qss

    def get_theme_color(self, key: str, default: str = "#000000") -> QColor:
        """Resolve one theme token to a QColor, for a data-driven paint.

        For per-row/per-cell colors driven by model state (e.g. a "this row
        is stale" highlight), QSS can't help -- it has no selector for
        arbitrary data, only static widget/objectName rules -- so this is
        the Python-side counterpart: it reads the same theme JSON
        `load_theme()` formats `base.qss` against, picking dark/light via
        the same ``QSettings`` key the theme switcher itself writes
        (``settings_panel.py``), so a per-row color follows the active
        theme like everything else does.
        """
        theme_name = QSettings("Blue Octa", "Trigger Designer").value("theme", "dark")
        try:
            with open(
                ResourceManager._res_folder
                / "resources/qt/themes"
                / f"{theme_name}.json",
                encoding="utf-8",
                mode="r",
            ) as f:
                theme_variables: dict = json.loads(f.read())
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Unable to load theme '{theme_name}' for color lookup: {e}")
            return QColor(default)
        return QColor(theme_variables.get(key, default))

    @staticmethod
    def get_full_path(id: str) -> Optional[Path]:
        """Get a resource's path from the ResourceManager.

        Args:
            id (str): The name of the resource.

        Returns:
            Path: The resource path if found, else None.
        """
        res: dict = ResourceManager._map.get(id, {})
        if not res:
            return None

        path_str = res.get("path")
        if not path_str:
            return None

        return ResourceManager._res_folder / "resources" / path_str  # type: ignore

    @staticmethod
    def get_icon_path(id: str) -> Optional[Path]:
        """Get a resource's path from the ResourceManager.

        Args:
            id (str): The name of the resource.

        Returns:
            Path: The resource path if found, else None.
        """
        res: dict = ResourceManager._map.get(id, {})
        if not res:
            return None

        path_str = res.get("path")
        if not path_str:
            return None

        return path_str  # type: ignore

    def get(self, id: str) -> Any:
        """Get a resource from the ResourceManager.

        This can include resources inside and outside of QResources, and will return
        theme-respecting variations of resources if available.

        Args:
            id (str): The name of the resource.

        Returns:
            Any: The resource if found, else None.
        """
        cached_res = ResourceManager._cache.get(id)
        if cached_res:
            logger.debug("Loading cached resource!")
            return cached_res
        else:
            res: dict = ResourceManager._map.get(id, {})
            if not res:
                return None

            try:
                file_path = (
                    ResourceManager._res_folder / "resources" / res.get("path", "")
                )

                # if res.get("mode") in ["r", "rb"]:
                #     with open(
                #         (file_path),
                #         res.get("mode", "r"),
                #     ) as f:
                #         data = f.read()
                #         if res.get("mode") == 'rb':
                #             data = bytes(data)
                #             # Convert this svg image into qpixmap
                #             qim = ImageQt.ImageQt(data)
                #             data = QPixmap.fromImage(qim)
                #             # data = QImage(data)
                #         ResourceManager._cache[id] = data
                #         return data
                if res.get("mode") == "rb":
                    # Create QPixmap for SVG
                    renderer = QSvgRenderer(str(file_path))
                    pixmap = QPixmap(renderer.defaultSize())
                    # Fill with transparent background
                    pixmap.fill(Qt.GlobalColor.transparent)

                    # Render SVG to pixmap
                    painter = QPainter(pixmap)
                    renderer.render(painter)
                    painter.end()

                    ResourceManager._cache[id] = pixmap
                    return pixmap
                elif res and res.get("mode") == "pil":
                    data = Image.open(file_path)
                    ResourceManager._cache[id] = data
                    return data
                elif res and res.get("mode") == "qimg":
                    data = Image.open(file_path)
                    qim = ImageQt.ImageQt(data)
                    ResourceManager._cache[id] = qim
                    return qim
                elif res and res.get("mode") in ["qpixmap"]:
                    data = Image.open(file_path)
                    qim = ImageQt.ImageQt(data)
                    pixmap = QPixmap.fromImage(qim)
                    ResourceManager._cache[id] = pixmap
                    return pixmap
            except FileNotFoundError:
                logger.error(
                    f"[ResourceManager][ERROR]: Could not find resource: {file_path}"
                )
                return QImage()

    def __getattr__(self, __name: str) -> Any:
        attr = self.get(__name)
        if attr:
            return attr
        raise AttributeError(f"{self.__class__.__name__} has no attribute {__name}")
