import yfinance as yf
import FinanceDataReader as fdr
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import time
import utils

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
                        'prev_close': float(prev_close),
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
                    
                    # 전일 종가 계산 (데이터가 충분할 때)
                    prev_close = last_row['Close'] # 기본값 (데이터 부족 시)
                    if len(df) >= 2:
                        prev_close = df['Close'].iloc[-2]
                    
                    # 전일 대비 등락률 계산 (Change 컬럼이 있으면 사용, 없으면 계산)
                    if 'Change' in df.columns:
                         change_rate = last_row['Change'] * 100
                    else:
                         if len(df) >= 2:
                             change_rate = ((last_row['Close'] - prev_close) / prev_close) * 100
                         else:
                             change_rate = 0.0
                    
                    data[code] = {
                        'price': int(last_row['Close']),
                        'prev_close': int(prev_close),
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
        
        # utils에서 랜덤 헤더 가져오기
        headers = utils.get_headers()
        
        titles = []
        links = []
        try:
            # 랜덤 슬립으로 차단 방지
            utils.random_sleep()
            
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = soup.select('.news_tit')
            
            for item in news_items:
                titles.append(item.get_text())
                links.append(item['href']) # 링크도 함께 수집
                if len(titles) >= 10: # 최근 10개만 수집
                    break
        except Exception as e:
            print(f"Error crawling news: {e}")
            utils.log_error(f"News Crawling Error ({keyword}): {e}")
            
        return titles, links

    def get_supply_demand(self, ticker):
        """
        pykrx를 사용하여 최근 3일간 외국인/기관 순매수 동향을 파악합니다.
        """
        try:
            # pykrx는 티커만 있으면 됨 (한국 주식)
            from pykrx import stock
            
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d") # 넉넉하게 일주일 전부터
            
            # 투자자별 거래실적 추이 (순매수)
            df = stock.get_market_net_purchases_of_equities_by_ticker(start_date, end_date, ticker)
            
            # 최근 3일치 데이터 확인 (데이터가 적을 수 있으니 체크)
            if len(df) >= 3:
                recent_3days = df.tail(3)
                
                # 외국인 순매수 연속 여부
                foreigner_streak = all(recent_3days['외국인'] > 0)
                
                # 기관 순매수 연속 여부
                institutional_streak = all(recent_3days['기관합계'] > 0)
                
                return foreigner_streak, institutional_streak
            
        except Exception as e:
            print(f"Error fetching supply/demand for {ticker}: {e}")
            utils.log_error(f"Supply/Demand Error ({ticker}): {e}")
            
            
        except Exception as e:
            print(f"Error fetching supply/demand for {ticker}: {e}")
            utils.log_error(f"Supply/Demand Error ({ticker}): {e}")
            
        return False, False

    def get_market_trend(self):
        """
        코스피, 코스닥 지수의 20일 이동평균선 위치를 파악합니다.
        Returns: {'KOSPI': 'bull'/'bear', 'KOSDAQ': 'bull'/'bear'}
        """
        trend = {}
        try:
            print("Checking Market Trend...")
            for symbol, name in [('KS11', 'KOSPI'), ('KQ11', 'KOSDAQ')]:
                df = fdr.DataReader(symbol, '2024')
                if len(df) >= 20:
                    current_price = df['Close'].iloc[-1]
                    ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
                    
                    if current_price < ma20:
                        trend[name] = 'bear' # 하락장
                    else:
                        trend[name] = 'bull' # 상승장
                else:
                    trend[name] = 'bull' # 데이터 부족 시 일단 긍정
        except Exception as e:
            print(f"Error fetching market trend: {e}")
            utils.log_error(f"Market Trend Error: {e}")
            
        return trend

    def get_fundamental_data(self, ticker):
        """
        pykrx를 사용하여 시가총액, 영업이익 등 펀더멘털 데이터를 가져옵니다.
        """
        try:
            from pykrx import stock
            # 오늘 날짜 기준
            date = datetime.now().strftime("%Y%m%d")
            
            # 1. 펀더멘털 (PER, PBR, DIV 등)
            df = stock.get_market_fundamental_by_date(date, date, ticker)
            
            # 2. 시가총액
            cap_df = stock.get_market_cap_by_date(date, date, ticker)
            
            market_cap = 0
            if not cap_df.empty:
                 market_cap = cap_df['시가총액'].iloc[0]
            
            return {
                'market_cap': market_cap,
                # 필요하다면 재무제표 API도 사용 가능하지만, 여기서는 시총과 기본 펀더멘털만 체크
                # 만년 적자 체크는 Fnguide 크롤링 등이 필요하므로 일단 시총 필터링 우선
            }
        except Exception as e:
            # 주말/휴일이라 데이터가 없을 수 있음 -> 전평일로 재시도 로직은 복잡하니 생략하고 None 반환
            # print(f"Fundamental data error for {ticker}: {e}") 
            return None

if __name__ == "__main__":
    # Test Code
    collector = DataCollector()
    us_data = collector.get_us_market_data(['NVDA', 'TSLA'])
    print("US Data:", us_data)
    
    kr_data = collector.get_korea_market_data(['005930']) # 삼성전자
    print("KR Data Sample:", kr_data['005930']['price'])
    
    news = collector.get_news_sentiment("삼성전자")
    print("News Sample:", news[:3])
