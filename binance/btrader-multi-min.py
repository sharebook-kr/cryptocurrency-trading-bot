import time
import ccxt
from ccxt.base.errors import *
import threading
import datetime
from pandas import DataFrame

import logging
import inspect
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler()
logger.addHandler(stream_handler)
file_handler = logging.FileHandler("log.txt")
logger.addHandler(file_handler)

DELAY = 1
COIN_NUMS = 5
DUAL_NOISE_LIMIT = 0.6
LARRY_K = 0.4
DEBUG = False


def threadable(fn):
    def run(*k, **kw):
        th = threading.Thread(target=fn, args=k, kwargs=kw)
        th.start()
        return th
    return run


def error_check(fun):
    def wrapper(self, *args, **kwargs):
        # 에러가 날 경우 20 (20초)번까지 반복 요청
        max_retry_cnt = 10
        for i in range(max_retry_cnt):
            try:
                ret = fun(self, *args, **kwargs)
                return ret
            except KeyError as e:
                print("{} Warning: Unknown key ({})".format(self.name, str(e)))
            except TypeError as e:
                # traceback.print_exc()
                print("{} Warning: {}".format(self.name, str(e)))
            except AttributeError as e:
                print("{} Warning: {}".format(self.name, str(e)))
            except IndexError as e:
                print("{} Warning: {}".format(self.name, str(e)))
            except RuntimeWarning :
                pass
            print("[{}] {} retry - {}: ".format(self.name, i, kwargs))
            time.sleep(1)

        # 정해진 횟수의 시도가 실패할 경우 system 종료
        print("MAX RETRY:", max_retry_cnt)
        raise SystemExit
    return wrapper

class Binance:
    '''
    Thread safe wrapper
    '''
    def __init__(self):
        with open("binance.conf") as f:
            lines = f.readlines()
            key = lines[0].strip()
            secret = lines[1].strip()
            self.binance = ccxt.binance({
                'apiKey': key,
                'secret': secret,
                'options': {'adjustForTimeDifference': True}
            })
        self.lock = threading.Lock()

        # 1회 주문에 사용될 예산을 구한다
        self.min_budget = self._get_budget() / 10

        # 제약 조건을 받아온다
        resp = self.binance.load_markets()
        self.restriction = {}
        for k, v in resp.items():
            self.restriction[k] = {}
            self.restriction[k]['min_quanity'] = v['limits']['amount']['min']
            self.restriction[k]['min_cost'] = v['limits']['cost']['min']
            self.restriction[k]['precision'] = v['precision']['amount']
            self.restriction[k]['hold'] = False

    @threadable
    def delay_cancel(self, ticker, order_id):
        # 3분 후 주문 취소
        time.sleep(60 * 3)
        self.cancel_order(ticker, order_id)
        remaining_unit = self.get_remaining(ticker, order_id)
        if not remaining_unit > 0:
            self.market_sell(ticker, remaining_unit)

        binance.restriction[ticker]['hold'] = False

    @error_check
    def cancel_order(self, ticker, order_id):
        self.lock.acquire()
        try:
            logger.info("{} ".format(inspect.stack()[0][3]))
            logger.debug(" - ticker {} order_id {}".format(ticker, order_id))
            self.binance.cancel_order(order_id, ticker)
        except OrderNotFound:
            pass
        self.lock.release()

    @error_check
    def get_remaining(self, ticker, order_id):
        self.lock.acquire()
        logger.info("{} ".format(inspect.stack()[0][3]))
        logger.debug(" - ticker {} order_id {}".format(ticker, order_id))
        resp = self.binance.fetch_order(order_id, ticker)
        self.lock.release()
        return resp['remaining']

    @error_check
    def limit_sell(self, ticker, price):
        self.lock.acquire()
        logger.info("{} ".format(inspect.stack()[0][3]))
        resp = self.binance.fetch_balance()
        unit = resp[ticker.split('/')[0]]['free']
        logger.debug(" - ticker {} price {} quanity {}".format(ticker, price, unit))
        resp = self.binance.create_limit_sell_order(ticker, unit, price)
        logger.debug(" - ticker {} order_id {}".format(ticker, resp['info']['orderId']))
        self.lock.release()
        return resp['info']['orderId']

    @error_check
    def market_buy(self, ticker, price):
        unit = 0
        self.lock.acquire()
        usdt_balance = self.binance.fetch_free_balance()['USDT']
        if usdt_balance >= self.min_budget:
            unit = self.min_budget / float(price)
            unit = round(unit, self.restriction[ticker]['precision'])
            logger.info("{} ".format(inspect.stack()[0][3]))
            logger.debug(" - ticker {} price {} quanity {}".format(ticker, price, unit))
            resp = self.binance.create_market_buy_order(ticker, unit)
            logger.debug(" - ticker {} order_id {}".format(ticker, resp['info']['orderId']))
            binance.restriction[ticker]['hold'] = True
        self.lock.release()

    @error_check
    def market_sell(self, ticker, unit):
        self.lock.acquire()
        logger.info("{} ".format(inspect.stack()[0][3]))
        logger.debug(" - ticker {} quanity {}".format(ticker, unit))
        self.binance.create_market_sell_order(ticker, unit)
        binance.restriction[ticker]['hold'] = False
        self.lock.release()

    @error_check
    def get_current_prices(self, ticker_list):
        self.lock.acquire()
        logger.info("{} ".format(inspect.stack()[0][3]))
        resp = self.binance.fetch_tickers()
        self.lock.release()
        return {ticker: resp[ticker]['ask'] for ticker in ticker_list}

    @error_check
    def get_ohlcs(self, ticker, time_unit, limit):
        self.lock.acquire()
        resp = self.binance.fetch_ohlcv(ticker, time_unit, limit=limit)
        self.lock.release()
        for i in range(len(resp)):
            resp[i][0] = datetime.datetime.fromtimestamp(int(resp[i][0] / 1000)).strftime('%Y-%m-%d %H:%M:%S')
        return DataFrame(resp, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    @error_check
    def get_tickers(self, market="USDT"):
        '''
        :return: 마켓이 지원하는 ticker의 리스트를 반환
        '''
        self.lock.acquire()
        response = self.binance.fetch_markets()
        self.lock.release()
        return [x['symbol'] for x in response if x['id'].endswith(market)]

    @error_check
    def _get_budget(self):
        self.lock.acquire()
        usdt_balance = self.binance.fetch_free_balance()['USDT']
        self.lock.release()
        budget_per_coin = usdt_balance / COIN_NUMS
        return budget_per_coin


class HistoryThread:
    '''
    '''
    def __init__(self, binance, ticker_list, time_unit, window, period):
        self.ma3 = {}
        self.ma6 = {}
        self.target_price = {}
        self._execute(binance, ticker_list, time_unit, window, period)

    @threadable
    def _execute(self, binance, ticker_list, time_unit, window, period):
        while(1) :
            for ticker in ticker_list:
                df = binance.get_ohlcs(ticker, time_unit, window)
                ma3 = df['close'].rolling(window=3).mean()
                self.ma3[ticker] = ma3.iloc[-1]
                ma6 = df['close'].rolling(window=6).mean()
                self.ma6[ticker] = ma6.iloc[-1]
                # 쉽게 문제를 해결해보자. 정확하게 같지 않다.
                target = df['close'] + (df['high'] - df['low']) * LARRY_K
                self.target_price[ticker] = target.iloc[-1]
                time.sleep(0.5)
            time.sleep(period)


class PortFolioThread:
    '''
    '''
    def __init__(self, binance, ticker_list, time_unit, window, period):
        self.portfolio = {}
        self._execute(binance, ticker_list, time_unit, window, period)

    @threadable
    def _execute(self, binance, ticker_list, time_unit, window, period):
        while(1):
            self.portfolio = {}
            noise_list = []
            for ticker in ticker_list:
                df = binance.get_ohlcs(ticker, time_unit, window)
                noise = 1 - abs(df['open'] - df['close']) / (df['high'] - df['low'])
                average_noise = noise.rolling(window=window).mean().dropna(axis=0)
                if average_noise.size != 0:
                    noise_list.append((ticker, average_noise.iloc[-1]))
                time.sleep(0.5)

            # noise가 낮은 순으로 정렬
            sorted_noise_list = sorted(noise_list, key=lambda x: x[1])
            for x in sorted_noise_list[:COIN_NUMS]:
                if x[1] < DUAL_NOISE_LIMIT:
                    self.portfolio[x[0]] = x[1]
            time.sleep(period)


if __name__ == "__main__":

    binance = Binance()

    # 바이넨스가 지원하는 코인 리스트를 얻는다.
    ticker_list = binance.get_tickers("USDT")

    # 백그라운드 반복 실행
    # -  1분봉  1 분에 이동평균을 업데이트한다
    # - 60분봉 60 분에 한 번씩 이동평균 업데이트
    # - 포트폴리오 5분에 한 번씩 업데이트
    history_m = HistoryThread(binance, ticker_list, "1m", 6, 60)
    history_h = HistoryThread(binance, ticker_list, "1h", 6, 3600)
    pf3m = PortFolioThread(binance, ticker_list, "1m", 3, 60 * 5)

    while(1):
        now = datetime.datetime.now()
        portfoio = pf3m.portfolio.copy()
        current_price = binance.get_current_prices(portfoio)

        print("---"*5)
        print(now)
        for ticker in portfoio:
            is_hold = binance.restriction[ticker]['hold']
            if is_hold:
                disp = 'x'
            else:
                disp = 'o'
            print("{:>9}-{}: 현재가:{:>4.2f} / 목표가:{:>4.2f} / 3m:{:>4.2f} / 6m:{:>4.2f} / 3h:{:>4.2f} / 6h:{:>4.2f}".format(
                ticker, disp, current_price[ticker], history_m.target_price[ticker], history_m.ma3[ticker], history_m.ma6[ticker], history_h.ma3[ticker], history_h.ma6[ticker]))

            # 매수 조건
            # 1) 현재가가 목표가 이상
            # 2) 1분봉 골든 크로스
            # 3) 60분봉 골든 크로스
            # 4) 코인을 보유하지 않음
            if (history_m.target_price[ticker] <= current_price[ticker]) and \
                    (history_m.ma3[ticker] < current_price[ticker]) and (history_m.ma6[ticker] < current_price[ticker]) and \
                    (history_h.ma3[ticker] < current_price[ticker]) and (history_h.ma6[ticker] < current_price[ticker]) and \
                    (binance.restriction[ticker]['hold'] is False):

                if DEBUG :
                    print("매수")
                    print("{}: 현재가:{:>4.2f} / 목표가:{:>4.2f}".format(ticker, current_price[ticker], history_m.target_price[ticker]))
                else:
                    print(" ## {}: 매수".format(ticker))
                    price = current_price[ticker]

                    binance.market_buy(ticker, price)

                    # 매도 주문을 1% 상승 가격에 걸어 놓는다.
                    order_id = binance.limit_sell(ticker, price * 1.01)
                    binance.delay_cancel(ticker, order_id)

        time.sleep(5)
