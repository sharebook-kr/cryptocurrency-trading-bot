import pyupbit
import datetime
import time
import larry
import manager
import noise
import betting

TICKER = "KRW-BTC"  # 투자할 코인의 티커 입력
FIAT = "KRW"  # Fiat
NUM_COINS = 1  # 코인 수

# 주문을 위한 객체 생성
upbit = manager.create_instance()

# 당일 진입을 위한 초기값 설정
df = pyupbit.get_ohlcv(TICKER)
k = noise.get_average_noise_ratio(df)
break_out_range = larry.get_break_out_range(df, k)
betting_ratio = betting.get_betting_ratio(df, break_out_range, NUM_COINS)

# 코인 보유 상태 (미보유)
hold = False

while True:
    now = datetime.datetime.now()

    # 매도
    if now.hour == 8 and now.minute == 50 and (0 <= now.second <= 10):
        if hold is True:
            coin_size = upbit.get_balance(TICKER)
            upbit.sell_market_order(TICKER, coin_size)
            hold = False
            break_out_range = None  # 다음 목표가 갱신까지 매수되지 않도록

        time.sleep(10)

    # 목표가 갱신 (09:01:00~09:01:10)
    if now.hour == 9 and now.minute == 1 and (0 <= now.second <= 10):
        df = pyupbit.get_ohlcv(TICKER)
        k = noise.get_average_noise_ratio(df)
        break_out_range = larry.get_break_out_range(df, k)
        betting_ratio = betting.get_betting_ratio(df, break_out_range, NUM_COINS)

        # 정상적으로 break out range를 얻은 경우
        if break_out_range is not None and betting_ratio is not None:
            time.sleep(10)

    # 매수 시도
    cur_price = pyupbit.get_current_price(TICKER)
    if hold is False and cur_price is not None and break_out_range is not None and cur_price >= break_out_range:
        krw_balance = upbit.get_balance(FIAT)
        upbit.buy_market_order(TICKER, krw_balance * betting_ratio)
        hold = True

    # 상태 출력
    manager.print_status(now, TICKER, hold, break_out_range, cur_price, betting_ratio)
    time.sleep(1)
