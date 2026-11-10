from typing import Any

from pydantic import BaseModel


class CalculatedVariantDTO(BaseModel):
    variant_index: int
    distance_meters: int
    fitness_score: float
    geojson: dict[str, Any]
