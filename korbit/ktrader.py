import pykorbit
import time
import datetime
import logging

file_handler = logging.FileHandler("log.txt")
stream_handler = logging.StreamHandler()

logger = logging.getLogger("logger")
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)


with open("korbit.txt") as f:
    lines = f.readlines()
    email = lines[0].strip()
    password = lines[1].strip()
    key = lines[2].strip()
    secret = lines[3].strip()
    korbit = pykorbit.Korbit(email, password, key, secret)
    refresh_time = datetime.datetime.now()


def make_times(now):
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


def cal_target():
    try:
        df = pykorbit.get_ohlc("BTC")
        yesterday = df.iloc[-1]

        today_open = yesterday['close']
        yesterday_high = yesterday['high']
        yesterday_low = yesterday['low']
        target = today_open + (yesterday_high - yesterday_low) * 0.5
        return target
    except:
        return None


def cal_moving_average(window=5):
    try:
        df = pykorbit.get_ohlc("BTC")
        close = df['close']
        ma = close.rolling(window=window).mean()
        return ma[-1]
    except:
        return None


def try_buy(now, price, target, ma):
    try:
        balances = korbit.get_balances()
        krw = int(balances["krw"]["available"])
        logger.info("원화잔고: {}".format(krw))

        if price > target and price > ma and (price / target) < 1.005:
            logger.info("    매수 API 호출")
            korbit.buy_market_order("BTC", krw)
        else:
            logger.info("    매수조건 미달")
            logger.info("    조건1 {}".format(price > target))
            logger.info("    조건2 {}".format(price > ma))
            logger.info("    조건3 {0} {1}".format((price / target) < 1.005, price/target))
    except:
        pass


def try_sell(now):
    try:
        balances = korbit.get_balances()
        unit = float(balances['btc']['available'])
        korbit.sell_market_order("BTC", unit)
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
    logger.info("갱신시간: {}".format(refresh_time))

    # 30분에 한 번씩 refresh token
    if (now - refresh_time) > datetime.timedelta(minutes=30):
        logger.info("코빗 토큰 갱신 (30분): {0}".format(now))
        korbit.renew_access_token()
        refresh_time = now

    # 09:01:00 ~ 09:01:10
    if time1 < now < time2:
        try_sell(now)
        target = cal_target()
        ma5 = cal_moving_average(window=5)
        time1, time2 = make_times(now)
        time.sleep(10)

    price = pykorbit.get_current_price("BTC")
    logger.info("현재가  : {}".format(price))
    logger.info("목표가  : {}".format(target))
    logger.info("이동평균: {}".format(ma5))

    if price is not None:
        try_buy(now, price, target, ma5)

    time.sleep(0.2)
