import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import json
# Add these new imports
from bs4 import BeautifulSoup
import re
from collections import defaultdict
import numpy as np
from textblob import TextBlob

# Configure page
st.set_page_config(
    page_title="EDGAR Filing Analyzer",
    page_icon="📊",
    layout="wide"
)

# Headers for SEC requests
HEADERS = {
    'User-Agent': 'Rahul Bakshi (rahul.bakshi@tradesforce.ai)',
    'Accept-Encoding': 'gzip, deflate'
}

# Add the new FinancialMetricsExtractor class here
class FinancialMetricsExtractor:
    def __init__(self):
        # Common financial metrics patterns
        self.metrics_patterns = {
            'revenue': r'(?i)(total revenue|net revenue|revenue)[:\s]*[$]?[\d,]+\.?\d*\s*(?:million|billion|thousand|m|b|k)?',
            'net_income': r'(?i)(net income|net earnings)[:\s]*[$]?[\d,]+\.?\d*\s*(?:million|billion|thousand|m|b|k)?',
            'eps': r'(?i)(earnings per share|eps)[:\s]*[$]?[\d,]+\.?\d*',
            'operating_income': r'(?i)(operating income)[:\s]*[$]?[\d,]+\.?\d*\s*(?:million|billion|thousand|m|b|k)?',
            'cash_flow': r'(?i)(operating cash flow)[:\s]*[$]?[\d,]+\.?\d*\s*(?:million|billion|thousand|m|b|k)?'
        }

    def extract_metrics(self, text):
        metrics = defaultdict(list)
        for metric_name, pattern in self.metrics_patterns.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                number_str = re.search(r'[$]?[\d,]+\.?\d*', match.group(0))
                if number_str:
                    value = self._parse_number(number_str.group(0))
                    metrics[metric_name].append(value)
        return metrics

    def _parse_number(self, number_str):
        try:
            cleaned = number_str.replace('$', '').replace(',', '')
            return float(cleaned)
        except ValueError:
            return None

    def analyze_sentiment(self, text):
        blob = TextBlob(text)
        return {
            'polarity': blob.sentiment.polarity,
            'subjectivity': blob.sentiment.subjectivity
        }

# Add the metrics analysis functions
@st.cache_data(ttl=3600)
def analyze_filing_content(url):
    """Analyze the content of a filing"""
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        
        metrics_extractor = FinancialMetricsExtractor()
        metrics = metrics_extractor.extract_metrics(text)
        sentiment = metrics_extractor.analyze_sentiment(text)
        
        return {
            'metrics': metrics,
            'sentiment': sentiment,
            'text_length': len(text)
        }
    except Exception as e:
        st.error(f"Error analyzing filing: {str(e)}")
        return None

def display_metrics(metrics, sentiment):
    """Display extracted metrics in Streamlit with proper error handling"""
    if metrics:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Key Financial Metrics")
            for metric_name, values in metrics.items():
                if values and len(values) > 0 and any(v is not None for v in values):
                    # Filter out None values and calculate mean
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        avg_value = np.mean(valid_values)
                        st.metric(
                            label=metric_name.replace('_', ' ').title(),
                            value=f"${avg_value:,.2f}"
                        )
                    else:
                        st.metric(
                            label=metric_name.replace('_', ' ').title(),
                            value="Not found"
                        )
        
        with col2:
            st.subheader("📈 Sentiment Analysis")
            if isinstance(sentiment, dict) and 'polarity' in sentiment:
                sentiment_color = 'green' if sentiment['polarity'] > 0 else 'red'
                st.markdown(f"""
                    Sentiment Polarity: <span style='color:{sentiment_color}'>{sentiment['polarity']:.2f}</span>
                    \nSubjectivity: {sentiment['subjectivity']:.2f}
                """, unsafe_allow_html=True)
            else:
                st.write("Sentiment analysis not available")

# Keep your existing helper functions (sec_request, get_company_info, get_filings)
def sec_request(url):
    """Make request to SEC with proper rate limiting"""
    time.sleep(0.1)  # SEC rate limit
    return requests.get(url, headers=HEADERS)

@st.cache_data(ttl=3600)
def get_company_info(ticker):
    try:
        response = sec_request('https://www.sec.gov/files/company_tickers.json')
        if response.status_code != 200:
            st.error(f"Error accessing SEC API: {response.status_code}")
            return None
            
        data = response.json()
        for entry in data.values():
            if entry['ticker'] == ticker.upper():
                return {
                    'cik': str(entry['cik_str']).zfill(10),
                    'name': entry['title'],
                    'ticker': entry['ticker']
                }
        return None
    except Exception as e:
        st.error(f"Error looking up company: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def get_filings(ticker, filing_type, days_back):
    """Get filings using company API"""
    try:
        company = get_company_info(ticker)
        if not company:
            return []

        cik = company['cik']
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        response = sec_request(url)
        
        if response.status_code != 200:
            st.error(f"Error fetching filings: {response.status_code}")
            return []

        data = response.json()
        if 'filings' not in data:
            st.error("Invalid response format from SEC")
            return []

        filings = []
        recent = data['filings']['recent']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        for i in range(len(recent['form'])):
            if recent['form'][i] == filing_type:
                filing_date = datetime.strptime(recent['filingDate'][i], '%Y-%m-%d')
                if start_date <= filing_date <= end_date:
                    acc_no = recent['accessionNumber'][i].replace('-', '')
                    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}/{recent['primaryDocument'][i]}"
                    
                    filings.append({
                        'date': recent['filingDate'][i],
                        'form': recent['form'][i],
                        'url': url,
                        'description': recent.get('reportDate', [''])[i]
                    })

        return filings

    except Exception as e:
        st.error(f"Error processing filings: {str(e)}")
        return []

def main():
    st.title("📊 SEC EDGAR Filing Analyzer")

    # Sidebar controls
    st.sidebar.header("Analysis Controls")
    ticker = st.sidebar.text_input("Enter Stock Ticker:", "AAPL").upper()
    filing_type = st.sidebar.selectbox(
        "Filing Type:",
        ["10-K", "10-Q", "8-K"],
        help="10-K: Annual report\n10-Q: Quarterly report\n8-K: Current report"
    )
    days_back = st.sidebar.slider("Days to Look Back:", 30, 365, 90)

    if not ticker:
        st.info("Please enter a stock ticker to begin analysis.")
        return

    # Get company info
    company = get_company_info(ticker)
    if not company:
        st.error(f"Could not find company information for {ticker}")
        return

    # Display company info
    st.header(f"{ticker} - {company['name']}")
    st.write(f"CIK: {company['cik']}")

    # Get filings
    with st.spinner("Fetching SEC filings..."):
        filings = get_filings(ticker, filing_type, days_back)

    if not filings:
        st.info(f"No {filing_type} filings found for {ticker} in the past {days_back} days.")
        return

    # Display stock chart
    with st.spinner("Loading stock data..."):
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days_back}d")
        if not hist.empty:
            fig = px.line(hist, y='Close', title=f'{ticker} Stock Price')
            st.plotly_chart(fig, use_container_width=True)

    # Define the analysis DataFrame creation function
    def create_analysis_dataframe(metrics):
        """Create analysis DataFrame with proper error handling"""
        try:
            metric_values = []
            for metric in ['revenue', 'net_income', 'eps', 'operating_income', 'cash_flow']:
                values = metrics.get(metric, [])
                valid_values = [v for v in values if v is not None]
                avg_value = np.mean(valid_values) if valid_values else 0
                metric_values.append(avg_value)
            
            return pd.DataFrame({
                'Metric': ['Revenue', 'Net Income', 'EPS', 'Operating Income', 'Cash Flow'],
                'Value': metric_values
            })
        except Exception as e:
            st.error(f"Error creating analysis summary: {str(e)}")
            return pd.DataFrame()

    # Display filings with enhanced analysis
    st.subheader(f"Recent {filing_type} Filings")
    for filing in filings:
        with st.expander(f"{filing_type} - Filed on {filing['date']}", expanded=False):
            st.write(f"**Filing Date:** {filing['date']}")
            if filing.get('description'):
                st.write(f"**Report Date:** {filing['description']}")
            st.markdown(f"[View Filing on SEC.gov]({filing['url']})")
            
            # Add the new metrics analysis here
            with st.spinner("Analyzing filing content..."):
                analysis = analyze_filing_content(filing['url'])
                if analysis:
                    display_metrics(analysis['metrics'], analysis['sentiment'])
                    
                    # Add download option for analysis
                    analysis_df = create_analysis_dataframe(analysis['metrics'])
                    if not analysis_df.empty:
                        csv = analysis_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "📥 Download Analysis",
                            csv,
                            f"{filing['form']}_{filing['date']}_analysis.csv",
                            "text/csv"
                        )
                    

    # Export option for all filings
    if filings:
        df = pd.DataFrame(filings)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download All Filings Data",
            csv,
            f"{ticker}_filings.csv",
            "text/csv"
        )

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>Data sourced directly from SEC EDGAR database</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
