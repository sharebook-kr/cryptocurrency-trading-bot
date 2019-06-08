"""
HiBit v0.03
"""
import argparse
import pyupbit
import datetime
import time
import larry
import manager
import noise
import betting
import trade

def main(args):

    TICKER = args.ticker    # 투자할 코인의 티커 입력
    NUM_COINS = args.num_coins         # 코인 수
    TIME_FRAMES = args.time_frames

    # 주문을 위한 객체 생성
    upbit = manager.create_instance()

    # 각 시간 대별로 보유 상태 저장
    # 시간대:[보유여부, 목표가, 배팅률, 보유코인양]
    status = {k: [False, None, 0, 0] for k in range(0, TIME_FRAMES)}

    while True:
        now = datetime.datetime.now()

        # 매 시각 30초 정도의 대기 시간을 줌으로써 첫 체결이 될 수 있도록 해줌
        if now.minute == 0 and (30 <= now.second <= 40):
            trade.try_sell(upbit, TICKER, status, now.hour)
            trade.set_break_out_range(TICKER, status, now.hour)

        # 매수 시도
        trade.try_buy(upbit, TICKER, status)

        # 상태 출력
        cur_price = pyupbit.get_current_price(TICKER)
        manager.print_status(now, status, cur_price)
        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', type=str, default='KRW-BTC')
    parser.add_argument('--num_coins', type=int, default=1)
    parser.add_argument('--time_frames', type=int, default=24)

    args = parser.parse_args()
    main(args)
