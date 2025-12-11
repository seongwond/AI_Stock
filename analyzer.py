import pandas as pd
import config
import openai
import utils

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

        return scores

    def analyze_news_llm(self, titles):
        """
        OpenAI API를 사용하여 뉴스 제목의 감성을 분석하고 요약합니다.
        Returns: (score, reason)
        """
        if not titles:
            return None, None
            
        try:
            if config.OPENAI_API_KEY == "YOUR_OPENAI_API_KEY_HERE":
                return None, None # 키가 없으면 키워드 분석으로 fallback

            client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
            
            prompt = f"""
            다음 뉴스 제목들을 보고 해당 주식에 대한 호재/악재 여부를 평가해줘.
            
            [응답 형식]
            점수 | 한줄요약
            
            [규칙]
            1. 점수는 -1 (악재) ~ 1 (호재) 사이의 소수점 숫자.
            2. 한줄요약은 뉴스 내용을 종합해서 "왜" 높은/낮은 점수를 줬는지 한국어로 설명 (50자 이내).
            3. 구분자는 파이프(|) 기호 사용.
            
            [뉴스 제목들]
            {chr(10).join(titles)}
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0
            )
            
            content = response.choices[0].message.content.strip()
            
            # 파싱
            if "|" in content:
                parts = content.split("|")
                score_str = parts[0].strip()
                reason_str = parts[1].strip()
                return float(score_str), reason_str
            else:
                # 형식이 안 맞을 경우 점수만이라도 시도
                return float(content), "AI 분석 완료"
            
        except Exception as e:
            utils.log_error(f"LLM Analysis Error: {e}")
            return None, None

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
        주가 데이터를 분석하여 기술적 점수를 계산합니다. (이동평균선, RSI, 볼린저밴드)
        """
        score = 0
        reasons = []
        
        if len(df) < 20:
            return 0, ["데이터 부족"]

        # 1. 이동평균선 및 추세
        ma5 = df['Close'].rolling(window=config.MA_SHORT).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=config.MA_LONG).mean().iloc[-1]
        current_price = df['Close'].iloc[-1]
        
        # 2. 골든크로스 (거래량 동반 필수)
        prev_ma5 = df['Close'].rolling(window=config.MA_SHORT).mean().iloc[-2]
        prev_ma20 = df['Close'].rolling(window=config.MA_LONG).mean().iloc[-2]
        
        if prev_ma5 <= prev_ma20 and ma5 > ma20:
            # 거래량 확인 (최근 5일 평균 대비 150% 이상)
            vol_ma5 = df['Volume'].rolling(window=5).mean().iloc[-2]
            current_vol = df['Volume'].iloc[-1]
            
            if current_vol >= vol_ma5 * 1.5:
                score += 2
                reasons.append("골든크로스 + 거래량 급증 (진짜 상승 신호)")
            else:
                reasons.append("골든크로스 발생했으나 거래량 부족 (신뢰도 낮음)")
            
        # 3. RSI (30 돌파 매수)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=config.RSI_PERIOD).mean()
        
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = rsi_series.iloc[-1]
        prev_rsi = rsi_series.iloc[-2]
        
        if current_rsi >= 70:
            score -= 1
            reasons.append(f"RSI 과열 ({round(current_rsi, 1)}) - 매도 주의")
        elif prev_rsi <= 30 and current_rsi > 30:
            # 30을 밑에서 위로 뚫을 때 점수 부여 (침체 탈출)
            score += 2
            reasons.append(f"RSI 침체 구간 탈출 ({round(current_rsi, 1)}) - 반등 시작")
            
        # 4. 볼린저 밴드 (하단 지지)
        std = df['Close'].rolling(window=20).std().iloc[-1]
        upper_band = ma20 + (std * 2)
        lower_band = ma20 - (std * 2)
        
        if current_price <= lower_band * 1.02: # 하단 밴드 근처 (2% 이내)
            score += 1
            reasons.append("볼린저밴드 하단 지지 (저점 매수 기회)")
            
        return score, reasons

    def analyze_fundamentals(self, data):
        """
        펀더멘털 데이터를 분석하여 자격 미달 종목을 필터링합니다.
        Returns: True(합격), False(불합격), reason
        """
        if not data:
            return True, "데이터 없음 (패스)" # 데이터 없으면 일단 통과
            
        market_cap = data.get('market_cap', 0)
        
        # 1. 시가총액 필터링 (1,000억 원 미만 제외)
        if market_cap < 100000000000:
            return False, f"시가총액 과소 ({round(market_cap/100000000, 1)}억) - 리스크 관리"
            
        return True, "펀더멘털 양호"

    def analyze_market_trend(self, trend_data):
        """
        시장 추세에 따른 페널티 점수를 반환합니다.
        """
        penalty = 0
        reasons = []
        
        if trend_data.get('KOSPI') == 'bear':
            penalty -= 2
            reasons.append("KOSPI 하락장 (20일선 이탈) - 보수적 접근 필요")
            
        if trend_data.get('KOSDAQ') == 'bear':
            penalty -= 2
            reasons.append("KOSDAQ 하락장 (20일선 이탈) - 현금 비중 확대 권장")
            
        return penalty, reasons

    def calculate_trading_strategy(self, current_price, score):
        """
        점수에 따라 매수가, 목표가, 손절가를 계산합니다.
        """
        buy_price = current_price
        target_price = 0
        stop_loss = 0
        
        # 점수에 따른 목표 수익률 설정 (시장 상황 반영 가능)
        target_rate = 0.03 # 기본 3%
        if score >= 5: # 기준 점수 상향 (+3 -> +5)
            target_rate = 0.07 # 강력 추천 7%
        elif score >= 2: # 기준 점수 상향 (+1 -> +2)
            target_rate = 0.05 # 매수 추천 5%
            
        target_price = int(buy_price * (1 + target_rate))
        
        # 손절가는 -3% 칼같이
        stop_loss = int(buy_price * 0.97)
        
        return buy_price, target_price, stop_loss
