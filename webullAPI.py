# Nelson Dane
# Webull API

import os
import traceback

from webull import webull
from dotenv import load_dotenv

from helperAPI import Brokerage, printAndDiscord, printHoldings, stockOrder


# Initialize Webull
def webull_init(WEBULL_EXTERNAL=None):
    # Initialize .env file
    load_dotenv()
    # Import Webull account
    if not os.getenv("WEBULL") and WEBULL_EXTERNAL is None:
        print("Webull not found, skipping...")
        return None
    accounts = (
        os.environ["WEBULL"].strip().split(",")
        if WEBULL_EXTERNAL is None
        else WEBULL_EXTERNAL.strip().split(",")
    )
    for account in accounts:
        name = f"Webull {accounts.index(account) + 1}"
        account = account.split(":")
        if len(account) != 4:
            print(f"Invalid number of parameters for {name}, got {len(account)}, expected 4")
            return None
        try:
            wb = webull()
            wb.login(account[0], account[1], "autoRSA", save_token=True)
            wb._access_token = account[2]
            if not wb.is_logged_in():
                raise Exception(f"Unable to log in to {name}. Check credentials.")
            # Initialize Webull account
            wb_obj = Brokerage("Webull")
            wb_obj.set_logged_in_object(name, wb, "wb")
            wb_obj.set_logged_in_object(name, account[3], "access_token")
            # TODO: Get other accounts (Roth, IRA, Margin, etc.)
            ac = wb.get_account()
            wb_obj.set_account_number(name, ac["brokerAccountId"])
            wb_obj.set_account_type(name, ac["brokerAccountId"], ac["accountType"])
            wb_obj.set_account_totals(name, ac["brokerAccountId"], ac["netLiquidation"])
        except Exception as e:
            print(traceback.format_exc())
            print(f"Error: Unable to log in to Webull: {e}")
            return None
        print("Logged in to Webull!")
    return wb_obj


def webull_holdings(wbo: Brokerage, loop=None):
    for key in wbo.get_account_numbers():
        for account in wbo.get_account_numbers(key):
            obj: webull = wbo.get_logged_in_objects(key)
            try:
                # Get account holdings
                positions = obj.get_positions()
                # List of holdings dictionaries
                if positions != []:
                    for item in positions:
                        sym = item["ticker"]["symbol"]
                        if sym == "":
                            sym = "Unknown"
                        qty = item["position"]
                        mv = item["marketValue"]
                        wbo.set_holdings(key, account, sym, qty, mv)
            except Exception as e:
                printAndDiscord(f"{key} {account}: Error getting holdings: {e}", loop)
                traceback.print_exc()
                continue
        printHoldings(wbo, loop=loop)


def webull_transaction(wbo: Brokerage, orderObj: stockOrder, loop=None):
    print()
    print("==============================")
    print("Webull")
    print("==============================")
    print()
    for s in orderObj.get_stocks():
        for key in wbo.get_account_numbers():
            printAndDiscord(
                f"{key}: {orderObj.get_action()}ing {orderObj.get_amount()} of {s}",
                loop,
            )
            for account in wbo.get_account_numbers(key):
                obj: webull = wbo.get_logged_in_objects(key, "wb")
                if not orderObj.get_dry():
                    try:
                        if orderObj.get_price() == "market":
                            orderObj.set_price("MKT")
                        # If stock price < $1 and buy, buy 100 shares and sell 100 - amount
                        price = float(obj.get_quote(s)["pPrice"])
                        if price < 1 and orderObj.get_action() == "buy":
                            old_amount = orderObj.get_amount() 
                            orderObj.set_amount(100)
                            webull_transaction(wbo, orderObj, loop)
                            orderObj.set_amount(100 - old_amount)
                            orderObj.set_action("sell")
                            webull_transaction(wbo, orderObj, loop)
                        else:
                            # Place normal order
                            obj.get_trade_token(wbo.get_logged_in_objects(key, "access_token"))
                            order = obj.place_order(
                                stock=s,
                                action=orderObj.get_action(),
                                orderType=orderObj.get_price(),
                                quant=orderObj.get_amount(),
                                enforce=orderObj.get_time().upper(),
                            )
                            if order["code"] != "200" or order["success"] == False:
                                raise Exception(f"{order['msg']} Code {order['code']}") 
                            printAndDiscord(
                                f"{key}: {orderObj.get_action()} {orderObj.get_amount()} of {s} in {account}: Success",
                                loop,
                            )
                    except Exception as e:
                        printAndDiscord(
                            f"{key} {account}: Error placing order: {e}", loop
                        )
                        traceback.format_exc()
                        continue
                else:
                    printAndDiscord(
                        f"{key} Running in DRY mode. Transaction would've been: {orderObj.get_action()} {orderObj.get_amount()} of {s}",
                        loop,
                    )
