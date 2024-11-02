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

# Properly formatted SEC headers
HEADERS = {
    'User-Agent': 'Rahul Bakshi (rahul.bakshi@tradesforce.ai)',
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

# Add rate limiting
def sec_request(url):
    """Make request to SEC with proper rate limiting"""
    time.sleep(0.1)  # SEC rate limit
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 429:  # Rate limit exceeded
            time.sleep(10)  # Wait longer if rate limited
            response = requests.get(url, headers=HEADERS)
        return response
    except Exception as e:
        st.error(f"Request error: {str(e)}")
        return None

# Test SEC connection
def test_sec_connection():
    try:
        response = sec_request('https://www.sec.gov/files/company_tickers.json')
        if response and response.status_code == 200:
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
                # Format CIK to 10 digits with leading zeros
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
        # Ensure CIK is properly formatted
        cik = str(cik).zfill(10)
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        
        # Debug URL
        st.write(f"Fetching data from: {url}")
        
        response = sec_request(url)
        if not response or response.status_code != 200:
            st.error(f"Error fetching filings: Status code {response.status_code if response else 'No response'}")
            # Debug response
            if response:
                st.write("Response headers:", dict(response.headers))
            return None
            
        return response.json()
    except Exception as e:
        st.error(f"Error processing filings: {str(e)}")
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
            st.error("Could not fetch filings data")
            return
            
        # Filter filings
        filings = filter_filings(filings_data, filing_type, days_back)
    
    if not filings:
        st.info(f"No {filing_type} filings found for {ticker} in the past {days_back} days.")
        return

    # Display filings
    st.subheader(f"Recent {filing_type} Filings")
    
    # Get stock data
    with st.spinner("Fetching stock data..."):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        stock = yf.Ticker(ticker)
        stock_data = stock.history(start=start_date)
        
        if not stock_data.empty:
            fig = px.line(stock_data, y='Close',
                         title=f'{ticker} Stock Price',
                         template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)
    
    # Display filings
    for filing in filings:
        with st.expander(f"{filing['form']} - Filed on {filing['date']}", expanded=False):
            st.write(f"**Filing Date:** {filing['date']}")
            st.write(f"**Document:** {filing['primaryDocument']}")
            st.markdown(f"[View Filing on SEC.gov]({filing['reportUrl']})")

    # Add export option
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
    if test_sec_connection():
        main()
    else:
        st.error("Unable to connect to SEC EDGAR. Please try again later.")
