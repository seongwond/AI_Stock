import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QTableWidget, 
                             QTableWidgetItem, QProgressBar, QHeaderView, QMessageBox, QTextEdit, QTabWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor
import qdarktheme

import data_collector
import analyzer
import config
import FinanceDataReader as fdr
import pandas as pd

class AnalysisThread(QThread):
    progress_updated = pyqtSignal(int, str)
    analysis_finished = pyqtSignal(list, list) # kr_results, us_results
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            self.progress_updated.emit(5, "모듈 초기화 중...")
            collector = data_collector.DataCollector()
            stock_analyzer = analyzer.Analyzer()

            self.progress_updated.emit(10, "미국 증시 데이터 수집 및 분석 중...")
            us_data = collector.get_us_market_data(config.US_TICKERS.keys())
            
            us_results = []
            for ticker, data in us_data.items():
                total_score = 0
                reasons = []
                
                # 차트 분석
                chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
                total_score += chart_score
                reasons.extend(chart_reasons)
                
                # 거래량 분석
                if len(data['df']) >= 5:
                    avg_vol = data['df']['Volume'].rolling(window=5).mean().iloc[-2]
                    if avg_vol > 0 and data['volume'] > avg_vol * 2:
                        total_score += 1
                        reasons.append("거래량 폭발 (5일 평균 대비 2배 이상)")
                
                # 매매 전략
                buy_price, target_price, stop_loss = stock_analyzer.calculate_trading_strategy(data['price'], total_score)
                
                # 한글 종목명 가져오기
                kor_name = config.US_TICKER_NAMES.get(ticker, ticker)
                display_name = f"{kor_name} ({ticker})"

                us_results.append({
                    'code': ticker,
                    'name': display_name, 
                    'price': data['price'],
                    'change_rate': data['change_rate'],
                    'score': total_score,
                    'reasons': reasons,
                    'buy_price': buy_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss
                })
            us_results.sort(key=lambda x: x['score'], reverse=True)

            # --- 국내 주식 분석 ---
            self.progress_updated.emit(30, "국내 주식 후보군 선정 중...")
            coupling_scores = stock_analyzer.analyze_coupling(us_data, config.KOREA_MAPPING)
            
            candidate_codes = set(coupling_scores.keys())
            df_krx = fdr.StockListing('KRX')
            top_10 = df_krx.sort_values('Marcap', ascending=False).head(10)['Code'].tolist()
            candidate_codes.update(top_10)

            self.progress_updated.emit(40, f"국내 주식 {len(candidate_codes)}개 종목 상세 분석 중...")
            kr_data = collector.get_korea_market_data(list(candidate_codes))
            
            kr_results = []
            total_items = len(kr_data)
            current_item = 0

            for code, data in kr_data.items():
                current_item += 1
                progress = 40 + int((current_item / total_items) * 50)
                
                name = df_krx[df_krx['Code'] == code]['Name'].values[0] if code in df_krx['Code'].values else code
                self.progress_updated.emit(progress, f"{name} 분석 중...")
                
                total_score = 0
                reasons = []
                
                # 1. 미국장 연동
                if code in coupling_scores:
                    total_score += coupling_scores[code]['score']
                    reasons.extend(coupling_scores[code]['reason'])
                    
                # 2. 차트 분석
                chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
                total_score += chart_score
                reasons.extend(chart_reasons)
                
                # 3. 뉴스 분석
                news_titles = collector.get_news_sentiment(name)
                news_score, news_reasons = stock_analyzer.analyze_news(news_titles)
                total_score += news_score
                reasons.extend(news_reasons)
                
                # 4. 거래량 분석
                if len(data['df']) >= 5:
                    avg_vol = data['df']['Volume'].rolling(window=5).mean().iloc[-2]
                    if avg_vol > 0 and data['volume'] > avg_vol * 2:
                        total_score += 1
                        reasons.append("거래량 폭발 (5일 평균 대비 2배 이상)")

                # 5. 매매 전략 계산
                buy_price, target_price, stop_loss = stock_analyzer.calculate_trading_strategy(data['price'], total_score)

                kr_results.append({
                    'code': code,
                    'name': name,
                    'price': data['price'],
                    'change_rate': data['change_rate'],
                    'score': total_score,
                    'reasons': reasons,
                    'buy_price': buy_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss
                })
            
            kr_results.sort(key=lambda x: x['score'], reverse=True)
            self.progress_updated.emit(100, "분석 완료!")
            self.analysis_finished.emit(kr_results, us_results)

        except Exception as e:
            self.error_occurred.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 주식 투자 비서")
        self.setGeometry(100, 100, 1100, 800)
        
        self.setup_ui()
        
        self.thread = AnalysisThread()
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.analysis_finished.connect(self.show_results)
        self.thread.error_occurred.connect(self.show_error)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 헤더
        header_layout = QHBoxLayout()
        title_label = QLabel("📈 AI 주식 투자 비서")
        title_label.setFont(QFont("Malgun Gothic", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4dabf7;") # 밝은 파란색 포인트
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.start_btn = QPushButton("오늘의 추천 종목 분석 시작")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setFont(QFont("Malgun Gothic", 14, QFont.Weight.Bold))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #228be6;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1c7ed6;
            }
            QPushButton:disabled {
                background-color: #868e96;
            }
        """)
        self.start_btn.clicked.connect(self.start_analysis)
        header_layout.addWidget(self.start_btn)
        
        layout.addLayout(header_layout)
        
        # 진행바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4dabf7;
                width: 20px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("준비됨")
        self.status_label.setFont(QFont("Malgun Gothic", 10))
        layout.addWidget(self.status_label)
        
        # 탭 위젯
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #495057; }
            QTabBar::tab {
                background: #343a40;
                color: #adb5bd;
                padding: 10px 20px;
                font-size: 14px;
                font-family: "Malgun Gothic";
            }
            QTabBar::tab:selected {
                background: #495057;
                color: white;
                font-weight: bold;
            }
        """)
        
        self.kr_table = self.create_table()
        self.us_table = self.create_table()
        
        self.tabs.addTab(self.kr_table, "🇰🇷 국내 주식")
        self.tabs.addTab(self.us_table, "🇺🇸 미국 주식")
        
        layout.addWidget(self.tabs)
        
        # 상세 정보 패널
        layout.addWidget(QLabel("🔍 상세 분석 결과 (종목을 클릭하세요)"))
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(200)
        self.detail_text.setFont(QFont("Malgun Gothic", 11))
        self.detail_text.setStyleSheet("background-color: #212529; color: #e9ecef; border: 1px solid #495057; padding: 10px;")
        layout.addWidget(self.detail_text)

    def create_table(self):
        table = QTableWidget()
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["순위", "종목명", "현재가", "추천강도", "매수가", "목표가", "손절가"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setFont(QFont("Malgun Gothic", 10))
        table.itemClicked.connect(self.show_details)
        table.setAlternatingRowColors(True)
        return table

    def start_analysis(self):
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.kr_table.setRowCount(0)
        self.us_table.setRowCount(0)
        self.detail_text.clear()
        self.thread.start()

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def show_results(self, kr_results, us_results):
        self.start_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"분석 완료: 국내 {len(kr_results)}개, 미국 {len(us_results)}개 종목")
        
        self.kr_results = kr_results
        self.us_results = us_results
        
        self.populate_table(self.kr_table, kr_results, is_kr=True)
        self.populate_table(self.us_table, us_results, is_kr=False)

    def populate_table(self, table, results, is_kr):
        table.setRowCount(len(results))
        for i, result in enumerate(results):
            recommendation = "관망"
            color = QColor("#ffffff")
            
            if result['score'] >= 3:
                recommendation = "강력 추천"
                color = QColor("#ff6b6b") # 밝은 빨강
            elif result['score'] >= 1:
                recommendation = "매수 추천"
                color = QColor("#ffc9c9") # 연한 빨강
            elif result['score'] <= -2:
                recommendation = "매도 경고"
                color = QColor("#748ffc") # 파랑
            
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(f"{result['name']} ({result['code']})"))
            
            currency = "원" if is_kr else "$"
            price_fmt = f"{result['price']:,}{currency}" if is_kr else f"${result['price']:,.2f}"
            table.setItem(i, 2, QTableWidgetItem(price_fmt))
            
            rec_item = QTableWidgetItem(recommendation)
            rec_item.setForeground(color)
            rec_item.setFont(QFont("Malgun Gothic", 10, QFont.Weight.Bold))
            table.setItem(i, 3, rec_item)
            
            buy_fmt = f"{result['buy_price']:,}{currency}" if is_kr else f"${result['buy_price']:,.2f}"
            target_fmt = f"{result['target_price']:,}{currency}" if is_kr else f"${result['target_price']:,.2f}"
            stop_fmt = f"{result['stop_loss']:,}{currency}" if is_kr else f"${result['stop_loss']:,.2f}"
            
            table.setItem(i, 4, QTableWidgetItem(buy_fmt))
            table.setItem(i, 5, QTableWidgetItem(target_fmt))
            table.setItem(i, 6, QTableWidgetItem(stop_fmt))

    def show_details(self, item):
        table = item.tableWidget()
        row = item.row()
        
        if table == self.kr_table:
            result = self.kr_results[row]
        else:
            result = self.us_results[row]
        
        details = f"=== {result['name']} 상세 분석 ===\n\n"
        details += f"종합 점수: {result['score']}점\n"
        details += f"등락률: {result['change_rate']}%\n\n"
        details += "[추천 사유]\n"
        for reason in result['reasons']:
            details += f"- {reason}\n"
            
        self.detail_text.setText(details)

    def show_error(self, message):
        self.start_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "오류 발생", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet())
    
    # 전역 폰트 설정
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
