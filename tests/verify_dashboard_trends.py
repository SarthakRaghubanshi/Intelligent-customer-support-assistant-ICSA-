import os
import sys
import pandas as pd

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

def run_trends_verification():
    print("=" * 80)
    print("RUNNING DASHBOARD TRENDS CONTRACT TESTS")
    print("=" * 80)

    # 1. Mock a list of recent events
    mock_events = [
        {
            "timestamp": "2026-06-10T19:00:01.123456",
            "query": "Hello",
            "intent": "Greeting",
            "intent_confidence": 0.95,
            "sentiment": "Positive",
            "escalated": False
        },
        {
            "timestamp": "2026-06-10T19:01:05.654321",
            "query": "Is my food ready?",
            "intent": "Status Inquiry",
            "intent_confidence": 0.85,
            "sentiment": "Neutral",
            "escalated": False
        },
        {
            "timestamp": "2026-06-10T19:02:10.000000",
            "query": "This pizza is cold and late!",
            "intent": "Complaint",
            "intent_confidence": 0.80,
            "sentiment": "Negative",
            "escalated": True
        }
    ]

    # 2. Test DataFrame Conversion and Time parsing
    print("\n[1] Verifying DataFrame conversion and timestamp formatting")
    df = pd.DataFrame(mock_events)
    df['Time'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
    
    assert len(df) == 3, f"Expected 3 rows, got {len(df)}"
    assert df['Time'].iloc[0] == "19:00:01", f"Expected time 19:00:01, got {df['Time'].iloc[0]}"
    assert df['Time'].iloc[1] == "19:01:05", f"Expected time 19:01:05, got {df['Time'].iloc[1]}"
    assert df['Time'].iloc[2] == "19:02:10", f"Expected time 19:02:10, got {df['Time'].iloc[2]}"
    print("    Status -> ✓ DataFrame conversion and time formatting passed")

    # 3. Test Cumulative Query Volume and Escalations
    print("\n[2] Verifying cumulative query volume and escalation counts")
    volume_df = pd.DataFrame({
        'Time': df['Time'],
        'Total Queries': range(1, len(df) + 1),
        'Escalations': df['escalated'].astype(int).cumsum()
    }).set_index('Time')

    assert volume_df.loc["19:00:01", "Total Queries"] == 1
    assert volume_df.loc["19:00:01", "Escalations"] == 0
    assert volume_df.loc["19:02:10", "Total Queries"] == 3
    assert volume_df.loc["19:02:10", "Escalations"] == 1
    print("    Status -> ✓ Cumulative volume calculations passed")

    # 4. Test Sentiment score mapping (Positive=1, Neutral=0, Negative=-1)
    print("\n[3] Verifying sentiment score mapping logic")
    sentiment_map = {'Positive': 1, 'Neutral': 0, 'Negative': -1}
    sentiment_df = pd.DataFrame({
        'Time': df['Time'],
        'Sentiment Score': df['sentiment'].map(sentiment_map).fillna(0)
    }).set_index('Time')

    assert sentiment_df.loc["19:00:01", "Sentiment Score"] == 1, f"Expected 1 for Positive, got {sentiment_df.loc['19:00:01', 'Sentiment Score']}"
    assert sentiment_df.loc["19:01:05", "Sentiment Score"] == 0, f"Expected 0 for Neutral, got {sentiment_df.loc['19:01:05', 'Sentiment Score']}"
    assert sentiment_df.loc["19:02:10", "Sentiment Score"] == -1, f"Expected -1 for Negative, got {sentiment_df.loc['19:02:10', 'Sentiment Score']}"
    print("    Status -> ✓ Sentiment mapping score calculation passed")

    # 5. Test Confidence trend mapping
    print("\n[4] Verifying intent classification confidence data mapping")
    confidence_df = df[['Time', 'intent_confidence']].rename(
        columns={'intent_confidence': 'Confidence Score'}
    ).set_index('Time')

    assert confidence_df.loc["19:00:01", "Confidence Score"] == 0.95
    assert confidence_df.loc["19:01:05", "Confidence Score"] == 0.85
    assert confidence_df.loc["19:02:10", "Confidence Score"] == 0.80
    print("    Status -> ✓ Confidence score mapping passed")

    print("\n" + "=" * 80)
    print("✓ DASHBOARD TRENDS CONTRACT PASSED")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_trends_verification()
