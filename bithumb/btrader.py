import pybithumb
import time
import datetime
import logging

file_handler = logging.FileHandler("log.txt")
stream_handler = logging.StreamHandler()

logger = logging.getLogger("logger")
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)


with open("bithumb.txt") as f:
    lines = f.readlines()
    key = lines[0].strip()
    secret = lines[1].strip()
    bithumb = pybithumb.Bithumb(key, secret)


def make_times(now):
    tomorrow = now + datetime.timedelta(1)
    midnight = datetime.datetime(year=tomorrow.year,
                                 month=tomorrow.month,
                                 day=tomorrow.day,
                                 hour=0,
                                 minute=0,
                                 second=0)
    midnight_after_10secs = midnight + datetime.timedelta(seconds=10)
    return (midnight, midnight_after_10secs)


def cal_target():
    try:
        df = pybithumb.get_ohlcv("BTC")
        yesterday = df.iloc[-2]

        today_open = yesterday['close']
        yesterday_high = yesterday['high']
        yesterday_low = yesterday['low']
        target = today_open + (yesterday_high - yesterday_low) * 0.5
        return target
    except:
        return None


def cal_moving_average(window=5):
    try:
        df = pybithumb.get_ohlcv("BTC")
        close = df['close']
        ma = close.rolling(window=window).mean()
        return ma[-2]
    except:
        return None


def try_buy(now, price, target, ma):
    try:
        krw = bithumb.get_balance("BTC")[2]
        orderbook = pybithumb.get_orderbook("BTC")
        asks = orderbook['asks']
        sell_price = asks[0]['price']               # 최우선 매도가
        unit = krw/float(sell_price)
        logger.info("원화잔고: {0} 매수수량: {1}".format(krw, unit))

        if price > target and price > ma and (price / target) < 1.005:
            logger.info("    매수 API 호출")
            bithumb.buy_market_order("BTC", unit)
        else:
            logger.info("    매수조건 미달")
            logger.info("    조건1 {}".format(price > target))
            logger.info("    조건2 {}".format(price > ma))
            logger.info("    조건3 {0} {1}".format((price / target) < 1.005, price/target))
    except:
        pass


def try_sell(now):
    try:
        unit = bithumb.get_balance("BTC")[0]
        bithumb.sell_market_order("BTC", unit)
        logger.info("    매도 API 호출 매도수량: {}".format(unit))
    except:
        logger.info("    매도 API 호출 실패")


now = datetime.datetime.now()
time1, time2 = make_times(now)
target = cal_target()
ma5 = cal_moving_average(window=5)

while True:
    now = datetime.datetime.now()
    logger.info("-" * 80)
    logger.info("현재시간: {}".format(now))

    # 00:00:00 ~ 00:00:10
    if time1 < now < time2:
        try_sell(now)
        target = cal_target()
        ma5 = cal_moving_average(window=5)
        time1, time2 = make_times(now)
        time.sleep(10)

    price = pybithumb.get_current_price("BTC")
    logger.info("현재가  : {}".format(price))
    logger.info("목표가  : {}".format(target))
    logger.info("이동평균: {}".format(ma5))

    if price is not None:
        try_buy(now, price, target, ma5)

    time.sleep(0.2)
