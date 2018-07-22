import time
import ccxt
from ccxt.base.errors import *
import threading
import datetime
from pandas import DataFrame

DELAY = 1
COIN_NUMS = 5
DUAL_NOISE_LIMIT = 0.6                              # 듀얼 노이즈
LARRY_K = 0.4
DEBUG = False


def threadable(fn):
    def run(*k, **kw):
        th = threading.Thread(target=fn, args=k, kwargs=kw)
        th.start()
        return th
    return run


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
                'secret': secret
            })
        self.lock = threading.Lock()

        # 1회 주문에 사용될 예산을 구한다
        self.min_budget = self._get_budget()

        # 제약 조건을 받아온다
        resp = self.binance.load_markets()
        self.restriction = {}
        for k, v in resp.items():
            self.restriction[k] = {}
            self.restriction[k]['min_quanity'] = v['limits']['amount']['min']
            self.restriction[k]['min_cost'] = v['limits']['cost']['min']
            self.restriction[k]['precision'] = v['precision']['amount']
            self.restriction[k]['hold'] = False

        # 디버깅 정보
        self.statistic = open("result.txt", "w")
        self.statistic_lock = threading.Lock()
        self.acc_earning = {}
        self.buy_total = {}
        for k, v in resp.items():
            self.acc_earning[k] = 1
            self.buy_total[k] = 0

    @threadable
    def sell_and_delay_cancel(self, ticker, price, unit):
        order_id = self.limit_sell(ticker, price, unit)
        # 15분후 주문 취소
        time.sleep(60 * 15)
        self.cancel_order(ticker, order_id)

        remaining_unit = self.get_remaining(ticker, order_id)
        self.market_sell(ticker, remaining_unit)
        filled_unit = (unit - remaining_unit)

        if not remaining_unit > 0:
            current_price = self.binance.fetch_tickers()[ticker]['ask']
            sell_total = (filled_unit * price + remaining_unit * current_price) * 0.999
        else:
            sell_total = price * unit * 0.000

        # 디버깅을 위한 로그 메시지 덤프
        earning_ratio = sell_total / self.buy_total[ticker]
        self.acc_earning *= earning_ratio
        self.statistic_lock.acquire()
        self.statistic.write(
            "[{:9}] 매수:{:3.4f} 매도:{:3.4f} 수익금:{ 6.2f} 수익률:{:2.2f}%  누적:{:2.2f}%".
            format(ticker, self.buy_total[ticker], sell_total, sell_total - self.buy_total[ticker],earning_ratio, self.acc_earning[ticker]))
        self.statistic_lock.release()

        binance.restriction[ticker]['hold'] = False

    def cancel_order(self, ticker, order_id):
        self.lock.acquire()
        try:
            self.binance.cancel_order(order_id, ticker)
        except OrderNotFound:
            pass
        self.lock.release()

    def get_remaining(self, ticker, order_id):
        self.lock.acquire()
        resp = self.binance.fetch_order(order_id, ticker)
        self.lock.release()
        return resp['remaining']

    def limit_sell(self, ticker, price, quanity):
        self.lock.acquire()
        resp = self.binance.create_limit_sell_order(ticker, quanity, price)
        self.lock.release()
        return resp['info']['orderId']

    def market_buy(self, ticker, price):
        unit = 0
        self.lock.acquire()
        usdt_balance = self.binance.fetch_free_balance()['USDT']
        if usdt_balance >= self.min_budget:
            unit = self.min_budget / float(price)
            unit = round(unit, self.restriction[ticker]['precision'])
            self.binance.create_market_buy_order(ticker, unit)
            # 수수료 0.001
            unit *= 0.999
            # 수수료 포함 매수 금액
            self.buy_total[ticker] = price * unit * 0.999
            binance.restriction[ticker]['hold'] = True
        self.lock.release()
        return unit

    def market_sell(self, ticker, unit):
        self.lock.acquire()
        self.binance.create_market_sell_order(ticker, unit)
        binance.restriction[ticker]['hold'] = False
        self.lock.release()

    def get_current_prices(self, ticker_list):
        self.lock.acquire()
        resp = self.binance.fetch_tickers()
        self.lock.release()
        return {ticker: resp[ticker]['ask'] for ticker in ticker_list}

    def get_ohlcs(self, ticker, time_unit, limit):
        self.lock.acquire()
        resp = self.binance.fetch_ohlcv(ticker, time_unit, limit=limit)
        self.lock.release()
        for i in range(len(resp)):
            resp[i][0] = datetime.datetime.fromtimestamp(int(resp[i][0] / 1000)).strftime('%Y-%m-%d %H:%M:%S')
        return DataFrame(resp, columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    def get_tickers(self, market="USDT"):
        '''
        :return: 마켓이 지원하는 ticker의 리스트를 반환
        '''
        self.lock.acquire()
        response = self.binance.fetch_markets()
        self.lock.release()
        return [x['symbol'] for x in response if x['id'].endswith(market)]

    def _get_budget(self):
        self.lock.acquire()
        usdt_balance = self.binance.fetch_free_balance()['USDT']
        self.lock.release()
        budget_per_coin = usdt_balance / COIN_NUMS
        return budget_per_coin


class MovingAverageThread:
    '''
    '''
    def __init__(self, binance, ticker_list, time_unit, window, period):
        self.average = {}
        self.target_price = {}
        self._execute(binance, ticker_list, time_unit, window, period)

    @threadable
    def _execute(self, binance, ticker_list, time_unit, window, period):
        while(1) :
            for ticker in ticker_list:
                df = binance.get_ohlcs(ticker, time_unit, window)
                ma = df['close'].rolling(window=window).mean()
                self.average[ticker] = ma.iloc[-1]
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
    # - 60 분에 이동평균을 업데이트한다
    # - 5 분에 한 번씩 포트 폴리오를 재선정한다
    ma5h = MovingAverageThread(binance, ticker_list, "1h", 5, 3600)
    pf3m = PortFolioThread(binance, ticker_list, "1m", 3, 60 * 5)


    while(1):
        now = datetime.datetime.now()
        portfoio = pf3m.portfolio.copy()
        current_price = binance.get_current_prices(portfoio)

        print("---"*5)
        print(now)
        for ticker in portfoio:
            print("{}: 현재가{:>4.2f} / 목표가{:>4.2f} / 이평선5 {:4.2f}".format(ticker, current_price[ticker], ma5h.target_price[ticker], ma5h.average[ticker]))
            # 매수 조건
            # 1) 현재가가 목표가 이상
            # 2) 현재가가 5시간 이동평균 이상
            # 3) 코인을 보유하지 않음
            if (ma5h.target_price[ticker] < current_price[ticker]) and (ma5h.average[ticker] < current_price[ticker])\
                    and binance.restriction[ticker]['hold'] is False:

                if DEBUG :
                    print("매수")
                    print("{}: 현재가{:>4.2f} / 목표가{:>4.2f}".format(ticker, current_price[ticker], ma5h.target_price[ticker]))
                else:
                    price = current_price[ticker]
                    unit = binance.market_buy(ticker, price)
                    # 매도 주문을 1% 상승 가격에 걸어 놓는다.
                    binance.sell_and_delay_cancel(ticker, price * 1.1, unit)

        time.sleep(5)
