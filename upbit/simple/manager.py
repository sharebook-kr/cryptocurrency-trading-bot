import pyupbit
import datetime


def create_instance():
    with open("upbit.txt") as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()

    inst = pyupbit.Upbit(key, secret)
    return inst


def print_status(now, ticker, hold, break_out_range, cur_price):
    if hold is True:
        status = "보유 중"
    else:
        status = "미보유 중"
    try:
        now = str(now)[:19]
        print("{}    코인: {:>10} 목표가: {:>8} 현재가: {:>8} {}".format(now, ticker, int(break_out_range), int(cur_price), status))
    except:
        pass


if __name__ == "__main__":
    inst = create_instance()
    print(inst.get_balance("KRW"))
    now = datetime.datetime.now()
    print_status(now, "KRW-BTC", True, 100.0, 90.0)
