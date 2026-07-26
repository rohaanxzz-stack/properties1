# app.py
import sqlite3
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Real Estate Portfolio Management System",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern SaaS UI
st.markdown("""
<style>
    /* Global Styles */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* Card Styles */
    .kpi-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #e2e8f0;
        margin-bottom: 12px;
    }
    .kpi-title {
        color: #64748b;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        color: #0f172a;
        font-size: 24px;
        font-weight: 700;
        margin-top: 5px;
    }
    .kpi-subtext {
        font-size: 12px;
        margin-top: 5px;
        font-weight: 500;
    }

    /* Active Property Card */
    .prop-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #cbd5e1;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    .prop-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .prop-title {
        font-size: 18px;
        font-weight: 700;
        color: #1e293b;
    }
    
    /* Status Badges */
    .badge-available {
        background-color: #dbeafe;
        color: #1e40af;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-construction {
        background-color: #ffedd5;
        color: #c2410c;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-sold {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }

    /* Utility Text Colors */
    .text-green { color: #16a34a; }
    .text-red { color: #dc2626; }
    .text-blue { color: #2563eb; }
    .text-purple { color: #9333ea; }
    .text-orange { color: #ea580c; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# DATABASE SETUP & MIGRATION
# ---------------------------------------------------------
DB_FILE = "portfolio.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Business Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY DEFAULT 1,
        business_name TEXT NOT NULL,
        business_logo TEXT,
        initial_cash REAL NOT NULL,
        initial_net_worth REAL NOT NULL,
        jaffar_net_worth REAL NOT NULL,
        tehseen_net_worth REAL NOT NULL,
        dealer_commission_pct REAL DEFAULT 25.0
    )
    """)
    
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
        current_value REAL NOT NULL,
        expected_selling_price REAL NOT NULL,
        actual_selling_price REAL DEFAULT 0,
        sold_date TEXT,
        status TEXT NOT NULL,
        dealer TEXT NOT NULL,
        notes TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# HELPER FUNCTIONS & FORMATTING
# ---------------------------------------------------------
def format_pkr(amount):
    """Formats numbers to Pakistani Rupee with Lakh/Crore notation."""
    if amount is None or pd.isna(amount):
        return "PKR 0"
    
    is_negative = amount < 0
    amount = abs(amount)
    
    if amount >= 10000000: # 1 Crore = 10,000,000
        crores = amount / 10000000
        val_str = f"{crores:,.2f} Crore"
    elif amount >= 100000: # 1 Lakh = 100,000
        lakhs = amount / 100000
        val_str = f"{lakhs:,.2f} Lakh"
    else:
        val_str = f"{amount:,.0f}"
        
    return f"-PKR {val_str}" if is_negative else f"PKR {val_str}"

def calculate_property_financials(buying_price, construction_cost, ownership_pct, 
                                 actual_selling_price, status, dealer_pct=25.0):
    total_cost = buying_price + construction_cost
    our_investment = total_cost * (ownership_pct / 100.0)
    
    if status == "Sold" and actual_selling_price > 0:
        our_selling_amount = actual_selling_price * (ownership_pct / 100.0)
        profit = our_selling_amount - our_investment
        
        if profit > 0:
            dealer_commission = profit * (dealer_pct / 100.0)
            remaining_profit = profit - dealer_commission
            jaffar_profit = remaining_profit / 2.0
            tehseen_profit = remaining_profit / 2.0
        else:
            dealer_commission = 0.0
            jaffar_profit = 0.0
            tehseen_profit = 0.0
        roi = (profit / our_investment * 100.0) if our_investment > 0 else 0.0
    else:
        our_selling_amount = 0.0
        profit = 0.0
        dealer_commission = 0.0
        jaffar_profit = 0.0
        tehseen_profit = 0.0
        roi = 0.0
        
    return {
        "total_cost": total_cost,
        "our_investment": our_investment,
        "our_selling_amount": our_selling_amount,
        "profit": profit,
        "dealer_commission": dealer_commission,
        "jaffar_profit": jaffar_profit,
        "tehseen_profit": tehseen_profit,
        "roi": roi
    }

def get_settings():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM settings WHERE id=1", conn)
    conn.close()
    if len(df) == 0:
        return None
    return df.iloc[0].to_dict()

def save_settings(name, logo, cash, nw, j_nw, t_nw, comm):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO settings (id, business_name, business_logo, initial_cash, initial_net_worth, jaffar_net_worth, tehseen_net_worth, dealer_commission_pct)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?)
    """, (name, logo, cash, nw, j_nw, t_nw, comm))
    conn.commit()
    conn.close()

def get_properties_df():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM properties", conn)
    conn.close()
    return df

# ---------------------------------------------------------
# INITIAL SETTINGS MODAL / SETUP
# ---------------------------------------------------------
settings = get_settings()

if settings is None:
    st.markdown("<h2 style='text-align: center;'>Welcome! Let's Configure Your Real Estate Business</h2>", unsafe_allow_html=True)
    with st.form("initial_setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            b_name = st.text_input("Business Name*", value="Apex Real Estate Holdings")
            b_logo = st.text_input("Business Logo (URL/Emoji)", value="🏢")
            b_comm = st.number_input("Dealer Commission %", min_value=0.0, max_value=100.0, value=25.0)
            b_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, value=100000000.0, step=1000000.0)
        with col2:
            b_nw = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, value=100000000.0, step=1000000.0)
            j_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, value=50000000.0, step=1000000.0)
            t_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, value=50000000.0, step=1000000.0)
            
        submit = st.form_submit_button("Save & Launch System", use_container_width=True)
        if submit:
            if not b_name:
                st.error("Business Name is required!")
            else:
                save_settings(b_name, b_logo, b_cash, b_nw, j_nw, t_nw, b_comm)
                st.success("Settings saved successfully!")
                st.rerun()
    st.stop()

# ---------------------------------------------------------
# CORE METRICS & FINANCIAL ENGINE
# ---------------------------------------------------------
df_props = get_properties_df()

# Calculate Financial Balances
dealer_pct = settings['dealer_commission_pct']
total_invested_active = 0.0
portfolio_value_active = 0.0
total_realized_profit = 0.0
total_realized_loss = 0.0
total_dealer_commission = 0.0
samiullah_commission = 0.0
sheikh_abid_commission = 0.0
jaffar_profit_total = 0.0
tehseen_profit_total = 0.0

if not df_props.empty:
    for _, row in df_props.iterrows():
        fin = calculate_property_financials(
            row['buying_price'], row['construction_cost'], 
            row['ownership_pct'], row['actual_selling_price'], 
            row['status'], dealer_pct
        )
        if row['status'] in ['Available', 'Under Construction']:
            total_invested_active += fin['our_investment']
            # Share of current estimated value
            portfolio_value_active += row['current_value'] * (row['ownership_pct'] / 100.0)
        elif row['status'] == 'Sold':
            if fin['profit'] > 0:
                total_realized_profit += fin['profit']
            else:
                total_realized_loss += abs(fin['profit'])
                
            total_dealer_commission += fin['dealer_commission']
            if row['dealer'] == 'Samiullah':
                samiullah_commission += fin['dealer_commission']
            elif row['dealer'] == 'Sheikh Abid':
                sheikh_abid_commission += fin['dealer_commission']
                
            jaffar_profit_total += fin['jaffar_profit']
            tehseen_profit_total += fin['tehseen_profit']

# Business Cash Dynamic Calculation
# Current Cash = Initial Cash - Invested in Active Props + Selling Cash Receipts
total_sold_our_share_received = 0.0
if not df_props.empty:
    sold_df = df_props[df_props['status'] == 'Sold']
    for _, row in sold_df.iterrows():
        total_sold_our_share_received += row['actual_selling_price'] * (row['ownership_pct'] / 100.0)

current_business_cash = settings['initial_cash'] - total_invested_active + total_sold_our_share_received
net_realized_gain_loss = total_realized_profit - total_realized_loss
current_business_net_worth = current_business_cash + portfolio_value_active + net_realized_gain_loss

jaffar_current_nw = settings['jaffar_net_worth'] + jaffar_profit_total
tehseen_current_nw = settings['tehseen_net_worth'] + tehseen_profit_total

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
with st.sidebar:
    st.title(f"{settings['business_logo']} {settings['business_name']}")
    st.caption("Real Estate Business Portfolio Engine")
    st.divider()
    
    menu = st.radio(
        "Navigation",
        ["🏠 Dashboard", "➕ Add Property", "🏢 Manage Properties", "📊 Portfolio", "📑 Reports", "⚙ Business Settings"],
        index=0
    )
    
    st.divider()
    st.markdown(f"**Current Cash:** {format_pkr(current_business_cash)}")
    st.markdown(f"**Net Worth:** {format_pkr(current_business_net_worth)}")

# ---------------------------------------------------------
# PAGE 1: DASHBOARD
# ---------------------------------------------------------
if menu == "🏠 Dashboard":
    st.title("Financial SaaS Dashboard")
    st.caption("Live Business Overview & Asset Metrics")
    
    # Top KPI Metrics Row 1
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.markdown(f"""<div class="kpi-card"><div class="kpi-title">Business Net Worth</div><div class="kpi-value text-purple">{format_pkr(current_business_net_worth)}</div></div>""", unsafe_allow_html=True)
    col2.markdown(f"""<div class="kpi-card"><div class="kpi-title">Business Cash</div><div class="kpi-value text-blue">{format_pkr(current_business_cash)}</div></div>""", unsafe_allow_html=True)
    col3.markdown(f"""<div class="kpi-card"><div class="kpi-title">Money Invested</div><div class="kpi-value text-blue">{format_pkr(total_invested_active)}</div></div>""", unsafe_allow_html=True)
    col4.markdown(f"""<div class="kpi-card"><div class="kpi-title">Portfolio Value</div><div class="kpi-value text-blue">{format_pkr(portfolio_value_active)}</div></div>""", unsafe_allow_html=True)
    col5.markdown(f"""<div class="kpi-card"><div class="kpi-title">Realized Profit</div><div class="kpi-value text-green">{format_pkr(total_realized_profit)}</div></div>""", unsafe_allow_html=True)

    # Top KPI Metrics Row 2
    col6, col7, col8, col9, col10 = st.columns(5)
    col6.markdown(f"""<div class="kpi-card"><div class="kpi-title">Realized Loss</div><div class="kpi-value text-red">{format_pkr(total_realized_loss)}</div></div>""", unsafe_allow_html=True)
    col7.markdown(f"""<div class="kpi-card"><div class="kpi-title">Dealer Earnings</div><div class="kpi-value text-orange">{format_pkr(total_dealer_commission)}</div></div>""", unsafe_allow_html=True)
    col8.markdown(f"""<div class="kpi-card"><div class="kpi-title">Jaffar Net Worth</div><div class="kpi-value text-purple">{format_pkr(jaffar_current_nw)}</div></div>""", unsafe_allow_html=True)
    col9.markdown(f"""<div class="kpi-card"><div class="kpi-title">Tehseen Net Worth</div><div class="kpi-value text-purple">{format_pkr(tehseen_current_nw)}</div></div>""", unsafe_allow_html=True)
    overall_roi = ((total_realized_profit - total_realized_loss) / total_invested_active * 100) if total_invested_active > 0 else 0.0
    col10.markdown(f"""<div class="kpi-card"><div class="kpi-title">Realized ROI %</div><div class="kpi-value">{overall_roi:.2f}%</div></div>""", unsafe_allow_html=True)

    # Counts Row
    cnt_total = len(df_props)
    cnt_avail = len(df_props[df_props['status'] == 'Available']) if cnt_total > 0 else 0
    cnt_const = len(df_props[df_props['status'] == 'Under Construction']) if cnt_total > 0 else 0
    cnt_sold = len(df_props[df_props['status'] == 'Sold']) if cnt_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Properties", cnt_total)
    c2.metric("Available", cnt_avail)
    c3.metric("Under Construction", cnt_const)
    c4.metric("Sold Properties", cnt_sold)

    st.divider()

    # Portfolio Summary Section
    st.subheader("📊 Portfolio Summary")
    cash_util = (total_invested_active / settings['initial_cash'] * 100) if settings['initial_cash'] > 0 else 0
    inv_util = (total_invested_active / current_business_net_worth * 100) if current_business_net_worth > 0 else 0
    port_growth = ((current_business_net_worth - settings['initial_net_worth']) / settings['initial_net_worth'] * 100) if settings['initial_net_worth'] > 0 else 0

    ps1, ps2, ps3, ps4 = st.columns(4)
    ps1.metric("Cash Utilization", f"{cash_util:.1f}%")
    ps2.metric("Investment Ratio", f"{inv_util:.1f}%")
    ps3.metric("Portfolio Growth", f"{port_growth:.2f}%")
    ps4.metric("Active Assets Count", cnt_avail + cnt_const)

    st.divider()

    # WHERE MY MONEY IS INVESTED (LARGEST SECTION)
    st.markdown("## 💰 Where My Money Is Invested")
    st.markdown(f"#### **Total Active Investment:** <span class='text-blue'>{format_pkr(total_invested_active)}</span>", unsafe_allow_html=True)
    st.write("")

    active_props = df_props[df_props['status'].isin(['Available', 'Under Construction'])] if not df_props.empty else pd.DataFrame()

    if active_props.empty:
        st.info("No active investments found. Add properties to populate this section.")
    else:
        grid_cols = st.columns(2)
        idx = 0
        for _, prop in active_props.iterrows():
            total_cost = prop['buying_price'] + prop['construction_cost']
            our_inv = total_cost * (prop['ownership_pct'] / 100.0)
            share_pct = (our_inv / total_invested_active * 100) if total_invested_active > 0 else 0
            
            # Estimated unrealized gain
            curr_val_our = prop['current_value'] * (prop['ownership_pct'] / 100.0)
            est_roi = ((curr_val_our - our_inv) / our_inv * 100) if our_inv > 0 else 0.0

            badge_class = "badge-available" if prop['status'] == 'Available' else "badge-construction"

            with grid_cols[idx % 2]:
                st.markdown(f"""
                <div class="prop-card">
                    <div class="prop-header">
                        <span class="prop-title">{prop['name']}</span>
                        <span class="{badge_class}">{prop['status']}</span>
                    </div>
                    <p style="margin-bottom: 5px; color: #475569;">📍 <b>Location:</b> {prop['location']} | 🤝 <b>Dealer:</b> {prop['dealer']}</p>
                    <p style="margin-bottom: 5px; color: #475569;">📅 <b>Purchased:</b> {prop['purchase_date']}</p>
                    <hr style="margin: 10px 0;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 14px;">
                        <div><b>Total Cost:</b> {format_pkr(total_cost)}</div>
                        <div><b>Our Ownership:</b> {prop['ownership_pct']}%</div>
                        <div><b>Our Investment:</b> <span class="text-blue">{format_pkr(our_inv)}</span></div>
                        <div><b>Current Value:</b> {format_pkr(prop['current_value'])}</div>
                        <div><b>Expected Price:</b> {format_pkr(prop['expected_selling_price'])}</div>
                        <div><b>Unrealized ROI:</b> <span class="{'text-green' if est_roi >=0 else 'text-red'}">{est_roi:.1f}%</span></div>
                    </div>
                    <div style="margin-top: 15px;">
                        <small><b>Portfolio Share ({share_pct:.1f}%):</b></small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(min(max(share_pct / 100.0, 0.0), 1.0))
            idx += 1

# ---------------------------------------------------------
# PAGE 2: ADD PROPERTY
# ---------------------------------------------------------
elif menu == "➕ Add Property":
    st.title("➕ Add New Property")
    st.caption("Record new real estate acquisition or project")

    with st.form("add_property_form"):
        col1, col2 = st.columns(2)
        with col1:
            p_name = st.text_input("Property Name*")
            p_loc = st.text_input("Location*")
            p_type = st.selectbox("Property Type", ["Residential Plot", "Commercial Plot", "House", "Plaza", "Agricultural Land", "Apartment"])
            p_size = st.text_input("Property Size (e.g., 10 Marla, 1 Kanal)", "1 Kanal")
            p_date = st.date_input("Purchase Date", datetime.now())
            p_buying = st.number_input("Buying Price (PKR)*", min_value=0.0, step=100000.0)
            p_const = st.number_input("Construction Cost (PKR)", min_value=0.0, step=100000.0)

        with col2:
            p_ownership = st.selectbox("Our Ownership Percentage*", [10.0, 20.0, 25.0, 40.0, 50.0, 60.0, 75.0, 100.0], index=7)
            p_current_val = st.number_input("Current Estimated Value (PKR)", min_value=0.0, step=100000.0)
            p_exp_sell = st.number_input("Expected Selling Price (PKR)", min_value=0.0, step=100000.0)
            p_status = st.selectbox("Status", ["Available", "Under Construction", "Sold"])
            p_dealer = st.selectbox("Dealer", ["Samiullah", "Sheikh Abid"])
            p_act_sell = 0.0
            p_sold_date = None
            if p_status == "Sold":
                p_act_sell = st.number_input("Actual Selling Price (PKR)*", min_value=0.0, step=100000.0)
                p_sold_date = st.date_input("Sold Date", datetime.now()).strftime("%Y-%m-%d")

            p_notes = st.text_area("Notes", "")

        # Dynamic Calculations Preview
        tot_cost_calc = p_buying + p_const
        our_inv_calc = tot_cost_calc * (p_ownership / 100.0)
        st.info(f"**Total Property Cost:** {format_pkr(tot_cost_calc)} | **Our Calculated Investment:** {format_pkr(our_inv_calc)}")

        submit = st.form_submit_button("Save Property", use_container_width=True)

        if submit:
            if not p_name or not p_loc:
                st.error("Property Name and Location are required!")
            elif p_buying < 0 or p_const < 0:
                st.error("Buying Price and Construction Cost cannot be negative!")
            elif p_ownership <= 0 or p_ownership > 100:
                st.error("Ownership must be between 1% and 100%!")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO properties (name, location, property_type, size, purchase_date, buying_price,
                                      construction_cost, total_cost, ownership_pct, our_investment,
                                      current_value, expected_selling_price, actual_selling_price,
                                      sold_date, status, dealer, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (p_name, p_loc, p_type, p_size, p_date.strftime("%Y-%m-%d"), p_buying,
                      p_const, tot_cost_calc, p_ownership, our_inv_calc,
                      p_current_val, p_exp_sell, p_act_sell,
                      p_sold_date, p_status, p_dealer, p_notes))
                conn.commit()
                conn.close()
                st.success("Property added successfully!")
                st.rerun()

# ---------------------------------------------------------
# PAGE 3: MANAGE PROPERTIES
# ---------------------------------------------------------
elif menu == "🏢 Manage Properties":
    st.title("🏢 Manage Properties")
    st.caption("View, Search, Edit, and Delete Real Estate Records")

    # Search and Filter Controls
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        search_query = st.text_input("🔍 Search (Name / Location)", "")
    with f_col2:
        filter_status = st.multiselect("Filter Status", ["Available", "Under Construction", "Sold"], default=["Available", "Under Construction", "Sold"])
    with f_col3:
        filter_dealer = st.multiselect("Filter Dealer", ["Samiullah", "Sheikh Abid"], default=["Samiullah", "Sheikh Abid"])
    with f_col4:
        filter_ownership = st.selectbox("Filter Ownership %", ["All", 10, 20, 25, 40, 50, 60, 75, 100])

    # Filter Logic
    filtered_df = df_props.copy()
    if not filtered_df.empty:
        if search_query:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search_query, case=False, na=False) |
                filtered_df['location'].str.contains(search_query, case=False, na=False)
            ]
        if filter_status:
            filtered_df = filtered_df[filtered_df['status'].isin(filter_status)]
        if filter_dealer:
            filtered_df = filtered_df[filtered_df['dealer'].isin(filter_dealer)]
        if filter_ownership != "All":
            filtered_df = filtered_df[filtered_df['ownership_pct'] == float(filter_ownership)]

    if filtered_df.empty:
        st.warning("No properties found matching criteria.")
    else:
        # Build Management Table Dataset
        table_rows = []
        for _, row in filtered_df.iterrows():
            fin = calculate_property_financials(
                row['buying_price'], row['construction_cost'],
                row['ownership_pct'], row['actual_selling_price'],
                row['status'], dealer_pct
            )
            table_rows.append({
                "ID": row['id'],
                "Property": row['name'],
                "Location": row['location'],
                "Dealer": row['dealer'],
                "Cost": format_pkr(fin['total_cost']),
                "Ownership %": f"{row['ownership_pct']}%",
                "Our Investment": format_pkr(fin['our_investment']),
                "Current Value": format_pkr(row['current_value']),
                "Selling Price": format_pkr(row['actual_selling_price']) if row['status'] == 'Sold' else format_pkr(row['expected_selling_price']),
                "Profit": format_pkr(fin['profit']),
                "Commission": format_pkr(fin['dealer_commission']),
                "Jaffar Profit": format_pkr(fin['jaffar_profit']),
                "Tehseen Profit": format_pkr(fin['tehseen_profit']),
                "ROI %": f"{fin['roi']:.2f}%",
                "Status": row['status']
            })

        display_df = pd.DataFrame(table_rows)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("⚡ Quick Actions")

        selected_id = st.selectbox("Select Property by ID to View / Edit / Delete", filtered_df['id'].tolist())

        prop_data = filtered_df[filtered_df['id'] == selected_id].iloc[0]

        act_col1, act_col2 = st.columns(2)

        with act_col1:
            st.markdown("### ✏ Edit Property")
            with st.form("edit_property_form"):
                e_name = st.text_input("Property Name", value=prop_data['name'])
                e_loc = st.text_input("Location", value=prop_data['location'])
                e_type = st.selectbox("Property Type", ["Residential Plot", "Commercial Plot", "House", "Plaza", "Agricultural Land", "Apartment"], index=0)
                e_size = st.text_input("Size", value=prop_data['size'])
                e_buying = st.number_input("Buying Price", value=float(prop_data['buying_price']))
                e_const = st.number_input("Construction Cost", value=float(prop_data['construction_cost']))
                e_ownership = st.selectbox("Ownership %", [10.0, 20.0, 25.0, 40.0, 50.0, 60.0, 75.0, 100.0], index=[10.0, 20.0, 25.0, 40.0, 50.0, 60.0, 75.0, 100.0].index(float(prop_data['ownership_pct'])))
                e_curr_val = st.number_input("Current Estimated Value", value=float(prop_data['current_value']))
                e_exp_sell = st.number_input("Expected Selling Price", value=float(prop_data['expected_selling_price']))
                e_status = st.selectbox("Status", ["Available", "Under Construction", "Sold"], index=["Available", "Under Construction", "Sold"].index(prop_data['status']))
                e_dealer = st.selectbox("Dealer", ["Samiullah", "Sheikh Abid"], index=["Samiullah", "Sheikh Abid"].index(prop_data['dealer']))
                
                e_act_sell = float(prop_data['actual_selling_price'])
                e_sold_date = prop_data['sold_date']
                if e_status == "Sold":
                    e_act_sell = st.number_input("Actual Selling Price", value=float(prop_data['actual_selling_price']))
                    e_sold_date = st.date_input("Sold Date", datetime.now() if not prop_data['sold_date'] else datetime.strptime(prop_data['sold_date'], "%Y-%m-%d")).strftime("%Y-%m-%d")

                # Warning
                e_tot_cost = e_buying + e_const
                e_our_inv = e_tot_cost * (e_ownership / 100.0)
                if e_status == "Sold" and (e_act_sell * (e_ownership / 100.0)) < e_our_inv:
                    st.warning("⚠️ Warning: Actual Selling Price share is lower than Our Investment! This will record a loss.")

                update_btn = st.form_submit_button("Update Property Record")
                if update_btn:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                    UPDATE properties 
                    SET name=?, location=?, property_type=?, size=?, buying_price=?, construction_cost=?,
                        total_cost=?, ownership_pct=?, our_investment=?, current_value=?, expected_selling_price=?,
                        actual_selling_price=?, sold_date=?, status=?, dealer=?
                    WHERE id=?
                    """, (e_name, e_loc, e_type, e_size, e_buying, e_const,
                          e_tot_cost, e_ownership, e_our_inv, e_curr_val, e_exp_sell,
                          e_act_sell, e_sold_date, e_status, e_dealer, selected_id))
                    conn.commit()
                    conn.close()
                    st.success("Property updated successfully!")
                    st.rerun()

        with act_col2:
            st.markdown("### 🗑 Delete Property")
            st.error(f"Are you sure you want to delete **{prop_data['name']}**?")
            if st.button("Confirm Delete", use_container_width=True):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM properties WHERE id=?", (selected_id,))
                conn.commit()
                conn.close()
                st.success("Property deleted successfully!")
                st.rerun()

# ---------------------------------------------------------
# PAGE 4: PORTFOLIO VISUALIZATIONS
# ---------------------------------------------------------
elif menu == "📊 Portfolio":
    st.title("📊 Portfolio Visualizations & Analytics")
    st.caption("Interactive charts comparing assets, investments, and distribution")

    if df_props.empty:
        st.info("No properties available to generate visual analytics.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Investments by Location")
            loc_df = df_props.groupby('location')['our_investment'].sum().reset_index()
            fig1 = px.pie(loc_df, values='our_investment', names='location', hole=0.4,
                          color_discrete_sequence=px.colors.qualitative.Pastel)
            fig1.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            st.markdown("### Portfolio Status Distribution")
            status_df = df_props.groupby('status').size().reset_index(name='count')
            fig2 = px.bar(status_df, x='status', y='count', color='status',
                          color_discrete_map={'Available': '#2563eb', 'Under Construction': '#ea580c', 'Sold': '#16a34a'})
            fig2.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        st.markdown("### Our Investment vs. Current Estimated Value")
        active_p = df_props[df_props['status'].isin(['Available', 'Under Construction'])].copy()
        if not active_p.empty:
            active_p['our_curr_val'] = active_p['current_value'] * (active_p['ownership_pct'] / 100.0)
            fig3 = go.Figure(data=[
                go.Bar(name='Our Investment', x=active_p['name'], y=active_p['our_investment'], marker_color='#2563eb'),
                go.Bar(name='Our Share Current Value', x=active_p['name'], y=active_p['our_curr_val'], marker_color='#9333ea')
            ])
            fig3.update_layout(barmode='group', margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------
# PAGE 5: REPORTS & EXPORTS
# ---------------------------------------------------------
elif menu == "📑 Reports":
    st.title("📑 Financial Reports & Multi-Format Exports")
    st.caption("Generate, view, and download comprehensive real estate business reports")

    report_type = st.selectbox("Select Report Type", [
        "Property Report", "Investment Report", "Profit Report", "Loss Report",
        "Dealer Report", "Jaffar Report", "Tehseen Report", "Portfolio Report",
        "Cash Flow Report", "Net Worth Report"
    ])

    # Filtered Datasets Logic
    if report_type == "Property Report":
        rep_df = df_props.copy()
    elif report_type == "Investment Report":
        rep_df = df_props[df_props['status'].isin(['Available', 'Under Construction'])].copy()
    elif report_type == "Profit Report":
        rep_df = df_props[df_props['status'] == 'Sold'].copy()
        # Filter for profitable ones
    elif report_type == "Loss Report":
        rep_df = df_props[df_props['status'] == 'Sold'].copy()
    elif report_type == "Dealer Report":
        rep_df = df_props.copy()
    else:
        rep_df = df_props.copy()

    st.subheader(f"📋 {report_type}")
    st.dataframe(rep_df, use_container_width=True)

    st.divider()
    st.subheader("📥 Export Options")

    exp_col1, exp_col2, exp_col3 = st.columns(3)

    # 1. CSV EXPORT
    with exp_col1:
        csv_data = rep_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download CSV",
            data=csv_data,
            file_name=f"{report_type.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # 2. EXCEL EXPORT
    with exp_col2:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            rep_df.to_excel(writer, index=False, sheet_name="Report")
            if not df_props.empty:
                df_props.to_excel(writer, index=False, sheet_name="All Properties")
        excel_data = excel_buffer.getvalue()

        st.download_button(
            label="📊 Download Excel Workbook",
            data=excel_data,
            file_name=f"{report_type.lower().replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # 3. PDF EXPORT
    with exp_col3:
        def generate_pdf_report():
            pdf_buffer = io.BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph(f"{settings['business_name']} - {report_type}", styles['Title']))
            elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            elements.append(Spacer(1, 20))

            # Table Data
            if not rep_df.empty:
                summary_data = [["Property", "Location", "Status", "Our Investment"]]
                for _, r in rep_df.iterrows():
                    summary_data.append([
                        str(r['name'])[:20],
                        str(r['location'])[:15],
                        str(r['status']),
                        format_pkr(r['our_investment'])
                    ])
                
                t = Table(summary_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                ]))
                elements.append(t)
            else:
                elements.append(Paragraph("No data available for this report.", styles['Normal']))

            doc.build(elements)
            return pdf_buffer.getvalue()

        pdf_data = generate_pdf_report()
        st.download_button(
            label="🔴 Download PDF Report",
            data=pdf_data,
            file_name=f"{report_type.lower().replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ---------------------------------------------------------
# PAGE 6: BUSINESS SETTINGS
# ---------------------------------------------------------
elif menu == "⚙ Business Settings":
    st.title("⚙ Business Settings")
    st.caption("Update Business Parameters, Balances & System Configurations")

    with st.form("update_settings_form"):
        col1, col2 = st.columns(2)
        with col1:
            u_name = st.text_input("Business Name", value=settings['business_name'])
            u_logo = st.text_input("Business Logo (Emoji / Symbol)", value=settings['business_logo'])
            u_comm = st.number_input("Dealer Commission %", min_value=0.0, max_value=100.0, value=float(settings['dealer_commission_pct']))
            u_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, value=float(settings['initial_cash']), step=1000000.0)

        with col2:
            u_nw = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, value=float(settings['initial_net_worth']), step=1000000.0)
            u_jnw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, value=float(settings['jaffar_net_worth']), step=1000000.0)
            u_tnw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, value=float(settings['tehseen_net_worth']), step=1000000.0)

        save_btn = st.form_submit_button("Save Settings Changes", use_container_width=True)
        if save_btn:
            save_settings(u_name, u_logo, u_cash, u_nw, u_jnw, u_tnw, u_comm)
            st.success("Business Settings updated successfully!")
            st.rerun()
