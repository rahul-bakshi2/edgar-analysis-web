import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import json

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

def sec_request(url):
    """Make request to SEC with proper rate limiting"""
    time.sleep(0.1)  # SEC rate limit
    return requests.get(url, headers=HEADERS)

# Get company info
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
        # First get company info
        company = get_company_info(ticker)
        if not company:
            return []

        cik = company['cik']
        
        # Use company filings feed
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        response = sec_request(url)
        
        if response.status_code != 200:
            st.error(f"Error fetching filings: {response.status_code}")
            return []

        data = response.json()
        if 'filings' not in data:
            st.error("Invalid response format from SEC")
            return []

        # Filter filings
        filings = []
        recent = data['filings']['recent']
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        for i in range(len(recent['form'])):
            if recent['form'][i] == filing_type:
                filing_date = datetime.strptime(recent['filingDate'][i], '%Y-%m-%d')
                if start_date <= filing_date <= end_date:
                    # Create filing URL
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

    # Display filings
    st.subheader(f"Recent {filing_type} Filings")
    for filing in filings:
        with st.expander(f"{filing_type} - Filed on {filing['date']}", expanded=False):
            st.write(f"**Filing Date:** {filing['date']}")
            if filing.get('description'):
                st.write(f"**Report Date:** {filing['description']}")
            st.markdown(f"[View Filing on SEC.gov]({filing['url']})")

    # Export option
    if filings:
        df = pd.DataFrame(filings)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Filings Data",
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
