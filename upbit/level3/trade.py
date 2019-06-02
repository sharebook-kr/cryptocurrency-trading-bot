import pyupbit
import time
import noise
import larry
import betting


def set_break_out_range(ticker, status, hour):
    df = pyupbit.get_daily_ohlcv_from_base(ticker, base=hour)
    k = noise.get_average_noise_ratio(df, days=9)
    break_out_range = larry.get_break_out_range(df, k)
    betting_ratio = betting.get_betting_ratio(df, break_out_range, num_coins=1)

    status[hour][1] = break_out_range                           # 해당 시간대 목표가 설정
    status[hour][2] = betting_ratio                             # 해당 시간대 베팅 비율


def try_sell(upbit, ticker, status, hour):
    hold = status[hour][0]                                      # 보유 여부
    coin_size = status[hour][3]                                 # 코인양

    if hold is True and coin_size > 0:
        upbit.sell_market_order(ticker, coin_size)              # 해당 시간대 코인 시장가 매도

        status[hour][0] = False                                 # 해당 시간대 코인 보유 없음
        status[hour][3] = 0                                     # 해당 시간대 보유 코인 0
        time.sleep(10)


def try_buy(upbit, ticker, status):
    cur_price = pyupbit.get_current_price(ticker)

    for hour in range(24):
        hold = status[hour][0]                                  # 해당 시간대 보유 여부
        target = status[hour][1]                                # 해당 시간대 목표가
        betting_ratio = status[hour][2]                         # 해당 시간대 배팅률

        # 해당 시간대에 보유 코인이 없고
        # 해당 시간대에 목표가가 설정되어 있고
        # 현재가 > 해당 시간대의 목표가
        if hold is False and target is not None and cur_price > target:
            remained_krw_balance = upbit.get_balance("KRW")             # 원화잔고 조회
            hold_count = sum([x[0] for x in status.values()])           # 각 시간대별 보유 상태

            krw_balance_for_time_frame = remained_krw_balance / (24-hold_count)                 # 타임 프레임 별 투자 금액
            coin_size = upbit.buy_market_order(ticker, krw_balance_for_time_frame * betting_ratio)

            # 매수 상태 업데이트
            status[hour][0] = True                              # 보유여부
            status[hour][3] = coin_size                         # 보유코인 양

            # 현재가 갱신 (매수 시도에 따라 시간이 경과됐으므로)
            cur_price = pyupbit.get_current_price(ticker)







