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

    We treat 1 pip = 0.0001 for most FX pairs (0.01 for JPY). Then:
      • TP1 = ea_tp_pips
      • TP2 & TP3  = chosen piecewise, as described below.
      • SL  = ea_sl_pips.

    Finally we build a Telegram‐formatted text string with Entry range,
    TP1/TP2/TP3, and SL.
    """

    # 1) Read & normalize inputs
    raw_signal  = data.get("signal", "").upper()
    raw_ticker  = data.get("ticker", "").upper()
    ticker      = raw_ticker.replace("/", "")              # "EUR/USD" → "EURUSD"
    price       = float(data.get("price", 0.0))
    ea_tp_pips  = float(data.get("tp_pips", 0.0))
    ea_sl_pips  = float(data.get("sl_pips", 0.0))

    # 2) Determine pip_value: 0.0001 for non‐JPY, 0.01 for JPY pairs
    if ticker.endswith("JPY"):
        pip_value = 0.001
        decimals  = 4
    else:
        pip_value = 0.00001
        decimals  = 6

    # 3) Compute TP1, TP2, TP3 (in “pips”), based on piecewise rules:
    #    - If TP < 75:    [TP, 2×TP, 3×TP]
    #    - If 75 ≤ TP <100: [TP, 100, 100 + (100 - TP)]
    #    - If 100 ≤ TP <150: [TP, TP+25, TP+50]
    #    - If TP ≥ 150:  [TP, TP+50, (TP+50)+25]
    tp1_pips = ea_tp_pips
    if ea_tp_pips < 75.0:
        tp2_pips = ea_tp_pips * 2.0
        tp3_pips = ea_tp_pips * 3.0
    elif ea_tp_pips < 100.0:
        tp2_pips = 100.0
        tp3_pips = 100.0 + (100.0 - ea_tp_pips)
    elif ea_tp_pips < 150.0:
        tp2_pips = ea_tp_pips + 25.0
        tp3_pips = ea_tp_pips + 50.0
    else:  # ea_tp_pips ≥ 150
        tp2_pips = ea_tp_pips + 50.0
        tp3_pips = tp2_pips + 25.0

    # 4) Convert those “pips” into actual price increments:
    #    e.g. if ea_tp_pips=50 and pip_value=0.0001, then Δprice=0.0050
    tp1_price = round(price + tp1_pips * pip_value, decimals)
    tp2_price = round(price + tp2_pips * pip_value, decimals)
    tp3_price = round(price + tp3_pips * pip_value, decimals)

    # 5) Compute SL price as simple price ± ea_sl_pips * pip_value
    sl_price = (round(price - ea_sl_pips * pip_value, decimals)
                if raw_signal == "BUY"
                else round(price + ea_sl_pips * pip_value, decimals))

    # 6) For BUY/SELL, flip signs appropriately
    if raw_signal == "BUY":
        entry_low   = round(price - (0.5 * pip_value * 10), decimals)  # e.g. price - 0.0005
        entry_high  = round(price + (0.5 * pip_value * 10), decimals)  # e.g. price + 0.0005
        # TP levels are already above price by +(tp_pips × pip_value)
        # SL computed above.
    elif raw_signal == "SELL":
        entry_low   = round(price - (0.5 * pip_value * 10), decimals)  # use same “bracket” logic
        entry_high  = round(price + (0.5 * pip_value * 10), decimals)
        # For SELL, we need to flip TP1/2/3 to below price:
        tp1_price   = round(price - tp1_pips * pip_value, decimals)
        tp2_price   = round(price - tp2_pips * pip_value, decimals)
        tp3_price   = round(price - tp3_pips * pip_value, decimals)
        # SL price was already computed as price + (sl_pips × pip_value)
    else:
        return "⚠️ Invalid signal received."

    # 7) Build the final message for Telegram
    message = (
        f"🌟{raw_signal} {ticker}🌟\n\n"
        f"Entry – {entry_low:.{decimals}f} – {entry_high:.{decimals}f}\n\n"
        f"TP1 – {tp1_price:.{decimals}f}\n"
        f"TP2 – {tp2_price:.{decimals}f}\n"
        f"TP3 – {tp3_price:.{decimals}f}\n\n"
        f"SL  – {sl_price:.{decimals}f}\n\n"
        f"-AJ"
    )
    return message


@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    signal_msg = generate_trade_signal(data)
    await client.send_message("jbasgallop", signal_msg)
    return {"status": "Message sent", "preview": signal_msg}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
