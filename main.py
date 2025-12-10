import data_collector
import analyzer
import config
import FinanceDataReader as fdr
import pandas as pd

def main():
    print("=== AI 주식 투자 비서 시작 ===")
    
    # 1. 모듈 초기화
    collector = data_collector.DataCollector()
    stock_analyzer = analyzer.Analyzer()
    
    # 2. 미국 증시 데이터 수집 및 연동 분석
    print("\n[1단계] 미국 증시 분석 및 후보군 선정")
    us_data = collector.get_us_market_data(config.US_TICKERS.keys())
    coupling_scores = stock_analyzer.analyze_coupling(us_data, config.KOREA_MAPPING)
    
    # 후보군 리스트업 (미국장 영향이 있는 종목 + 시총 상위 일부)
    candidate_codes = set(coupling_scores.keys())
    
    # 국내 시총 상위 10개 추가 (미국장 영향 없어도 기본 분석 대상)
    # KRX 전체 상장 종목 중 시가총액 순으로 정렬하여 상위 10개 추출
    df_krx = fdr.StockListing('KRX')
    top_10 = df_krx.sort_values('Marcap', ascending=False).head(10)['Code'].tolist()
    candidate_codes.update(top_10)
    
    print(f"분석 대상 종목 수: {len(candidate_codes)}개")
    
    # 3. 국내 주식 데이터 수집 및 상세 분석
    print("\n[2단계] 국내 주식 상세 분석 (뉴스/차트)")
    kr_data = collector.get_korea_market_data(list(candidate_codes))
    
    final_results = []
    
    for code, data in kr_data.items():
        # 종목명 찾기
        name = df_krx[df_krx['Code'] == code]['Name'].values[0] if code in df_krx['Code'].values else code
        
        total_score = 0
        reasons = []
        
        # 3-1. 미국장 연동 점수 반영
        if code in coupling_scores:
            total_score += coupling_scores[code]['score']
            reasons.extend(coupling_scores[code]['reason'])
            
        # 3-2. 차트 분석
        chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
        total_score += chart_score
        reasons.extend(chart_reasons)
        
        # 3-3. 뉴스 분석
        news_titles = collector.get_news_sentiment(name)
        news_score, news_reasons = stock_analyzer.analyze_news(news_titles)
        total_score += news_score
        reasons.extend(news_reasons)
        
        # 3-4. 거래량 분석 (평소 대비 200% 폭발 시 가점)
        # 간단히 최근 5일 평균 거래량 대비 전일 거래량 비교
        if len(data['df']) >= 5:
            avg_vol = data['df']['Volume'].rolling(window=5).mean().iloc[-2]
            if avg_vol > 0 and data['volume'] > avg_vol * 2:
                total_score += 1
                reasons.append("거래량 폭발 (5일 평균 대비 2배 이상)")

        final_results.append({
            'code': code,
            'name': name,
            'price': data['price'],
            'change_rate': data['change_rate'],
            'score': total_score,
            'reasons': reasons
        })
        
    # 4. 결과 출력 (점수순 정렬)
    final_results.sort(key=lambda x: x['score'], reverse=True)
    
    print("\n" + "="*50)
    print("📢 오늘의 AI 주식 추천 리포트")
    print("="*50)
    
    for rank, result in enumerate(final_results[:5], 1): # 상위 5개만 출력
        recommendation = "관망"
        if result['score'] >= 3:
            recommendation = "강력 추천 (Strong Buy)"
        elif result['score'] >= 1:
            recommendation = "매수 추천 (Buy)"
        elif result['score'] <= -2:
            recommendation = "매도 경고 (Sell)"
            
        print(f"\n[{rank}위] {result['name']} ({result['code']})")
        print(f"현재가: {result['price']:,}원 ({result['change_rate']}%)")
        print(f"추천 강도: {recommendation} (점수: {result['score']}점)")
        print("추천 이유:")
        for reason in result['reasons']:
            print(f" - {reason}")
            
    print("\n" + "="*50)
    print("※ 본 리포트는 참고용이며, 투자의 책임은 본인에게 있습니다.")

if __name__ == "__main__":
    main()
