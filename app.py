# app.py
import io
import os
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==========================================
# PAGE CONFIG & CUSTOM STYLING
# ==========================================
st.set_page_config(
    page_title="Real Estate Portfolio Management System",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Premium UI Enhancements */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Modern Metric Cards */
    div[data-testid="stMetric"] {
        background-color: var(--background-secondary);
        border: 1px solid rgba(128, 128, 128, 0.2);
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Property Card Styling */
    .property-card {
        background-color: var(--background-secondary);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    .property-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .property-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
    }
    .badge-available {
        background-color: #2563eb;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-construction {
        background-color: #f59e0b;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-sold {
        background-color: #10b981;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DATABASE INITIALIZATION & SERVICES
# ==========================================
DB_FILE = "portfolio_management.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Business Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS business_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            business_name TEXT NOT NULL,
            initial_cash REAL NOT NULL,
            initial_net_worth REAL NOT NULL,
            jaffar_initial_net_worth REAL NOT NULL,
            tehseen_initial_net_worth REAL NOT NULL,
            dealer_commission_pct REAL DEFAULT 25.0,
            logo_data BLOB
        )
    """)
    
    # Safe schema migration for business_settings table
    cursor.execute("PRAGMA table_info(business_settings)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    required_cols = {
        "jaffar_initial_net_worth": "REAL DEFAULT 0.0",
        "tehseen_initial_net_worth": "REAL DEFAULT 0.0",
        "dealer_commission_pct": "REAL DEFAULT 25.0",
        "logo_data": "BLOB"
    }
    
    for col_name, col_type in required_cols.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE business_settings ADD COLUMN {col_name} {col_type}")

    # Properties Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            property_type TEXT NOT NULL,
            size TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            buying_price REAL NOT NULL,
            construction_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            ownership_pct REAL NOT NULL,
            our_investment REAL NOT NULL,
            current_est_value REAL NOT NULL,
            expected_selling_price REAL NOT NULL,
            actual_selling_price REAL DEFAULT 0.0,
            sold_date TEXT,
            status TEXT NOT NULL,
            dealer TEXT NOT NULL,
            notes TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# CURRENCY & FORMATTING HELPERS
# ==========================================
def format_pkr(amount):
    """Formats a number in Pakistani Lakh/Crore notation."""
    if amount is None or np.isnan(amount):
        return "PKR 0"
    
    is_negative = amount < 0
    amount = abs(amount)
    
    if amount >= 10000000:  # 1 Crore = 10,000,000
        val = amount / 10000000
        formatted = f"{val:,.2f} Crore"
    elif amount >= 100000:  # 1 Lakh = 100,000
        val = amount / 100000
        formatted = f"{val:,.2f} Lakh"
    else:
        formatted = f"{amount:,.2f}"
        
    prefix = "-PKR " if is_negative else "PKR "
    return prefix + formatted

# ==========================================
# SETTINGS MANAGERS
# ==========================================
def get_settings():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM business_settings WHERE id=1", conn)
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def save_settings(name, cash, net_worth, jaffar_nw, tehseen_nw, commission_pct):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM business_settings WHERE id=1")
    exists = cursor.fetchone()
    if exists:
        cursor.execute("""
            UPDATE business_settings SET
                business_name=?, initial_cash=?, initial_net_worth=?,
                jaffar_initial_net_worth=?, tehseen_initial_net_worth=?,
                dealer_commission_pct=?
            WHERE id=1
        """, (name, cash, net_worth, jaffar_nw, tehseen_nw, commission_pct))
    else:
        cursor.execute("""
            INSERT INTO business_settings (id, business_name, initial_cash, initial_net_worth, jaffar_initial_net_worth, tehseen_initial_net_worth, dealer_commission_pct)
            VALUES (1, ?, ?, ?, ?, ?, ?)
        """, (name, cash, net_worth, jaffar_nw, tehseen_nw, commission_pct))
    conn.commit()
    conn.close()

# ==========================================
# PROPERTY DATA MANAGERS
# ==========================================
def get_properties():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM properties", conn)
    conn.close()
    return df

def add_property_db(p_data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO properties (
            name, location, property_type, size, purchase_date,
            buying_price, construction_cost, total_cost, ownership_pct,
            our_investment, current_est_value, expected_selling_price,
            actual_selling_price, sold_date, status, dealer, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p_data['name'], p_data['location'], p_data['property_type'], p_data['size'],
        p_data['purchase_date'], p_data['buying_price'], p_data['construction_cost'],
        p_data['total_cost'], p_data['ownership_pct'], p_data['our_investment'],
        p_data['current_est_value'], p_data['expected_selling_price'],
        p_data['actual_selling_price'], p_data['sold_date'], p_data['status'],
        p_data['dealer'], p_data['notes']
    ))
    conn.commit()
    conn.close()

def update_property_db(pid, p_data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE properties SET
            name=?, location=?, property_type=?, size=?, purchase_date=?,
            buying_price=?, construction_cost=?, total_cost=?, ownership_pct=?,
            our_investment=?, current_est_value=?, expected_selling_price=?,
            actual_selling_price=?, sold_date=?, status=?, dealer=?, notes=?
        WHERE id=?
    """, (
        p_data['name'], p_data['location'], p_data['property_type'], p_data['size'],
        p_data['purchase_date'], p_data['buying_price'], p_data['construction_cost'],
        p_data['total_cost'], p_data['ownership_pct'], p_data['our_investment'],
        p_data['current_est_value'], p_data['expected_selling_price'],
        p_data['actual_selling_price'], p_data['sold_date'], p_data['status'],
        p_data['dealer'], p_data['notes'], pid
    ))
    conn.commit()
    conn.close()

def delete_property_db(pid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM properties WHERE id=?", (pid,))
    conn.commit()
    conn.close()

# ==========================================
# FINANCIAL CALCULATIONS ENGINE
# ==========================================
def calculate_financials():
    settings = get_settings()
    df = get_properties()
    
    if settings is None:
        return None

    commission_pct = settings['dealer_commission_pct'] / 100.0
    
    # Base Values
    initial_cash = settings['initial_cash']
    
    total_active_investment = 0.0
    current_portfolio_value = 0.0
    total_realized_profit = 0.0
    total_realized_loss = 0.0
    
    dealer_earnings = {"Samiullah": 0.0, "Sheikh Abid": 0.0}
    jaffar_realized_profit = 0.0
    tehseen_realized_profit = 0.0
    
    cash_spent = 0.0
    cash_received = 0.0
    
    if not df.empty:
        for _, row in df.iterrows():
            our_inv = row['our_investment']
            status = row['status']
            ownership_fraction = row['ownership_pct'] / 100.0
            
            # Cash spent on ALL properties invested in
            cash_spent += our_inv
            
            if status in ['Available', 'Under Construction']:
                total_active_investment += our_inv
                current_portfolio_value += (row['current_est_value'] * ownership_fraction)
            elif status == 'Sold':
                our_selling_amount = row['actual_selling_price'] * ownership_fraction
                cash_received += our_selling_amount
                
                profit = our_selling_amount - our_inv
                if profit > 0:
                    total_realized_profit += profit
                    dealer_comm = profit * commission_pct
                    rem_profit = profit * (1.0 - commission_pct)
                    partner_share = rem_profit / 2.0
                    
                    if row['dealer'] in dealer_earnings:
                        dealer_earnings[row['dealer']] += dealer_comm
                    
                    jaffar_realized_profit += partner_share
                    tehseen_realized_profit += partner_share
                else:
                    total_realized_loss += abs(profit)
                    
    # Dynamic Business Cash = Initial Cash - Money Spent on Investments + Cash Inflows from Sales
    current_business_cash = initial_cash - cash_spent + cash_received
    
    # Net Realized Gain/Loss
    net_realized_gain_loss = total_realized_profit - total_realized_loss
    
    # Business Net Worth = Business Cash + Current Value of Active Investments
    business_net_worth = current_business_cash + current_portfolio_value
    
    # Partner Net Worths
    jaffar_net_worth = settings['jaffar_initial_net_worth'] + jaffar_realized_profit
    tehseen_net_worth = settings['tehseen_initial_net_worth'] + tehseen_realized_profit
    
    # Utilization Metrics
    total_assets = current_business_cash + total_active_investment
    cash_utilization_pct = (total_active_investment / total_assets * 100) if total_assets > 0 else 0.0
    investment_utilization_pct = (current_portfolio_value / total_active_investment * 100) if total_active_investment > 0 else 0.0
    
    # Portfolio Growth %
    overall_roi_pct = ((current_portfolio_value - total_active_investment) / total_active_investment * 100) if total_active_investment > 0 else 0.0

    return {
        "business_cash": current_business_cash,
        "business_net_worth": business_net_worth,
        "total_active_investment": total_active_investment,
        "current_portfolio_value": current_portfolio_value,
        "total_realized_profit": total_realized_profit,
        "total_realized_loss": total_realized_loss,
        "dealer_earnings": dealer_earnings,
        "jaffar_net_worth": jaffar_net_worth,
        "jaffar_realized_profit": jaffar_realized_profit,
        "tehseen_net_worth": tehseen_net_worth,
        "tehseen_realized_profit": tehseen_realized_profit,
        "cash_utilization_pct": cash_utilization_pct,
        "investment_utilization_pct": investment_utilization_pct,
        "portfolio_growth_pct": overall_roi_pct,
        "total_properties": len(df),
        "available_properties": len(df[df['status'] == 'Available']) if not df.empty else 0,
        "under_construction_properties": len(df[df['status'] == 'Under Construction']) if not df.empty else 0,
        "sold_properties": len(df[df['status'] == 'Sold']) if not df.empty else 0
    }

# ==========================================
# REPORT GENERATION HELPERS
# ==========================================
def generate_pdf_report(df, title_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=12
    )
    
    elements.append(Paragraph(title_text, title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if not df.empty:
        data = [df.columns.tolist()]
        for row in df.values:
            formatted_row = []
            for item in row:
                if isinstance(item, (int, float)):
                    formatted_row.append(f"{item:,.2f}")
                else:
                    formatted_row.append(str(item))
            data.append(formatted_row)
            
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F3F4F6')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
            ('FONTSIZE', (0,1), (-1,-1), 8),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No record data available.", styles['Normal']))
        
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_excel_report(df_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return output

# ==========================================
# APPLICATION INTERFACE (FLOW CONTROL)
# ==========================================
settings = get_settings()

# First-time Setup Gatekeeper
if settings is None:
    st.markdown("## 🏢 Real Estate Portfolio Management Setup")
    st.info("Welcome! Please configure your initial business details to initialize the workspace.")
    
    with st.form("initial_setup_form"):
        b_name = st.text_input("Business Name *", value="Apex Real Estate Holdings")
        col1, col2 = st.columns(2)
        with col1:
            init_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, value=50000000.0, step=100000.0)
            jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, value=25000000.0, step=100000.0)
        with col2:
            init_nw = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, value=50000000.0, step=100000.0)
            tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, value=25000000.0, step=100000.0)
            
        comm_pct = st.number_input("Dealer Commission Percentage (%)", min_value=0.0, max_value=100.0, value=25.0)
        submit_setup = st.form_submit_button("🚀 Initialize Business Portfolio")
        
        if submit_setup:
            if not b_name.strip():
                st.error("Business Name is required.")
            else:
                save_settings(b_name, init_cash, init_nw, jaffar_nw, tehseen_nw, comm_pct)
                st.success("Business workspace initialized successfully!")
                st.rerun()
    st.stop()

# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title(f"🏢 {settings['business_name']}")
st.sidebar.markdown("---")

menu_options = [
    "🏠 Dashboard",
    "➕ Add Property",
    "🏢 Manage Properties",
    "📊 Portfolio",
    "📑 Reports",
    "⚙ Business Settings"
]

choice = st.sidebar.radio("Navigation", menu_options, index=0)

fin = calculate_financials()

# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if choice == "🏠 Dashboard":
    st.title("🏠 Executive Financial Dashboard")
    st.caption("Real-Time Asset Allocation & Financial Metrics")
    
    # TOP KPI CARDS - ROW 1: PRIMARY FINANCIALS
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Business Net Worth", format_pkr(fin['business_net_worth']))
    kpi2.metric("Business Cash", format_pkr(fin['business_cash']))
    kpi3.metric("Money Invested", format_pkr(fin['total_active_investment']))
    kpi4.metric("Portfolio Value", format_pkr(fin['current_portfolio_value']))
    kpi5.metric("Total Realized Profit", format_pkr(fin['total_realized_profit']))
    
    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)
    
    # TOP KPI CARDS - ROW 2: PARTNERS & ACCOUNTS
    kpi6, kpi7, kpi8, kpi9, kpi10 = st.columns(5)
    kpi6.metric("Realized Loss", format_pkr(fin['total_realized_loss']))
    kpi7.metric("Jaffar Net Worth", format_pkr(fin['jaffar_net_worth']))
    kpi8.metric("Tehseen Net Worth", format_pkr(fin['tehseen_net_worth']))
    kpi9.metric("Samiullah Comm.", format_pkr(fin['dealer_earnings']['Samiullah']))
    kpi10.metric("Sheikh Abid Comm.", format_pkr(fin['dealer_earnings']['Sheikh Abid']))
    
    st.markdown("<div style='margin: 10px 0;'></div>", unsafe_allow_html=True)

    # TOP KPI CARDS - ROW 3: PROPERTY COUNTS
    kpi11, kpi12, kpi13, kpi14, kpi15 = st.columns(5)
    kpi11.metric("Total Properties", fin['total_properties'])
    kpi12.metric("Available", fin['available_properties'])
    kpi13.metric("Under Construction", fin['under_construction_properties'])
    kpi14.metric("Sold Properties", fin['sold_properties'])
    kpi15.metric("Unrealized ROI", f"{fin['portfolio_growth_pct']:.2f}%")

    st.markdown("---")

    # PORTFOLIO SUMMARY SECTION
    st.subheader("📊 Portfolio Performance Summary")
    sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
    sum_col1.metric("Cash Utilization", f"{fin['cash_utilization_pct']:.1f}%")
    sum_col2.metric("Investment Utilization", f"{fin['investment_utilization_pct']:.1f}%")
    sum_col3.metric("Portfolio Growth", f"{fin['portfolio_growth_pct']:.2f}%")
    sum_col4.metric("Active Assets Value", format_pkr(fin['total_active_investment'] + fin['current_portfolio_value']))

    st.markdown("---")

    # LARGEST SECTION: WHERE MY MONEY IS INVESTED
    st.header("💡 Where My Money Is Invested")
    st.info(f"**Total Active Investment:** {format_pkr(fin['total_active_investment'])}")
    
    df_props = get_properties()
    active_props = df_props[df_props['status'].isin(['Available', 'Under Construction'])] if not df_props.empty else pd.DataFrame()
    
    if active_props.empty:
        st.warning("No active property investments currently found in portfolio.")
    else:
        for idx, row in active_props.iterrows():
            total_active_inv = fin['total_active_investment']
            portfolio_share = (row['our_investment'] / total_active_inv * 100) if total_active_inv > 0 else 0.0
            
            our_curr_val = row['current_est_value'] * (row['ownership_pct'] / 100.0)
            roi_pct = ((our_curr_val - row['our_investment']) / row['our_investment'] * 100) if row['our_investment'] > 0 else 0.0
            
            status_class = "badge-available" if row['status'] == 'Available' else "badge-construction"
            
            st.markdown(f"""
                <div class="property-card">
                    <div class="property-header">
                        <span class="property-title">🏠 {row['name']} ({row['location']})</span>
                        <span class="{status_class}">{row['status']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.write(f"**Total Cost:** {format_pkr(row['total_cost'])}")
            c1.write(f"**Ownership:** {row['ownership_pct']}%")
            
            c2.write(f"**Our Investment:** {format_pkr(row['our_investment'])}")
            c2.write(f"**Est. Value:** {format_pkr(row['current_est_value'])}")
            
            c3.write(f"**Expected Price:** {format_pkr(row['expected_selling_price'])}")
            c3.write(f"**Purchase Date:** {row['purchase_date']}")
            
            c4.write(f"**Dealer:** {row['dealer']}")
            c4.write(f"**Unrealized ROI:** {roi_pct:.2f}%")
            
            st.write(f"**Portfolio Share:** {portfolio_share:.1f}%")
            st.progress(min(max(portfolio_share / 100.0, 0.0), 1.0))
            st.markdown("---")

# ==========================================
# PAGE 2: ADD PROPERTY
# ==========================================
elif choice == "➕ Add Property":
    st.title("➕ Register New Property Investment")
    st.caption("Add property assets to your active portfolio")
    
    with st.form("add_property_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Property Name *")
            location = st.text_input("Location *")
            property_type = st.selectbox("Property Type", ["Plot", "House", "Commercial Plaza", "Apartment", "Agricultural Land", "Industrial File"])
            size = st.text_input("Property Size (e.g., 1 Kanal, 10 Marla, 240 Sq Yds)")
            purchase_date = st.date_input("Purchase Date", datetime.now()).strftime('%Y-%m-%d')
            buying_price = st.number_input("Buying Price (PKR) *", min_value=0.0, step=100000.0)
            construction_cost = st.number_input("Construction / Improvement Cost (PKR)", min_value=0.0, step=50000.0)
            
        with col2:
            ownership_pct = st.selectbox("Our Ownership Percentage (%)", [100.0, 75.0, 60.0, 50.0, 40.0, 25.0, 20.0, 10.0, 5.0, 1.0], index=0)
            current_est_value = st.number_input("Current Estimated Market Value (PKR) *", min_value=0.0, step=100000.0)
            expected_selling_price = st.number_input("Expected Selling Price (PKR) *", min_value=0.0, step=100000.0)
            dealer = st.selectbox("Assigned Dealer *", ["Samiullah", "Sheikh Abid"])
            status = st.selectbox("Status *", ["Available", "Under Construction"])
            notes = st.text_area("Notes & Description")

        total_cost = buying_price + construction_cost
        our_investment = total_cost * (ownership_pct / 100.0)
        
        st.markdown("---")
        st.write(f"💰 **Total Calculated Property Cost:** {format_pkr(total_cost)}")
        st.write(f"💳 **Our Investment (Deducted from Cash):** {format_pkr(our_investment)}")
        
        submit = st.form_submit_button("➕ Save Property to Database")
        
        if submit:
            if not name.strip() or not location.strip():
                st.error("Please fill in all required fields marked with *")
            else:
                p_data = {
                    "name": name,
                    "location": location,
                    "property_type": property_type,
                    "size": size,
                    "purchase_date": purchase_date,
                    "buying_price": buying_price,
                    "construction_cost": construction_cost,
                    "total_cost": total_cost,
                    "ownership_pct": ownership_pct,
                    "our_investment": our_investment,
                    "current_est_value": current_est_value,
                    "expected_selling_price": expected_selling_price,
                    "actual_selling_price": 0.0,
                    "sold_date": None,
                    "status": status,
                    "dealer": dealer,
                    "notes": notes
                }
                add_property_db(p_data)
                st.success(f"Property '{name}' successfully registered!")
                st.rerun()

# ==========================================
# PAGE 3: MANAGE PROPERTIES
# ==========================================
elif choice == "🏢 Manage Properties":
    st.title("🏢 Property Asset Management")
    
    df_props = get_properties()
    
    if df_props.empty:
        st.info("No properties found. Add properties using the 'Add Property' tab.")
    else:
        # SEARCH AND FILTERS
        st.subheader("🔍 Search & Filter Portfolio")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        search_query = f_col1.text_input("Search Name / Location", "")
        filter_dealer = f_col2.selectbox("Filter Dealer", ["All", "Samiullah", "Sheikh Abid"])
        filter_status = f_col3.selectbox("Filter Status", ["All", "Available", "Under Construction", "Sold"])
        filter_ownership = f_col4.selectbox("Filter Ownership", ["All"] + sorted(df_props['ownership_pct'].unique().tolist()))
        
        filtered_df = df_props.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search_query, case=False, na=False) |
                filtered_df['location'].str.contains(search_query, case=False, na=False)
            ]
        if filter_dealer != "All":
            filtered_df = filtered_df[filtered_df['dealer'] == filter_dealer]
        if filter_status != "All":
            filtered_df = filtered_df[filtered_df['status'] == filter_status]
        if filter_ownership != "All":
            filtered_df = filtered_df[filtered_df['ownership_pct'] == float(filter_ownership)]

        display_rows = []
        comm_pct = settings['dealer_commission_pct'] / 100.0
        
        for _, r in filtered_df.iterrows():
            ownership_fraction = r['ownership_pct'] / 100.0
            
            if r['status'] == 'Sold':
                our_selling = r['actual_selling_price'] * ownership_fraction
                profit = our_selling - r['our_investment']
                if profit > 0:
                    dealer_comm = profit * comm_pct
                    j_profit = (profit - dealer_comm) / 2.0
                    t_profit = (profit - dealer_comm) / 2.0
                else:
                    dealer_comm, j_profit, t_profit = 0.0, 0.0, 0.0
                roi = ((profit) / r['our_investment'] * 100) if r['our_investment'] > 0 else 0.0
            else:
                profit, dealer_comm, j_profit, t_profit = 0.0, 0.0, 0.0, 0.0
                our_curr_val = r['current_est_value'] * ownership_fraction
                roi = ((our_curr_val - r['our_investment']) / r['our_investment'] * 100) if r['our_investment'] > 0 else 0.0

            display_rows.append({
                "ID": r['id'],
                "Property": r['name'],
                "Location": r['location'],
                "Dealer": r['dealer'],
                "Total Cost": format_pkr(r['total_cost']),
                "Ownership": f"{r['ownership_pct']}%",
                "Our Investment": format_pkr(r['our_investment']),
                "Current Value": format_pkr(r['current_est_value']),
                "Selling Price": format_pkr(r['actual_selling_price']) if r['status'] == 'Sold' else format_pkr(r['expected_selling_price']),
                "Realized Profit": format_pkr(profit) if r['status'] == 'Sold' else "N/A",
                "Dealer Comm.": format_pkr(dealer_comm) if r['status'] == 'Sold' else "N/A",
                "Jaffar Profit": format_pkr(j_profit) if r['status'] == 'Sold' else "N/A",
                "Tehseen Profit": format_pkr(t_profit) if r['status'] == 'Sold' else "N/A",
                "ROI": f"{roi:.2f}%",
                "Status": r['status']
            })
            
        st.dataframe(pd.DataFrame(display_rows), use_container_width=True)
        st.markdown("---")

        st.subheader("⚙️ Edit Property Record")
        prop_list = {f"{r['name']} (ID: {r['id']})": r['id'] for _, r in filtered_df.iterrows()}
        
        if prop_list:
            selected_prop_str = st.selectbox("Select Property to Modify / Sell / Delete", list(prop_list.keys()))
            selected_id = prop_list[selected_prop_str]
            selected_row = df_props[df_props['id'] == selected_id].iloc[0]

            col_act1, col_act2 = st.columns(2)
            with col_act1:
                st.markdown("#### Modify / Sell Property")
                with st.form("edit_property_form"):
                    e_name = st.text_input("Property Name", value=selected_row['name'])
                    e_location = st.text_input("Location", value=selected_row['location'])
                    e_type = st.selectbox("Type", ["Plot", "House", "Commercial Plaza", "Apartment", "Agricultural Land", "Industrial File"], index=0)
                    e_size = st.text_input("Size", value=selected_row['size'])
                    e_buying_price = st.number_input("Buying Price (PKR)", value=float(selected_row['buying_price']), step=100000.0)
                    e_construction = st.number_input("Construction Cost (PKR)", value=float(selected_row['construction_cost']), step=50000.0)
                    e_ownership = st.selectbox("Ownership %", [100.0, 75.0, 60.0, 50.0, 40.0, 25.0, 20.0, 10.0, 5.0, 1.0], index=[100.0, 75.0, 60.0, 50.0, 40.0, 25.0, 20.0, 10.0, 5.0, 1.0].index(selected_row['ownership_pct']))
                    
                    e_est_val = st.number_input("Current Estimated Value (PKR)", value=float(selected_row['current_est_value']), step=100000.0)
                    e_exp_price = st.number_input("Expected Selling Price (PKR)", value=float(selected_row['expected_selling_price']), step=100000.0)
                    
                    e_status = st.selectbox("Status", ["Available", "Under Construction", "Sold"], index=["Available", "Under Construction", "Sold"].index(selected_row['status']))
                    
                    st.markdown("---")
                    st.markdown("**Sale Settlement Details (If Sold):**")
                    e_actual_selling_price = st.number_input("Actual Selling Price (PKR)", value=float(selected_row['actual_selling_price']), step=100000.0)
                    e_sold_date = st.date_input("Sold Date", datetime.now()).strftime('%Y-%m-%d')
                    
                    e_dealer = st.selectbox("Dealer", ["Samiullah", "Sheikh Abid"], index=["Samiullah", "Sheikh Abid"].index(selected_row['dealer']))
                    e_notes = st.text_area("Notes", value=selected_row['notes'] or "")

                    e_total_cost = e_buying_price + e_construction
                    e_our_inv = e_total_cost * (e_ownership / 100.0)

                    if e_status == 'Sold' and e_actual_selling_price > 0:
                        our_sell_amt = e_actual_selling_price * (e_ownership / 100.0)
                        if our_sell_amt < e_our_inv:
                            st.warning(f"⚠️ Warning: Our Selling Amount ({format_pkr(our_sell_amt)}) is lower than Our Investment ({format_pkr(e_our_inv)}). This sale results in a LOSS.")

                    save_changes = st.form_submit_button("💾 Update Property Record")
                    
                    if save_changes:
                        updated_pdata = {
                            "name": e_name, "location": e_location, "property_type": e_type, "size": e_size,
                            "purchase_date": selected_row['purchase_date'], "buying_price": e_buying_price,
                            "construction_cost": e_construction, "total_cost": e_total_cost,
                            "ownership_pct": e_ownership, "our_investment": e_our_inv,
                            "current_est_value": e_est_val, "expected_selling_price": e_exp_price,
                            "actual_selling_price": e_actual_selling_price if e_status == 'Sold' else 0.0,
                            "sold_date": e_sold_date if e_status == 'Sold' else None,
                            "status": e_status, "dealer": e_dealer, "notes": e_notes
                        }
                        update_property_db(selected_id, updated_pdata)
                        st.success("Property details updated successfully!")
                        st.rerun()

            with col_act2:
                st.markdown("#### Delete Property Record")
                st.error("⚠️ Deleting a property will remove it permanently from database records.")
                if st.button("🗑️ Delete Selected Property", type="primary"):
                    delete_property_db(selected_id)
                    st.success("Property deleted successfully!")
                    st.rerun()

# ==========================================
# PAGE 4: PORTFOLIO
# ==========================================
elif choice == "📊 Portfolio":
    st.title("📊 Portfolio Visual Analytics")
    
    df_props = get_properties()
    
    if df_props.empty:
        st.info("No properties found to visualize.")
    else:
        v_col1, v_col2 = st.columns(2)
        
        with v_col1:
            st.subheader("Asset Allocation by Property Status")
            fig_status = px.pie(
                df_props, names='status', values='our_investment',
                color='status',
                color_discrete_map={'Available': '#2563eb', 'Under Construction': '#f59e0b', 'Sold': '#10b981'},
                hole=0.4
            )
            st.plotly_chart(fig_status, use_container_width=True)
            
        with v_col2:
            st.subheader("Capital Investment by Location")
            fig_loc = px.bar(
                df_props, x='location', y='our_investment', color='status',
                barmode='stack',
                color_discrete_map={'Available': '#2563eb', 'Under Construction': '#f59e0b', 'Sold': '#10b981'},
                labels={'our_investment': 'Our Investment (PKR)'}
            )
            st.plotly_chart(fig_loc, use_container_width=True)

        st.markdown("---")
        
        v_col3, v_col4 = st.columns(2)
        
        with v_col3:
            st.subheader("Dealer Performance & Portfolio Share")
            fig_dealer = px.pie(
                df_props, names='dealer', values='our_investment',
                title="Capital Managed by Dealer",
                color_discrete_sequence=['#8b5cf6', '#ec4899']
            )
            st.plotly_chart(fig_dealer, use_container_width=True)
            
        with v_col4:
            st.subheader("Active Investments vs Current Value")
            active_df = df_props[df_props['status'] != 'Sold'].copy()
            if not active_df.empty:
                active_df['Our Est Value'] = active_df['current_est_value'] * (active_df['ownership_pct'] / 100.0)
                fig_compare = go.Figure(data=[
                    go.Bar(name='Our Investment', x=active_df['name'], y=active_df['our_investment'], marker_color='#2563eb'),
                    go.Bar(name='Our Current Share Value', x=active_df['name'], y=active_df['Our Est Value'], marker_color='#10b981')
                ])
                fig_compare.update_layout(barmode='group')
                st.plotly_chart(fig_compare, use_container_width=True)
            else:
                st.info("No active properties available for market comparison.")

# ==========================================
# PAGE 5: REPORTS & EXPORTS
# ==========================================
elif choice == "📑 Reports":
    st.title("📑 Comprehensive Financial Reports")
    
    df_props = get_properties()
    comm_pct = settings['dealer_commission_pct'] / 100.0
    
    processed_records = []
    for _, r in df_props.iterrows():
        ownership_fraction = r['ownership_pct'] / 100.0
        
        if r['status'] == 'Sold':
            our_selling = r['actual_selling_price'] * ownership_fraction
            profit = our_selling - r['our_investment']
            if profit > 0:
                dealer_comm = profit * comm_pct
                j_profit = (profit - dealer_comm) / 2.0
                t_profit = (profit - dealer_comm) / 2.0
            else:
                dealer_comm, j_profit, t_profit = 0.0, 0.0, 0.0
        else:
            profit, dealer_comm, j_profit, t_profit = 0.0, 0.0, 0.0, 0.0

        processed_records.append({
            "ID": r['id'],
            "Name": r['name'],
            "Location": r['location'],
            "Status": r['status'],
            "Dealer": r['dealer'],
            "Total Cost": r['total_cost'],
            "Ownership %": r['ownership_pct'],
            "Our Investment": r['our_investment'],
            "Current Est Value": r['current_est_value'],
            "Actual Selling Price": r['actual_selling_price'],
            "Realized Profit": profit,
            "Realized Loss": abs(profit) if profit < 0 else 0.0,
            "Dealer Commission": dealer_comm,
            "Jaffar Profit": j_profit,
            "Tehseen Profit": t_profit
        })

    report_df = pd.DataFrame(processed_records) if processed_records else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Individual Reports", "📥 CSV Downloads", "📗 Excel Export", "📄 PDF Reports"])

    with tab1:
        report_type = st.selectbox("Select Report Category", [
            "Property Report", "Investment Report", "Profit Report", "Loss Report",
            "Dealer Report", "Jaffar Report", "Tehseen Report", "Portfolio Report",
            "Cash Flow Report", "Net Worth Report"
        ])
        
        if not report_df.empty:
            if report_type == "Property Report":
                st.dataframe(report_df[["ID", "Name", "Location", "Status", "Dealer", "Total Cost"]], use_container_width=True)
            elif report_type == "Investment Report":
                st.dataframe(report_df[["Name", "Total Cost", "Ownership %", "Our Investment", "Status"]], use_container_width=True)
            elif report_type == "Profit Report":
                st.dataframe(report_df[report_df['Realized Profit'] > 0][["Name", "Our Investment", "Actual Selling Price", "Realized Profit", "Dealer Commission"]], use_container_width=True)
            elif report_type == "Loss Report":
                st.dataframe(report_df[report_df['Realized Loss'] > 0][["Name", "Our Investment", "Actual Selling Price", "Realized Loss"]], use_container_width=True)
            elif report_type == "Dealer Report":
                st.dataframe(report_df[["Name", "Dealer", "Status", "Realized Profit", "Dealer Commission"]], use_container_width=True)
            elif report_type == "Jaffar Report":
                st.dataframe(report_df[report_df['Jaffar Profit'] > 0][["Name", "Realized Profit", "Dealer Commission", "Jaffar Profit"]], use_container_width=True)
            elif report_type == "Tehseen Report":
                st.dataframe(report_df[report_df['Tehseen Profit'] > 0][["Name", "Realized Profit", "Dealer Commission", "Tehseen Profit"]], use_container_width=True)
            elif report_type == "Portfolio Report":
                st.dataframe(report_df, use_container_width=True)
            elif report_type == "Cash Flow Report":
                st.write(f"**Business Cash Balance:** {format_pkr(fin['business_cash'])}")
                st.write(f"**Total Capital Outflow:** {format_pkr(report_df['Our Investment'].sum())}")
            elif report_type == "Net Worth Report":
                st.write(f"**Business Net Worth:** {format_pkr(fin['business_net_worth'])}")
                st.write(f"**Jaffar Net Worth:** {format_pkr(fin['jaffar_net_worth'])}")
                st.write(f"**Tehseen Net Worth:** {format_pkr(fin['tehseen_net_worth'])}")

    with tab2:
        st.subheader("Download Individual CSV Files")
        if not report_df.empty:
            csv_all = report_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download All Properties CSV", csv_all, "all_properties.csv", "text/csv")
            
            csv_inv = report_df[["Name", "Our Investment", "Status"]].to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Investment Report CSV", csv_inv, "investment_report.csv", "text/csv")
            
            csv_profit = report_df[report_df['Realized Profit'] > 0].to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Profit Report CSV", csv_profit, "profit_report.csv", "text/csv")

    with tab3:
        st.subheader("Export Complete Business Portfolio to Excel")
        if not report_df.empty:
            excel_sheets = {
                "All Properties": report_df,
                "Profits": report_df[report_df['Realized Profit'] > 0],
                "Losses": report_df[report_df['Realized Loss'] > 0],
                "Dealers": report_df[["Name", "Dealer", "Dealer Commission"]]
            }
            excel_file = generate_excel_report(excel_sheets)
            st.download_button("📗 Download Full Portfolio Workbook (.xlsx)", excel_file, "business_portfolio_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab4:
        st.subheader("Generate Official PDF Report")
        if not report_df.empty:
            pdf_file = generate_pdf_report(report_df[["Name", "Status", "Our Investment", "Realized Profit"]], f"{settings['business_name']} - Executive Portfolio Report")
            st.download_button("📄 Download Official PDF Report", pdf_file, "executive_portfolio_report.pdf", "application/pdf")

# ==========================================
# PAGE 6: BUSINESS SETTINGS
# ==========================================
elif choice == "⚙ Business Settings":
    st.title("⚙️ Business Configuration & Settings")
    st.caption("Manage business constants, capital parameters, and commission structures")
    
    with st.form("update_settings_form"):
        u_name = st.text_input("Business Name", value=settings['business_name'])
        
        c1, c2 = st.columns(2)
        with c1:
            u_cash = st.number_input("Initial Business Cash (PKR)", value=float(settings['initial_cash']), step=100000.0)
            u_jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", value=float(settings['jaffar_initial_net_worth']), step=100000.0)
        with c2:
            u_nw = st.number_input("Initial Business Net Worth (PKR)", value=float(settings['initial_net_worth']), step=100000.0)
            u_tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", value=float(settings['tehseen_initial_net_worth']), step=100000.0)
            
        u_comm_pct = st.number_input("Dealer Commission Percentage (%)", value=float(settings['dealer_commission_pct']), min_value=0.0, max_value=100.0)
        
        btn_update = st.form_submit_button("💾 Update Settings")
        
        if btn_update:
            if not u_name.strip():
                st.error("Business Name cannot be empty.")
            else:
                save_settings(u_name, u_cash, u_nw, u_jaffar_nw, u_tehseen_nw, u_comm_pct)
                st.success("Business settings successfully updated!")
                st.rerun()
