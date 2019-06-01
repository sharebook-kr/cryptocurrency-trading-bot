import pyupbit
import pandas as pd


pd.options.display.float_format = '{:.2f}'.format


def get_moving_average_score(df, target):
    try:
        moving_average_score = 0
        for window in range(3, 21):
            s = df['close'].rolling(window).mean()
            moving_average = s[-2]                              # N일 이동평균

            # 목표가가 이동평균선을 넘었는지를 비교
            if target > moving_average:
                moving_average_score += 1/18

        return moving_average_score
    except:
        return None


def get_volatility_adjustment_ratio(df):
    try:
        yesterday = df.iloc[-2]
        target_volatility = 0.02            # 2%

        # 변동성 조절 비율 = 타겟변동성/전일변동성/대상암호화폐 수
        # 전일 변동성 : (전일 고점-전일 저점)/전일 종가
        yesterday_volatility = (yesterday['high'] - yesterday['low']) / yesterday['close']
        volatility_adjustment_ratio = target_volatility / yesterday_volatility
        return volatility_adjustment_ratio
    except:
        return None


def get_betting_ratio(df, target, num_coins=1):
    try:
        mas = get_moving_average_score(df, target)
        var = get_volatility_adjustment_ratio(df)
        return (mas * var) / num_coins
    except:
        return None


if __name__ == "__main__":
    df = pyupbit.get_ohlcv("KRW-BTC")
    yesterday = df.iloc[-2]
    today = df.iloc[-1]
    target = today['open'] + (yesterday['high'] - yesterday['low']) * 0.5

    betting_ratio = get_betting_ratio(df, target, num_coins=1)
    print("배팅비율: ", betting_ratio)
