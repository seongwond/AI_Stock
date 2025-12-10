import data_collector
import analyzer
import config

def test_us_analysis():
    print("Testing US Stock Analysis...")
    collector = data_collector.DataCollector()
    stock_analyzer = analyzer.Analyzer()

    print("Fetching US Data...")
    us_data = collector.get_us_market_data(config.US_TICKERS.keys())
    print(f"Fetched {len(us_data)} US stocks.")
    print(f"Keys: {list(us_data.keys())}")

    for ticker, data in us_data.items():
        print(f"\nAnalyzing {ticker}...")
        print(f"Price: {data.get('price')}")
        print(f"Change Rate: {data.get('change_rate')}")
        
        if 'df' in data:
            print(f"Data Length: {len(data['df'])}")
            chart_score, chart_reasons = stock_analyzer.analyze_chart(data['df'])
            print(f"Chart Score: {chart_score}")
            print(f"Reasons: {chart_reasons}")
        else:
            print("No DataFrame found!")

if __name__ == "__main__":
    test_us_analysis()
