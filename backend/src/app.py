from fastapi import FastAPI

app = FastAPI()


@app.get("/dummy")
def get_dummy():
    return {"message": "Dummy"}
