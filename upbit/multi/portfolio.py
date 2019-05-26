import requests
from bs4 import BeautifulSoup


DEFAULT = ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-BCH', 'KRW-LTC']


def get_tickers_by_market_cap_rank(num=5):
    try:
        url = "https://coinmarketcap.com/ko/"
        resp = requests.get(url)
        html = resp.text
        soup = BeautifulSoup(html, "html5lib")
        tags = soup.select("#currencies > tbody > tr > td.no-wrap.text-right.circulating-supply > span > span.hidden-xs")
        tickers_by_market_cap = [tag.text for tag in tags]
        upbit_tickers_by_market_cap = [ 'KRW-' + ticker for ticker in tickers_by_market_cap[:num]]
        return upbit_tickers_by_market_cap
    except:
        return DEFAULT


if __name__ == "__main__":
   tickers = get_tickers_by_market_cap_rank()
   print(tickers)