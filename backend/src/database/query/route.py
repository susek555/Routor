import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.database import get_sync_db
from src.database.dto.route import CalculatedVariantDTO
from src.database.models import RouteVariant

DEFAULT_TTL_HOURS = int(os.getenv("ROUTE_VARIANTS_TTL_HOURS", "24"))


def save_route_variants_sync(
    task_id: str,
    user_id: uuid.UUID,
    variants: list[CalculatedVariantDTO],
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> list[uuid.UUID]:
    """Saves calculated route variants into the PostgreSQL temporary buffer.

    Executed synchronously inside Celery worker.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=ttl_hours)

    entities = [
        RouteVariant(
            user_id=user_id,
            task_id=task_id,
            variant_index=variant.variant_index,
            distance_meters=variant.distance_meters,
            fitness_score=variant.fitness_score,
            geojson=variant.geojson,
            created_at=now,
            expires_at=expires_at,
        )
        for variant in variants
    ]

    with get_sync_db() as session:
        session.add_all(entities)
        session.flush()  # Populates entity IDs before commit
        return [entity.id for entity in entities]


async def get_route_variants_by_task_id(
    session: AsyncSession,
    task_id: str,
) -> list[RouteVariant]:
    """Fetches non-expired route variants for a given task_id ordered by variant index."""

    stmt = (
        select(RouteVariant)
        .where(
            RouteVariant.task_id == task_id,
        )
        .order_by(RouteVariant.variant_index.asc())
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())
