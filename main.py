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

def generate_trade_signal(data: dict) -> str:
    signal = data.get("signal", "").upper()
    ticker = data.get("ticker", "").replace("/", "").upper()
    price = float(data.get("price", 0))

    # Pip settings (assume 1 pip = 0.01 for crypto or most FX)
    pip_value = 0.01
    tp1_pips = 180 * pip_value
    tp2_pips = 200 * pip_value
    tp3_pips = 225 * pip_value
    sl_pips = 100 * pip_value

    if signal == "BUY":
        entry_range = f"{price - 0.5}-{price - 1.5}"
        tp1 = round(price + tp1_pips, 2)
        tp2 = round(price + tp2_pips, 2)
        tp3 = round(price + tp3_pips, 2)
        sl = round(price - sl_pips, 2)
    elif signal == "SELL":
        entry_range = f"{price + 0.5}-{price + 1.5}"
        tp1 = round(price - tp1_pips, 2)
        tp2 = round(price - tp2_pips, 2)
        tp3 = round(price - tp3_pips, 2)
        sl = round(price + sl_pips, 2)
    else:
        return "⚠️ Invalid signal received."

    message = (
        f"🌟{signal} {ticker}🌟\n\n"
        f"Entry - {entry_range}\n\n"
        f"TP1 - {tp1}\n"
        f"TP2 - {tp2}\n"
        f"TP3 - {tp3}\n\n"
        f"SL - {sl}\n\n"
        f"-AJ."
    )
    return message

@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    signal_msg = generate_trade_signal(data)
    await client.send_message("jbasgallop", signal_msg)
    return {"status": "Message sent", "preview": signal_msg}

# @app.post("/webhook")
# async def receive_webhook(request: Request):
#     data = await request.json()
#     message = f"📈 TradingView Alert:\n{data}"
#     await client.send_message("jbasgallop", message)
#     return {"status": "Message sent"}
