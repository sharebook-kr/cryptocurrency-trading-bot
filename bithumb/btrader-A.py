#----------------------------------------------------------------------------------------------------------------------
# PyStock
# Larry Williams Volatility Breakout Strategy + Moving Average
#----------------------------------------------------------------------------------------------------------------------
# A version
#
#----------------------------------------------------------------------------------------------------------------------
import pybithumb
import time
import datetime
import logging
import logging.handlers

MIN_ORDERS = {"BTC": 0.001, "ETH": 0.01, "DASH": 0.01, "LTC": 0.01, "ETC": 0.1, "XRP": 10, "BCH": 0.001,
              "XMR": 0.01, "ZEC": 0.01, "QTUM": 0.1, "BTG": 0.1, "EOS": 0.1, "ICX": 1, "VEN": 1, "TRX": 100,
              "ELF": 10, "MITH": 10, "MCO": 10, "OMG": 0.1, "KNC": 1, "GNT": 10, "HSR": 1, "ZIL": 100,
              "ETHOS": 1, "PAY": 1, "WAX": 10, "POWR": 10, "LRC": 10, "GTO": 10, "STEEM": 10, "STRAT": 1,
              "ZRX": 1, "REP": 0.1, "AE": 1, "XEM": 10, "SNT": 10, "ADA": 10, "PPT": 1, "CTXC": 10,
              "CMT": 10, "THETA": 10, "WTC": 1, "ITC": 10}

#----------------------------------------------------------------------------------------------------------------------
# 아래의 값을 적당히 수정해서 사용하세요.
#----------------------------------------------------------------------------------------------------------------------
INTERVAL = 1                                        # 매수 시도 interval (1초 기본)
DEBUG = False                                      # True: 매매 API 호출 안됨, False: 실제로 매매 API 호출

COIN_NUMS = 15                                      # 분산 투자 코인 개수 (자산/COIN_NUMS를 각 코인에 투자)
LARRY_K = 0.5

GAIN = 0.3                                          # 30% 이상 이익시 50% 물량 익절
DUAL_NOISE_LIMIT1 = 0.75                            # 듀얼 노이즈가 0.75 이하인 종목만 투자


#----------------------------------------------------------------------------------------------------------------------
# Logging
#----------------------------------------------------------------------------------------------------------------------
logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)

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
    익일 00:01:00 시각과 00:01:10초를 만드는 함수
    :param now:
    :return:
    '''
    tomorrow = now + datetime.timedelta(1)
    setup_time = datetime.datetime(year=tomorrow.year,
                                   month=tomorrow.month,
                                   day=tomorrow.day,
                                   hour=0,
                                   minute=1,
                                   second=0)
    setup_time_after_10secs = setup_time + datetime.timedelta(seconds=10)
    return setup_time, setup_time_after_10secs


def inquiry_cur_prices(tickers):
    '''
    모든 가상화폐에 대한 현재가 조회
    :param tickers: 티커 목록, ['BTC', 'XRP', ... ]
    :return: 현재가, {'BTC': 7200000, 'XRP': 500, ...}
    '''
    try:
        all = pybithumb.get_current_price("ALL")
        cur_prices = {ticker: int(all[ticker]['closing_price']) for ticker in tickers}
        return cur_prices
    except:
        logger.info("inquiry_cur_prices error")
        return None


def cal_noise(tickers, window=5):
    '''
    모든 가상화폐에 대한 최근 5일 noise의 평균을 계산
    :param tickers: 티커 리스트
    :param window: 평균을 위한 윈도우 길이
    :return:
    '''
    try:
        noise_dict = {}

        for ticker in tickers:
            df = pybithumb.get_ohlcv(ticker)
            noise = 1 - abs(df['open'] - df['close']) / (df['high'] - df['low'])
            average_noise = noise.rolling(window=window).mean()
            noise_dict[ticker] = average_noise[-2]

        return noise_dict
    except:
        logger.info("cal_noise error")
        return None


def cal_target(ticker):
    '''
    각 코인에 대한 목표가 계산
    :param ticker: 코인에 대한 티커
    :return:
    '''
    try:
        df = pybithumb.get_ohlcv(ticker)
        yesterday = df.iloc[-2]
        today = df.iloc[-1]
        today_open = today['open']
        yesterday_high = yesterday['high']
        yesterday_low = yesterday['low']
        target = today_open + (yesterday_high - yesterday_low) * LARRY_K
        return target
    except:
        logger.info("cal_target error {}".format(ticker))
        return None


def inquiry_high_prices(tickers):
    try:
        high_prices = {}
        for ticker in tickers:
            df = pybithumb.get_ohlcv(ticker)
            today = df.iloc[-1]
            today_high = today['high']
            high_prices[ticker] = today_high
        return high_prices
    except:
        logger.info("inquiry_high_prices error")
        return  {ticker:0 for ticker in tickers}


def inquiry_targets(tickers):
    '''
    모든 코인에 대한 목표가 계산
    :param tickers: 코인에 대한 티커 리스트
    :return:
    '''
    targets = {}
    for ticker in tickers:
        targets[ticker] = cal_target(ticker)
    return targets


def cal_moving_average(ticker="BTC", window=5):
    '''
    5일 이동평균을 계산
    :param ticker:
    :param window:
    :return:
    '''
    try:
        df = pybithumb.get_ohlcv(ticker)
        close = df['close']
        ma_series = close.rolling(window=window).mean()
        yesterday_ma = ma_series[-2]
        return yesterday_ma
    except:
        logger.info("cal_moving_average error")
        return None


def inquiry_moving_average(tickers):
    '''
    모든 코인에 대해 5일 이동평균값을 계산
    :param tickers: 티커 리스트
    :return:
    '''
    mas = {}
    for ticker in tickers:
        ma = cal_moving_average(ticker)
        mas[ticker] = ma
    return mas


def try_buy(tickers, prices, targets, noises, mas, budget_per_coin, holdings, high_prices):
    '''
    모든 가상화폐에 대해 매수 조건 확인 후 매수 시도
    :param tickers: 티커 리스트
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param noises: noise 리스트
    :param mas: 이동평균 리스트
    :param budget_per_coin: 코인 당 투자 금액
    :param holdings: 보유 여부 리스트
    :param high_prices: 당일 고가 리스트
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]              # 현재가
            target = targets[ticker]            # 목표가
            noise = noises[ticker]              # noise
            ma = mas[ticker]                    # N일 이동평균
            high = high_prices[ticker]          # 당일 고가

            # 매수 조건
            # 0) noise가 0.75 이하이고
            # 1) 현재가가 목표가 이상이고
            # 2) 당일 고가가 목표가 대비 2% 이상 오르지 않았으며 (프로그램을 장중에 실행했을 때 고점찍고 하락중인 종목을 사지 않기 위해)
            # 3) 현재가가 5일 이동평균 이상이고
            # 4) 해당 코인을 보유하지 않았을 때
            # 5) 현재가가 100원 이상
            if holdings[ticker] is False:
                if price >= 100 and noise <= DUAL_NOISE_LIMIT1 and price >= target and target >= ma and high <= target * 1.02:
                    orderbook = pybithumb.get_orderbook(ticker)
                    asks = orderbook['asks']
                    sell_price = asks[0]['price']
                    unit = budget_per_coin/float(sell_price)

                    if DEBUG is False:
                        bithumb.buy_market_order(ticker, unit)
                    else:
                        logger.info("BUY API CALLED {} {}".format(ticker, unit))
                    time.sleep(INTERVAL)
                    holdings[ticker] = True
    except:
        logger.info("try buy error")
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
                time.sleep(INTERVAL)
            else:
                logger.info("SELL API CALLED {} {}".format(ticker, unit))

            retry_cnt = retry_cnt - 1
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
                    if ret is None:
                        retry_sell(ticker, unit, 10)
                else:
                    logger.info("SELL API CALLED {} {}".format(ticker, unit))
    except:
        logger.info("try_sell error")
        pass


def try_profit_cut(tickers, prices, targets, holdings):
    '''
    trailling stop
    :param tickers: 티커 리스트
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param holdings: 보유 여부 리스트
    :return:
    '''
    try:
        for ticker in tickers:
            price = prices[ticker]                          # 현재가
            target = targets[ticker]                        # 매수가
            gain = (price - target) / target                # 이익률: (매도가-매수가)/매수가

            if holdings[ticker] is True:
                if gain >= GAIN:
                    unit = bithumb.get_balance(ticker)[0] / 2   # 50% 물량 매도
                    min_order = MIN_ORDERS.get(ticker, 0.001)

                    if unit >= min_order:
                        if DEBUG is False:
                            ret = bithumb.sell_market_order(ticker, unit)
                            time.sleep(INTERVAL)
                            if ret is None:
                                retry_sell(ticker, unit, 10)
                            else:
                                holdings[ticker] = False
                        else:
                            logger.info("Trailing Stop {} {}".format(ticker, unit))
    except:
        logger.info("try_trailing_stop error")
        pass


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


def print_status(now, tickers, prices, targets, noises, mas, high_prices):
    '''
    현재 상태를 출력
    :param now: 현재 시간
    :param tickers: 티커 리스트
    :param prices: 현재가 리스트
    :param targets: 목표가 리스트
    :param noises: noise 리스트
    :param mas: moving average 리스트
    :param high_prices: 당일 고가 리스트
    :return:
    '''
    try:
        print("_" * 80)
        print(now)

        for ticker in tickers:
            noise = noises[ticker]
            target = targets[ticker]
            ma = mas[ticker]
            price = prices[ticker]
            high_price = high_prices[ticker]

            gain = 0.0
            if high_price >= target and target >= ma and noise <= DUAL_NOISE_LIMIT1:
                gain = (price - target) / target                # (매도 - 매수)/매수
                gain = gain * 100

            print("{:<6} {:0.2f} 목표가: {:>8.0f} 이동평균: {:>8.0f} 현재가: {:>8.0f} 고가: {:>8.0f} 수익률: {:>3.1f}".format(ticker, noise, target, ma, price, high_price, gain))
    except:
        logger.info("print_status error")
        pass


#----------------------------------------------------------------------------------------------------------------------
# 매매 알고리즘 시작
#---------------------------------------------------------------------------------------------------------------------
now = datetime.datetime.now()                                           # 현재 시간 조회
sell_time1, sell_time2 = make_sell_times(now)                           # 초기 매도 시간 설정
setup_time1, setup_time2 = make_setup_times(now)                        # 초기 셋업 시간 설정

tickers = pybithumb.get_tickers()                                       # 티커 리스트 얻기

noises = cal_noise(tickers)
targets = inquiry_targets(tickers)                                      # 코인별 목표가 계산
mas = inquiry_moving_average(tickers)                                   # 코인별로 5일 이동평균 계산
budget_per_coin = cal_budget()                                          # 코인별 최대 배팅 금액 계산

holdings = {ticker:False for ticker in tickers}                       # 보유 상태 초기화
high_prices = inquiry_high_prices(tickers)                              # 코인별 당일 고가 저장

while True:
    now = datetime.datetime.now()

    # 당일 청산 (23:50:00 ~ 23:50:10)
    if sell_time1 < now < sell_time2:
        try_sell(tickers)                                                    # 각 가상화폐에 대해 매도 시도
        holdings = {ticker:True for ticker in tickers}                     # 당일에는 더 이상 매수되지 않도록
        time.sleep(10)

    # 새로운 거래일에 대한 데이터 셋업 (00:01:00 ~ 00:01:10)
    if setup_time1 < now < setup_time2:
        tickers = pybithumb.get_tickers()                                   # 티커 목록 갱신
        try_sell(tickers)                                                   # 매도 되지 않은 코인에 대해서 한 번 더 매도 시도

        noises = cal_noise(tickers)
        targets = inquiry_targets(tickers)                                  # 목표가 갱신
        mas = inquiry_moving_average(tickers)                               # 이동평균 갱신
        budget_per_coin = cal_budget()                                      # 코인별 최대 배팅 금액 계산

        sell_time1, sell_time2 = make_sell_times(now)                       # 당일 매도 시간 갱신
        setup_time1, setup_time2 = make_setup_times(now)                    # 다음 거래일 셋업 시간 갱신

        holdings = {ticker:False for ticker in tickers}                   # 모든 코인에 대한 보유 상태 초기화
        high_prices = {ticker: 0 for ticker in tickers}                    # 코인별 당일 고가 초기화
        time.sleep(10)

    # 현재가 조회
    prices = inquiry_cur_prices(tickers)
    update_high_prices(tickers, high_prices, prices)
    print_status(now, tickers, prices, targets, noises, mas, high_prices)

    # 매수
    if prices is not None:
        try_buy(tickers, prices, targets, noises, mas, budget_per_coin, holdings, high_prices)

    # 익절
    try_profit_cut(tickers, prices, targets, holdings)

    time.sleep(INTERVAL)

