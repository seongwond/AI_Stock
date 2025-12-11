# config.py

# 미국 주식 티커 (섹터 대장주)
# 미국 주식 티커 (섹터 대장주 및 주요 ETF)
US_TICKERS = {
    # Mag 7 & Big Tech
    'NVDA': 'Semiconductor', 'TSLA': 'EV', 'AAPL': 'IT', 'MSFT': 'AI_Software',
    'AMZN': 'Retail', 'GOOGL': 'Internet', 'META': 'Social', 'NFLX': 'Streaming',
    
    # AI & Semiconductor
    'AMD': 'Semiconductor', 'AVGO': 'Semiconductor', 'INTC': 'Semiconductor', 
    'QCOM': 'Semiconductor', 'TSM': 'Semiconductor', 'MU': 'Semiconductor',

    # Bio & Pharma
    'LLY': 'Bio', 'NVO': 'Bio', 'PFE': 'Bio',

    # Consumer & Dividend
    'KO': 'Consumer', 'PEP': 'Consumer', 'MCD': 'Consumer', 
    'SBUX': 'Consumer', 'O': 'Realty',

    # ETFs (Market & Sector)
    'QQQ': 'ETF_Nasdaq', 'SPY': 'ETF_SP500', 'SOXL': 'ETF_Semi_3x', 
    'TQQQ': 'ETF_Nasdaq_3x', 'JEPI': 'ETF_Dividend', 'SCHD': 'ETF_Dividend'
}

# 미국 주식 한글명 매핑
US_TICKER_NAMES = {
    'NVDA': '엔비디아', 'TSLA': '테슬라', 'AAPL': '애플', 'MSFT': '마이크로소프트',
    'AMZN': '아마존', 'GOOGL': '구글', 'META': '메타(페북)', 'NFLX': '넷플릭스',
    'AMD': 'AMD', 'AVGO': '브로드컴', 'INTC': '인텔', 'QCOM': '퀄컴',
    'TSM': 'TSMC', 'MU': '마이크론',
    'LLY': '일라이릴리', 'NVO': '노보노디스크', 'PFE': '화이자',
    'KO': '코카콜라', 'PEP': '펩시코', 'MCD': '맥도날드', 'SBUX': '스타벅스', 'O': '리얼티인컴',
    'QQQ': 'QQQ (나스닥)', 'SPY': 'SPY (S&P500)', 'SOXL': 'SOXL (반도체 3배)',
    'TQQQ': 'TQQQ (나스닥 3배)', 'JEPI': 'JEPI (월배당)', 'SCHD': 'SCHD (배당성장)'
}

# 한국 관련주 매핑 (미국 섹터 -> 한국 종목 코드)
# 예: 삼성전자(005930), SK하이닉스(000660), LG에너지솔루션(373220) 등
KOREA_MAPPING = {
    'Semiconductor': ['005930', '000660', '042700', '000210'],  # 삼성전자, 닉스, 한미반도체, DL
    'EV': ['373220', '006400', '051910', '003670'],            # LG엔솔, 삼성SDI, LG화학, 포스코퓨처엠
    'IT': ['005930', '009150', '066570'],                      # 삼성전자, 삼성전기, LG전자
    'AI_Software': ['035420', '035720'],                       # NAVER, 카카오
    'Retail': ['035420', '005830'],                            # NAVER, DB손해보험
    'Internet': ['035420', '035720'],                          # NAVER, 카카오
    'Social': ['035420', '035720'],
    'Streaming': ['041510', '003550'],                         # SM, LG
    'Bio': ['207940', '068270'],                               # 삼성바이오로직스, 셀트리온
    'Consumer': ['005380', '000270'],                          # 현대차, 기아 (소비재 대표)
    'ETF_Nasdaq': ['005930'], 'ETF_SP500': ['005930'],         # ETF는 전체 영향
    'ETF_Semi_3x': ['000660'], 'ETF_Nasdaq_3x': ['035420'], 'ETF_Dividend': ['055550']
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

# API 키 설정 (사용자가 직접 입력해야 함)
import os

# API 키 설정 (환경변수 또는 직접 설정)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# SQLite DB 설정
DB_PATH = "stock_data.db"
