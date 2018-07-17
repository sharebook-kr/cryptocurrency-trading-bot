#----------------------------------------------------------------------------------------------------------------------
# PyStock
# Larry Williams Volatility Breakout Strategy + Moving Average
# Ver 0.05
#----------------------------------------------------------------------------------------------------------------------
# History
# v0.05: 1) Trailling Stop 알고리즘 추가
#
# v0.04: 1) 노이즈 비율에 의한 K값 조절 알고리즘 반영
#        2) 매도 시간, 셋업 시간을 분리
#        3) 정적으로 분산 투자 코인 개수 설정
#        4) 이동평균선 스코어에 의한 비팅비율 조정
#
# v0.03: 1) 최소 주문 수량 추가
#        2) RotatingFileHandler
#----------------------------------------------------------------------------------------------------------------------

import pybithumb
import time
import datetime
import logging
import logging.handlers
from pandas import Series


MIN_ORDERS = {"BTC": 0.001, "ETH": 0.01, "DASH": 0.01, "LTC": 0.01, "ETC": 0.1, "XRP": 10, "BCH": 0.001,
              "XMR": 0.01, "ZEC": 0.01, "QTUM": 0.1, "BTG": 0.1, "EOS": 0.1, "ICX": 1, "VEN": 1, "TRX": 100,
              "ELF": 10, "MITH": 10, "MCO": 10, "OMG": 0.1, "KNC": 1, "GNT": 10, "HSR": 1, "ZIL": 100,
              "ETHOS": 1, "PAY": 1, "WAX": 10, "POWR": 10, "LRC": 10, "GTO": 10, "STEEM": 10, "STRAT": 1,
              "ZRX": 1, "REP": 0.1, "AE": 1, "XEM": 10, "SNT": 10, "ADA": 10}


COIN_NUMS = 15                                      # 분산 투자 코인 개수 (자산/COIN_NUMS를 각 코인에 투자)
INTERVAL = 1                                        # 매수 시도 interval (1초 기본)
DEBUG = False                                      # True: 매매 API 호출 안됨, False: 실제로 매매 API 호출

TRAILLING_STOP = True                              # True: Trailling Stop 사용, False: Trailling Stop 미사용
TRAILLING_STOP_MIN_PROOFIT = 0.1                    # 최소 10% 이상 수익이 발생한 경우에 Traillig Stop 동작
TRAILLING_STOP_GAP = 0.05                           # 최고점 대비 5% 하락시 매도

PROFIT_CUT = 0.5                                    # 익절 수익률 (50%)


# Logging
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
#logger.setLevel(logging.ERROR)

file_handler = logging.handlers.RotatingFileHandler("log.txt", maxBytes=100 * 1000000, backupCount=5)
stream_handler = logging.StreamHandler()
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


# Load account
with open("bithumb.txt") as f:
    lines = f.readlines()
    key = lines[0].strip()
    secret = lines[1].strip()
    bithumb = pybithumb.Bithumb(key, secret)


def make_sell_times(now):
    '''
    당일 23:50:00 시각과 23:50:10초를 만드는 함수
    :param now: DateTime
    :return:
    '''
    sell_time = datetime.datetime(year=now.year,
                                  month=now.month,
                                  day=now.day,
                                  hour=23,
                                  minute=50,
                                  second=0)
    sell_time_after_10secs = sell_time + datetime.timedelta(seconds=10)
    return sell_time, sell_time_after_10secs


def make_setup_times(now):
    '''
    익일 00:00:00 시각과 00:00:10초를 만드는 함수
    :param now:
    :return:
    '''
    tomorrow = now + datetime.timedelta(1)
    midnight = datetime.datetime(year=tomorrow.year,
                                 month=tomorrow.month,
                                 day=tomorrow.day,
                                 hour=0,
                                 minute=0,
                                 second=0)
    midnight_after_10secs = midnight + datetime.timedelta(seconds=10)
    return midnight, midnight_after_10secs


def inquiry_prices(tickers):
    '''
    모든 가상화폐에 대한 현재가 조회
    :param tickers: 티커 목록, ['BTC', 'XRP', ... ]
    :return: 현재가, {'BTC': 7200000, 'XRP': 500, ...}
    '''
    try:
        all = pybithumb.get_current_price("ALL")

        prices = {}
        for ticker in tickers:
            prices[ticker] = int(all[ticker]['closing_price'])
        return prices
    except:
        return None


def cal_adaptive_k(df):
    '''
    noise 비율에 따른 k 값 계산
    :param df: 일봉 데이터 (DataFrame)
    :return: k 값
    '''
    try:
        noise = 1 - abs(df['open'] - df['close']) / (df['high'] - df['low'])
        noise_avg = noise.rolling(window=20).mean()
        return noise_avg[-2]
    except:
        return None


def cal_target(ticker, kvalues):
    '''
    각 코인에 대한 목표가 저장
    :param ticker: 티커, 'BTC'
    :return: 목표가
    '''
    try:
        df = pybithumb.get_ohlcv(ticker)
        k = cal_adaptive_k(df)
        kvalues[ticker] = k
        yesterday = df.iloc[-2]

        today_open = yesterday['close']
        yesterday_high = yesterday['high']
        yesterday_low = yesterday['low']
        target = today_open + (yesterday_high - yesterday_low) * k
        return target
    except:
        return None


def cal_multiple_moving_average(ticker="BTC"):
    '''
    3일 ~ 20일의 18개의 이동 평균값을 계산
    :param ticker: 티커
    :return:
    '''
    try:
        df = pybithumb.get_ohlcv(ticker)
        close = df['close']

        multiple_ma = []
        for window in range(3, 21):
            ma_series = close.rolling(window=window).mean()
            ma = ma_series[-2]
            multiple_ma.append(ma)
        return multiple_ma
    except:
        return None


def try_buy(tickers, prices, targets, multiple_mas, budget_per_coin, holdings, profit_cut):
    '''
    매수 조건 확인 및 매수 시도
    :param tickers: 빗썸에서 거래되는 모든 티커 목록
    :param prices: 각 코인에 대한 현재가
    :param targets: 각 코인에 대한 목표가
    :param multiple_mas: 각 코인에 대한 3~20일 이동평균
    :param budget_per_coin: 코인별 최대 투자 금액
    :param holdings: 보유 여부
    :param profit_cut: 익절 여부
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]              # 현재가
            target = targets[ticker]            # 목표가

            if price > target and (price / target) < 1.005 and holdings[ticker] is False and profit_cut[ticker] is False:
                logger.info("    {} 매수 API 호출".format(ticker))

                # 배팅비율에 따른 budget 계산
                # 3 ~ 20일 이동평균값 중 몇개를 넘었는지를 계산 후 이에 따라 배팅 금액 조절
                s = Series(multiple_mas[ticker])
                bull_count = sum(price > s)
                score = bull_count * 0.055
                batting_budget = int(budget_per_coin * score)

                orderbook = pybithumb.get_orderbook(ticker)
                asks = orderbook['asks']
                sell_price = asks[0]['price']                           # 최우선 매도가
                unit = batting_budget/float(sell_price)                  # 매수 가능한 코인 개수 계산

                if DEBUG is False:
                    bithumb.buy_market_order(ticker, unit)
                else:
                    logger.info("매수 API 호출 {} {}".format(tickers, unit))

                time.sleep(INTERVAL)
                holdings[ticker] = True
    except:
        pass


def retry_sell(ticker, unit, retry_cnt=10):
    '''
    retry count 만큼 매도 시도
    :param ticker: 티커
    :param unit: 매도 수량
    :param retry_cnt: 최대 매수 시도 횟수
    :return:
    '''
    try:
        ret = None
        while ret is None and retry_cnt > 0:
            if DEBUG is False:
                ret = bithumb.sell_market_order(ticker, unit)
            else:
                logger.info("매도 API 호출 {} {}".format(ticker, unit))

            retry_cnt = retry_cnt - 1
            time.sleep(INTERVAL)
    except:
        pass


def try_sell(tickers):
    '''
    보유하고 있는 모든 코인에 대해 전량 매도
    :param tickers: 빗썸에서 지원하는 암호화폐의 티커 목록
    :return:
    '''
    try:
        for ticker in tickers:
            unit = bithumb.get_balance(ticker)[0]
            min_order = MIN_ORDERS.get(ticker, 0.001)

            if unit >= min_order:
                if DEBUG is False:
                    ret = bithumb.sell_market_order(ticker, unit)
                time.sleep(INTERVAL)
                logger.info("    {} 매도 API 호출 매도수량: {}".format(ticker, unit))

                # 매도 에러 발생 시 매도 재시도
                if ret is None:
                    retry_sell(ticker, unit, 10)
            else:
                logger.info("    {} 매도 보유 수량 없음".format(ticker))
    except:
        logger.info("    매도 API 호출 실패")


def try_trailling_stop(tickers, prices, targets, holdings, high_prices):
    '''
    trailling stop
    :param tickers: 모든 티커 목록
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param holdings: 보유 여부 리스트
    :param high_prices: 각 코인에 대한 당일 최고가 리스트
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]                          # 현재가
            target = targets[ticker]                        # 매수가
            high_price = high_prices[ticker]                # 당일 최고가

            gain = (price - target) / target                # 이익률
            gap_from_high = 1 - (price/high_price)          # 고점과 현재가 사이의 갭

            if gain >= TRAILLING_STOP_MIN_PROOFIT and gap_from_high >= TRAILLING_STOP_GAP and holdings[ticker] is True:
                unit = bithumb.get_balance(ticker)[0]
                if unit > 0:
                    if DEBUG is False:
                        ret = bithumb.sell_market_order(ticker, unit)
                    time.sleep(INTERVAL)
                    logger.info("    {} Trailling Stop API 호출 매도수량: {}".format(ticker, unit))

                    # 매도 에러 발생 시 매도 재시도
                    if ret is None:
                        retry_sell(ticker, unit, 10)

                    holdings[ticker] = False
                else:
                    logger.info("    {} Trailling Stop 보유 수량 없음".format(ticker))
    except:
        logger.info("    Trailling Stop API 호출 실패")


def try_sell_profit_cut(tickers, prices, targets, holdings, profit_cut):
    '''
    익절 알고리즘 (50% 수익 시 절반 매도)
    :param tickers: 모든 티커 목록
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param holdings: 보유 여부 리스트
    :param profit_cut: 익절 여부 리스트
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]                  # 현재가
            target = targets[ticker]                # 목표가 (매수가)

            # 50% 이상 수익, 보유하고 있고, 익절한적이 없다면
            if ((price - target) / target) >= PROFIT_CUT and holdings[ticker] is True and profit_cut[ticker] is False:
                unit = bithumb.get_balance(ticker)[0]
                unit = unit / 2                                                                  # 수량 50% 익절

                if unit > 0:
                    if DEBUG is False:
                        ret = bithumb.sell_market_order(ticker, unit)
                    time.sleep(INTERVAL)
                    logger.info("    {} 익절 매도 API 호출 매도수량: {}".format(ticker, unit))

                    profit_cut[ticker] = True

                    # 매도 에러 발생 시 매도 재시도
                    if ret is None:
                        retry_sell(ticker, unit, 10)
                else:
                    logger.info("    {} 익절 매도 보유 수량 없음".format(ticker))
    except:
        logger.info("    익절 매도 API 호출 실패")


def inquiry_targets(tickers, kvalues):
    '''
    모든 코인에 대한 목표가 계산
    :param tickers: 코인에 대한 티커 리스트
    :return:
    '''
    targets = {}
    for ticker in tickers:
        targets[ticker] = cal_target(ticker, kvalues)
    return targets


def inquiry_multiple_ma(tickers):
    '''
    각 코인에 대해 3~20일 이동평균값을 계산
    :param tickers:
    :return:
    '''
    multiple_mas = {}
    for ticker in tickers:
        multiple_ma = cal_multiple_moving_average(ticker)
        multiple_mas[ticker] = multiple_ma
    return multiple_mas


def cal_budget():
    '''
    한 코인에 대해 투자할 투자 금액 계산
    :return: 원화잔고/투자 코인 수
    '''
    try:
        krw_balance = bithumb.get_balance("BTC")[2]
        budget_per_coin = int(krw_balance / COIN_NUMS)
        return budget_per_coin
    except:
        return 0


def update_high_prices(tickers, high_prices, cur_prices):
    '''
    모든 코인에 대해서 당일 고가를 갱신하여 저장
    :param tickers: 티커 목록 리스트
    :param high_prices: 당일 고가
    :param cur_prices: 현재가
    :return:
    '''
    try:
        for ticker in tickers:
            cur_price = cur_prices[ticker]
            high_price = high_prices[ticker]
            if cur_price > high_price:
                high_prices[ticker] = cur_price
    except:
        pass


def print_status(tickers, prices, targets, high_prices, kvalues):
    '''
    코인별 현재 상태를 출력
    :param tickers: 티커 리스트
    :param prices: 가격 리스트
    :param targets: 목표가 리스트
    :param high_prices: 당일 고가 리스트
    :param kvalues: k값 리스트
    :return:
    '''
    try:
        for ticker in tickers:
            print("{:<6} 목표가: {:>8} 현재가: {:>8} 고가: {:>8} K: {:0.2f}".format(ticker, int(targets[ticker]), int(prices[ticker]), int(high_prices[ticker]),  kvalues[ticker]))
    except:
        pass


#----------------------------------------------------------------------------------------------------------------------
# 매매 알고리즘 시작
#----------------------------------------------------------------------------------------------------------------------
now = datetime.datetime.now()                                           # 현재 시간 조회
sell_time1, sell_time2 = make_sell_times(now)                           # 초기 매도 시간 설정
setup_time1, setup_time2 = make_setup_times(now)                        # 초기 셋업 시간 설정

tickers = pybithumb.get_tickers()                                       # 티커 리스트 얻기
kvalues = {}
targets = inquiry_targets(tickers, kvalues)                             # 코인별 목표가 계산
multiple_mas = inquiry_multiple_ma(tickers)                             # 코인별로 3~20일 이동평균 계산
budget_per_coin = cal_budget()                                          # 코인별 최대 배팅 금액 계산

holdings = {ticker:False for ticker in tickers}                       # 보유 상태 초기화
profit_cut = {ticker:False for ticker in tickers}                      # 익절 상태 초기화
high_prices = {ticker: 0 for ticker in tickers}                         # 코인별 당일 고가 초기화

while True:
    now = datetime.datetime.now()
    logger.info("-" * 80)
    logger.info("현재시간: {}".format(now))

    # 당일 청산 (23:50:00 ~ 23:50:10)
    if sell_time1 < now < sell_time2:
        try_sell(tickers)                                                    # 각 가상화폐에 대해 매도 시도
        holdings = {ticker:True for ticker in tickers}                     # 당일에는 더 이상 매수되지 않도록
        time.sleep(10)

    # 새로운 거래일에 대한 데이터 셋업 (00:00:00 ~ 00:00:10)
    if setup_time1 < now < setup_time2:
        tickers = pybithumb.get_tickers()                                   # 티커 목록 갱신
        kvalues = {}
        targets = inquiry_targets(tickers, kvalues)                         # 목표가 갱신
        multiple_mas = inquiry_multiple_ma(tickers)                         # 이동평균 갱신
        budget_per_coin = cal_budget()                                      # 코인별 최대 배팅 금액 계산

        sell_time1, sell_time2 = make_sell_times(now)                       # 당일 매도 시간 갱신
        setup_time1, setup_time2 = make_setup_times(now)                    # 다음 거래일 셋업 시간 갱신

        holdings = {ticker:False for ticker in tickers}                   # 모든 코인에 대한 보유 상태 초기화
        profit_cut = {ticker:False for ticker in tickers}                 # 익절 상태 초기화
        high_prices = {ticker: 0 for ticker in tickers}                    # 코인별 당일 고가 초기화
        time.sleep(10)

    # 현재가 조회
    prices = inquiry_prices(tickers)
    update_high_prices(tickers, high_prices, prices)
    print_status(tickers, prices, targets, high_prices, kvalues)

    # 매수
    if prices is not None:
        try_buy(tickers, prices, targets, multiple_mas, budget_per_coin, holdings, profit_cut)

    # Trailling Stop
    if TRAILLING_STOP is True:
        try_trailling_stop(tickers, prices, targets, holdings, high_prices)
    else:
        try_sell_profit_cut(tickers, prices, targets, holdings, profit_cut)

    time.sleep(INTERVAL)

