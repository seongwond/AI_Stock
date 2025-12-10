import yfinance as yf
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import time

class DataCollector:
    def __init__(self):
        pass

    def get_us_market_data(self, tickers):
        """
        미국 주식(티커 리스트)의 데이터를 가져옵니다.
        """
        data = {}
        print("Collecting US Market Data...")
        for ticker in tickers:
            try:
                # FinanceDataReader를 사용하여 미국 주식 데이터 조회
                # fdr은 미국 주식도 지원함 (예: 'NVDA', 'AAPL')
                df = fdr.DataReader(ticker, '2024') # 1년치 데이터 확보를 위해 2024년부터 (필요시 조정)
                
                # 2024년 데이터가 너무 적으면 2023년부터
                if len(df) < 20:
                     df = fdr.DataReader(ticker, '2023')

                if len(df) >= 2:
                    prev_close = df['Close'].iloc[-2]
                    last_close = df['Close'].iloc[-1]
                    change_rate = ((last_close - prev_close) / prev_close) * 100
                    
                    data[ticker] = {
                        'price': float(last_close),
                        'change_rate': round(change_rate, 2),
                        'volume': int(df['Volume'].iloc[-1]),
                        'df': df
                    }
                else:
                    print(f"Insufficient data for {ticker}")
            except Exception as e:
                print(f"Error fetching {ticker}: {e}")
        return data

    def get_korea_market_data(self, codes):
        """
        한국 주식(종목코드 리스트)의 현재가 및 등락률을 가져옵니다.
        """
        data = {}
        print("Collecting Korea Market Data...")
        for code in codes:
            try:
                # FinanceDataReader를 사용하여 데이터 조회
                df = fdr.DataReader(code, '2024') # 올해 데이터
                if len(df) > 0:
                    last_row = df.iloc[-1]
                    # 전일 대비 등락률 계산 (Change 컬럼이 있으면 사용, 없으면 계산)
                    if 'Change' in df.columns:
                         change_rate = last_row['Change'] * 100
                    else:
                         # 직접 계산 (데이터가 충분할 때)
                         if len(df) >= 2:
                             prev_close = df['Close'].iloc[-2]
                             last_close = df['Close'].iloc[-1]
                             change_rate = ((last_close - prev_close) / prev_close) * 100
                         else:
                             change_rate = 0.0
                    
                    data[code] = {
                        'price': int(last_row['Close']),
                        'change_rate': round(change_rate, 2),
                        'volume': int(last_row['Volume']) if 'Volume' in df.columns else 0,
                        'df': df # 차트 분석을 위해 DataFrame 저장
                    }
            except Exception as e:
                print(f"Error fetching KR stock {code}: {e}")
        return data

    def get_news_sentiment(self, keyword):
        """
        네이버 뉴스에서 특정 키워드(종목명)로 검색하여 뉴스 제목을 크롤링합니다.
        """
        print(f"Crawling News for {keyword}...")
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sm=tab_opt&sort=1&photo=0&field=0&pd=0&ds=&de=&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so%3Add%2Cp%3Aall&is_sug_officeid=0"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        titles = []
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = soup.select('.news_tit')
            
            for item in news_items:
                titles.append(item.get_text())
                if len(titles) >= 10: # 최근 10개만 수집
                    break
        except Exception as e:
            print(f"Error crawling news: {e}")
            
        return titles

if __name__ == "__main__":
    # Test Code
    collector = DataCollector()
    us_data = collector.get_us_market_data(['NVDA', 'TSLA'])
    print("US Data:", us_data)
    
    kr_data = collector.get_korea_market_data(['005930']) # 삼성전자
    print("KR Data Sample:", kr_data['005930']['price'])
    
    news = collector.get_news_sentiment("삼성전자")
    print("News Sample:", news[:3])
