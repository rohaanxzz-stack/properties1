# ==============================================================================
# PROPERTY INVESTMENT & BUSINESS PORTFOLIO MANAGEMENT DASHBOARD
# Single-File Production Application (app.py)
# ==============================================================================

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import io

# ReportLab Imports for Production PDF Export
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

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
    """Initialize database schema, tables, and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Business Settings Table (No Initial Profit field)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            business_logo TEXT,
            initial_business_cash REAL NOT NULL,
            current_business_cash REAL NOT NULL,
            initial_business_net_worth REAL NOT NULL,
            jaffar_initial_net_worth REAL NOT NULL,
            jaffar_current_net_worth REAL NOT NULL,
            tehseen_initial_net_worth REAL NOT NULL,
            tehseen_current_net_worth REAL NOT NULL,
            dealer_commission_pct REAL NOT NULL DEFAULT 25.0,
            theme_mode TEXT DEFAULT 'Dark',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            actual_selling_price REAL DEFAULT 0.0,
            our_selling_amount REAL DEFAULT 0.0,
            our_profit REAL DEFAULT 0.0,
            dealer_commission REAL DEFAULT 0.0,
            jaffar_profit REAL DEFAULT 0.0,
            tehseen_profit REAL DEFAULT 0.0,
            expected_selling_date TEXT NOT NULL,
            sold_date TEXT,
            dealer_name TEXT NOT NULL CHECK(dealer_name IN ('Samiullah', 'Sheikh Abid')),
            status TEXT NOT NULL CHECK(status IN ('Available', 'Under Construction', 'Sold')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 3. FINANCIAL ENGINE & FORMATTING SERVICES
# ==============================================================================

def format_pkr(amount):
    """Formats numeric values into Pakistani Rupee (PKR) standard format."""
    if amount is None:
        amount = 0.0
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    
    s = f"{amount:,.0f}"
    parts = s.split(".")
    integer_part = parts[0].replace(",", "")
    
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
        
    return f"{sign}PKR {formatted_int}"

def get_business_settings():
    """Retrieves current business settings from SQLite."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM business_settings ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def recalculate_business_metrics():
    """
    Dynamic financial recalculation engine.
    Applies Realized Profit rules strictly for Sold properties.
    """
    settings = get_business_settings()
    if not settings:
        return
    
    conn = get_db_connection()
    properties = conn.execute("SELECT * FROM properties").fetchall()
    
    initial_cash = settings["initial_business_cash"]
    jaffar_initial = settings["jaffar_initial_net_worth"]
    tehseen_initial = settings["tehseen_initial_net_worth"]
    
    total_invested_active = 0.0
    total_selling_inflow = 0.0
    jaffar_accumulated_profit = 0.0
    tehseen_accumulated_profit = 0.0
    
    cursor = conn.cursor()
    
    for p in properties:
        p_dict = dict(p)
        status = p_dict["status"]
        our_inv = p_dict["our_investment"]
        
        if status in ["Available", "Under Construction"]:
            total_invested_active += our_inv
            # Reset realized profits to 0 for unsold properties
            cursor.execute("""
                UPDATE properties
                SET actual_selling_price = 0.0,
                    our_selling_amount = 0.0,
                    our_profit = 0.0,
                    dealer_commission = 0.0,
                    jaffar_profit = 0.0,
                    tehseen_profit = 0.0
                WHERE id = ?
            """, (p_dict["id"],))
            
        elif status == "Sold":
            act_price = p_dict["actual_selling_price"]
            ownership = p_dict["our_ownership_pct"]
            our_selling_amt = act_price * (ownership / 100.0)
            our_profit = our_selling_amt - our_inv
            
            if our_profit > 0:
                comm_rate = (settings["dealer_commission_pct"] or 25.0) / 100.0
                dealer_comm = our_profit * comm_rate
                remaining_profit = our_profit - dealer_comm
                jaffar_share = remaining_profit / 2.0
                tehseen_share = remaining_profit / 2.0
            else:
                dealer_comm = 0.0
                jaffar_share = 0.0
                tehseen_share = 0.0
                
            cursor.execute("""
                UPDATE properties
                SET our_selling_amount = ?,
                    our_profit = ?,
                    dealer_commission = ?,
                    jaffar_profit = ?,
                    tehseen_profit = ?
                WHERE id = ?
            """, (our_selling_amt, our_profit, dealer_comm, jaffar_share, tehseen_share, p_dict["id"]))
            
            total_selling_inflow += our_selling_amt
            jaffar_accumulated_profit += jaffar_share
            tehseen_accumulated_profit += tehseen_share
            
    # Business Cash = Initial Cash - Active Investments + Realized Selling Inflows - Partner Disbursements
    current_cash = initial_cash - total_invested_active + total_selling_inflow - (jaffar_accumulated_profit + tehseen_accumulated_profit)
    jaffar_current_nw = jaffar_initial + jaffar_accumulated_profit
    tehseen_current_nw = tehseen_initial + tehseen_accumulated_profit
    
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
# 4. CUSTOM INJECTED CSS STYLES
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
            padding: 16px;
            margin-bottom: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(0, 0, 0, 0.1);
        }}
        .kpi-title {{
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {sub_text};
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 1.35rem;
            font-weight: 700;
            color: {text_color};
            margin-bottom: 2px;
        }}
        .kpi-subtext {{
            font-size: 0.75rem;
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
        
        /* Streamlit Customizations */
        .stProgress > div > div > div > div {{
            background-image: linear-gradient(to right, #3182CE , #63B3ED);
        }}
        .stButton>button {{
            border-radius: 8px;
            font-weight: 600;
        }}
    </style>
    """, unsafe_allow_html=True)

# Fetch settings or initiate setup
settings = get_business_settings()
if settings:
    inject_custom_css(settings.get("theme_mode", "Dark"))

# ==============================================================================
# 5. INITIAL SETUP WIZARD (FIRST TIME RUN ONLY)
# ==============================================================================

if not settings:
    st.markdown("# ⚙️ Initial Business System Setup")
    st.info("Welcome to the Property Investment & Business Portfolio Management Dashboard. Please configure your initial business metrics.")
    
    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            b_name = st.text_input("Business Name *", value="Real Estate Capital Holdings")
            b_logo = st.text_input("Business Logo URL (Optional)", value="")
            b_cash = st.number_input("Initial Business Cash (PKR) *", min_value=0.0, value=50000000.0, step=500000.0)
            b_nw = st.number_input("Initial Business Net Worth (PKR) *", min_value=0.0, value=50000000.0, step=500000.0)
        with col2:
            j_nw = st.number_input("Jaffar Initial Net Worth (PKR) *", min_value=0.0, value=25000000.0, step=500000.0)
            t_nw = st.number_input("Tehseen Initial Net Worth (PKR) *", min_value=0.0, value=25000000.0, step=500000.0)
            d_comm = st.number_input("Default Dealer Commission (%) *", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            
        submitted = st.form_submit_button("Complete Setup & Launch Dashboard", use_container_width=True)
        if submitted:
            if not b_name:
                st.error("Please provide a valid Business Name.")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO business_settings 
                    (business_name, business_logo, initial_business_cash, current_business_cash, initial_business_net_worth,
                     jaffar_initial_net_worth, jaffar_current_net_worth, tehseen_initial_net_worth, tehseen_current_net_worth, dealer_commission_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (b_name, b_logo, b_cash, b_cash, b_nw, j_nw, j_nw, t_nw, t_nw, d_comm))
                conn.commit()
                conn.close()
                st.success("Setup complete!")
                st.rerun()

# ==============================================================================
# 6. MAIN APPLICATION NAVIGATION & ROUTING
# ==============================================================================

elif settings:
    recalculate_business_metrics() # Ensure financial integrity on render
    settings = get_business_settings() # Refresh settings
    
    # --------------------------------------------------------------------------
    # SIDEBAR CONTROL CENTER
    # --------------------------------------------------------------------------
    if settings.get("business_logo"):
        st.sidebar.image(settings["business_logo"], use_column_width=True)
    st.sidebar.markdown(f"## 🏢 {settings['business_name']}")
    st.sidebar.divider()
    
    navigation = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Dashboard",
            "🏢 Properties",
            "➕ Add Property",
            "📊 Portfolio",
            "👤 Dealer Accounts",
            "👥 Jaffar Account",
            "👥 Tehseen Account",
            "📑 Reports",
            "⚙ Business Settings"
        ]
    )

    # ==========================================================================
    # MODULE 1: DASHBOARD (EXECUTIVE OVERVIEW)
    # ==========================================================================
    if navigation == "🏠 Dashboard":
        st.markdown(f"# 🏠 Executive Dashboard — {settings['business_name']}")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        total_properties = len(props_df)
        available_props = len(props_df[props_df["status"] == "Available"])
        construction_props = len(props_df[props_df["status"] == "Under Construction"])
        sold_props = len(props_df[props_df["status"] == "Sold"])
        
        active_props_df = props_df[props_df["status"].isin(["Available", "Under Construction"])]
        money_invested = active_props_df["our_investment"].sum() if not active_props_df.empty else 0.0
        
        # Current Value of Active Investments based on Expected Selling Price share
        active_investments_val = (active_props_df["expected_selling_price"] * (active_props_df["our_ownership_pct"] / 100.0)).sum() if not active_props_df.empty else 0.0
        
        # Unrealized Gain/Loss = Current Value of Active Investments - Our Active Investment
        unrealized_gain_loss = active_investments_val - money_invested
            
        # Realized Calculations (STRICTLY SOLD PROPERTIES)
        sold_df = props_df[props_df["status"] == "Sold"]
        total_realized_profit = sold_df[sold_df["our_profit"] > 0]["our_profit"].sum() if not sold_df.empty else 0.0
        total_realized_loss = abs(sold_df[sold_df["our_profit"] < 0]["our_profit"].sum()) if not sold_df.empty else 0.0
        total_dealer_earnings = sold_df["dealer_commission"].sum() if not sold_df.empty else 0.0
        jaffar_profit_earned = sold_df["jaffar_profit"].sum() if not sold_df.empty else 0.0
        tehseen_profit_earned = sold_df["tehseen_profit"].sum() if not sold_df.empty else 0.0
        
        current_cash = settings["current_business_cash"]
        
        # Net Worth = Business Cash + Current Value of Active Investments + Realized Profit - Realized Loss
        business_net_worth = current_cash + active_investments_val + total_realized_profit - total_realized_loss
        roi_pct = (((total_realized_profit - total_realized_loss) / money_invested) * 100) if money_invested > 0 else 0.0
        
        # ----------------------------------------------------------------------
        # REQUIRED DASHBOARD PROFIT KPI CARDS
        # ----------------------------------------------------------------------
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        
        with k1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Realized Profit</div>
                <div class="kpi-value" style="color: #48BB78;">{format_pkr(total_realized_profit)}</div>
                <div class="kpi-subtext">From Sold Properties Only</div>
            </div>
            """, unsafe_allow_html=True)

        with k2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Unrealized Gain / Loss</div>
                <div class="kpi-value" style="color: {'#38B2AC' if unrealized_gain_loss >= 0 else '#F56565'};">{format_pkr(unrealized_gain_loss)}</div>
                <div class="kpi-subtext">Unsold Est. Market Delta</div>
            </div>
            """, unsafe_allow_html=True)

        with k3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Total Realized Loss</div>
                <div class="kpi-value" style="color: #F56565;">{format_pkr(total_realized_loss)}</div>
                <div class="kpi-subtext">Realized Drawdown</div>
            </div>
            """, unsafe_allow_html=True)

        with k4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Dealer Earnings</div>
                <div class="kpi-value" style="color: #ED8936;">{format_pkr(total_dealer_earnings)}</div>
                <div class="kpi-subtext">Commissions Paid</div>
            </div>
            """, unsafe_allow_html=True)

        with k5:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Jaffar Profit Earned</div>
                <div class="kpi-value" style="color: #319795;">{format_pkr(jaffar_profit_earned)}</div>
                <div class="kpi-subtext">Realized Share</div>
            </div>
            """, unsafe_allow_html=True)

        with k6:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Tehseen Profit Earned</div>
                <div class="kpi-value" style="color: #319795;">{format_pkr(tehseen_profit_earned)}</div>
                <div class="kpi-subtext">Realized Share</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # ----------------------------------------------------------------------
        # PORTFOLIO SUMMARY
        # ----------------------------------------------------------------------
        st.markdown("### 📊 Business Capital & Net Worth Overview")
        
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Business Cash", format_pkr(current_cash))
        sc2.metric("Active Investments Value", format_pkr(active_investments_val))
        sc3.metric("Realized Profit", format_pkr(total_realized_profit))
        sc4.metric("Business Net Worth", format_pkr(business_net_worth))
        
        inv_utilization = (money_invested / business_net_worth * 100) if business_net_worth > 0 else 0.0
        st.progress(min(max(inv_utilization / 100.0, 0.0), 1.0))
        st.divider()

        # ----------------------------------------------------------------------
        # WHERE MY MONEY IS INVESTED
        # ----------------------------------------------------------------------
        st.markdown("## 💰 Where My Money Is Invested")
        st.caption("Active unsold properties showing investment exposure and unrealized estimated gains.")
        
        if active_props_df.empty:
            st.info("No active property investments found. Add properties to populate cards.")
        else:
            grid_cols = st.columns(2)
            for idx, prop in active_props_df.reset_index().iterrows():
                col_idx = idx % 2
                
                total_cost = prop["total_property_cost"]
                ownership = prop["our_ownership_pct"]
                our_inv = prop["our_investment"]
                exp_selling = prop["expected_selling_price"]
                our_exp_selling = exp_selling * (ownership / 100.0)
                unrealized_item = our_exp_selling - our_inv
                portfolio_share = (our_inv / money_invested * 100) if money_invested > 0 else 0.0
                
                status_badge = f'<span class="badge-available">Available</span>' if prop["status"] == "Available" else f'<span class="badge-construction">Under Construction</span>'
                
                with grid_cols[col_idx]:
                    st.markdown(f"""
                    <div class="prop-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3 style="margin: 0;">🏠 {prop['property_name']}</h3>
                            {status_badge}
                        </div>
                        <p style="color: #A0AEC0; margin-top: 5px; font-size: 0.85rem;">📍 {prop['location']} | Purchase: {prop['purchase_date']}</p>
                        <hr style="border-color: rgba(255,255,255,0.08); margin: 10px 0;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.85rem;">
                            <div><strong>Total Property Cost:</strong><br>{format_pkr(total_cost)}</div>
                            <div><strong>Our Ownership Percentage:</strong><br><span style="color: #63B3ED; font-weight: 700;">{ownership}%</span></div>
                            <div><strong>Our Investment:</strong><br><span style="color: #ECC94B; font-weight: 700;">{format_pkr(our_inv)}</span></div>
                            <div><strong>Current Estimated Value:</strong><br>{format_pkr(our_exp_selling)}</div>
                            <div><strong>Expected Selling Price:</strong><br>{format_pkr(exp_selling)}</div>
                            <div><strong>Unrealized Gain/Loss:</strong><br><span style="color: {'#38B2AC' if unrealized_item >= 0 else '#F56565'}; font-weight: 700;">{format_pkr(unrealized_item)}</span></div>
                            <div><strong>Dealer:</strong><br><span style="color: #ED8936;">👤 {prop['dealer_name']}</span></div>
                            <div><strong>Profit Status:</strong><br><span style="color: #A0AEC0;">PKR 0 (Unsold)</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # ==========================================================================
    # MODULE 2: PROPERTIES MANAGEMENT
    # ==========================================================================
    elif navigation == "🏢 Properties":
        st.markdown("# 🏢 Property Directory & Asset Management")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        # Search & Filter Controls
        st.markdown("### 🔍 Search & Filters")
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        with f_col1:
            search_q = st.text_input("Search Name / Location", "")
        with f_col2:
            f_location = st.selectbox("Location", ["All"] + list(props_df["location"].unique()) if not props_df.empty else ["All"])
        with f_col3:
            f_status = st.selectbox("Status", ["All", "Available", "Under Construction", "Sold"])
        with f_col4:
            f_dealer = st.selectbox("Dealer", ["All", "Samiullah", "Sheikh Abid"])

        filtered_df = props_df.copy()
        if search_q:
            filtered_df = filtered_df[
                filtered_df["property_name"].str.contains(search_q, case=False, na=False) |
                filtered_df["location"].str.contains(search_q, case=False, na=False)
            ]
        if f_location != "All":
            filtered_df = filtered_df[filtered_df["location"] == f_location]
        if f_status != "All":
            filtered_df = filtered_df[filtered_df["status"] == f_status]
        if f_dealer != "All":
            filtered_df = filtered_df[filtered_df["dealer_name"] == f_dealer]

        st.divider()
        st.write(f"Showing **{len(filtered_df)}** properties:")

        for idx, row in filtered_df.iterrows():
            calc_our_exp_val = row["expected_selling_price"] * (row["our_ownership_pct"] / 100.0)
            calc_unrealized = calc_our_exp_val - row["our_investment"]

            with st.expander(f"🏠 {row['property_name']} — {row['location']} | Dealer: {row['dealer_name']} [{row['status']}]"):
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.write(f"**Property Type:** {row['property_type']}")
                    st.write(f"**Property Size:** {row['property_size']}")
                    st.write(f"**Purchase Date:** {row['purchase_date']}")
                    st.write(f"**Dealer Name:** {row['dealer_name']}")
                    
                with c2:
                    st.write(f"**Buying Price:** {format_pkr(row['buying_price'])}")
                    st.write(f"**Construction Cost:** {format_pkr(row['construction_cost'])}")
                    st.write(f"**Total Property Cost:** {format_pkr(row['total_property_cost'])}")
                    st.write(f"**Our Ownership %:** {row['our_ownership_pct']}%")
                    st.write(f"**Our Investment:** {format_pkr(row['our_investment'])}")
                    
                with c3:
                    if row["status"] == "Sold":
                        st.write(f"**Actual Selling Price:** {format_pkr(row['actual_selling_price'])}")
                        st.write(f"**Our Selling Share:** {format_pkr(row['our_selling_amount'])}")
                        st.write(f"**Realized Profit:** :{ 'green' if row['our_profit'] >= 0 else 'red' }[{format_pkr(row['our_profit'])}]")
                        st.write(f"**Dealer Commission:** {format_pkr(row['dealer_commission'])}")
                        st.write(f"**Jaffar Share:** {format_pkr(row['jaffar_profit'])}")
                        st.write(f"**Tehseen Share:** {format_pkr(row['tehseen_profit'])}")
                        st.write(f"**Sold Date:** {row['sold_date']}")
                    else:
                        st.write(f"**Expected Selling Price:** {format_pkr(row['expected_selling_price'])}")
                        st.write(f"**Current Estimated Value:** {format_pkr(calc_our_exp_val)}")
                        st.write(f"**Unrealized Gain/Loss:** {format_pkr(calc_unrealized)}")
                        st.write(f"**Expected Selling Date:** {row['expected_selling_date']}")
                        st.info("ℹ️ Unsold Property — Profit, Commission & Shares are PKR 0.")

                st.write(f"**Notes:** {row['notes'] or 'N/A'}")
                st.divider()

                act_col1, act_col2, act_col3 = st.columns(3)
                
                # Mark as Sold Workflow
                if row["status"] != "Sold":
                    with act_col1:
                        with st.popover("💰 Process Sale"):
                            st.markdown("### Process Property Sale")
                            act_price = st.number_input(
                                f"Actual Total Selling Price (PKR)",
                                min_value=0.0,
                                value=float(row['expected_selling_price']),
                                key=f"sell_p_{row['id']}"
                            )
                            s_date = st.date_input("Sold Date", value=date.today(), key=f"s_date_{row['id']}")
                            
                            if st.button("Confirm Sale Execution", key=f"conf_sale_{row['id']}"):
                                ownership = row['our_ownership_pct']
                                our_inv = row['our_investment']
                                our_selling_amt = act_price * (ownership / 100.0)
                                our_profit = our_selling_amt - our_inv
                                
                                # Exact Formula Implementation
                                if our_profit > 0:
                                    comm_rate = (settings["dealer_commission_pct"] or 25.0) / 100.0
                                    dealer_comm = our_profit * comm_rate
                                    remaining_profit = our_profit - dealer_comm
                                    jaffar_share = remaining_profit / 2.0
                                    tehseen_share = remaining_profit / 2.0
                                else:
                                    dealer_comm = 0.0
                                    jaffar_share = 0.0
                                    tehseen_share = 0.0
                                    
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE properties
                                    SET status = 'Sold',
                                        actual_selling_price = ?,
                                        our_selling_amount = ?,
                                        our_profit = ?,
                                        dealer_commission = ?,
                                        jaffar_profit = ?,
                                        tehseen_profit = ?,
                                        sold_date = ?,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                """, (act_price, our_selling_amt, our_profit, dealer_comm, jaffar_share, tehseen_share, str(s_date), row['id']))
                                conn.commit()
                                conn.close()
                                
                                recalculate_business_metrics()
                                st.success(f"Property '{row['property_name']}' marked as SOLD!")
                                st.rerun()

                # Edit Property
                with act_col2:
                    with st.popover("✏️ Edit Property"):
                        st.markdown("### Edit Property Details")
                        with st.form(f"edit_form_{row['id']}"):
                            e_name = st.text_input("Property Name *", value=row["property_name"])
                            e_loc = st.text_input("Location *", value=row["location"])
                            e_type = st.selectbox("Type", ["Residential Plot", "Commercial Plot", "House", "Plaza", "Apartment", "Agricultural Land"], index=0)
                            e_size = st.text_input("Size *", value=row["property_size"])
                            e_p_date = st.date_input("Purchase Date", value=datetime.strptime(row["purchase_date"], "%Y-%m-%d").date() if row["purchase_date"] else date.today())
                            e_buy = st.number_input("Buying Price (PKR)", value=float(row["buying_price"]))
                            e_const = st.number_input("Construction Cost (PKR)", value=float(row["construction_cost"]))
                            e_own = st.number_input("Our Ownership %", min_value=1.0, max_value=100.0, value=float(row["our_ownership_pct"]))
                            e_exp_p = st.number_input("Expected Selling Price (PKR)", value=float(row["expected_selling_price"]))
                            e_exp_d = st.date_input("Expected Selling Date", value=datetime.strptime(row["expected_selling_date"], "%Y-%m-%d").date() if row["expected_selling_date"] else date.today())
                            e_dealer = st.selectbox("Dealer", ["Samiullah", "Sheikh Abid"], index=0 if row["dealer_name"] == "Samiullah" else 1)
                            e_status = st.selectbox("Status", ["Available", "Under Construction", "Sold"], index=["Available", "Under Construction", "Sold"].index(row["status"]))
                            e_notes = st.text_area("Notes", value=row["notes"] or "")
                            
                            edit_submit = st.form_submit_button("Update Property")
                            if edit_submit:
                                e_total_cost = e_buy + e_const
                                e_our_inv = e_total_cost * (e_own / 100.0)
                                
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE properties
                                    SET property_name=?, location=?, property_type=?, property_size=?, purchase_date=?,
                                        buying_price=?, construction_cost=?, total_property_cost=?,
                                        our_ownership_pct=?, our_investment=?, expected_selling_price=?, expected_selling_date=?,
                                        dealer_name=?, status=?, notes=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE id=?
                                """, (e_name, e_loc, e_type, e_size, str(e_p_date), e_buy, e_const, e_total_cost, e_own, e_our_inv, e_exp_p, str(e_exp_d), e_dealer, e_status, e_notes, row['id']))
                                conn.commit()
                                conn.close()
                                
                                recalculate_business_metrics()
                                st.success("Property details updated!")
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
    # MODULE 3: ADD PROPERTY FORM
    # ==========================================================================
    elif navigation == "➕ Add Property":
        st.markdown("# ➕ Register New Property Asset")
        
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
                p_ownership_pct = st.selectbox("Our Ownership Percentage (%) *", [10.0, 20.0, 25.0, 40.0, 50.0, 60.0, 75.0, 100.0], index=7)
                p_expected_selling_price = st.number_input("Expected Selling Price (PKR) *", min_value=0.0, step=50000.0)
                p_expected_selling_date = st.date_input("Expected Selling Date", value=date.today())
                p_dealer_name = st.selectbox("Dealer *", ["Samiullah", "Sheikh Abid"])
                p_status = st.selectbox("Property Status", ["Available", "Under Construction", "Sold"])
                p_notes = st.text_area("Notes / Remarks", placeholder="Enter legal or payment details...")
                
            calculated_total_cost = p_buying_price + p_construction_cost
            calculated_our_investment = calculated_total_cost * (p_ownership_pct / 100.0)
            
            st.info(f"💡 **Financial Preview:** Total Property Cost: **{format_pkr(calculated_total_cost)}** | Our Investment (Cash Outflow): **{format_pkr(calculated_our_investment)}**")

            submitted = st.form_submit_button("Submit & Register Property", use_container_width=True)
            
            if submitted:
                if not p_name or not p_location or not p_size:
                    st.error("Please fill in all required fields marked with *.")
                else:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO properties (
                            property_name, location, property_type, property_size, purchase_date,
                            buying_price, construction_cost, total_property_cost, our_ownership_pct,
                            our_investment, expected_selling_price, expected_selling_date,
                            dealer_name, status, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        p_name, p_location, p_type, p_size, str(p_purchase_date),
                        p_buying_price, p_construction_cost, calculated_total_cost, p_ownership_pct,
                        calculated_our_investment, p_expected_selling_price, str(p_expected_selling_date),
                        p_dealer_name, p_status, p_notes
                    ))
                    conn.commit()
                    conn.close()
                    
                    recalculate_business_metrics()
                    st.success(f"Property '{p_name}' successfully added into portfolio database!")
                    st.rerun()

    # ==========================================================================
    # MODULE 4: PORTFOLIO ANALYTICS
    # ==========================================================================
    elif navigation == "📊 Portfolio":
        st.markdown("# 📊 Advanced Portfolio Analytics")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        if props_df.empty:
            st.warning("No property data available for analytics. Please add properties first.")
        else:
            c1, c2 = st.columns(2)
            
            with c1:
                active_inv = props_df[props_df["status"].isin(["Available", "Under Construction"])]["our_investment"].sum()
                cash_val = settings["current_business_cash"]
                
                fig_cash_inv = px.pie(
                    values=[cash_val, active_inv],
                    names=["Liquid Cash", "Active Investments"],
                    title="Cash vs Active Investment",
                    color_discrete_sequence=["#3182CE", "#ECC94B"],
                    hole=0.4
                )
                st.plotly_chart(fig_cash_inv, use_container_width=True)
                
            with c2:
                active_df = props_df[props_df["status"].isin(["Available", "Under Construction"])]
                if not active_df.empty:
                    fig_dist = px.pie(
                        active_df,
                        values="our_investment",
                        names="property_name",
                        title="Investment Distribution by Property",
                        hole=0.4
                    )
                    st.plotly_chart(fig_dist, use_container_width=True)
                else:
                    st.info("No active properties for allocation breakdown.")

            c3, c4 = st.columns(2)
            
            with c3:
                status_counts = props_df["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Count"]
                fig_status = px.pie(
                    status_counts,
                    values="Count",
                    names="Status",
                    title="Property Status Distribution",
                    color="Status",
                    color_discrete_map={"Available": "#48BB78", "Under Construction": "#ECC94B", "Sold": "#F56565"}
                )
                st.plotly_chart(fig_status, use_container_width=True)
                
            with c4:
                sold_props = props_df[props_df["status"] == "Sold"]
                if not sold_props.empty:
                    fig_profit = px.bar(
                        sold_props,
                        x="property_name",
                        y="our_profit",
                        color="our_profit",
                        title="Realized Profit / Loss by Property (Sold Only)",
                        color_continuous_scale=["#F56565", "#48BB78"]
                    )
                    st.plotly_chart(fig_profit, use_container_width=True)
                else:
                    st.info("No sold properties yet to display realized profit.")

    # ==========================================================================
    # MODULE 5: DEALER ACCOUNTS
    # ==========================================================================
    elif navigation == "👤 Dealer Accounts":
        st.markdown("# 👤 Dealer Commission Accounts")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        dealers = ["Samiullah", "Sheikh Abid"]
        
        for d in dealers:
            st.markdown(f"## 👤 {d}")
            d_df = props_df[props_df["dealer_name"] == d]
            sold_d_df = d_df[d_df["status"] == "Sold"]
            
            comm_earned = sold_d_df["dealer_commission"].sum() if not sold_d_df.empty else 0.0
            num_deals = len(sold_d_df)
            total_managed = len(d_df)
            
            dc1, dc2, dc3 = st.columns(3)
            dc1.metric("Commission Earned", format_pkr(comm_earned))
            dc2.metric("Number of Sold Deals", num_deals)
            dc3.metric("Total Properties Managed", total_managed)
            
            st.markdown(f"**Commission History — {d}**")
            if not sold_d_df.empty:
                st.dataframe(sold_d_df[["property_name", "actual_selling_price", "our_profit", "dealer_commission", "sold_date"]], use_container_width=True)
            else:
                st.info(f"No completed sales history for {d}.")
            st.divider()

    # ==========================================================================
    # MODULE 6: JAFFAR ACCOUNT
    # ==========================================================================
    elif navigation == "👥 Jaffar Account":
        st.markdown("# 👥 Jaffar Partner Account")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        sold_props = props_df[props_df["status"] == "Sold"]
        jaffar_profit = sold_props["jaffar_profit"].sum() if not sold_props.empty else 0.0
        participated_props = len(props_df)
        
        jc1, jc2, jc3 = st.columns(3)
        jc1.metric("Current Net Worth", format_pkr(settings["jaffar_current_net_worth"]))
        jc2.metric("Total Realized Profit Earned", format_pkr(jaffar_profit))
        jc3.metric("Properties Participated", participated_props)
        
        st.divider()
        st.markdown("### 📈 Profit Share History (Sold Properties)")
        if not sold_props.empty:
            st.dataframe(sold_props[["property_name", "actual_selling_price", "our_profit", "jaffar_profit", "sold_date"]], use_container_width=True)
        else:
            st.info("No realized profit history available.")

    # ==========================================================================
    # MODULE 7: TEHSEEN ACCOUNT
    # ==========================================================================
    elif navigation == "👥 Tehseen Account":
        st.markdown("# 👥 Tehseen Partner Account")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        sold_props = props_df[props_df["status"] == "Sold"]
        tehseen_profit = sold_props["tehseen_profit"].sum() if not sold_props.empty else 0.0
        participated_props = len(props_df)
        
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("Current Net Worth", format_pkr(settings["tehseen_current_net_worth"]))
        tc2.metric("Total Realized Profit Earned", format_pkr(tehseen_profit))
        tc3.metric("Properties Participated", participated_props)
        
        st.divider()
        st.markdown("### 📈 Profit Share History (Sold Properties)")
        if not sold_props.empty:
            st.dataframe(sold_props[["property_name", "actual_selling_price", "our_profit", "tehseen_profit", "sold_date"]], use_container_width=True)
        else:
            st.info("No realized profit history available.")

    # ==========================================================================
    # MODULE 8: REPORTS & EXPORTS
    # ==========================================================================
    elif navigation == "📑 Reports":
        st.markdown("# 📑 Comprehensive Business Reports")
        
        conn = get_db_connection()
        props_df = pd.read_sql_query("SELECT * FROM properties", conn)
        conn.close()
        
        report_choice = st.selectbox(
            "Select Report Type",
            [
                "Property Report",
                "Investment Report",
                "Profit Report (Sold Only)",
                "Loss Report (Sold Only)",
                "Dealer Report",
                "Jaffar Report",
                "Tehseen Report",
                "Portfolio Report"
            ]
        )
        
        st.divider()
        
        if report_choice == "Property Report":
            export_data = props_df
        elif report_choice == "Investment Report":
            export_data = props_df[props_df["status"].isin(["Available", "Under Construction"])]
        elif report_choice == "Profit Report (Sold Only)":
            export_data = props_df[(props_df["status"] == "Sold") & (props_df["our_profit"] > 0)]
        elif report_choice == "Loss Report (Sold Only)":
            export_data = props_df[(props_df["status"] == "Sold") & (props_df["our_profit"] < 0)]
        elif report_choice == "Dealer Report":
            export_data = props_df[props_df["status"] == "Sold"][["property_name", "dealer_name", "actual_selling_price", "our_profit", "dealer_commission", "sold_date"]]
        elif report_choice == "Jaffar Report":
            export_data = props_df[props_df["status"] == "Sold"][["property_name", "actual_selling_price", "our_profit", "jaffar_profit", "sold_date"]]
        elif report_choice == "Tehseen Report":
            export_data = props_df[props_df["status"] == "Sold"][["property_name", "actual_selling_price", "our_profit", "tehseen_profit", "sold_date"]]
        elif report_choice == "Portfolio Report":
            export_data = props_df[["property_name", "location", "status", "our_ownership_pct", "our_investment", "expected_selling_price"]]
            
        st.dataframe(export_data, use_container_width=True)
        st.divider()
        
        # Export Actions
        st.markdown("### 📥 Download Report")
        ex1, ex2, ex3 = st.columns(3)
        
        with ex1:
            csv_data = export_data.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv_data, f"{report_choice.lower().replace(' ', '_')}.csv", "text/csv", use_container_width=True)
            
        with ex2:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                export_data.to_excel(writer, sheet_name="Report", index=False)
            st.download_button("Download Excel", excel_buffer.getvalue(), f"{report_choice.lower().replace(' ', '_')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
        with ex3:
            def build_pdf(df, title):
                pdf_buf = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
                elements = []
                styles = getSampleStyleSheet()
                
                elements.append(Paragraph(f"{settings['business_name']} - {title}", styles['Heading1']))
                elements.append(Spacer(1, 12))
                
                sample_df = df.head(20).astype(str)
                table_data = [sample_df.columns.tolist()] + sample_df.values.tolist()
                
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]))
                elements.append(t)
                doc.build(elements)
                return pdf_buf.getvalue()
                
            pdf_data = build_pdf(export_data, report_choice)
            st.download_button("Download PDF", pdf_data, f"{report_choice.lower().replace(' ', '_')}.pdf", "application/pdf", use_container_width=True)

    # ==========================================================================
    # MODULE 9: BUSINESS SETTINGS
    # ==========================================================================
    elif navigation == "⚙ Business Settings":
        st.markdown("# ⚙ Business System Configuration")
        
        with st.form("edit_settings_form"):
            st.markdown("### Update Capital Baselines & Parameters")
            col1, col2 = st.columns(2)
            
            with col1:
                u_b_name = st.text_input("Business Name *", value=settings["business_name"])
                u_b_logo = st.text_input("Business Logo URL", value=settings.get("business_logo") or "")
                u_b_cash = st.number_input("Initial Business Cash Baseline (PKR) *", value=float(settings["initial_business_cash"]))
                u_b_nw = st.number_input("Initial Business Net Worth Baseline (PKR) *", value=float(settings["initial_business_net_worth"]))
                
            with col2:
                u_j_nw = st.number_input("Jaffar Initial Net Worth Baseline (PKR) *", value=float(settings["jaffar_initial_net_worth"]))
                u_t_nw = st.number_input("Tehseen Initial Net Worth Baseline (PKR) *", value=float(settings["tehseen_initial_net_worth"]))
                u_d_comm = st.number_input("Default Dealer Commission Rate (%) *", value=float(settings["dealer_commission_pct"]))
                u_theme = st.selectbox("UI Visual Theme Mode", ["Dark", "Light"], index=0 if settings["theme_mode"] == "Dark" else 1)
                
            save_settings = st.form_submit_button("Save & Update Settings", use_container_width=True)
            
            if save_settings:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE business_settings
                    SET business_name=?, business_logo=?, initial_business_cash=?, initial_business_net_worth=?,
                        jaffar_initial_net_worth=?, tehseen_initial_net_worth=?,
                        dealer_commission_pct=?, theme_mode=?, updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                """, (u_b_name, u_b_logo, u_b_cash, u_b_nw, u_j_nw, u_t_nw, u_d_comm, u_theme, settings["id"]))
                conn.commit()
                conn.close()
                
                recalculate_business_metrics()
                st.success("Business settings updated successfully!")
                st.rerun()
