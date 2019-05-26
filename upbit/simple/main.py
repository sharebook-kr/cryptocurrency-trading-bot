import pyupbit
import datetime
import time
import larry
import manager

TICKER = "KRW-BTC"
FIAT = "KRW"


upbit = manager.create_instance()
break_out_range = larry.get_break_out_range(TICKER)

hold = False

while True:
    now = datetime.datetime.now()

    # 매도
    if now.hour == 8 and now.minute == 50 and (0 <= now.second <= 10):
        if hold is True:
            coin_size = upbit.get_balance(TICKER)
            upbit.sell_market_order(TICKER, coin_size)
            hold = False

        time.sleep(10)

    # 목표가 갱신
    if now.hour == 9 and now.minute == 0 and (0 <= now.second <= 10):
        break_out_range = larry.get_break_out_range(TICKER)

        # 정상적으로 break out range를 얻은 경우
        if break_out_range is not None:
            time.sleep(10)

    # 매수 시도
    cur_price = pyupbit.get_current_price(TICKER)
    if hold is False and cur_price is not None and cur_price >= break_out_range:
        krw_balance = upbit.get_balance(FIAT)
        upbit.buy_market_order(TICKER, krw_balance)
        hold = True

    # 상태 출력
    manager.print_status(TICKER, hold, break_out_range, cur_price)
    time.sleep(1)




