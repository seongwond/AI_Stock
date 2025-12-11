import logging
import time
import random

# 로깅 설정
logging.basicConfig(
    filename='stock_assistant.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def get_headers():
    """
    네이버 크롤링 차단 방지를 위한 User-Agent 헤더 생성
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
    ]
    return {'User-Agent': random.choice(user_agents)}

def random_sleep(min_seconds=0.5, max_seconds=1.5):
    """
    크롤링 속도 조절을 위한 랜덤 슬립
    """
    time.sleep(random.uniform(min_seconds, max_seconds))

def log_error(message):
    logging.error(message)

def log_info(message):
    logging.info(message)
