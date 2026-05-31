from fastapi import FastAPI, HTTPException, Request

from src.database.database import get_dummies
from src.generate_routes.task import dummy_task

app = FastAPI(title="Routor API")


@app.get("/dummy")
def get_dummy():
    return {"message": "Dummy"}


@app.get("/healthcheck-db")
async def check_db_connection():
    try:
        rows = await get_dummies()

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


@app.post("/dummy-task")
async def dummy_task_endpoint(request: Request):
    task = dummy_task.delay(request.client.host, "Message from api.")

    return {
        "status": "Accepted",
        "message": "Dummy task started in the background.",
        "task_id": task.id,
    }
