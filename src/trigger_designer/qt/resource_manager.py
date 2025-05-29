from pathlib import Path
from typing import Any, Optional

from loguru import logger
from PIL import Image, ImageQt
from qtpy.QtCore import QSettings, Qt
from qtpy.QtGui import QPixmap, QImage, QPainter
from qtpy.QtSvg import QSvgRenderer

import orjson as json

logger = logger.bind(resource_manager=True)


class ResourceManager:
    _map: dict = {}
    _cache: dict[str, Any] = {}
    _initialized: bool = False
    _res_folder: Path = Path(__file__).parents[1]

    def __init__(self) -> None:
        """Load JSON resource map
        """

        if not ResourceManager._initialized:
            self.load_resource_map()
            ResourceManager._initialized = True

    def load_resource_map(self) -> None:
        """Load JSON resource map
        """
        logger.debug("Loading resource map")
        with open(Path(__file__).parent / "resources.json", encoding="utf-8") as f:
            # Read file content as string first
            content = f.read()
            ResourceManager._map = json.loads(content)
            logger.info(
                f"{self.__class__.__name__} Loaded {len(ResourceManager._map.items())} resources")

    def load_theme(self, theme_file: str = 'dark') -> str:
        """To load theme.json file.

        Args:
            theme_file (str): Theme file name.

        Raises:
            AttributeError: _description_

        Returns:
            str: will return theme in qss format.
        """

        try:
            with open(ResourceManager._res_folder / "resources/qt/themes" / f"{theme_file}.json", encoding="utf-8", mode="r") as f:
                # Read file content as string first
                content = f.read()
                theme_variables: dict = json.loads(content)

            with open(ResourceManager._res_folder / "resources/qt/themes" / f"base.qss", encoding="utf-8", mode="r") as f:
                theme_qss = f.read()

            if theme_qss and theme_variables:
                theme_qss = theme_qss.format(**theme_variables)
        except FileNotFoundError:
            print("Error: File not found.")
        except json.JSONDecodeError:
            print("Error: Invalid JSON format in file.")

        except Exception as e:
            logger.error(e)

        # Save this theme to a file
        with open(str(ResourceManager._res_folder/"resources/qt/themes/runtime_theme.qss"), 'w') as f:
            f.write(theme_qss)

        return theme_qss

    @staticmethod
    def get_path(id: str) -> Optional[Path]:
        """Get a resource's path from the ResourceManager.

        Args:
            id (str): The name of the resource.

        Returns:
            Path: The resource path if found, else None.
        """

        # res: dict = ResourceManager._map.get(id, {})
        # if res:
        #     path_str = res.get("path")
        #     if path_str:
        #         return ResourceManager._res_folder / "resources" / path_str
        # return None

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
                file_path = ResourceManager._res_folder / \
                    "resources" / res.get("path", "")

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
                if res.get("mode") == 'rb':
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
                    f"[ResourceManager][ERROR]: Could not find resource: {file_path}")
                return None

    def __getattr__(self, __name: str) -> Any:
        attr = self.get(__name)
        if attr:
            return attr
        raise AttributeError(
            f"{self.__class__.__name__} has no attribute {__name}")
