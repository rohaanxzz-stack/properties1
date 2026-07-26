# ==============================================================================
# PROPERTY INVESTMENT & BUSINESS PORTFOLIO MANAGEMENT DASHBOARD
# Architecture: Single-file Streamlit Application with Embedded Database & UI
# Author: Senior Software Architect & Financial Systems Engineer
# Language: Python 3.9+ | Framework: Streamlit
# ==============================================================================

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import io
import json
import base64

# ReportLab Imports for Production PDF Export
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# 1. APPLICATION INITIALIZATION & CONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title="Property Investment & Business Portfolio Management Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_FILE = "portfolio_management.db"

# ==============================================================================
# 2. DATABASE ARCHITECTURE & MIGRATIONS
# ==============================================================================

def get_db_connection():
    """Establish connection to SQLite database with Row factory."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema, tables, default indexes, and seed data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Business Settings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            initial_business_cash REAL NOT NULL,
            current_business_cash REAL NOT NULL,
            initial_business_net_worth REAL NOT NULL,
            jaffar_initial_net_worth REAL NOT NULL,
            jaffar_current_net_worth REAL NOT NULL,
            tehseen_initial_net_worth REAL NOT NULL,
            tehseen_current_net_worth REAL NOT NULL,
            dealer_commission_pct REAL NOT NULL DEFAULT 25.0,
            theme_mode TEXT DEFAULT 'Dark',
            logo_data TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('ADMIN', 'VIEWER')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Properties Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_name TEXT NOT NULL,
            location TEXT NOT NULL,
            property_type TEXT NOT NULL,
            property_size TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            buying_price REAL NOT NULL,
            construction_cost REAL NOT NULL,
            total_property_cost REAL NOT NULL,
            our_ownership_pct REAL NOT NULL,
            our_investment REAL NOT NULL,
            expected_selling_price REAL NOT NULL,
            expected_selling_date TEXT NOT NULL,
            selling_price REAL DEFAULT 0.0,
            our_selling_amount REAL DEFAULT 0.0,
            our_profit REAL DEFAULT 0.0,
            dealer_commission REAL DEFAULT 0.0,
            jaffar_profit REAL DEFAULT 0.0,
            tehseen_profit REAL DEFAULT 0.0,
            broker_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Available', 'Under Construction', 'Sold')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Audit & Financial Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            log_type TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(property_id) REFERENCES properties(id) ON DELETE SET NULL
        )
    ''')
    
    # Seed Admin User if none exists
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "admin123", "ADMIN"))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("viewer", "viewer123", "VIEWER"))
        
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 3. FINANCIAL ENGINE & COMPUTATION SERVICES
# ==============================================================================

def format_pkr(amount):
    """Formats numeric values into Pakistani Rupee (PKR) standard format."""
    if amount is None:
        amount = 0.0
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    
    s = f"{amount:,.2f}"
    parts = s.split(".")
    integer_part = parts[0].replace(",", "")
    decimal_part = parts[1]
    
    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last_three = integer_part[-3:]
        other_numbers = integer_part[:-3]
        res = ""
        while len(other_numbers) > 2:
            res = "," + other_numbers[-2:] + res
            other_numbers = other_numbers[:-2]
        if other_numbers:
            res = other_numbers + res
        formatted_int = res + "," + last_three
        
    return f"{sign}PKR {formatted_int}.{decimal_part}"

def get_business_settings():
    """Retrieves current business settings from SQLite."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM business_settings ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def recalculate_business_metrics():
    """Dynamic financial recalculation engine for Portfolio Net Worth & Wallets."""
    settings = get_business_settings()
    if not settings:
        return
    
    conn = get_db_connection()
    properties = conn.execute("SELECT * FROM properties").fetchall()
    
    initial_cash = settings["initial_business_cash"]
    jaffar_initial = settings["jaffar_initial_net_worth"]
    tehseen_initial = settings["tehseen_initial_net_worth"]
    
    total_invested_active = 0.0
    total_realized_profit = 0.0
    total_selling_inflow = 0.0
    jaffar_accumulated_profit = 0.0
    tehseen_accumulated_profit = 0.0
    
    for p in properties:
        p_dict = dict(p)
        our_inv = p_dict["our_investment"]
        status = p_dict["status"]
        
        if status in ["Available", "Under Construction"]:
            total_invested_active += our_inv
        elif status == "Sold":
            total_selling_inflow += p_dict["our_selling_amount"]
            total_realized_profit += p_dict["our_profit"]
            jaffar_accumulated_profit += p_dict["jaffar_profit"]
            tehseen_accumulated_profit += p_dict["tehseen_profit"]
            
    # Business Cash = Initial Cash - Cash Outflow for Active Investments + Inflow from Sold Properties
    current_cash = initial_cash - total_invested_active + total_selling_inflow - (jaffar_accumulated_profit + tehseen_accumulated_profit)
    current_net_worth = current_cash + total_invested_active
    jaffar_current_nw = jaffar_initial + jaffar_accumulated_profit
    tehseen_current_nw = tehseen_initial + tehseen_accumulated_profit
    
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE business_settings 
        SET current_business_cash = ?,
            jaffar_current_net_worth = ?,
            tehseen_current_net_worth = ?
        WHERE id = ?
    """, (current_cash, jaffar_current_nw, tehseen_current_nw, settings["id"]))
    
    conn.commit()
    conn.close()

# ==============================================================================
# 4. CUSTOM INJECTED CSS STYLES (PREMIUM SAAS DESIGN SYSTEM)
# ==============================================================================

def inject_custom_css(theme="Dark"):
    bg_color = "#0E1117" if theme == "Dark" else "#F8F9FA"
    card_bg = "#1E222D" if theme == "Dark" else "#FFFFFF"
    text_color = "#FFFFFF" if theme == "Dark" else "#212529"
    sub_text = "#A0AEC0" if theme == "Dark" else "#6C757D"
    border_color = "rgba(255, 255, 255, 0.08)" if theme == "Dark" else "rgba(0, 0, 0, 0.08)"
    
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            background-color: {bg_color};
            color: {text_color};
        }}
        
        /* Metric Card Layouts */
        .kpi-card {{
            background-color: {card_bg};
            border: 1px solid {border_color};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 0, 0, 0.1);
        }}
        .kpi-title {{
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {sub_text};
            margin-bottom: 8px;
        }}
        .kpi-value {{
            font-size: 1.6rem;
            font-weight: 700;
            color: {text_color};
            margin-bottom: 4px;
        }}
        .kpi-subtext {{
            font-size: 0.8rem;
            color: {sub_text};
        }}
        
        /* Property Showcase Cards */
        .prop-card {{
            background-color: {card_bg};
            border-left: 5px solid #3182CE;
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 18px;
            border-top: 1px solid {border_color};
            border-right: 1px solid {border_color};
            border-bottom: 1px solid {border_color};
        }}
        .badge-available {{
            background-color: rgba(72, 187, 120, 0.2);
            color: #48BB78;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-construction {{
            background-color: rgba(236, 201, 75, 0.2);
            color: #ECC94B;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-sold {{
            background-color: rgba(245, 101, 101, 0.2);
            color: #F56565;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        
        /* Progress Bar Customization */
        .stProgress > div > div > div > div {{
            background-image: linear-gradient(to right, #3182CE , #63B3ED);
        }}
        
        /* Streamlit Button Tweaks */
        .stButton>button {{
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 5. AUTHENTICATION & SESSION STATE MANAGEMENT
# ==============================================================================

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None

def render_login():
    """Renders sleek professional SaaS login portal."""
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px;'>🏢 Property Investment System Login</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div style='background-color: rgba(255,255,255,0.03); padding: 30px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1);'>
            <h4 style='margin-top: 0;'>Sign In to Portfolio</h4>
            <p style='color: #A0AEC0; font-size: 0.9rem;'>Enter administrative or viewer credentials to proceed.</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Authenticate", use_container_width=True)
            
            if submit:
                conn = get_db_connection()
                user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
                conn.close()
                
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user["username"]
                    st.session_state["role"] = user["role"]
                    st.success("Authentication successful! Redirecting...")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password.")

# Check for Initial Business Setup
settings = get_business_settings()
if settings:
    inject_custom_css(settings.get("theme_mode", "Dark"))

# ==============================================================================
# 6. INITIAL SETUP WIZARD (FIRST TIME RUN ONLY)
# ==============================================================================

if st.session_state["authenticated"] and not settings:
    st.markdown("# ⚙️ Initial Business System Setup")
    st.info("Welcome to your Property Investment & Business Portfolio Management Dashboard. Please configure your financial baseline.")
    
    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            b_name = st.text_input("Business Name", value="Real Estate Capital Holdings")
            b_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, value=50000000.0, step=100000.0)
            b_nw = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, value=50000000.0, step=100000.0)
        with col2:
            j_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, value=25000000.0, step=100000.0)
            t_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, value=25000000.0, step=100000.0)
            d_comm = st.number_input("Default Dealer Commission (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            
        submitted = st.form_submit_button("Complete Setup & Initialize Dashboard", use_container_width=True)
        if submitted:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO business_settings 
                (business_name, initial_business_cash, current_business_cash, initial_business_net_worth,
                 jaffar_initial_net_worth, jaffar_current_net_worth, tehseen_initial_net_worth, tehseen_current_net_worth, dealer_commission_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (b_name, b_cash, b_cash, b_nw, j_nw, j_nw, t_nw, t_nw, d_comm))
            conn.commit()
            conn.close()
            st.success("Setup complete!")
            st.rerun()

# ==============================================================================
# 7. MAIN APPLICATION NAVIGATION & ROUTING
# ==============================================================================

if not st.session_state["authenticated"]:
    render_login()
elif settings:
    recalculate_business_metrics() # Ensure financial integrity on render
    settings = get_business_settings() # Refresh settings
    
    # --------------------------------------------------------------------------
    # SIDEBAR CONTROL CENTER
    # --------------------------------------------------------------------------
    st.sidebar.markdown(f"## 🏢 {settings['business_name']}")
    st.sidebar.markdown(f"**User:** `{st.session_state['username']}` | **Role:** `{st.session_state['role']}`")
    st.sidebar.divider()
    
    navigation = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Dashboard",
            "📊 Portfolio Analytics",
            "🏢 Properties Directory",
            "➕ Add Property",
            "📑 Financial Reports",
            "⚙️ Business Settings",
            "👥 User Management"
        ]
    )
    
    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["role"] = None
        st.rerun()

    # ==========================================================================
    # MODULE 1: DASHBOARD (EXECUTIVE OVERVIEW)
    # ==========================================================================
    if navigation == "🏠 Dashboard":
        st.markdown(f"# 🏠 Executive Dashboard — {settings['business_name']}")
        
        # Load Property Dataset
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        # Financial Summary Calculation
        total_properties = len(props_df)
        available_props = len(props_df[props_df["status"] == "Available"])
        construction_props = len(props_df[props_df["status"] == "Under Construction"])
        sold_props = len(props_df[props_df["status"] == "Sold"])
        
        active_props_df = props_df[props_df["status"].isin(["Available", "Under Construction"])]
        money_invested = active_props_df["our_investment"].sum() if not active_props_df.empty else 0.0
        current_portfolio_value = active_props_df["expected_selling_price"].sum() * (active_props_df["our_ownership_pct"].sum()/100.0) if not active_props_df.empty else 0.0 # Weighted estimate
        
        # Simple estimate for active current portfolio expected value
        if not active_props_df.empty:
            current_portfolio_value = (active_props_df["expected_selling_price"] * (active_props_df["our_ownership_pct"] / 100.0)).sum()
        else:
            current_portfolio_value = 0.0
            
        sold_df = props_df[props_df["status"] == "Sold"]
        total_realized_profit = sold_df["our_profit"].sum() if not sold_df.empty else 0.0
        total_realized_loss = abs(sold_df[sold_df["our_profit"] < 0]["our_profit"].sum()) if not sold_df.empty else 0.0
        total_dealer_earnings = sold_df["dealer_commission"].sum() if not sold_df.empty else 0.0
        
        current_cash = settings["current_business_cash"]
        net_worth = current_cash + money_invested
        roi_pct = ((total_realized_profit - total_realized_loss) / money_invested * 100) if money_invested > 0 else 0.0
        
        # ----------------------------------------------------------------------
        # TOP ROW: HIGH-LEVEL KPI METRICS (14 KPIS COMPACT TILES)
        # ----------------------------------------------------------------------
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Net Worth</div>
                <div class="kpi-value" style="color: #9F7AEA;">{format_pkr(net_worth)}</div>
                <div class="kpi-subtext">Cash + Active Portfolio</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Current Portfolio ROI</div>
                <div class="kpi-value" style="color: {'#48BB78' if roi_pct >= 0 else '#F56565'};">{roi_pct:.2f}%</div>
                <div class="kpi-subtext">Yield on Active Capital</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Jaffar Net Worth</div>
                <div class="kpi-value" style="color: #319795;">{format_pkr(settings['jaffar_current_net_worth'])}</div>
                <div class="kpi-subtext">Base + Realized Profit Share</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Cash</div>
                <div class="kpi-value" style="color: #4299E1;">{format_pkr(current_cash)}</div>
                <div class="kpi-subtext">Liquid Liquidity</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Realized Profit</div>
                <div class="kpi-value" style="color: #48BB78;">{format_pkr(total_realized_profit)}</div>
                <div class="kpi-subtext">Realized Closed Trades</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Tehseen Net Worth</div>
                <div class="kpi-value" style="color: #319795;">{format_pkr(settings['tehseen_current_net_worth'])}</div>
                <div class="kpi-subtext">Base + Realized Profit Share</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi_col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Money Invested</div>
                <div class="kpi-value" style="color: #ECC94B;">{format_pkr(money_invested)}</div>
                <div class="kpi-subtext">Capital Committed</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Realized Loss</div>
                <div class="kpi-value" style="color: #F56565;">{format_pkr(total_realized_loss)}</div>
                <div class="kpi-subtext">Realized Drawdown</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Properties</div>
                <div class="kpi-value">{total_properties}</div>
                <div class="kpi-subtext">Available ({available_props}) | Built ({construction_props}) | Sold ({sold_props})</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi_col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Active Portfolio Value</div>
                <div class="kpi-value" style="color: #38B2AC;">{format_pkr(current_portfolio_value)}</div>
                <div class="kpi-subtext">Estimated Selling Total</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Dealer Earnings</div>
                <div class="kpi-value" style="color: #ED8936;">{format_pkr(total_dealer_earnings)}</div>
                <div class="kpi-subtext">Commission Paid</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Portfolio Health</div>
                <div class="kpi-value" style="color: #48BB78;">Optimal</div>
                <div class="kpi-subtext">Solvency & Cash Ratio Stable</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ----------------------------------------------------------------------
        # SECOND ROW: LARGE PORTFOLIO SUMMARY CARD & RATIOS
        # ----------------------------------------------------------------------
        st.markdown("### 📊 Business Balance & Utilization Summary")
        
        cash_utilization = (money_invested / settings["initial_business_cash"] * 100) if settings["initial_business_cash"] > 0 else 0.0
        inv_utilization = (money_invested / net_worth * 100) if net_worth > 0 else 0.0
        portfolio_growth = ((net_worth - settings["initial_business_net_worth"]) / settings["initial_business_net_worth"] * 100) if settings["initial_business_net_worth"] > 0 else 0.0
        
        sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
        sum_col1.metric("Cash Utilization %", f"{cash_utilization:.1f}%")
        sum_col2.metric("Investment / Net Worth Ratio", f"{inv_utilization:.1f}%")
        sum_col3.metric("Net Worth Growth", f"{portfolio_growth:.2f}%", delta=f"{portfolio_growth:.2f}%")
        sum_col4.metric("Liquid Reserve Ratio", f"{100 - inv_utilization:.1f}%")
        
        st.progress(min(max(inv_utilization / 100.0, 0.0), 1.0))
        st.divider()

        # ----------------------------------------------------------------------
        # THIRD ROW: WHERE MY MONEY IS INVESTED (MAJOR VISUAL SECTION)
        # ----------------------------------------------------------------------
        st.markdown("## 💰 Where My Money Is Invested")
        st.caption("Detailed overview of active investments and business capital exposure.")
        
        if active_props_df.empty:
            st.info("No active property investments found. Add properties to populate capital allocation cards.")
        else:
            grid_cols = st.columns(2)
            for idx, prop in active_props_df.reset_index().iterrows():
                col_idx = idx % 2
                
                # Calculations for card
                total_cost = prop["total_property_cost"]
                ownership = prop["our_ownership_pct"]
                our_inv = prop["our_investment"]
                exp_selling = prop["expected_selling_price"]
                our_exp_selling = exp_selling * (ownership / 100.0)
                exp_profit = our_exp_selling - our_inv
                portfolio_share = (our_inv / money_invested * 100) if money_invested > 0 else 0.0
                roi_est = (exp_profit / our_inv * 100) if our_inv > 0 else 0.0
                
                status_badge = f'<span class="badge-available">Available</span>' if prop["status"] == "Available" else f'<span class="badge-construction">Under Construction</span>'
                
                with grid_cols[col_idx]:
                    st.markdown(f"""
                    <div class="prop-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3 style="margin: 0;">🏠 {prop['property_name']}</h3>
                            {status_badge}
                        </div>
                        <p style="color: #A0AEC0; margin-top: 5px; font-size: 0.9rem;">📍 {prop['location']} | Type: {prop['property_type']} ({prop['property_size']})</p>
                        <hr style="border-color: rgba(255,255,255,0.08); margin: 10px 0;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem;">
                            <div><strong>Total Property Cost:</strong><br>{format_pkr(total_cost)}</div>
                            <div><strong>Our Ownership:</strong><br><span style="color: #63B3ED; font-weight: 700;">{ownership}%</span></div>
                            <div><strong>Our Investment:</strong><br><span style="color: #ECC94B; font-weight: 700;">{format_pkr(our_inv)}</span></div>
                            <div><strong>Expected Selling Value:</strong><br>{format_pkr(our_exp_selling)}</div>
                            <div><strong>Expected Profit:</strong><br><span style="color: #48BB78;">{format_pkr(exp_profit)}</span></div>
                            <div><strong>Estimated ROI:</strong><br><span style="color: #48BB78;">{roi_est:.1f}%</span></div>
                        </div>
                        <div style="margin-top: 15px;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #A0AEC0; margin-bottom: 3px;">
                                <span>Portfolio Share</span>
                                <span>{portfolio_share:.1f}%</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.progress(min(max(portfolio_share / 100.0, 0.0), 1.0))

    # ==========================================================================
    # MODULE 2: PORTFOLIO ANALYTICS (VISUAL CHARTS & GRAPHICAL INTELLIGENCE)
    # ==========================================================================
    elif navigation == "📊 Portfolio Analytics":
        st.markdown("# 📊 Advanced Portfolio Analytics")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        if props_df.empty:
            st.warning("No property data available for analytics. Please add properties first.")
        else:
            c1, c2 = st.columns(2)
            
            with c1:
                # 1. Pie Chart: Cash vs Active Investment
                active_inv = props_df[props_df["status"].isin(["Available", "Under Construction"])]["our_investment"].sum()
                cash_val = settings["current_business_cash"]
                
                fig_cash_inv = px.pie(
                    values=[cash_val, active_inv],
                    names=["Liquid Cash", "Active Investments"],
                    title="Liquid Cash vs Active Capital Investment",
                    color_discrete_sequence=["#3182CE", "#ECC94B"],
                    hole=0.4
                )
                st.plotly_chart(fig_cash_inv, use_container_width=True)
                
            with c2:
                # 2. Pie Chart: Investment Distribution by Property
                active_df = props_df[props_df["status"].isin(["Available", "Under Construction"])]
                if not active_df.empty:
                    fig_dist = px.pie(
                        active_df,
                        values="our_investment",
                        names="property_name",
                        title="Active Capital Allocation by Property",
                        hole=0.4
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                else:
                    st.info("No active properties for allocation breakdown.")

            c3, c4 = st.columns(2)
            
            with c3:
                # 3. Property Status Breakdown
                status_counts = props_df["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                fig_status = px.bar(
                    status_counts,
                    x="Status",
                    y="Count",
                    color="Status",
                    title="Portfolio Breakdown by Property Status",
                    color_discrete_map={"Available": "#48BB78", "Under Construction": "#ECC94B", "Sold": "#F56565"}
                )
                st.plotly_chart(fig_status, use_container_width=True)
                
            with c4:
                # 4. Investment Amount by Property
                fig_bar_inv = px.bar(
                    props_df,
                    x="property_name",
                    y="our_investment",
                    color="status",
                    title="Capital Investment per Property (PKR)",
                    labels={"our_investment": "Our Investment (PKR)", "property_name": "Property Name"}
                )
                st.plotly_chart(fig_bar_inv, use_container_width=True)
                
            c5, c6 = st.columns(2)
            
            with c5:
                # 5. Profit by Property (For Sold Properties)
                sold_props = props_df[props_df["status"] == "Sold"]
                if not sold_props.empty:
                    fig_profit = px.bar(
                        sold_props,
                        x="property_name",
                        y="our_profit",
                        color="our_profit",
                        title="Realized Profit / Loss by Property (PKR)",
                        color_continuous_scale=["#F56565", "#48BB78"]
                    )
                    st.plotly_chart(fig_profit, use_container_width=True)
                else:
                    st.info("No sold properties yet to calculate realized profits.")
                    
            with c6:
                # 6. Ownership Percentage Distribution
                fig_ownership = px.pie(
                    props_df,
                    values="our_ownership_pct",
                    names="property_name",
                    title="Ownership Percentage Distribution",
                    hole=0.3
                )
                st.plotly_chart(fig_ownership, use_container_width=True)

    # ==========================================================================
    # MODULE 3: PROPERTIES DIRECTORY (SEARCH, EDIT, DELETE, SOLD WORKFLOW)
    # ==========================================================================
    elif navigation == "🏢 Properties Directory":
        st.markdown("# 🏢 Properties Directory & Asset Management")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        # Search & Filter Controls
        col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
        with col_s1:
            search_query = st.text_input("🔍 Search Properties (Name, Location, Broker)", "")
        with col_s2:
            status_filter = st.selectbox("Filter Status", ["All", "Available", "Under Construction", "Sold"])
        with col_s3:
            type_filter = st.selectbox("Filter Type", ["All"] + list(props_df["property_type"].unique()) if not props_df.empty else ["All"])
            
        # Apply Filters
        filtered_df = props_df.copy()
        if search_query:
            filtered_df = filtered_df[
                filtered_df["property_name"].str.contains(search_query, case=False, na=False) |
                filtered_df["location"].str.contains(search_query, case=False, na=False) |
                filtered_df["broker_name"].str.contains(search_query, case=False, na=False)
            ]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]
        if type_filter != "All":
            filtered_df = filtered_df[filtered_df["property_type"] == type_filter]
            
        st.write(f"Showing **{len(filtered_df)}** properties:")
        
        for idx, row in filtered_df.iterrows():
            with st.expander(f"🏠 {row['property_name']} — {row['location']} [{row['status']}]"):
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.write(f"**Property Type:** {row['property_type']}")
                    st.write(f"**Property Size:** {row['property_size']}")
                    st.write(f"**Purchase Date:** {row['purchase_date']}")
                    st.write(f"**Broker Name:** {row['broker_name']}")
                    
                with c2:
                    st.write(f"**Buying Price:** {format_pkr(row['buying_price'])}")
                    st.write(f"**Construction Cost:** {format_pkr(row['construction_cost'])}")
                    st.write(f"**Total Cost:** {format_pkr(row['total_property_cost'])}")
                    st.write(f"**Ownership %:** {row['our_ownership_pct']}%")
                    st.write(f"**Our Investment:** {format_pkr(row['our_investment'])}")
                    
                with c3:
                    if row["status"] == "Sold":
                        st.write(f"**Selling Price:** {format_pkr(row['selling_price'])}")
                        st.write(f"**Our Selling Share:** {format_pkr(row['our_selling_amount'])}")
                        st.write(f"**Our Profit:** {format_pkr(row['our_profit'])}")
                        st.write(f"**Dealer Commission:** {format_pkr(row['dealer_commission'])}")
                        st.write(f"**Jaffar Profit Share:** {format_pkr(row['jaffar_profit'])}")
                        st.write(f"**Tehseen Profit Share:** {format_pkr(row['tehseen_profit'])}")
                    else:
                        st.write(f"**Expected Selling Price:** {format_pkr(row['expected_selling_price'])}")
                        st.write(f"**Expected Selling Date:** {row['expected_selling_date']}")
                        
                st.write(f"**Notes:** {row['notes'] or 'N/A'}")
                
                # Role-Based Action Controls
                if st.session_state["role"] == "ADMIN":
                    st.divider()
                    act_col1, act_col2, act_col3 = st.columns(3)
                    
                    # Mark as Sold Workflow
                    if row["status"] != "Sold":
                        with act_col1:
                            with st.popover("💰 Mark as Sold"):
                                st.markdown("### Process Property Sale")
                                actual_selling_price = st.number_input(
                                    f"Actual Selling Price for {row['property_name']} (PKR)",
                                    min_value=0.0,
                                    value=float(row['expected_selling_price']),
                                    key=f"sell_price_{row['id']}"
                                )
                                
                                if st.button("Confirm Sale Execution", key=f"confirm_sale_{row['id']}"):
                                    # Perform Automatic Profit Split Computations
                                    ownership = row['our_ownership_pct']
                                    our_investment = row['our_investment']
                                    our_selling_amount = actual_selling_price * (ownership / 100.0)
                                    our_profit = our_selling_amount - our_investment
                                    
                                    # Commission & Profit Division Logic
                                    if our_profit > 0:
                                        comm_rate = settings["dealer_commission_pct"] / 100.0
                                        dealer_comm = our_profit * comm_rate
                                        remaining_profit = our_profit - dealer_comm
                                        jaffar_share = remaining_profit / 2.0
                                        tehseen_share = remaining_profit / 2.0
                                    else:
                                        # Profit <= 0 (Loss/Breakeven) -> Zero Dealer Comm & Zero Profit Splits
                                        dealer_comm = 0.0
                                        jaffar_share = 0.0
                                        tehseen_share = 0.0
                                        
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE properties
                                        SET status = 'Sold',
                                            selling_price = ?,
                                            our_selling_amount = ?,
                                            our_profit = ?,
                                            dealer_commission = ?,
                                            jaffar_profit = ?,
                                            tehseen_profit = ?,
                                            updated_at = CURRENT_TIMESTAMP
                                        WHERE id = ?
                                    """, (actual_selling_price, our_selling_amount, our_profit, dealer_comm, jaffar_share, tehseen_share, row['id']))
                                    conn.commit()
                                    conn.close()
                                    
                                    recalculate_business_metrics()
                                    st.success(f"Property '{row['property_name']}' successfully marked as SOLD!")
                                    st.rerun()

                    # Edit Property
                    with act_col2:
                        with st.popover("✏️ Edit Property"):
                            st.markdown("### Edit Property Details")
                            with st.form(f"edit_form_{row['id']}"):
                                e_name = st.text_input("Name", value=row["property_name"])
                                e_loc = st.text_input("Location", value=row["location"])
                                e_type = st.selectbox("Type", ["Residential Plot", "Commercial Plot", "House", "Plaza", "Apartment", "Agricultural Land"], index=0)
                                e_size = st.text_input("Size", value=row["property_size"])
                                e_buy = st.number_input("Buying Price (PKR)", value=float(row["buying_price"]))
                                e_const = st.number_input("Construction Cost (PKR)", value=float(row["construction_cost"]))
                                e_own = st.number_input("Our Ownership %", min_value=1.0, max_value=100.0, value=float(row["our_ownership_pct"]))
                                e_exp_price = st.number_input("Expected Selling Price (PKR)", value=float(row["expected_selling_price"]))
                                e_status = st.selectbox("Status", ["Available", "Under Construction", "Sold"], index=["Available", "Under Construction", "Sold"].index(row["status"]))
                                e_broker = st.text_input("Broker Name", value=row["broker_name"])
                                e_notes = st.text_area("Notes", value=row["notes"] or "")
                                
                                edit_submit = st.form_submit_button("Update Property")
                                if edit_submit:
                                    e_total_cost = e_buy + e_const
                                    e_our_inv = e_total_cost * (e_own / 100.0)
                                    
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE properties
                                        SET property_name=?, location=?, property_type=?, property_size=?,
                                            buying_price=?, construction_cost=?, total_property_cost=?,
                                            our_ownership_pct=?, our_investment=?, expected_selling_price=?,
                                            status=?, broker_name=?, notes=?, updated_at=CURRENT_TIMESTAMP
                                        WHERE id=?
                                    """, (e_name, e_loc, e_type, e_size, e_buy, e_const, e_total_cost, e_own, e_our_inv, e_exp_price, e_status, e_broker, e_notes, row['id']))
                                    conn.commit()
                                    conn.close()
                                    
                                    recalculate_business_metrics()
                                    st.success("Property updated successfully!")
                                    st.rerun()

                    # Delete Property
                    with act_col3:
                        if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                            conn = get_db_connection()
                            conn.execute("DELETE FROM properties WHERE id = ?", (row['id'],))
                            conn.commit()
                            conn.close()
                            recalculate_business_metrics()
                            st.warning("Property record deleted.")
                            st.rerun()

    # ==========================================================================
    # MODULE 4: ADD PROPERTY FORM (VALIDATIONS & CASH OUTFLOW LOGIC)
    # ==========================================================================
    elif navigation == "➕ Add Property":
        st.markdown("# ➕ Add New Property Asset")
        
        if st.session_state["role"] != "ADMIN":
            st.error("🔒 Access Denied: Only Admin users can register new properties.")
        else:
            with st.form("add_property_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    p_name = st.text_input("Property Name *", placeholder="e.g. Blue World City Sector A")
                    p_location = st.text_input("Location *", placeholder="e.g. Rawalpindi / Islamabad")
                    p_type = st.selectbox("Property Type", ["Residential Plot", "Commercial Plot", "House", "Plaza", "Apartment", "Agricultural Land"])
                    p_size = st.text_input("Property Size *", placeholder="e.g. 10 Marla / 1 Kanal")
                    p_purchase_date = st.date_input("Purchase Date", value=date.today())
                    p_buying_price = st.number_input("Buying Price (PKR) *", min_value=0.0, step=50000.0)
                    p_construction_cost = st.number_input("Construction Cost (PKR)", min_value=0.0, step=50000.0)
                    
                with col2:
                    p_ownership_pct = st.number_input("Our Ownership Percentage (%) *", min_value=1.0, max_value=100.0, value=100.0, step=1.0)
                    p_expected_selling_price = st.number_input("Expected Selling Price (PKR) *", min_value=0.0, step=50000.0)
                    p_expected_selling_date = st.date_input("Expected Selling Date", value=date.today())
                    p_broker_name = st.text_input("Broker / Dealer Name *", placeholder="e.g. Malik Estate Agency")
                    p_status = st.selectbox("Property Status", ["Available", "Under Construction", "Sold"])
                    p_notes = st.text_area("Notes / Remarks", placeholder="Enter legal or payment details...")
                    
                # Real-time Calculated Preview
                calculated_total_cost = p_buying_price + p_construction_cost
                calculated_our_investment = calculated_total_cost * (p_ownership_pct / 100.0)
                
                st.info(f"💡 **Financial Preview:** Total Property Cost: **{format_pkr(calculated_total_cost)}** | Our Investment (Cash Outflow): **{format_pkr(calculated_our_investment)}**")
                
                if calculated_expected_selling := p_expected_selling_price * (p_ownership_pct / 100.0):
                    if calculated_expected_selling < calculated_our_investment:
                        st.warning("⚠️ Warning: The Expected Selling Price is LOWER than Our Investment cost (Potential Loss).")

                submitted = st.form_submit_button("Submit & Register Property", use_container_width=True)
                
                if submitted:
                    if not p_name or not p_location or not p_broker_name:
                        st.error("Please fill in all required fields marked with *.")
                    else:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO properties (
                                property_name, location, property_type, property_size, purchase_date,
                                buying_price, construction_cost, total_property_cost, our_ownership_pct,
                                our_investment, expected_selling_price, expected_selling_date,
                                broker_name, status, notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            p_name, p_location, p_type, p_size, str(p_purchase_date),
                            p_buying_price, p_construction_cost, calculated_total_cost, p_ownership_pct,
                            calculated_our_investment, p_expected_selling_price, str(p_expected_selling_date),
                            p_broker_name, p_status, p_notes
                        ))
                        conn.commit()
                        conn.close()
                        
                        recalculate_business_metrics()
                        st.success(f"Property '{p_name}' successfully added into portfolio database!")
                        st.rerun()

    # ==========================================================================
    # MODULE 5: FINANCIAL REPORTS & EXPORTS (EXCEL, CSV, REPORTLAB PDF)
    # ==========================================================================
    elif navigation == "📑 Financial Reports":
        st.markdown("# 📑 Comprehensive Financial & Business Reports")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        report_type = st.selectbox(
            "Select Financial Report Category",
            [
                "Complete Property Directory Report",
                "Active Investment Capital Allocation",
                "Realized Profit & Loss Ledger",
                "Dealer Commission Statement",
                "Jaffar & Tehseen Equity & Wallet Report"
            ]
        )
        
        st.divider()
        
        if report_type == "Complete Property Directory Report":
            st.markdown("### Complete Property Directory")
            st.dataframe(props_df, use_container_width=True)
            export_data = props_df
            
        elif report_type == "Active Investment Capital Allocation":
            st.markdown("### Active Investment Capital Allocation")
            export_data = props_df[props_df["status"].isin(["Available", "Under Construction"])]
            st.dataframe(export_data, use_container_width=True)
            
        elif report_type == "Realized Profit & Loss Ledger":
            st.markdown("### Realized Profit & Loss Ledger")
            export_data = props_df[props_df["status"] == "Sold"]
            st.dataframe(export_data, use_container_width=True)
            
        elif report_type == "Dealer Commission Statement":
            st.markdown("### Dealer Commission Statement")
            export_data = props_df[props_df["status"] == "Sold"][["property_name", "broker_name", "selling_price", "our_profit", "dealer_commission"]]
            st.dataframe(export_data, use_container_width=True)
            
        elif report_type == "Jaffar & Tehseen Equity & Wallet Report":
            st.markdown("### Partner Profit Distribution Breakdown")
            export_data = props_df[props_df["status"] == "Sold"][["property_name", "selling_price", "our_profit", "jaffar_profit", "tehseen_profit"]]
            st.dataframe(export_data, use_container_width=True)

        st.divider()
        st.markdown("### 📥 Export Report Options")
        
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        
        # 1. CSV Export
        with exp_col1:
            csv_buffer = export_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Download CSV Report",
                data=csv_buffer,
                file_name=f"{report_type.lower().replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        # 2. Excel Export
        with exp_col2:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                export_data.to_excel(writer, sheet_name="Financial_Report", index=False)
            excel_data = excel_buffer.getvalue()
            
            st.download_button(
                "📥 Download Excel (.xlsx)",
                data=excel_data,
                file_name=f"{report_type.lower().replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        # 3. ReportLab PDF Generation
        with exp_col3:
            def generate_pdf_report(dataframe, title):
                pdf_buffer = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
                elements = []
                
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'TitleStyle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    textColor=colors.HexColor("#1A365D"),
                    spaceAfter=12
                )
                
                elements.append(Paragraph(f"{settings['business_name']} — {title}", title_style))
                elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
                elements.append(Spacer(1, 15))
                
                # Format Table Data
                df_sample = dataframe.copy().head(25) # Limit rows for clean PDF render
                table_data = [df_sample.columns.tolist()] + df_sample.astype(str).values.tolist()
                
                pdf_table = Table(table_data)
                pdf_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,0), 6),
                    ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#F7FAFC")),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                ]))
                
                elements.append(pdf_table)
                doc.build(elements)
                return pdf_buffer.getvalue()
                
            pdf_bytes = generate_pdf_report(export_data, report_type)
            st.download_button(
                "📥 Download PDF Document",
                data=pdf_bytes,
                file_name=f"{report_type.lower().replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

    # ==========================================================================
    # MODULE 6: BUSINESS SETTINGS (CONFIGURATION & THEME CONTROLS)
    # ==========================================================================
    elif navigation == "⚙️ Business Settings":
        st.markdown("# ⚙️ Business System Configuration")
        
        if st.session_state["role"] != "ADMIN":
            st.error("🔒 Access Denied: Only Admin users can alter business settings.")
        else:
            with st.form("edit_settings_form"):
                st.markdown("### Update Capital Baselines & Parameters")
                col1, col2 = st.columns(2)
                
                with col1:
                    u_b_name = st.text_input("Business Name", value=settings["business_name"])
                    u_b_cash = st.number_input("Initial Business Cash Baseline (PKR)", value=float(settings["initial_business_cash"]))
                    u_b_nw = st.number_input("Initial Business Net Worth Baseline (PKR)", value=float(settings["initial_business_net_worth"]))
                    
                with col2:
                    u_j_nw = st.number_input("Jaffar Initial Net Worth Baseline (PKR)", value=float(settings["jaffar_initial_net_worth"]))
                    u_t_nw = st.number_input("Tehseen Initial Net Worth Baseline (PKR)", value=float(settings["tehseen_initial_net_worth"]))
                    u_d_comm = st.number_input("Default Dealer Commission Rate (%)", value=float(settings["dealer_commission_pct"]))
                    u_theme = st.selectbox("UI Visual Theme Mode", ["Dark", "Light"], index=0 if settings["theme_mode"] == "Dark" else 1)
                    
                save_settings = st.form_submit_button("Save & Update Settings", use_container_width=True)
                
                if save_settings:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE business_settings
                        SET business_name=?, initial_business_cash=?, initial_business_net_worth=?,
                            jaffar_initial_net_worth=?, tehseen_initial_net_worth=?,
                            dealer_commission_pct=?, theme_mode=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (u_b_name, u_b_cash, u_b_nw, u_j_nw, u_t_nw, u_d_comm, u_theme, settings["id"]))
                    conn.commit()
                    conn.close()
                    
                    recalculate_business_metrics()
                    st.success("Business settings updated successfully!")
                    st.rerun()

    # ==========================================================================
    # MODULE 7: USER MANAGEMENT (ADMIN CONTROL PANEL)
    # ==========================================================================
    elif navigation == "👥 User Management":
        st.markdown("# 👥 User Management & Access Control")
        
        if st.session_state["role"] != "ADMIN":
            st.error("🔒 Access Denied: Administrator clearance required.")
        else:
            conn = get_db_connection()
            users_df = pd.read_sql_query("SELECT id, username, role, created_at FROM users", conn)
            conn.close()
            
            st.markdown("### Existing System Accounts")
            st.dataframe(users_df, use_container_width=True)
            
            st.divider()
            st.markdown("### ➕ Register New System User")
            
            with st.form("new_user_form"):
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    new_username = st.text_input("Username")
                with col_u2:
                    new_password = st.text_input("Password", type="password")
                with col_u3:
                    new_role = st.selectbox("Role Permission", ["VIEWER", "ADMIN"])
                    
                create_user = st.form_submit_button("Create User Account")
                
                if create_user:
                    if new_username and new_password:
                        try:
                            conn = get_db_connection()
                            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (new_username, new_password, new_role))
                            conn.commit()
                            conn.close()
                            st.success(f"User '{new_username}' created successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already exists. Please choose another.")
                    else:
                        st.error("Please provide both username and password.")
