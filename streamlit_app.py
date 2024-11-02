import streamlit as st
import pandas as pd
import yfinance as yf
from sec_api import QueryApi
import plotly.express as px
from datetime import datetime, timedelta
import os
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
import time

# Page configuration
st.set_page_config(
    page_title="EDGAR Filing Analyzer",
    page_icon="📊",
    layout="wide",
    menu_items={
        'Get Help': 'https://github.com/yourusername/edgar-analysis-web/issues',
        'Report a bug': 'https://github.com/yourusername/edgar-analysis-web/issues',
        'About': 'EDGAR Filing Analysis Tool - Created by Your Name'
    }
)

# Display "How to Use" guide in the sidebar
with st.sidebar:
    with st.expander("ℹ️ How to Use"):
        st.markdown("""
        1. Enter a stock ticker (e.g., AAPL, MSFT)
        2. Select the type of filing you want to analyze
        3. Adjust the time range using the slider
        4. View the analysis and charts
        5. Download reports using the export button
        
        **Note:** If you encounter any issues, please report them using the ⋮ menu in the top right.
        """)

# Initialize NLTK and API
@st.cache_resource
def initialize_nltk():
    try:
        nltk.download('vader_lexicon', quiet=True)
        return SentimentIntensityAnalyzer()
    except Exception as e:
        st.error("Error initializing sentiment analyzer. Please try again later.")
        return None

# Get API key from Streamlit secrets
def get_api_key():
    try:
        return st.secrets["SEC_API_KEY"]
    except Exception as e:
        st.error("SEC API key not found. Please contact the administrator.")
        return None

# Initialize components
sia = initialize_nltk()
api_key = get_api_key()

if api_key:
    queryApi = QueryApi(api_key=api_key)
else:
    st.stop()

class EDGARAnalyzer:
    @staticmethod
    @st.cache_data(ttl=3600)
    def fetch_filings(ticker, filing_type, start_date):
        """Fetch SEC filings with error handling"""
        with st.spinner("Fetching SEC filings..."):
            try:
                query = {
                    "query": {
                        "query_string": {
                            "query": f"ticker:{ticker} AND formType:\"{filing_type}\""
                        }
                    },
                    "from": "0",
                    "size": "10",
                    "sort": [{"filedAt": {"order": "desc"}}]
                }
                response = queryApi.get_filings(query)
                return response.get('filings', [])
            except Exception as e:
                st.error(f"Error fetching filings: Please check your ticker symbol and try again.")
                return []

    @staticmethod
    @st.cache_data
    def analyze_sentiment(text):
        """Analyze sentiment of text"""
        if not text or not sia:
            return {'pos': 0, 'neg': 0, 'neu': 0, 'compound': 0}
        return sia.polarity_scores(text)

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_stock_data(ticker, start_date):
        """Fetch stock data with error handling"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date)
            if hist.empty:
                st.warning(f"No stock data found for {ticker}. Please verify the ticker symbol.")
                return pd.DataFrame()
            return hist
        except Exception as e:
            st.error(f"Error fetching stock data: Please check your ticker symbol.")
            return pd.DataFrame()

def main():
    st.title("📊 EDGAR Filings Analysis Dashboard")
    
    # Main interface
    col1, col2 = st.columns([3, 1])
    
    with col2:
        ticker = st.text_input("Enter Stock Ticker:", placeholder="e.g., AAPL, MSFT").upper()
        filing_type = st.selectbox(
            "Select Filing Type:",
            ["10-K", "10-Q", "8-K"],
            help="10-K: Annual report\n10-Q: Quarterly report\n8-K: Material events"
        )
        days_back = st.slider(
            "Days to Look Back:",
            30, 365, 90,
            help="Adjust the time range for analysis"
        )

    if not ticker:
        st.info("👆 Enter a stock ticker to begin analysis")
        return

    # Initialize analyzer
    analyzer = EDGARAnalyzer()
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

    # Stock Price Analysis
    with st.expander("📈 Stock Price Analysis", expanded=True):
        stock_data = analyzer.get_stock_data(ticker, start_date)
        if not stock_data.empty:
            fig = px.line(stock_data, y='Close',
                         title=f'{ticker} Stock Price',
                         template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)

    # Filings Analysis
    st.header("📑 SEC Filings Analysis")
    filings = analyzer.fetch_filings(ticker, filing_type, start_date)
    
    if filings:
        # Create a list to store processed data for export
        processed_data = []
        
        for filing in filings:
            with st.expander(f"{filing['formType']} - {filing['filedAt'][:10]}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    description = filing.get('description', 'No description available')
                    st.markdown("### Filing Details")
                    st.write("**Description:**", description)
                    
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/{filing.get('cik', '')}/{filing.get('accessionNo', '').replace('-', '')}/{filing.get('primaryDocument', '')}"
                    st.markdown(f"[View Full Filing]({filing_url})")
                
                with col2:
                    if description != 'No description available':
                        sentiment = analyzer.analyze_sentiment(description)
                        
                        # Create sentiment visualization
                        fig = px.pie(
                            values=[sentiment['pos'], sentiment['neu'], sentiment['neg']],
                            names=['Positive', 'Neutral', 'Negative'],
                            title='Sentiment Analysis',
                            hole=0.4,
                            color_discrete_map={
                                'Positive': 'green',
                                'Neutral': 'gray',
                                'Negative': 'red'
                            }
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Add to processed data
                processed_data.append({
                    'Date': filing['filedAt'][:10],
                    'Type': filing['formType'],
                    'Description': description,
                    'Sentiment Score': sentiment['compound']
                })
        
        # Export option
        if processed_data:
            df = pd.DataFrame(processed_data)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download Analysis",
                csv,
                f"{ticker}_filing_analysis.csv",
                "text/csv",
                key='download-csv'
            )
    else:
        st.info(f"No {filing_type} filings found for {ticker} in the selected time range.")

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>Built with Streamlit • Data from SEC EDGAR</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
