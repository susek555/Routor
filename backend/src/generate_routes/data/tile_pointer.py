from dataclasses import dataclass

import mercantile


@dataclass(frozen=True)
class TilePointer:
    x: int
    y: int
    z: int

    @property
    def id(self) -> str:
        return f"{self.z}_{self.x}_{self.y}"

    @property
    def bounds(self):
        return mercantile.bounds(self.x, self.y, self.z)
