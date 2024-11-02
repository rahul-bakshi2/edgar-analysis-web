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

# Different headers for different SEC endpoints
EDGAR_HEADERS = {
    'User-Agent': 'Rahul Bakshi (rahul.bakshi@tradesforce.ai)',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

DATA_SEC_HEADERS = {
    'User-Agent': 'Rahul Bakshi (rahul.bakshi@tradesforce.ai)',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'data.sec.gov'
}

# Add rate limiting
def sec_request(url):
    """Make request to SEC with proper rate limiting and headers"""
    time.sleep(0.1)  # SEC rate limit
    try:
        # Choose headers based on the URL
        headers = DATA_SEC_HEADERS if 'data.sec.gov' in url else EDGAR_HEADERS
        response = requests.get(url, headers=headers)
        
        # Debug information
        st.write(f"Request URL: {url}")
        st.write(f"Response Status: {response.status_code}")
        
        if response.status_code == 429:  # Rate limit exceeded
            time.sleep(10)  # Wait longer if rate limited
            response = requests.get(url, headers=headers)
        return response
    except Exception as e:
        st.error(f"Request error: {str(e)}")
        return None

# Test SEC connection
def test_sec_connection():
    try:
        response = sec_request('https://www.sec.gov/files/company_tickers.json')
        if response and response.status_code == 200:
            st.success("Successfully connected to SEC EDGAR")
            return True
        else:
            st.error(f"SEC connection error: Status code {response.status_code if response else 'No response'}")
            return False
    except Exception as e:
        st.error(f"SEC connection error: {str(e)}")
        return False

# Get company info
@st.cache_data(ttl=3600)
def get_company_info(ticker):
    try:
        response = sec_request('https://www.sec.gov/files/company_tickers.json')
        if not response or response.status_code != 200:
            return None
            
        data = response.json()
        
        for entry in data.values():
            if entry['ticker'] == ticker.upper():
                cik = str(entry['cik_str']).zfill(10)
                return {
                    'cik': cik,
                    'name': entry['title']
                }
        return None
    except Exception as e:
        st.error(f"Error looking up company: {str(e)}")
        return None

# Get company filings
@st.cache_data(ttl=3600)
def get_company_filings(cik):
    """Get all company filings from SEC API"""
    try:
        cik = str(cik).zfill(10)
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        
        # Debug information
        st.write("Attempting to fetch filings...")
        st.write(f"URL: {url}")
        st.write(f"Headers being used: {DATA_SEC_HEADERS}")
        
        response = sec_request(url)
        
        if not response:
            st.error("No response received from SEC")
            return None
            
        if response.status_code != 200:
            st.error(f"Error fetching filings: Status code {response.status_code}")
            st.write("Response headers:", dict(response.headers))
            return None
            
        return response.json()
    except Exception as e:
        st.error(f"Error processing filings: {str(e)}")
        st.write("Full error details:", str(e))
        return None

def filter_filings(filings_data, filing_type, days_back):
    """Filter filings by type and date"""
    if not filings_data or 'filings' not in filings_data:
        return []
        
    filtered_filings = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    recent = filings_data['filings']['recent']
    
    for i, form in enumerate(recent['form']):
        if form == filing_type:
            filing_date = datetime.strptime(recent['filingDate'][i], '%Y-%m-%d')
            if start_date <= filing_date <= end_date:
                filtered_filings.append({
                    'date': recent['filingDate'][i],
                    'accessionNumber': recent['accessionNumber'][i],
                    'form': form,
                    'primaryDocument': recent['primaryDocument'][i],
                    'reportUrl': f"https://www.sec.gov/Archives/edgar/data/{recent['cik'][i]}/{recent['accessionNumber'][i].replace('-', '')}/{recent['primaryDocument'][i]}"
                })
    
    return filtered_filings

def main():
    st.title("📊 SEC EDGAR Filing Analyzer")
    
    # Debug mode toggle
    debug_mode = st.sidebar.checkbox("Debug Mode")
    
    # Sidebar
    with st.sidebar:
        st.header("Analysis Controls")
        ticker = st.text_input("Enter Stock Ticker:", "AAPL").upper()
        filing_type = st.selectbox(
            "Filing Type:",
            ["10-K", "10-Q", "8-K"],
            help="10-K: Annual report\n10-Q: Quarterly report\n8-K: Current report"
        )
        days_back = st.slider("Days to Look Back:", 30, 365, 90)

    if not ticker:
        st.info("Please enter a stock ticker to begin analysis.")
        return

    # Get company info
    with st.spinner("Looking up company information..."):
        company = get_company_info(ticker)
    
    if not company:
        st.error(f"Could not find company information for ticker {ticker}")
        return

    # Display company info
    st.header(f"{ticker} - {company['name']}")
    st.write(f"CIK: {company['cik']}")
    
    # Get all filings
    with st.spinner("Fetching SEC filings..."):
        filings_data = get_company_filings(company['cik'])
        if not filings_data:
            if debug_mode:
                st.write("Debug information will appear here")
            return
            
        # Filter filings
        filings = filter_filings(filings_data, filing_type, days_back)
    
    if not filings:
        st.info(f"No {filing_type} filings found for {ticker} in the past {days_back} days.")
        return

    # Rest of your code remains the same...

if __name__ == "__main__":
    st.write("Testing SEC connection...")
    if test_sec_connection():
        main()
    else:
        st.error("Unable to connect to SEC EDGAR. Please try again later.")
