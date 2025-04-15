import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, requests, responses
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone_number = os.getenv("TELEGRAM_PHONE")

app = FastAPI()

# Initialize Telethon client
client = TelegramClient("user_session", api_id=api_id, api_hash=api_hash)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.start()
    yield
    await client.disconnect()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    message = f"📈 TradingView Alert:\n{data}"
    await client.send_message("jbasgallop", message)
    return {"status": "Message sent"}
