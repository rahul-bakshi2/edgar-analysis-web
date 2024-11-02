# At the top of your streamlit_app.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
from bs4 import BeautifulSoup
import json

# Configure page
st.set_page_config(
    page_title="EDGAR Filing Analyzer",
    page_icon="📊",
    layout="wide"
)

# Define headers for SEC EDGAR
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Test connection to SEC
def test_sec_connection():
    try:
        response = requests.get(
            'https://www.sec.gov/files/company_tickers.json',
            headers=headers
        )
        if response.status_code == 200:
            return True
        else:
            st.error(f"SEC connection error: Status code {response.status_code}")
            return False
    except Exception as e:
        st.error(f"SEC connection error: {str(e)}")
        return False

# Function to get company info
@st.cache_data(ttl=3600)
def get_company_info(ticker):
    try:
        # Get CIK from ticker lookup
        response = requests.get(
            'https://www.sec.gov/files/company_tickers.json',
            headers=headers
        )
        data = response.json()
        
        # Find the matching ticker
        for entry in data.values():
            if entry['ticker'] == ticker.upper():
                cik = str(entry['cik_str']).zfill(10)
                name = entry['title']
                return {'cik': cik, 'name': name}
        
        return None
    except Exception as e:
        st.error(f"Error looking up company: {str(e)}")
        return None

# Function to get filings
@st.cache_data(ttl=3600)
def get_company_filings(cik, filing_type, days_back):
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Get company filings
        url = f'https://data.sec.gov/submissions/CIK{cik}.json'
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            st.error(f"Error fetching filings: Status code {response.status_code}")
            return []
            
        data = response.json()
        filings = []
        
        # Process recent filings
        recent_filings = data['filings']['recent']
        for i, form in enumerate(recent_filings['form']):
            if form == filing_type:
                filing_date = datetime.strptime(recent_filings['filingDate'][i], '%Y-%m-%d')
                if start_date <= filing_date <= end_date:
                    filings.append({
                        'date': recent_filings['filingDate'][i],
                        'accessionNumber': recent_filings['accessionNumber'][i],
                        'form': form,
                        'primaryDocument': recent_filings['primaryDocument'][i],
                        'reportUrl': f"https://www.sec.gov/Archives/edgar/data/{cik}/{recent_filings['accessionNumber'][i].replace('-', '')}/{recent_filings['primaryDocument'][i]}"
                    })
        
        return filings
    except Exception as e:
        st.error(f"Error processing filings: {str(e)}")
        return []

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
    company = get_company_info(ticker)
    
    if not company:
        st.error(f"Could not find company information for ticker {ticker}")
        return

    # Display company info
    st.header(f"{ticker} - {company['name']}")
    
    # Get filings
    filings = get_company_filings(company['cik'], filing_type, days_back)
    
    if not filings:
        st.info(f"No {filing_type} filings found for {ticker} in the past {days_back} days.")
        return

    # Display filings
    st.subheader(f"Recent {filing_type} Filings")
    
    for filing in filings:
        with st.expander(f"{filing['form']} - Filed on {filing['date']}", expanded=False):
            st.write(f"**Filing Date:** {filing['date']}")
            st.write(f"**Document:** {filing['primaryDocument']}")
            st.markdown(f"[View Filing on SEC.gov]({filing['reportUrl']})")
            
            # Add a download button for the filing URL
            st.markdown(f"[Download Filing]({filing['reportUrl']})")

    # Add export option for all filings
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
    if test_sec_connection():
        main()
    else:
        st.error("Unable to connect to SEC EDGAR. Please try again later.")
