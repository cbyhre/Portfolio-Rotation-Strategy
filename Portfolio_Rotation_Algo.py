import alpaca_trade_api as tradeapi
from datetime import datetime
from pytz import timezone
import time

API_KEY = ''
API_SECRET = ''
BASE_URL = 'https://api.alpaca.markets'
api = tradeapi.REST(API_KEY, API_SECRET, base_url=BASE_URL)

EASTERN = timezone("US/Eastern")

TICKERS = {
    "AH": {
        "QQQ":  0.1200,
        "ONEQ": 0.1080,
        "COPX": 0.0624,
        "XOP":  0.1314,
        "PSCE": 0.0624,
        "ISCG": 0.0524,
        "AVUV": 0.0524,
        "CALF": 0.0524,
        "GLD":  0.0421,
        "SLV":  0.0421,
        "URA":  0.0421,
        "URNM": 0.0421,
        "XAR":  0.1052,
        "AFK":  0.0264
    },
    "INTRADAY": {
        "QQQ":  0.1282,
        "EWJ":  0.0933,
        "EWS":  0.1282,
        "EWU":  0.1282,
        "EWL":  0.0700,
        "EWG":  0.0933,
        "EWA":  0.0700,
        "EWH":  0.0700,
        "EWM":  0.0933,
        "BBJP": 0.1749,
        "EWD":  0.1166
    }
}

executed = {
    "09:30:01": False,
    "09:31:30": False,
    "15:55:00": False,
    "15:56:00": False
}

def current_et_time():
    return datetime.now(EASTERN).strftime('%H:%M:%S')

def get_available_cash():
    try:
        account = api.get_account()
        return float(account.cash) * 0.99
    except Exception as e:
        print(f"[❌] Could not fetch account cash: {e}")
        return 0

def liquidate_all():
    try:
        api.close_all_positions()
        print("[✔] All positions liquidated.")
    except Exception as e:
        print(f"[❌] Error during liquidation:", e)

def submit_orders(ticker_weights, mode):
    cash = get_available_cash()
    if cash <= 0:
        print("[⚠️] No cash available to trade.")
        return

    extended = (mode == "AH")
    order_type = "limit"

    for symbol, weight in ticker_weights.items():
        try:
            trade = api.get_latest_trade(symbol)
            market_price = float(trade.price)
            if market_price <= 0:
                continue

            allocated_cash = cash * weight
            qty = int(allocated_cash // market_price)
            if qty <= 0:
                continue

            limit_price = round(market_price * 1.005, 2)

            order_params = {
                "symbol": symbol,
                "qty": qty,
                "side": "buy",
                "type": order_type,
                "time_in_force": "day",
                "extended_hours": extended,
                "limit_price": limit_price
            }

            api.submit_order(**order_params)
            print(f"[BUY] {symbol}: {qty} shares @ ${limit_price} (cash: ${allocated_cash:.2f})")
        except Exception as e:
            print(f"[❌] Failed to buy {symbol}: {e}")

print("⏱ Starting strategy loop...")
while True:
    now = current_et_time()

    if now == "09:30:01" and not executed["09:30:01"]:
        liquidate_all()
        executed["09:30:01"] = True

    elif now == "09:31:30" and not executed["09:31:30"]:
        print("[▶] Buying intraday portfolio")
        submit_orders(TICKERS["INTRADAY"], mode="INTRADAY")
        executed["09:31:30"] = True

    elif now == "15:55:00" and not executed["15:55:00"]:
        liquidate_all()
        executed["15:55:00"] = True

    elif now == "15:56:00" and not executed["15:56:00"]:
        print("[▶] Buying after-hours portfolio")
        submit_orders(TICKERS["AH"], mode="AH")
        executed["15:56:00"] = True

    if now == "00:00:00":
        for key in executed:
            executed[key] = False
        print("🔄 Resetting daily execution flags.")

    time.sleep(1)
