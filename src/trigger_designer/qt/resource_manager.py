import sys
from pathlib import Path
from typing import Any, ClassVar, Optional

from loguru import logger
from PIL import Image, ImageQt
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPixmap, QImage, QPainter
from qtpy.QtSvg import QSvgRenderer

import orjson as json

logger = logger.bind(resource_manager=True)


def _bundle_base() -> Path:
    # ponytail: _MEIPASS/_internal is read-only under Program Files; writes go to user scope
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "trigger_designer"
    return Path(__file__).parents[1]


class ResourceManager:
    _map: dict = {}
    _cache: dict[str, Any] = {}
    #: Maps a rendered pixmap's cache key to the resource id it came from, so
    #: a widget that was handed a pixmap can ask which resource it was and
    #: re-resolve it after a theme switch.
    _id_by_key: ClassVar[dict[int, str]] = {}
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
        """Deprecated: build QSS for a theme id.

        Kept so older call sites keep working; new code uses
        ``ThemeManager`` directly. Applying the stylesheet is the
        ThemeManager's job, not this class's.
        """
        from trigger_designer.qt.theme_manager import get_theme_manager

        try:
            return get_theme_manager().stylesheet_for(theme_file)
        except Exception as exc:
            logger.error(f"Unable to build theme '{theme_file}': {exc}")
            return ""

    def get_theme_color(self, key: str, default: str = "#000000") -> QColor:
        """Resolve one theme token to a QColor, for a data-driven paint.

        Defers to the ThemeManager so per-row/per-cell colours follow the
        active theme (accent override included) instead of re-reading a
        second QSettings scope.
        """
        from trigger_designer.qt.theme_manager import get_theme_manager

        return get_theme_manager().color(key, default)

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

    def get(self, id: str) -> Any:
        """Get a resource from the ResourceManager.

        This can include resources inside and outside of QResources, and will return
        theme-respecting variations of resources if available.

        The monochrome ``ui/`` glyphs are re-rendered for the active theme
        (see :mod:`trigger_designer.qt.theme_icons`); node icons and the
        app chrome are returned untouched.

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

                    pixmap = self._themed(id, res, file_path, pixmap)
                    ResourceManager._cache[id] = pixmap
                    ResourceManager._id_by_key[pixmap.cacheKey()] = id
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
                    pixmap = self._themed(id, res, file_path, pixmap)
                    ResourceManager._cache[id] = pixmap
                    ResourceManager._id_by_key[pixmap.cacheKey()] = id
                    return pixmap
            except FileNotFoundError:
                logger.error(
                    f"[ResourceManager][ERROR]: Could not find resource: {file_path}"
                )
                return QImage()

    @staticmethod
    def resource_id_for(pixmap: QPixmap) -> str | None:
        """The resource id a rendered ``pixmap`` came from, if known.

        A widget that was handed a pixmap (rather than an id) uses this to
        find its way back to the resource, so it can re-resolve the icon
        after a theme switch.
        """
        if pixmap is None or pixmap.isNull():
            return None
        return ResourceManager._id_by_key.get(pixmap.cacheKey())

    @staticmethod
    def _themed(id: str, res: dict, file_path: Path, pixmap: QPixmap) -> QPixmap:
        """Re-render a monochrome glyph for the active theme.

        Node icons carry their type in their colour, so only the ``ui/``
        glyph set is re-rendered. Everything else - including the app icon
        and the splash - is returned as loaded.
        """
        from trigger_designer.qt import theme_icons

        path = res.get("path", "")
        if not theme_icons.is_themable(id, path):
            return pixmap
        return theme_icons.themed_pixmap(id, file_path, pixmap)

    def __getattr__(self, __name: str) -> Any:
        attr = self.get(__name)
        if attr:
            return attr
        raise AttributeError(f"{self.__class__.__name__} has no attribute {__name}")
