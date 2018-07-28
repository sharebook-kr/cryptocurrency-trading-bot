#----------------------------------------------------------------------------------------------------------------------
# PyStock
# Larry Williams Volatility Breakout Strategy + Moving Average
#----------------------------------------------------------------------------------------------------------------------

import pyupbit
import time
import datetime
import pandas as pd


#----------------------------------------------------------------------------------------------------------------------
# 기본 설정
#----------------------------------------------------------------------------------------------------------------------
INTERVAL = 1                                        # 매수 시도 interval (1초 기본)
DEBUG = False                                      # True: 매매 API 호출 안됨, False: 실제로 매매 API 호출

COIN_NUMS = 10                                      # 분산 투자 코인 개수 (자산/COIN_NUMS를 각 코인에 투자)
LARRY_K = 0.5                                       # 변동성 돌파 전략 K

TRAILLING_STOP_MIN_PROOFIT = 0.5                    # 최소 50% 이상 수익이 발생한 경우에 Traillig Stop 동작
TRAILLING_STOP_GAP = 0.05                           # 최고점 대비 5% 하락시 매도

DUAL_NOISE_LIMIT1 = 0.8                             # 듀얼 노이즈가 0.8 이하인 종목만 투자
DUAL_NOISE_LIMIT2 = 0.65                            # 듀얼 노이즈 0.65~0.8 종목은 짧게 익절 및 손절
MIN_PROFIT = 0.1                                    # 10% 이익이면 익절
MAX_LOSS   = 0.05                                   # 5% 손실이면 손절


with open("upbit.txt") as f:
    lines = f.readlines()
    key = lines[0].strip()
    secret = lines[1].strip()
    upbit = pyupbit.Upbit(key, secret)


def make_sell_times(now):
    '''
    익일 08:50:00 시각과 08:50:10초를 만드는 함수
    :param now: 현재 시각
    :return:
    '''
    tomorrow = now + datetime.timedelta(1)
    sell_time = datetime.datetime(year=tomorrow.year,
                                  month=tomorrow.month,
                                  day=tomorrow.day,
                                  hour=8,
                                  minute=50,
                                  second=0)
    sell_time_after_10secs = sell_time + datetime.timedelta(seconds=10)
    return sell_time, sell_time_after_10secs


def make_setup_times(now):
    '''
    익일 09:01:00 시각과 09:01:10초를 만드는 함수
    :param now: 현재 시각
    :return:
    '''
    tomorrow = now + datetime.timedelta(1)
    setup_time = datetime.datetime(year=tomorrow.year,
                                   month=tomorrow.month,
                                   day=tomorrow.day,
                                   hour=9,
                                   minute=1,
                                   second=0)
    setup_time_after_10secs = setup_time + datetime.timedelta(seconds=10)
    return setup_time, setup_time_after_10secs


def inquiry_cur_prices(tickers):
    '''
    모든 가상화폐에 대한 현재가 조회
    :param tickers: 티커 목록
    :return: 현재가, {'KRW-BTC': 7200000, 'KRW-XRP': 500, ...}
    '''
    try:
        return pyupbit.get_current_price(tickers)
    except:
        return None


def cal_noise(tickers, window=5):
    '''
    모든 가상화폐에 대한 최근 5일의 noise 평균 계산
    :param tickers: 티커 리스트
    :param window: 평균을 위한 윈도우 길이
    :return:
    '''
    try:
        noise_dict = {}
        for ticker in tickers:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=10)
            noise = 1 - abs(df['open'] - df['close']) / (df['high'] - df['low'])
            average_noise = noise.rolling(window=window).mean()
            noise_dict[ticker] = average_noise[-2]

        return noise_dict
    except:
        return None


def cal_target(ticker, setup_time):
    '''
    각 코인에 대한 목표가 저장
    :param ticker: 티커, 'BTC'
    :return: 목표가
    '''
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=10)
        last_date = pd.Timestamp(df.index.values[-1])
        if last_date != setup_time:
            return -1

        yesterday = df.iloc[-2]
        today = df.iloc[-1]
        today_open = today['open']
        yesterday_high = yesterday['high']
        yesterday_low = yesterday['low']
        target = today_open + (yesterday_high - yesterday_low) * LARRY_K
        return target
    except:
        return None


def inquiry_high_prices(tickers):
    try:
        high_prices = {}
        for ticker in tickers:
            df = pyupbit.get_ohlcv(ticker, interval="day", count=10)
            today = df.iloc[-1]
            today_high = today['high']
            high_prices[ticker] = today_high

        return high_prices
    except:
        return  {ticker:0 for ticker in tickers}


def inquiry_targets(tickers):
    '''
    티커 코인들에 대한 목표가 계산
    :param tickers: 코인에 대한 티커 리스트
    :return:
    '''
    now = datetime.datetime.now()
    setup_time = datetime.datetime(year=now.year, month=now.month, day=now.day, hour=9, minute=0, second=0)

    targets = {}
    for ticker in tickers:
        targets[ticker] = cal_target(ticker, setup_time)

    # 당일 open, high, low, close, volume이 아직 생성되지 않은 경우 목표가 재계산
    for ticker in tickers:
        if targets[ticker] == -1:
            targets[ticker] = cal_target(ticker, setup_time)
            time.sleep(INTERVAL)

    return targets


def cal_moving_average(ticker="BTC", window=5):
    '''
    5일 이동평균을 계산
    :param ticker:
    :param window:
    :return:
    '''
    try:
        df = pyupbit.get_ohlcv(ticker, interval="day", count=10)
        close = df['close']
        ma_series = close.rolling(window=window).mean()
        yesterday_ma = ma_series[-2]
        return yesterday_ma
    except:
        return None


def inquiry_moving_average(tickers):
    '''
    각 코인에 대해 5일 이동평균값을 계산
    :param tickers:
    :return:
    '''
    mas = {}
    for ticker in tickers:
        ma = cal_moving_average(ticker)
        mas[ticker] = ma
    return mas


def try_buy(tickers, prices, targets, noises, ma5s, budget_per_coin, holdings, high_prices):
    '''
    매수 조건 확인 및 매수 시도
    :param tickers: 원화 티커
    :param prices: 각 코인에 대한 현재가
    :param targets: 각 코인에 대한 목표가
    :param ma5s: 5일 이동평균
    :param budget_per_coin: 코인별 최대 투자 금액
    :param holdings: 보유 여부
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]              # 현재가
            target = targets[ticker]            # 목표가
            noise = noises[ticker]              # 노이즈
            ma5 = ma5s[ticker]                  # 5일 이동평균
            high = high_prices[ticker]

            # 매수 조건
            # 0) noise가 0.8 이하이고
            # 1) 현재가가 목표가 이상이고
            # 2) 당일 고가가 목표가 대비 2% 이상 오르지 않았으며 (프로그램을 장중에 실행했을 때 고점찍고 하락중인 종목을 사지 않기 위해)
            # 3) 현재가가 5일 이동평균 이상이고
            # 4) 해당 코인을 보유하지 않았을 때
            if noise <= DUAL_NOISE_LIMIT1 and price >= target and high <= target * 1.02  and price >= ma5 and holdings[ticker] is False:
                orderbook = pyupbit.get_orderbook(ticker)[0]['orderbook_units'][0]
                sell_price = int(orderbook['ask_price'])
                sell_unit = orderbook['ask_size']
                unit = budget_per_coin/float(sell_price)
                min_unit = min(unit, sell_unit)

                if DEBUG is False:
                    upbit.buy_limit_order(ticker, sell_price, min_unit)
                else:
                    print("BUY API CALLED", ticker, sell_price, min_unit)

                time.sleep(INTERVAL)
                holdings[ticker] = True
    except:
        print("try buy error");


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
            orderbook = pyupbit.get_orderbook(ticker)[0]['orderbook_units'][0]
            buy_price = int(orderbook['bid_price'])                                 # 최우선 매수가
            buy_unit = orderbook['bid_size']                                        # 최우선 매수수량
            min_unit = min(unit, buy_unit)

            if DEBUG is False:
                ret = upbit.sell_limit_order(ticker, buy_price, min_unit)
                time.sleep(INTERVAL)
            else:
                print("SELL API CALLED", ticker, buy_price, min_unit)

            retry_cnt = retry_cnt - 1
    except:
        print("retry sell error")

def try_sell(tickers):
    '''
    보유하고 있는 모든 코인에 대해 전량 매도
    :param tickers: 빗썸에서 지원하는 암호화폐의 티커 목록
    :return:
    '''
    try:
        # 잔고조회
        units = get_blance_unit(tickers)

        for ticker in tickers:
            short_ticker = ticker.split('-')[1]
            unit = units.get(ticker, 0)                     # 보유 수량

            if unit > 0:
                orderbook = pyupbit.get_orderbook(ticker)[0]['orderbook_units'][0]
                buy_price = int(orderbook['bid_price'])                                 # 최우선 매수가
                buy_unit = orderbook['bid_size']                                        # 최우선 매수수량
                min_unit = min(unit, buy_unit)

                if DEBUG is False:
                    ret = upbit.sell_limit_order(ticker, buy_price, min_unit)
                    time.sleep(INTERVAL)

                    if ret is None:
                        retry_sell(ticker, unit, 10)
                else:
                    print("SELL API CALLED", ticker, buy_price, min_unit)
    except:
        print("try sell error")


def get_blance_unit(tickers):
    balances = upbit.get_balances()[0]
    units = {ticker:0 for ticker in tickers}

    for balance in balances:
        if balance['currency'] == "KRW":
            continue

        ticker = "KRW-" + balance['currency']        # XRP -> KRW-XRP
        unit = float(balance['balance'])
        units[ticker] = unit
    return units


def try_trailling_stop(tickers, prices, targets, noises, holdings, high_prices):
    '''
    trailling stop
    :param tickers: tickers
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param holdings: 보유 여부 리스트
    :param high_prices: 각 코인에 대한 당일 최고가 리스트
    :return:
    '''
    try:
        # 잔고 조회
        units = get_blance_unit(tickers)

        for ticker in tickers:
            price = prices[ticker]                          # 현재가
            target = targets[ticker]                        # 매수가
            noise = noises[ticker]                          # noise
            high_price = high_prices[ticker]                # 당일 최고가
            unit = units.get(ticker, 0)                     # 보유 수량

            gain = (price - target) / target                # 이익률
            gap_from_high = 1 - (price/high_price)          # 고점과 현재가 사이의 갭

            # 보유하고 있고 잔고가 0 이상이고
            if holdings[ticker] is True and unit > 0:
                # noise가 0.65 보다 적은 종목은 trailing stop
                # noise가 0.65 이상인 종목은 10% 익절, 5% 손절
                if (noise < DUAL_NOISE_LIMIT2 and gain >= TRAILLING_STOP_MIN_PROOFIT and gap_from_high >= TRAILLING_STOP_GAP) or (noise >= DUAL_NOISE_LIMIT2 and (gain >= MIN_PROFIT or gain <= -MAX_LOSS)):
                    orderbook = pyupbit.get_orderbook(ticker)[0]['orderbook_units'][0]
                    buy_price = int(orderbook['bid_price'])                                 # 최우선 매수가
                    buy_unit = orderbook['bid_size']                                        # 최우선 매수수량
                    min_unit = min(unit, buy_unit)

                    if DEBUG is False:
                        ret = upbit.sell_limit_order(ticker, buy_price, min_unit)
                        time.sleep(INTERVAL)

                        if ret is None:
                            retry_sell(ticker, unit, 10)
                    else:
                        print("trailing stop", ticker, buy_price, min_unit)

                    holdings[ticker] = False
    except:
        print("try trailing stop error")

def cal_budget():
    '''
    한 코인에 대해 투자할 투자 금액 계산
    :return: 원화잔고/투자 코인 수
    '''
    try:
        balances = upbit.get_balances()[0]
        krw_balance = 0
        for balance in balances:
            if balance['currency'] == 'KRW':
                krw_balance = float(balance['balance'])
                break
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


def print_status(tickers, now, noises, prices, targets, mas, high_prices):
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
        print("_" * 80)
        print(now)
        larry_coins = []

        for ticker in tickers:
            print("{:<10} {:0.2f} 목표가: {:>8.1f} 이동평균: {:>8.1f} 현재가: {:>8.1f} 고가: {:>8.1f}".format(ticker, noises[ticker], targets[ticker], mas[ticker], prices[ticker], high_prices[ticker]))

            if noises[ticker] <= DUAL_NOISE_LIMIT1 and high_prices[ticker] >= targets[ticker] and high_prices[ticker] >= mas[ticker]:
                larry_coins.append(ticker)

        print(larry_coins)
    except:
        pass


#----------------------------------------------------------------------------------------------------------------------
# 매매 알고리즘 시작
#---------------------------------------------------------------------------------------------------------------------
now = datetime.datetime.now()                                           # 현재 시간 조회
sell_time1, sell_time2 = make_sell_times(now)                           # 초기 매도 시간 설정
setup_time1, setup_time2 = make_setup_times(now)                        # 초기 셋업 시간 설정

tickers = pyupbit.get_tickers(fiat="KRW")                              # 티커 리스트 얻기

noises = cal_noise(tickers)
targets = inquiry_targets(tickers)                                      # 코인별 목표가 계산
mas = inquiry_moving_average(tickers)                                   # 코인별로 5일 이동평균 계산
budget_per_coin = cal_budget()                                          # 코인별 최대 배팅 금액 계산

holdings = {ticker:False for ticker in tickers}                       # 보유 상태 초기화
high_prices = inquiry_high_prices(tickers)                              # 코인별 당일 고가 저장


while True:
    now = datetime.datetime.now()

    # 1차 청산 (08:50:00 ~ 08:50:10)
    if sell_time1 < now < sell_time2:
        try_sell(tickers)                                                 # 각 가상화폐에 대해 매도 시도
        holdings = {ticker:True for ticker in tickers}                  # 당일에는 더 이상 매수되지 않도록
        time.sleep(10)

    # 새로운 거래일에 대한 데이터 셋업 (09:01:00 ~ 09:01:10)
    if setup_time1 < now < setup_time2:
        tickers = pyupbit.get_tickers(fiat="KRW")                          # 티커 리스트 얻기
        try_sell(tickers)                                                   # 매도 되지 않은 코인에 대해서 한 번 더 매도 시도

        targets = inquiry_targets(tickers)                                  # 목표가 갱신
        noises = cal_noise(tickers)
        mas = inquiry_moving_average(tickers)                               # 이동평균 갱신
        budget_per_coin = cal_budget()                                      # 코인별 최대 배팅 금액 계산

        sell_time1, sell_time2 = make_sell_times(now)                       # 당일 매도 시간 갱신
        setup_time1, setup_time2 = make_setup_times(now)                    # 다음 거래일 셋업 시간 갱신

        holdings = {ticker:False for ticker in tickers}                  # 모든 코인에 대한 보유 상태 초기화
        high_prices = {ticker: 0 for ticker in tickers}                   # 코인별 당일 고가 초기화
        time.sleep(10)

    # 현재가 조회
    prices = inquiry_cur_prices(tickers)
    update_high_prices(tickers, high_prices, prices)
    print_status(tickers, now, noises, prices, targets, mas, high_prices)

    # 매수
    if prices is not None:
        try_buy(tickers, prices, targets, noises, mas, budget_per_coin, holdings, high_prices)

    # 매도 (익절)
    try_trailling_stop(tickers, prices, targets, noises, holdings, high_prices)
    time.sleep(INTERVAL)


