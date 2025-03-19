from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageQt
from numpy import byte
from qtpy.QtGui import QPixmap, QImage

import json

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
            ResourceManager._map = json.load(f)
            logger.info(
                f"{self.__class__.__name__} Loaded {len(ResourceManager._map.items())} resources")

    @staticmethod
    def get_path(id: str) -> Path | None:
        """Get a resource's path from the ResourceManager.

        Args:
            id (str): The name of the resource.

        Returns:
            Path: The resource path if found, else None.
        """

        res: dict = ResourceManager._map.get(id)
        if res:
            return ResourceManager._res_folder / "resources" / res.get("path")
        return None

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
            res: dict = ResourceManager._map.get(id)
            if not res:
                return None

            try:
                file_path = ResourceManager._res_folder / \
                    "resources" / res.get("path")

                if res.get("mode") in ["r", "rb"]:
                    with open(
                        (file_path),
                        res.get("mode")
                    ) as f:
                        data = f.read()
                        if res.get("mode") == 'rb':
                            data = bytes(data)
                        ResourceManager._cache[id] = data
                        return data
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
