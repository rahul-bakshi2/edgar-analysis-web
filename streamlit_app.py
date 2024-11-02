import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
from bs4 import BeautifulSoup
import json

# Page configuration
st.set_page_config(
    page_title="EDGAR Filing Analyzer",
    page_icon="📊",
    layout="wide",
    menu_items={
        'Get Help': 'https://github.com/yourusername/edgar-analysis-web/issues',
        'Report a bug': 'https://github.com/yourusername/edgar-analysis-web/issues',
        'About': 'EDGAR Filing Analysis Tool - Free and Open Source'
    }
)

# User agent header for SEC EDGAR
HEADERS = {
    'User-Agent': 'Your Name yourname@email.com',  # Replace with your information
    'Accept-Encoding': 'gzip, deflate',
    'Host': 'www.sec.gov'
}

class EDGARAnalyzer:
    @staticmethod
    @st.cache_data(ttl=3600)
    def get_cik_from_ticker(ticker):
        """Get CIK number from ticker symbol"""
        try:
            # Use SEC's ticker to CIK lookup
            response = requests.get(
                f'https://www.sec.gov/files/company_tickers.json',
                headers=HEADERS
            )
            time.sleep(0.1)  # SEC rate limit compliance
            
            if response.status_code == 200:
                data = response.json()
                for entry in data.values():
                    if entry['ticker'] == ticker.upper():
                        return str(entry['cik_str']).zfill(10)
            return None
        except Exception as e:
            st.error(f"Error looking up company: {str(e)}")
            return None

    @staticmethod
    @st.cache_data(ttl=3600)
    def fetch_company_submissions(cik):
        """Fetch company filings metadata"""
        try:
            url = f'https://data.sec.gov/submissions/CIK{cik}.json'
            response = requests.get(url, headers=HEADERS)
            time.sleep(0.1)  # SEC rate limit compliance
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Error fetching company data: {str(e)}")
            return None

    @staticmethod
    @st.cache_data(ttl=3600)
    def get_filing_details(accession_number, cik):
        """Fetch filing details from EDGAR"""
        try:
            # Format the accession number
            acc_no = accession_number.replace('-', '')
            url = f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}/filing-details.json'
            response = requests.get(url, headers=HEADERS)
            time.sleep(0.1)  # SEC rate limit compliance
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Error fetching filing details: {str(e)}")
            return None

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
    st.title("📊 SEC EDGAR Filing Analyzer")
    
    # Sidebar help
    with st.sidebar:
        with st.expander("ℹ️ How to Use"):
            st.markdown("""
            1. Enter a stock ticker (e.g., AAPL, MSFT)
            2. Select the type of filing you want to analyze
            3. Adjust the time range using the slider
            4. View the analysis and charts
            5. Download reports using the export button
            
            This tool uses direct SEC EDGAR data and is completely free.
            """)

    # Main interface
    col1, col2 = st.columns([3, 1])
    
    with col2:
        ticker = st.text_input("Enter Stock Ticker:", placeholder="e.g., AAPL, MSFT").upper()
        filing_types = ["10-K", "10-Q", "8-K"]
        filing_type = st.selectbox(
            "Select Filing Type:",
            filing_types,
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

    # Initialize analyzer and get company data
    analyzer = EDGARAnalyzer()
    cik = analyzer.get_cik_from_ticker(ticker)
    
    if not cik:
        st.error(f"Could not find CIK for ticker {ticker}. Please verify the ticker symbol.")
        return

    # Fetch company submissions
    submissions = analyzer.fetch_company_submissions(cik)
    
    if not submissions:
        st.error("Could not fetch company filings. Please try again later.")
        return

    # Stock Price Analysis
    with st.expander("📈 Stock Price Analysis", expanded=True):
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        stock_data = analyzer.get_stock_data(ticker, start_date)
        if not stock_data.empty:
            fig = px.line(stock_data, y='Close',
                         title=f'{ticker} Stock Price',
                         template='plotly_white')
            st.plotly_chart(fig, use_container_width=True)

    # Filings Analysis
    st.header("📑 SEC Filings Analysis")
    
    # Filter filings
    recent_filings = []
    start_date = datetime.now() - timedelta(days=days_back)
    
    for idx, form in enumerate(submissions['filings']['recent']['form']):
        if form == filing_type:
            filing_date = datetime.strptime(
                submissions['filings']['recent']['filingDate'][idx],
                '%Y-%m-%d'
            )
            if filing_date >= start_date:
                recent_filings.append({
                    'form': form,
                    'filingDate': submissions['filings']['recent']['filingDate'][idx],
                    'accessionNumber': submissions['filings']['recent']['accessionNumber'][idx],
                    'primaryDocument': submissions['filings']['recent']['primaryDocument'][idx],
                })

    if recent_filings:
        processed_data = []
        
        for filing in recent_filings:
            with st.expander(f"{filing['form']} - {filing['filingDate']}", expanded=False):
                # Get filing details
                details = analyzer.get_filing_details(filing['accessionNumber'], cik)
                
                if details:
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown("### Filing Details")
                        
                        # Display useful information from the filing
                        if 'documentFormatFiles' in details:
                            for doc in details['documentFormatFiles']:
                                if doc.get('type') == '10-K' or doc.get('type') == '10-Q':
                                    st.write("**Document Type:**", doc.get('type'))
                                    st.write("**Description:**", doc.get('description', 'No description available'))
                        
                        # Create SEC filing URL
                        filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{filing['accessionNumber'].replace('-', '')}/{filing['primaryDocument']}"
                        st.markdown(f"[View Full Filing]({filing_url})")
                    
                    # Add to processed data
                    processed_data.append({
                        'Date': filing['filingDate'],
                        'Type': filing['form'],
                        'Document': filing['primaryDocument'],
                        'URL': filing_url
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

    # Footer with SEC attribution
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center'>
            <p>Data sourced directly from SEC EDGAR • This tool is free and open source</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
