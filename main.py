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
    """
    Expects incoming JSON with at least:
      {
        "signal":   "BUY" or "SELL",
        "ticker":   "EURUSD" (or "EUR/USD" – we'll strip the slash),
        "price":    1.08345,
        "tp_pips":  50.0,
        "sl_pips":  100.0
      }
    We treat 1 pip = 0.0001 (for most FX pairs). Then:
      TP1 = price ± 50 × 0.0001
      TP2 = price ± 100 × 0.0001
      TP3 = price ± 150 × 0.0001
      SL  = price ∓ 100 × 0.0001

    (For JPY pairs, you might want to use 0.01 instead.
    You could check ticker.endswith("JPY") and override pip_value=0.01 if needed.)
    """
    # 1) Read & normalize inputs
    signal     = data.get("signal", "").upper()
    raw_ticker = data.get("ticker", "").upper()
    # Remove any slash so "EUR/USD" → "EURUSD"
    ticker     = raw_ticker.replace("/", "")
    price      = float(data.get("price", 0.0))
    ea_tp_pips = float(data.get("tp_pips", 0.0))
    ea_sl_pips = float(data.get("sl_pips", 0.0))



    # 2) Determine pip_value (0.0001 for most FX; 0.01 for JPY pairs)
    if ticker.endswith("JPY"):
        pip_value = 0.01
    else:
        pip_value = 0.0001

    # 3) Compute TP1, TP2, TP3, and SL
    #    We use 1×, 2×, 3× of ea_tp_pips, as is common for TP levels.
    if signal == "BUY":
        entry_low   = price - pip_value    # you can adjust this margin if you like
        entry_high  = price + pip_value

        tp1 = round(price + ea_tp_pips * pip_value, 5 if not ticker.endswith("JPY") else 3)
        tp2 = round(price + (ea_tp_pips + 50) * pip_value, 5 if not ticker.endswith("JPY") else 3)
        tp3 = round(price + (ea_tp_pips + 100) * pip_value, 5 if not ticker.endswith("JPY") else 3)

        sl  = round(price - ea_sl_pips * pip_value, 5 if not ticker.endswith("JPY") else 3)

    elif signal == "SELL":
        entry_low   = price + pip_value   # you can adjust this margin if you like
        entry_high  = price - pip_value

        tp1 = round(price - ea_tp_pips * pip_value, 5 if not ticker.endswith("JPY") else 3)
        tp2 = round(price - (ea_tp_pips + 50) * pip_value, 5 if not ticker.endswith("JPY") else 3)
        tp3 = round(price - (ea_tp_pips + 100) * pip_value, 5 if not ticker.endswith("JPY") else 3)

        sl  = round(price + ea_sl_pips * pip_value, 5 if not ticker.endswith("JPY") else 3)

    else:
        return "⚠️ Invalid signal received."


    # 4) Build the Telegram‐formatted message
    message = (
        f"🌟{signal} {ticker}🌟\n\n"
        f"Entry – {entry_low:.5f} – {entry_high:.5f}\n\n"
        f"TP1 – {tp1:.5f}\n"
        f"TP2 – {tp2:.5f}\n"
        f"TP3 – {tp3:.5f}\n\n"
        f"SL – {sl:.5f}\n\n"
        f"-AJ"
    ) if not ticker.endswith("JPY") else (
        f"🌟{signal} {ticker}🌟\n\n"
        f"Entry – {entry_low:.3f} – {entry_high:.3f}\n\n"
        f"TP1 – {tp1:.3f}\n"
        f"TP2 – {tp2:.3f}\n"
        f"TP3 – {tp3:.3f}\n\n"
        f"SL – {sl:.3f}\n\n"
        f"-AJ"
    )

    return message


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    signal_msg = generate_trade_signal(data)
    await client.send_message("jbasgallop", signal_msg)
    await client.send_message("its_ajs", signal_msg)
    return {"status": "Message sent", "preview": signal_msg}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
