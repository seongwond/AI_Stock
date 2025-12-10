import pandas as pd
import config

class Analyzer:
    def __init__(self):
        pass

    def analyze_coupling(self, us_data, sector_mapping):
        """
        미국 주식 등락률을 기반으로 한국 관련주에 가점을 부여합니다.
        """
        scores = {}
        for us_ticker, data in us_data.items():
            # 해당 미국 주식의 섹터 찾기
            sector = config.US_TICKERS.get(us_ticker)
            if sector and sector in sector_mapping:
                change_rate = data['change_rate']
                
                # 미국 주식이 2% 이상 상승했을 때 가점
                score = 0
                if change_rate >= 3.0:
                    score = 2
                elif change_rate >= 1.0:
                    score = 1
                elif change_rate <= -3.0:
                    score = -2
                elif change_rate <= -1.0:
                    score = -1
                
                # 해당 섹터의 한국 종목들에 점수 부여
                for kr_code in sector_mapping[sector]:
                    if kr_code not in scores:
                        scores[kr_code] = {'score': 0, 'reason': []}
                    
                    if score != 0:
                        scores[kr_code]['score'] += score
                        scores[kr_code]['reason'].append(f"미국 {us_ticker} {change_rate}% 등락 영향")
        return scores

    def analyze_news(self, titles):
        """
        뉴스 제목에서 키워드를 찾아 점수를 매깁니다.
        """
        score = 0
        reasons = []
        
        for title in titles:
            for keyword in config.NEWS_KEYWORDS['positive']:
                if keyword in title:
                    score += 1
                    reasons.append(f"호재 뉴스: {keyword} 포함")
                    break # 한 제목에 여러 키워드가 있어도 한 번만 카운트
            
            for keyword in config.NEWS_KEYWORDS['negative']:
                if keyword in title:
                    score -= 1
                    reasons.append(f"악재 뉴스: {keyword} 포함")
                    break
                    
        return score, list(set(reasons)) # 중복 사유 제거

    def analyze_chart(self, df):
        """
        주가 데이터를 분석하여 기술적 점수를 계산합니다. (이동평균선, RSI)
        """
        score = 0
        reasons = []
        
        if len(df) < 20:
            return 0, ["데이터 부족"]

        # 이동평균선 계산
        ma5 = df['Close'].rolling(window=config.MA_SHORT).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=config.MA_LONG).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]
        
        # 정배열 및 이평선 지지 여부
        if current_price > ma5 and current_price > ma20:
            score += 1
            reasons.append("5일/20일 이평선 상회 (상승 추세)")
        elif current_price < ma5 and current_price < ma20:
            score -= 1
            reasons.append("5일/20일 이평선 하회 (하락 추세)")
            
        # 골든크로스 (최근 2일 기준)
        prev_ma5 = df['Close'].rolling(window=config.MA_SHORT).mean().iloc[-2]
        prev_ma20 = df['Close'].rolling(window=config.MA_LONG).mean().iloc[-2]
        
        if prev_ma5 <= prev_ma20 and ma5 > ma20:
            score += 2
            reasons.append("골든크로스 발생 (매수 신호)")
            
        # RSI 계산 (14일)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        if rsi >= config.RSI_OVERBOUGHT:
            score -= 1
            reasons.append(f"RSI 과열 ({round(rsi, 1)}) - 매도 주의")
        elif rsi <= 30:
            score += 1
            reasons.append(f"RSI 침체 ({round(rsi, 1)}) - 반등 가능성")
            
        return score, reasons

    def calculate_trading_strategy(self, current_price, score):
        """
        점수에 따라 매수가, 목표가, 손절가를 계산합니다.
        """
        buy_price = current_price
        target_price = 0
        stop_loss = 0
        
        # 점수에 따른 목표 수익률 설정
        target_rate = 0.03 # 기본 3%
        if score >= 3:
            target_rate = 0.07 # 강력 추천 7%
        elif score >= 1:
            target_rate = 0.04 # 매수 추천 4%
            
        target_price = int(buy_price * (1 + target_rate))
        
        # 손절가는 -3% 고정 (또는 이평선 이탈 로직 추가 가능)
        stop_loss = int(buy_price * 0.97)
        
        return buy_price, target_price, stop_loss
