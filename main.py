import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
phone_number = os.getenv("TELEGRAM_PHONE")

# Initialize Telethon client
client = TelegramClient("user_session", api_id=api_id, api_hash=api_hash)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.start()
    yield
    await client.disconnect()

app = FastAPI(lifespan=lifespan)


def generate_trade_signal(data: dict) -> str:
    # 1) Read mandatory fields
    signal   = data.get("signal", "").upper()
    ticker   = data.get("ticker", "").replace("/", "").upper()
    price    = float(data.get("price", 0.0))

    # 2) Read dynamic TP/SL pip inputs from EA
    ea_tp_pips = float(data.get("tp_pips", 0.0))
    ea_sl_pips = float(data.get("sl_pips", 0.0))

    # 3) Convert “pips” into actual price increments.
    #    (Adjust pip_value if you trade crypto or different precision.)
    pip_value = 0.01

    # Compute the three TP levels and one SL level:
    # • TP1 = ± ea_tp_pips * pip_value
    # • TP2 = ± (ea_tp_pips * 2) * pip_value
    # • TP3 = ± (ea_tp_pips * 4) * pip_value   (or choose 3× if that’s your RR logic)
    # • SL  = ± ea_sl_pips * pip_value
    if signal == "BUY":
        entry_low  = price - 0.5    # you can adjust how you want to show entry ranges
        entry_high = price - 1.5
        tp1 = round(price + ea_tp_pips * pip_value, 2)
        tp2 = round(price + (ea_tp_pips * 2) * pip_value, 2)
        tp3 = round(price + (ea_tp_pips * 4) * pip_value, 2)
        sl  = round(price - ea_sl_pips * pip_value, 2)
    elif signal == "SELL":
        entry_low  = price + 0.5
        entry_high = price + 1.5
        tp1 = round(price - ea_tp_pips * pip_value, 2)
        tp2 = round(price - (ea_tp_pips * 2) * pip_value, 2)
        tp3 = round(price - (ea_tp_pips * 4) * pip_value, 2)
        sl  = round(price + ea_sl_pips * pip_value, 2)
    else:
        return "⚠️ Invalid signal received."

    # 4) Build the Telegram‐ready text
    message = (
        f"🌟{signal} {ticker}🌟\n\n"
        f"Entry – {entry_low:.2f} – {entry_high:.2f}\n\n"
        f"TP1 – {tp1:.2f}\n"
        f"TP2 – {tp2:.2f}\n"
        f"TP3 – {tp3:.2f}\n\n"
        f"SL – {sl:.2f}\n\n"
        f"-AJ"
    )
    return message


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    # The EA now sends: signal, ticker, price, tp_pips, sl_pips
    signal_msg = generate_trade_signal(data)
    await client.send_message("jbasgallop", signal_msg)
    return {"status": "Message sent", "preview": signal_msg}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
