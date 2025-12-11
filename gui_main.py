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
import db_manager
import FinanceDataReader as fdr
import pandas as pd

class AnalysisThread(QThread):
    progress_updated = pyqtSignal(int, str)
    analysis_finished = pyqtSignal(list, list) # kr_results, us_results
    error_occurred = pyqtSignal(str)

    def run(self):
        db = None
        try:
            self.progress_updated.emit(5, "모듈 초기화 중...")
            collector = data_collector.DataCollector()
            stock_analyzer = analyzer.Analyzer()
            db = db_manager.DBManager()

            # 0. 시장 추세 파악 (전체 적용)
            self.progress_updated.emit(5, "시장 추세(Bull/Bear) 분석 중...")
            market_trend = collector.get_market_trend()
            trend_penalty, trend_reasons = stock_analyzer.analyze_market_trend(market_trend)

            self.progress_updated.emit(10, "미국 증시 데이터 수집 및 분석 중...")
            us_data = collector.get_us_market_data(config.US_TICKERS.keys())
            
            us_results = []
            for ticker, data in us_data.items():
                total_score = 0
                reasons = []
                
                # 시장 페널티 적용 (미국은 일단 한국 장 추세와 별개로 볼 수도 있으나 설명상 추가)
                # total_score += trend_penalty 
                # reasons.extend(trend_reasons)
                
                # 차트 분석
                chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
                total_score += chart_score
                reasons.extend(chart_reasons)
                
                # 거래량 분석 (기존 유지)
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

                result = {
                    'code': ticker,
                    'name': display_name, 
                    'price': data['price'],
                    'change_rate': data['change_rate'],
                    'score': total_score,
                    'reasons': reasons,
                    'buy_price': buy_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss
                }
                us_results.append(result)
                
                # DB 저장
                db.save_result(result)

            us_results.sort(key=lambda x: x['score'], reverse=True)

            # --- 국내 주식 분석 ---
            self.progress_updated.emit(30, "국내 주식 후보군 선정 중... (Top 50)")
            coupling_scores = stock_analyzer.analyze_coupling(us_data, config.KOREA_MAPPING)
            
            candidate_codes = set(coupling_scores.keys())
            df_krx = fdr.StockListing('KRX')
            top_50 = df_krx.sort_values('Marcap', ascending=False).head(50)['Code'].tolist()
            candidate_codes.update(top_50)

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
                
                # 1. 펀더멘털 필터링 (자격 요건 심사)
                fundamental_data = collector.get_fundamental_data(code)
                is_valid, fund_reason = stock_analyzer.analyze_fundamentals(fundamental_data)
                
                if not is_valid:
                    # 자격 미달 종목은 과감히 스킵하거나 점수 페널티를 줄 수 있음. 여기선 스킵.
                    print(f"Skipping {name}: {fund_reason}")
                    continue

                total_score = 0
                reasons = []
                
                # 시장 추세 페널티 적용
                if trend_penalty != 0:
                    total_score += trend_penalty
                    reasons.extend(trend_reasons)

                # 2. 미국장 연동
                if code in coupling_scores:
                    total_score += coupling_scores[code]['score']
                    reasons.extend(coupling_scores[code]['reason'])
                    
                # 3. 차트 분석
                chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
                total_score += chart_score
                reasons.extend(chart_reasons)
                
                # 4. 뉴스 분석 (LLM + Keyword)
                news_titles, news_links = collector.get_news_sentiment(name)
                
                # LLM 분석 시도
                llm_score, llm_reason = stock_analyzer.analyze_news_llm(news_titles)
                if llm_score is not None:
                    news_score = llm_score * 5 # 다소 높은 가중치 유지 (단, AI 신뢰)
                    total_score += news_score
                    
                    sentiment = "긍정적" if news_score >= 0 else "부정적"
                    if llm_reason:
                        reasons.append(f"[AI 뉴스 분석] {llm_reason} ({round(news_score, 1)}점)")
                    else:
                        reasons.append(f"뉴스 AI 분석 {sentiment} ({round(news_score, 1)}점)")
                else:
                    news_score, news_reasons = stock_analyzer.analyze_news(news_titles)
                    total_score += news_score
                    reasons.extend(news_reasons)
                
                if news_links:
                     reasons.append(f"관련 뉴스: {news_links[0]}")

                # 5. 수급 분석 (로직 개선)
                foreigner_streak, institutional_streak = collector.get_supply_demand(code)
                
                supply_score = 0
                # 기본 점수 하향 (+10 -> +3)
                if foreigner_streak:
                    supply_score += 3
                    reasons.append("외국인 3일 연속 매수 (+3점)")
                if institutional_streak:
                    supply_score += 3
                    reasons.append("기관 3일 연속 매수 (+3점)")
                    
                # 양매수 보너스 (+5)
                if foreigner_streak and institutional_streak:
                    supply_score += 5
                    reasons.append("🔥 메이저 쌍끌이 매수 (추가 +5점)")
                    
                total_score += supply_score
                
                # 6. 거래량 분석 (기존 로직 + 차트에서 이미 골든크로스와 결합됨)
                # 여기서는 '거래량 폭발' 단독 이벤트만 체크
                if len(data['df']) >= 5:
                    avg_vol = data['df']['Volume'].rolling(window=5).mean().iloc[-2]
                    # 전일 대비 200% 이상 & 양봉일 때만 
                    if avg_vol > 0 and data['volume'] > avg_vol * 2 and data['price'] >= data['df']['Open'].iloc[-1]:
                        total_score += 1
                        reasons.append("거래량 폭발+양봉 (진성 매수세)")
 
                # 7. 매매 전략 계산
                buy_price, target_price, stop_loss = stock_analyzer.calculate_trading_strategy(data['price'], total_score)

                # 어제 샀다면?
                yesterday_profit = data['change_rate']
                prev_close = data.get('prev_close', data['price'])
                diff = data['price'] - prev_close

                result = {
                    'code': code,
                    'name': name,
                    'price': data['price'],
                    'change_rate': data['change_rate'],
                    'prev_close': prev_close,
                    'diff': diff,
                    'yesterday_profit': yesterday_profit,
                    'score': total_score,
                    'reasons': reasons,
                    'buy_price': buy_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss
                }
                kr_results.append(result)
                
                # DB 저장
                db.save_result(result)
            
            kr_results.sort(key=lambda x: x['score'], reverse=True)
            self.progress_updated.emit(100, "분석 완료!")
            self.analysis_finished.emit(kr_results, us_results)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if db:
                db.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 주식 투자 비서")
        self.setGeometry(100, 100, 1200, 800) # 너비 확장
        
        self.setup_ui()
        
        self.thread = AnalysisThread()
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.analysis_finished.connect(self.show_results)
        self.thread.error_occurred.connect(self.show_error)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20) # 여백 증가
        layout.setContentsMargins(30, 30, 30, 30)
        
        # --- Modern Stylesheet ---
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa; /* 아주 연한 회색 배경 */
            }
            QWidget {
                color: #343a40;
                font-family: "Malgun Gothic";
            }
            /* Header Style */
            QLabel#TitleLabel {
                color: #228be6;
                font-weight: bold;
            }
            
            /* Button Style (Soft & Round) */
            /* Button Style (Soft & Round) */
            QPushButton {
                background-color: #228be6; /* 솔리드 컬러로 변경 (안전성 확보) */
                color: white;
                border: none;
                border-radius: 12px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #1c7ed6; /* 호버 시 진하게 */
                margin-top: -2px;
            }
            QPushButton:pressed {
                margin-top: 1px;
                background-color: #1864ab;
            }
            QPushButton:disabled {
                background-color: #adb5bd;
            }
            
            /* Table Style (Clean & Spacious) */
            QTableWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 12px;
                gridline-color: transparent; /* 그리드 제거 */
                selection-background-color: #e7f5ff;
                selection-color: #1971c2;
                padding: 5px;
            }
            QTableWidget::item {
                padding: 8px; /* 셀 내부 여백 */
                border-bottom: 1px solid #f1f3f5;
            }
            QHeaderView::section {
                background-color: white;
                color: #868e96;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #228be6;
                padding: 10px;
            }
            
            /* Tab Style (Modern Pill) */
            QTabWidget::pane {
                border: 1px solid #dee2e6;
                border-radius: 12px;
                background: white;
                top: -1px; 
            }
            QTabBar::tab {
                background: #f1f3f5;
                color: #495057;
                padding: 10px 25px;
                margin-right: 5px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background: white;
                color: #228be6;
                border: 1px solid #dee2e6;
                border-bottom: 2px solid white; /* 연결된 느낌 */
            }
            
            /* Progress Bar */
            QProgressBar {
                border: none;
                background-color: #e9ecef;
                border-radius: 10px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #74c0fc;
                border-radius: 10px;
            }
            
            /* Detail Text Area */
            QTextEdit {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 12px;
                padding: 15px;
                color: #495057;
                line-height: 1.6;
            }
        """)

        # 헤더
        header_layout = QHBoxLayout()
        title_label = QLabel("📈 AI 주식 투자 비서")
        title_label.setObjectName("TitleLabel")
        title_label.setFont(QFont("Malgun Gothic", 26, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.start_btn = QPushButton("오늘의 추천 종목 분석 시작")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setMinimumHeight(55)
        # 스타일시트가 전역으로 적용되므로 개별 스타일 제거
        self.start_btn.clicked.connect(self.start_analysis)
        header_layout.addWidget(self.start_btn)
        
        layout.addLayout(header_layout)
        
        # 진행바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("준비됨")
        self.status_label.setStyleSheet("color: #868e96; font-size: 13px;")
        layout.addWidget(self.status_label)
        
        # 탭 위젯
        self.tabs = QTabWidget()
        # 탭 스타일도 전역 스타일시트에서 처리
        
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
        # self.detail_text.setStyleSheet(...) # 전역 스타일시트 사용을 위해 제거
        layout.addWidget(self.detail_text)

    def create_table(self):
        table = QTableWidget()
        table.setColumnCount(8) 
        table.setHorizontalHeaderLabels(["순위", "종목명", "현재가", "어제 샀다면?", "추천강도", "매수가", "목표가", "손절가"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 테이블 속성 설정 (버그 수정 및 사용성 개선)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus) 
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows) # 줄 단위 선택
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # 수정 방지
        table.verticalHeader().setVisible(False)
        
        # cellClicked 시그널 연결 (더 확실한 동작)
        table.cellClicked.connect(self.show_details)
        
        return table

    def start_analysis(self):
        self.start_btn.setEnabled(False)
        self.start_btn.setText("분석 진행 중... ⏳") 
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
        self.start_btn.setText("오늘의 추천 종목 분석 시작") 
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"분석 완료: 국내 {len(kr_results)}개, 미국 {len(us_results)}개 종목")
        
        self.kr_results = kr_results
        self.us_results = us_results
        
        self.populate_table(self.kr_table, kr_results, is_kr=True)
        self.populate_table(self.us_table, us_results, is_kr=False)

        # 1등 종목 자동 강조
        if self.kr_results:
             self.kr_table.selectRow(0)
             self.show_details(0, 0) # 인자 맞춰줌

    def populate_table(self, table, results, is_kr):
        table.setRowCount(len(results))
        for i, result in enumerate(results):
            recommendation = "관망"
            rec_color = QColor("#868e96") 
            
            if result['score'] >= 5:
                recommendation = "강력 추천"
                rec_color = QColor("#fa5252") 
            elif result['score'] >= 2:
                recommendation = "매수 추천"
                rec_color = QColor("#fab005") 
            elif result['score'] <= -2:
                recommendation = "매도 경고"
                rec_color = QColor("#4c6ef5") 
            
            if result['score'] >= 2 and result['score'] < 5:
                 rec_color = QColor("#fd7e14") 
            
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(f"{result['name']} ({result['code']})"))
            
            currency = "원" if is_kr else "$"
            price_fmt = f"{result['price']:,}{currency}" if is_kr else f"${result['price']:,.2f}"
            table.setItem(i, 2, QTableWidgetItem(price_fmt))
            
            # 어제 샀다면?
            change_rate = result.get('yesterday_profit', 0)
            profit_item = QTableWidgetItem(f"{change_rate:+.2f}%")
            if change_rate > 0:
                profit_item.setForeground(QColor("#fa5252")) 
            elif change_rate < 0:
                profit_item.setForeground(QColor("#4c6ef5")) 
            table.setItem(i, 3, profit_item)
            
            rec_item = QTableWidgetItem(recommendation)
            rec_item.setForeground(rec_color)
            rec_item.setFont(QFont("Malgun Gothic", 10, QFont.Weight.Bold))
            table.setItem(i, 4, rec_item)
            
            buy_fmt = f"{result['buy_price']:,}{currency}" if is_kr else f"${result['buy_price']:,.2f}"
            target_fmt = f"{result['target_price']:,}{currency}" if is_kr else f"${result['target_price']:,.2f}"
            stop_fmt = f"{result['stop_loss']:,}{currency}" if is_kr else f"${result['stop_loss']:,.2f}"
            
            table.setItem(i, 5, QTableWidgetItem(buy_fmt))
            table.setItem(i, 6, QTableWidgetItem(target_fmt))
            table.setItem(i, 7, QTableWidgetItem(stop_fmt))

    def show_details(self, row, col):
        # sender()를 통해 어떤 테이블에서 신호가 왔는지 확인
        sender = self.sender()
        if sender == self.us_table:
            result = self.us_results[row]
            table_name = "미국 주식"
        elif sender == self.kr_table:
            result = self.kr_results[row]
            table_name = "국내 주식"
        else:
            # 직접 호출된 경우 (자동 선택 등) - 현재 탭 기준
            if self.tabs.currentIndex() == 0:
                result = self.kr_results[row]
                table_name = "국내 주식"
            else:
                result = self.us_results[row]
                table_name = "미국 주식"
        
        # HTML 포맷팅으로 예쁘게 꾸미기
        score_color = "#fa5252" if result['score'] >= 0 else "#4c6ef5"
        diff = result.get('diff', 0)
        diff_str = f"{diff:+,}" if isinstance(diff, int) else f"{diff:+.2f}"
        diff_color = "red" if diff > 0 else "blue" if diff < 0 else "black"
        
        html = f"""
        <h2 style='color: #343a40; margin-bottom: 5px;'>{result['name']} <span style='font-size: 14px; color: #868e96;'>({table_name})</span></h2>
        <div style='font-size: 16px; margin-bottom: 10px;'>
            <b>종합 점수:</b> <span style='color: {score_color}; font-size: 18px;'>{result['score']}점</span>
        </div>
        
        <div style='background-color: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 10px;'>
            <p style='margin: 5px 0;'><b>💰 현재가:</b> {result['price']:,} <span style='color: {diff_color};'>({diff_str} / {result['change_rate']}%)</span></p>
            <p style='margin: 5px 0;'><b>🔥 목표가:</b> <span style='color: #e03131;'>{result['target_price']:,}</span></p>
            <p style='margin: 5px 0;'><b>🛡️ 손절가:</b> <span style='color: #1971c2;'>{result['stop_loss']:,}</span> (칼손절 권장)</p>
            <p style='margin: 5px 0;'><b>📉 트레일링 스탑:</b> {int(result['price'] * 0.98):,} (수익 보전)</p>
        </div>

        <h3 style='color: #495057;'>📋 분석 상세 사유</h3>
        <ul style='line-height: 1.6;'>
        """
        
        for reason in result['reasons']:
            html += f"<li>{reason}</li>"
            
        html += "</ul>"
            
        self.detail_text.setHtml(html)

    def show_error(self, message):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("종목 분석 재시도")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "오류 발생", message)

    def closeEvent(self, event):
        # 종료 시 스레드 정리
        if self.thread.isRunning():
            self.thread.terminate()
            self.thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # qdarktheme 제거 (커스텀 스타일 사용)
    # app.setStyleSheet(qdarktheme.load_stylesheet())
    
    # 전역 폰트 설정
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
