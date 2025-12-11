import sqlite3
import config
import utils
from datetime import datetime

class DBManager:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        try:
            # check_same_thread=False는 GUI 환경(스레드)에서 사용하기 위해 필요할 수 있음
            self.conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            utils.log_info(f"SQLite DB Connected: {config.DB_PATH}")
            self.create_table()
        except Exception as e:
            utils.log_error(f"DB Connection Error: {e}")

    def create_table(self):
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            # 분석 결과 저장 테이블 생성
            # SQLite에서는 NUMBER 대신 INTEGER/REAL, VARCHAR2 대신 TEXT 사용
            # AUTOINCREMENT를 위해 INTEGER PRIMARY KEY 사용
            sql = """
                CREATE TABLE IF NOT EXISTS STOCK_ANALYSIS (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    ANALYSIS_DATE TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    TICKER TEXT,
                    NAME TEXT,
                    SCORE REAL,
                    RECOMMENDATION TEXT,
                    BUY_PRICE INTEGER,
                    TARGET_PRICE INTEGER,
                    STOP_LOSS INTEGER,
                    REASONS TEXT
                )
            """
            cursor.execute(sql)
            self.conn.commit()
            utils.log_info("Table STOCK_ANALYSIS checked/created")
        except Exception as e:
            utils.log_error(f"Table Creation Error: {e}")

    def save_result(self, result):
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            # Oracle의 :1, :2 대신 ? 사용
            sql = """
                INSERT INTO STOCK_ANALYSIS 
                (TICKER, NAME, SCORE, RECOMMENDATION, BUY_PRICE, TARGET_PRICE, STOP_LOSS, REASONS)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            reasons_str = "\n".join(result['reasons'])
            
            # 추천 강도 문자열 변환
            rec_str = "관망"
            if result['score'] >= 3: rec_str = "강력 추천"
            elif result['score'] >= 1: rec_str = "매수 추천"
            elif result['score'] <= -2: rec_str = "매도 경고"

            cursor.execute(sql, (
                result['code'],
                result['name'],
                result['score'],
                rec_str,
                result['buy_price'],
                result['target_price'],
                result['stop_loss'],
                reasons_str
            ))
            self.conn.commit()
            utils.log_info(f"Saved result for {result['name']}")
        except Exception as e:
            utils.log_error(f"DB Save Error: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
