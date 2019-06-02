import pyupbit


def get_average_noise_ratio(df, days=20):
    try:
        start = -2 - days                             # days 이전 날짜 (기본 20일 전)
        end = -2                                      # 어제
        df = df.iloc[start:end].copy()                # 최근 20일간의 데이터
        df['noise_ratio'] = 1 - (abs(df['open'] - df['close']) / (df['high'] - df['low']))
        return df['noise_ratio'].mean()
    except:
        return 1


if __name__ == "__main__":
    df = pyupbit.get_ohlcv("KRW-BTC")
    average_noise_ratio = get_average_noise_ratio(df)
    print(average_noise_ratio)

