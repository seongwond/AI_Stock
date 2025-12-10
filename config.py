# config.py

# 미국 주식 티커 (섹터 대장주)
US_TICKERS = {
    'NVDA': 'Semiconductor',  # 반도체
    'TSLA': 'Battery',        # 2차전지/전기차
    'AAPL': 'IT',             # IT/모바일
    'MSFT': 'AI_Software',    # AI/소프트웨어
    'AMZN': 'Retail',         # 유통/클라우드
    'GOOGL': 'Internet'       # 인터넷
}

# 미국 주식 한글명 매핑
US_TICKER_NAMES = {
    'NVDA': '엔비디아',
    'TSLA': '테슬라',
    'AAPL': '애플',
    'MSFT': '마이크로소프트',
    'AMZN': '아마존',
    'GOOGL': '구글 (알파벳)'
}

# 한국 관련주 매핑 (미국 섹터 -> 한국 종목 코드)
# 예: 삼성전자(005930), SK하이닉스(000660), LG에너지솔루션(373220) 등
KOREA_MAPPING = {
    'Semiconductor': ['005930', '000660', '042700'],  # 삼성전자, SK하이닉스, 한미반도체
    'Battery': ['373220', '006400', '051910'],        # LG엔솔, 삼성SDI, LG화학
    'IT': ['005930', '009150'],                       # 삼성전자, 삼성전기
    'AI_Software': ['035420', '035720'],              # NAVER, 카카오
    'Retail': ['035420', '005830'],                   # NAVER, DB손해보험(예시)
    'Internet': ['035420', '035720']                  # NAVER, 카카오
}

# 뉴스 키워드 점수
NEWS_KEYWORDS = {
    'positive': ['공급계약', '무상증자', 'FDA 승인', '신고가', '흑자전환', '인수합병', 'M&A', '체결', '급등', '호실적'],
    'negative': ['유상증자', '전환사채', 'CB', '임원 매도', '적자지속', '관리종목', '횡령', '배임', '하락', '손실']
}

# 차트 분석 설정
MA_SHORT = 5
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
