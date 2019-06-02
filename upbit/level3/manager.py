import pyupbit
import datetime


def create_instance():
    with open("upbit.txt") as f:
        lines = f.readlines()
        key = lines[0].strip()
        secret = lines[1].strip()

    inst = pyupbit.Upbit(key, secret)
    return inst


def print_status(now, status, cur_price):
    try:
        now = str(now)[:19]
        print("-" * 80)
        print(now)
        for hour in status:
            # 보유여부
            if status[hour][0] is True:
                hold = "보유 중"
            else:
                hold = "미 보유 중"

            # 목표가
            if status[hour][1] is None:
                target = 0
                betting = 0
            else:
                target = status[hour][1]
                betting = status[hour][2]

            print("    시간대: {:02d} 목표가: {:,} 현재가: {:,} 배팅율: {:.2f} {}".format(int(hour), int(target), int(cur_price), betting, hold))
    except:
        pass


if __name__ == "__main__":
    inst = create_instance()
    print(inst.get_balance("KRW"))
