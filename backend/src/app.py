from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.database import get_db

app = FastAPI(title="Routor API")
DBDependency = Annotated[AsyncSession, Depends(get_db)]


@app.get("/dummy")
def get_dummy():
    return {"message": "Dummy"}


@app.get("/healthcheck-db")
async def check_db_connection(db: DBDependency):
    try:
        result = await db.execute(text("SELECT * FROM dummy"))

        rows = [dict(row) for row in result.mappings().all()]

        return {
            "status": "ok",
            "database": "connected",
            "records_count": len(rows),
            "data": rows,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error connecting to database: {str(e)}"
        ) from e
