from fastapi import FastAPI

from models import *
from routers.transactions import router as transaction_router
from routers.dev import router as dev_router
from routers.auth import router as auth_router
from routers.accounts import router as accounts_router

app = FastAPI()



app.include_router(transaction_router)
app.include_router(auth_router)
app.include_router(accounts_router)

app.include_router(dev_router)
@app.get("/")
async def root():
    return {"message": "BankGuard backend running"}