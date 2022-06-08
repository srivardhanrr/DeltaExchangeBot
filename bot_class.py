from delta_rest_client import DeltaRestClient, OrderType, TimeInForce
from datetime import datetime, timedelta
from threading import Thread
import schedule
import telepot
import telebot
import ccxt
import math
import time
import urllib3
import pendulum



class DeltaBot:
    def __init__(self, base_url, api_key=None, api_secret=None, telegram_api=None, chat_id=None):
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.telegram_api = telegram_api
        self.chat_id = chat_id
        self.client = self._deltaLogin()
        self.delta = self._delta()
        self.reorder = []
        self.max_quantity = 4000

    def _deltaLogin(self):
        deltaClient = DeltaRestClient(
            base_url=self.base_url,
            api_key=self.api_key,
            api_secret=self.api_secret)
        return deltaClient

    def _delta(self):
        delta = ccxt.delta({
            'api_key': self.api_key,
            'secret': self.api_secret})
        return delta

    def message_bot(self):
        API_KEY = self.telegram_api
        bot = telebot.TeleBot(API_KEY)
        self.telegram_bot("TeleBot Started.")

        @bot.message_handler(commands=['isrunning'])
        def isrunning(message):
            bot.reply_to(message, 'Bot is Running.')

        @bot.message_handler(commands=['avlbal'])
        def greet(message):
            bot.reply_to(message, self.usdt_balance())

        @bot.message_handler(commands=['btcltp'])
        def btcltp(message):
            bot.reply_to(message, self.get_ltp("BTCUSDT"))

        # @bot.message_handler(commands=['openorders'])
        # def openord(message):
        #     bot.reply_to(message, self.open_orders())

        try:
            bot.polling()
        except Exception:
            self.telegram_bot("Bot Messenger Has Stopped \nRetrying")
            self.message_bot()

    def time_teller(self):
        current_time = time.strftime("%Y-%m-%d  %H:%M", time.localtime())
        self.telegram_bot(f"Current Time: {current_time}")
        return current_time

    def telegram_bot(self, bot_message):
        proxy_url = "http://proxy.server:3128"
        telepot.api._pools = {
        'default': urllib3.ProxyManager(proxy_url=proxy_url, num_pools=3, maxsize=10, retries=False, timeout=30)}
        telepot.api._onetime_pool_spec = (urllib3.ProxyManager, dict(proxy_url=proxy_url, num_pools=1, maxsize=1, retries=False, timeout=30))
        bot_message = str(bot_message)
        print(bot_message)
        telegram_api = self.telegram_api
        chat_id = self.chat_id
        bot = telepot.Bot(telegram_api)
        return bot.sendMessage(chat_id, bot_message)



    def open_orders(self):
        orders = self.client.get_live_orders()
        if orders:
            self.telegram_bot("←﷼Open Orders→")
            for order in orders:
                self.telegram_bot(f'{order["side"]} {order["unfilled_size"]} Contracts of {order["product_symbol"]} at {order["limit_price"]}')
        else:
            self.telegram_bot("No Open Orders")
        self.telegram_bot('-'*40)

    def lev_100x(self):
        self.telegram_bot("Started Leverage Change Bot.")
        current_date = time.strftime("%y%m%d", time.localtime())
        next_date = (datetime.now() + timedelta(days=1)).strftime('%y%m%d')
        day_after_date = (datetime.now() + timedelta(days=2)).strftime('%y%m%d')
        wk_expiry = pendulum.now().next(pendulum.FRIDAY).strftime('%y%m%d')
        markets = self.delta.load_markets()
        for market in markets:
            try:
                if market[0:20] == f'BTC/USDT:USDT-{next_date}' and market[0:20] == f'BTC/USDT:USDT-{wk_expiry}' and market[0:20] == f'BTC/USDT:USDT-{day_after_date}':
                    symbol = self.delta.fetch_ticker(market)['info']['product_id']
                    print(market)
                    self.client.set_leverage(symbol, 100)
            except:
                pass
                self.telegram_bot("Error Occurred!")
        self.telegram_bot("Leverage Changed..")

    def place_order(self, productId, size, price, side='sell', order_type=OrderType.LIMIT,
                    time_in_force=TimeInForce.GTC):
        order_response = self.client.place_order(
            product_id=productId,
            size=size,
            side=side,
            limit_price=price,
            order_type=order_type,
            time_in_force=time_in_force)
        return order_response

    def cancel_order(self, productId, orderId):
        order_response = self.client.cancel_order(product_id=productId, order_id=orderId)
        return order_response

    def get_ltp(self, symbol):
        response = self.client.get_ticker(symbol)['spot_price']
        return response

    def usdt_balance(self):
        balance = self.client.get_balances(asset_id=5)['available_balance']
        return balance

    def orderbook(self, productId):
        tries = 5
        while tries > 0:
            try:
                time.sleep(1)
                orderbook_bid = self.client.get_l2_orderbook(productId)['buy'][0]['price']
                orderbook_ask = self.client.get_l2_orderbook(productId)['sell'][0]['price']
                return orderbook_bid, orderbook_ask
                break
            except Exception as e:
                self.telegram_bot(f"Error Occurred in Orderbook: {e}")
                tries -= 1

    def deltabot(self):
        # Strike Selection and Fetching Token
        ltp = float(self.get_ltp('BTCUSDT'))
        print(ltp)
        self.telegram_bot(f'BTC SPOT Price: {ltp}')
        mod_val = math.fmod(ltp, 1000)
        x = ltp - mod_val
        ce_strike = "{}".format("{:.0f}".format(x + 2000))
        self.telegram_bot(f"Identified OTM Strike to sell: {ce_strike}")
        current_date = time.strftime("%d%m%y", time.localtime())
        symbol = f'C-BTC-{ce_strike}-{current_date}'
        self.telegram_bot(symbol)
        product_id = self.client.get_ticker(symbol)['product_id']
        if product_id is None:
            self.telegram_bot("Token not Found")
            self.telegram_bot("Trying Again with other Symbol.")
            ce_strike = int(ce_strike) - 1000
            symbol = f'C-BTC-{ce_strike}-{current_date}'
            product_id = self.client.get_ticker(symbol)['product_id']
            if product_id is None:
                self.telegram_bot("Token not Found Again.")
                self.telegram_bot("Trying 2nd Symbol.")
                ce_strike = int(ce_strike) - 1000
                symbol = f'C-BTC-{ce_strike}-{current_date}'
                product_id = self.client.get_ticker(symbol)['product_id']
        self.telegram_bot(f'{symbol}, {product_id}')
        # OrderBook
        orderbook_bid = self.orderbook(product_id)[0]
        orderbook_ask = self.orderbook(product_id)[1]
        self.telegram_bot(f"Bid: {orderbook_bid} Ask: {orderbook_ask}")
        # Available Balance
        balance = self.usdt_balance()
        self.telegram_bot(f"Available Balance: {balance}")
        # Quantity
        max_cont = self.max_quantity
        quantity = int(float(balance) / (ltp / 100000))
        if quantity <= max_cont:
            cont = quantity
        else:
            self.telegram_bot("Condition Overthorwn: Max Quantity Exceeded")
            cont = 0
        self.telegram_bot(f"Quantity: {cont}")
        # Set Leverage
        leverage = self.client.set_leverage(product_id=product_id, leverage='100')
        self.telegram_bot(f"Leverage changed to {leverage['leverage']}x.")
        # Order Placement
        tries = 5
        if cont > 0 and float(balance) > 0.3:
            while tries > 0:
                try:
                    orig_ord = self.place_order(product_id, size=cont, price=orderbook_ask)
                    self.telegram_bot(f"\nOrder Submitted \n"
                                      f"{orig_ord['side']} {orig_ord['size']} Contracts of {orig_ord['product_symbol']} at {orig_ord['limit_price']}")
                    break
                except Exception as e:
                    self.telegram_bot(f"Exception Occurred: {e}")
                    cont -= 2
                    self.telegram_bot(f'Trying Again with {cont} Quantity.')
                    tries -= 1
            self.telegram_bot("\nStrategy Executed")
        else:
            self.telegram_bot("No Balance!")

    def live_orders(self):
        current_date = time.strftime("%d%m%y", time.localtime())
        open_orders = self.client.get_live_orders()
        if open_orders:
            self.telegram_bot("-" * 35)
            self.telegram_bot('Found Existing Orders \n Cancelling Orders...')
            for orders in open_orders:
                symbol = orders['product_symbol']
                if symbol[12:] > current_date:
                    self.reorder.append(orders)
                cancelled = self.cancel_order(productId=orders['product_id'], orderId=orders['id'])
                self.telegram_bot(f"Cancelled {cancelled['product_symbol']}, Quantity: {cancelled['unfilled_size']}")
            self.telegram_bot('Cancelled Existing Orders. \n')
            time.sleep(1)
            self.telegram_bot('Started Strategy Execution. \n')
            # self.deltabot()
        else:
            self.telegram_bot("-" * 35)
            self.telegram_bot('Started Strategy Execution. \n')
            # self.deltabot()

    def re_order(self):
        if self.reorder is not None:
            self.telegram_bot('Re Ordering Started...')
            for re in self.reorder:
                repeat_order = self.place_order(productId=re['product_id'], size=re['unfilled_size'],
                                                price=re['limit_price'],
                                                side=re['side'])
                self.telegram_bot(f"\nRE Order Submitted \n"
                                  f"{repeat_order['side']} {repeat_order['size']} Contracts of {repeat_order['product_symbol']} at {repeat_order['limit_price']}")
            self.reorder.clear()
            self.telegram_bot("Successfully Executed Re-Ordering.")
            self.telegram_bot("-" * 40)

    def schedule_strategy(self):
        schedule.every(120).minutes.do(self.usdt_balance)
        schedule.every(120).minutes.do(self.time_teller)
        schedule.every().day.at('19:37:00').do(self.lev_100x)
        schedule.every().day.at('19:30:00').do(self.live_orders)
        schedule.every().day.at('19:32:00').do(self.re_order)

        while 1:
            schedule.run_pending()
            time.sleep(1)

    def main(self):
        self.telegram_bot("Algo Started.")
        Thread(target=self.schedule_strategy).start()
        Thread(target=self.message_bot).start()
