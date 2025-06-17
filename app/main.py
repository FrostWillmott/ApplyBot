from fastapi import FastAPI

from app.routers.apply import router as apply_router
from app.routers.auth import router as auth_router
from app.routers.hh_apply import router as hh_apply_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(apply_router)
app.include_router(hh_apply_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
