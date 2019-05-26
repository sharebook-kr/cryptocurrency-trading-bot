import pyupbit


def create_instance():
    with open("upbit.txt") as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()

    inst = pyupbit.Upbit(key, secret)
    return inst


def print_status(ticker, hold, break_out_range, cur_price):
    if hold is True:
        status = "보유 중"
    else:
        status = "미보유 중"

    print("코인: {:>10} 목표가: {:>8} 현재가: {:>8} {}".format(ticker, int(break_out_range), int(cur_price), status))


if __name__ == "__main__":
    inst = create_instance()
    print(inst.get_balance("KRW"))
    print_status(True, 100.0, 90.0)
