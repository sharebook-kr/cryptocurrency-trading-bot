import pyupbit
import datetime


def get_break_out_range(ticker, k = 0.5):
    """
    변동성 돌파 전략 목표가를 계산하는 함수
    :param ticker:
    :param k:
    :return:
    """
    try:
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        df = pyupbit.get_ohlcv(ticker, interval="day", count=5)

        if date in df.index:
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            gap = yesterday['high'] - yesterday['low']
            break_out_range = today['open'] + gap * k
            return break_out_range
        else:
            return None
    except:
        return None


if __name__ == "__main__":
    ticker = "KRW-BTC"
    break_out_range = get_break_out_range(ticker)
    print(break_out_range)
