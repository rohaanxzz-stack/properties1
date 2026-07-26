import sqlite3
import hashlib
import io
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Property Investment & Business Portfolio Management Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for SaaS Financial Dashboard styling
st.markdown("""
<style>
    /* Main Layout Aesthetics */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* SaaS KPI Card Styling */
    .kpi-card {
        background-color: var(--background-secondary, #f8fafc);
        border: 1px solid var(--border-color, #e2e8f0);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .kpi-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 1.55rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .kpi-subtitle {
        font-size: 0.78rem;
        color: #94a3b8;
    }
    
    /* Active Investment Card Styling */
    .prop-card {
        border-radius: 12px;
        border-left: 6px solid #2563eb;
        background-color: var(--background-secondary, #ffffff);
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
        padding: 18px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .status-available { border-left-color: #2563eb !important; }
    .status-construction { border-left-color: #d97706 !important; }
    .status-sold { border-left-color: #10b981 !important; }
    
    /* Badges */
    .badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-available { background-color: #dbeafe; color: #1e40af; }
    .badge-construction { background-color: #fef3c7; color: #92400e; }
    .badge-sold { background-color: #d1fae5; color: #065f46; }
    
    .hr-divider {
        margin: 2rem 0;
        border: 0;
        border-top: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# DATABASE & BACKEND SYSTEM
# ==========================================
DB_FILE = "portfolio_management.db"

def get_db_connection():
    """Establish connection to SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hash plain text password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """Initialize database schemas and default user accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table 1: Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Table 2: Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            business_name TEXT NOT NULL,
            initial_business_cash REAL NOT NULL,
            initial_business_net_worth REAL NOT NULL,
            jaffar_initial_net_worth REAL NOT NULL,
            tehseen_initial_net_worth REAL NOT NULL,
            dealer_default_commission REAL NOT NULL
        )
    ''')
    
    # Table 3: Properties
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            buying_price REAL NOT NULL,
            construction_cost REAL NOT NULL,
            selling_price REAL DEFAULT 0,
            property_size TEXT NOT NULL,
            status TEXT NOT NULL,
            expected_completion_date TEXT,
            sold_date TEXT,
            notes TEXT
        )
    ''')
    
    # Seed Admin and Viewer credentials if table is empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ("admin", hash_password("admin123"), "Admin"))
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                       ("viewer", hash_password("viewer123"), "Viewer"))
    
    conn.commit()
    conn.close()

init_db()


# ==========================================
# PAKISTANI CURRENCY & FORMATTING ENGINE
# ==========================================
def format_pkr(amount):
    """Format numbers into Pakistani Rupee format (e.g. PKR 1,00,00,000)."""
    if amount is None:
        amount = 0.0
    is_negative = amount < 0
    amount = abs(amount)
    
    s = f"{amount:.2f}"
    parts = s.split('.')
    whole = parts[0]
    decimals = parts[1]
    
    if len(whole) > 3:
        last_three = whole[-3:]
        other_digits = whole[:-3]
        res = ""
        while len(other_digits) > 2:
            res = "," + other_digits[-2:] + res
            other_digits = other_digits[:-2]
        if other_digits:
            res = other_digits + res
        formatted_whole = res + "," + last_three
    else:
        formatted_whole = whole
        
    formatted = f"PKR {formatted_whole}"
    if decimals != "00":
        formatted += f".{decimals}"
    return f"-{formatted}" if is_negative else formatted


# ==========================================
# FINANCIAL CALCULATIONS & ENGINE
# ==========================================
def get_settings():
    """Retrieve system business settings."""
    conn = get_db_connection()
    settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return settings

def update_settings(business_name, cash, net_worth, jaffar_nw, tehseen_nw, commission):
    """Save or update business baseline settings."""
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO settings (id, business_name, initial_business_cash, initial_business_net_worth, jaffar_initial_net_worth, tehseen_initial_net_worth, dealer_default_commission)
        VALUES (1, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            business_name=excluded.business_name,
            initial_business_cash=excluded.initial_business_cash,
            initial_business_net_worth=excluded.initial_business_net_worth,
            jaffar_initial_net_worth=excluded.jaffar_initial_net_worth,
            tehseen_initial_net_worth=excluded.tehseen_initial_net_worth,
            dealer_default_commission=excluded.dealer_default_commission
    ''', (business_name, cash, net_worth, jaffar_nw, tehseen_nw, commission))
    conn.commit()
    conn.close()

def get_all_properties():
    """Fetch all property records from SQLite database."""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM properties", conn)
    conn.close()
    return df

def calculate_portfolio_metrics():
    """
    Automated Core Financial Calculation Engine:
    - Business Cash = Initial Cash - All Property Investments + Selling Prices of Sold Properties
    - Business Net Worth = Business Cash + Current Value of Unsold Properties (Investment Cost)
    - Profit Split: 25% Dealer Commission, 37.5% Jaffar, 37.5% Tehseen (75% remaining split 50/50)
    - Wallets: Initial Net Worth + Profit Earned
    """
    settings = get_settings()
    if not settings:
        return None

    init_cash = float(settings["initial_business_cash"])
    init_jaffar = float(settings["jaffar_initial_net_worth"])
    init_tehseen = float(settings["tehseen_initial_net_worth"])
    default_comm_pct = float(settings["dealer_default_commission"]) / 100.0

    df = get_all_properties()

    total_active_investment = 0.0
    total_unsold_current_value = 0.0
    total_realized_profit = 0.0
    total_realized_loss = 0.0
    total_dealer_commission = 0.0
    total_jaffar_earned = 0.0
    total_tehseen_earned = 0.0
    
    cash_flow_adjustments = 0.0
    processed_properties = []

    for _, prop in df.iterrows():
        buying = float(prop["buying_price"])
        const = float(prop["construction_cost"])
        selling = float(prop["selling_price"])
        status = prop["status"]
        investment = buying + const

        # Cash is deducted immediately upon property save for all properties
        cash_flow_adjustments -= investment

        if status in ["Available", "Under Construction"]:
            total_active_investment += investment
            total_unsold_current_value += investment
            profit = 0.0
            loss = 0.0
            dealer_comm = 0.0
            jaffar_share = 0.0
            tehseen_share = 0.0
        else:  # Status == "Sold"
            # When sold, full selling price is added back to cash
            cash_flow_adjustments += selling
            
            if selling > investment:
                profit = selling - investment
                loss = 0.0
                dealer_comm = profit * default_comm_pct
                remaining_profit = profit - dealer_comm
                jaffar_share = remaining_profit * 0.50  # 37.5% of total profit
                tehseen_share = remaining_profit * 0.50 # 37.5% of total profit
            else:
                profit = 0.0
                loss = investment - selling
                dealer_comm = 0.0
                jaffar_share = 0.0
                tehseen_share = 0.0

        total_realized_profit += profit
        total_realized_loss += loss
        total_dealer_commission += dealer_comm
        total_jaffar_earned += jaffar_share
        total_tehseen_earned += tehseen_share

        p_dict = dict(prop)
        p_dict["investment"] = investment
        p_dict["profit"] = profit
        p_dict["loss"] = loss
        p_dict["dealer_commission"] = dealer_comm
        p_dict["jaffar_share"] = jaffar_share
        p_dict["tehseen_share"] = tehseen_share
        processed_properties.append(p_dict)

    current_business_cash = init_cash + cash_flow_adjustments
    current_business_net_worth = current_business_cash + total_unsold_current_value
    jaffar_current_net_worth = init_jaffar + total_jaffar_earned
    tehseen_current_net_worth = init_tehseen + total_tehseen_earned

    proc_df = pd.DataFrame(processed_properties) if processed_properties else pd.DataFrame()

    return {
        "business_cash": current_business_cash,
        "business_net_worth": current_business_net_worth,
        "active_investment": total_active_investment,
        "portfolio_value": total_unsold_current_value,
        "total_profit": total_realized_profit,
        "total_loss": total_realized_loss,
        "dealer_earnings": total_dealer_commission,
        "jaffar_net_worth": jaffar_current_net_worth,
        "jaffar_profit": total_jaffar_earned,
        "tehseen_net_worth": tehseen_current_net_worth,
        "tehseen_profit": total_tehseen_earned,
        "properties_df": proc_df,
        "total_properties": len(df),
        "available_count": len(df[df["status"] == "Available"]) if not df.empty else 0,
        "construction_count": len(df[df["status"] == "Under Construction"]) if not df.empty else 0,
        "sold_count": len(df[df["status"] == "Sold"]) if not df.empty else 0,
    }


# ==========================================
# AUTHENTICATION & LOGIN PAGE
# ==========================================
def login_page():
    """Render Login Page."""
    st.markdown("<h2 style='text-align: center;'>🏢 Property Investment System</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Sign in to access your business portfolio dashboard</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", use_container_width=True)
            
            if submit:
                conn = get_db_connection()
                hashed_pw = hash_password(password)
                user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
                                    (username, hashed_pw)).fetchone()
                conn.close()
                
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user["username"]
                    st.session_state["role"] = user["role"]
                    st.success(f"Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password.")


# ==========================================
# INITIAL BUSINESS SETTINGS SETUP
# ==========================================
def initial_setup_page():
    """Form shown on first initialization to capture baseline settings."""
    st.markdown("## ⚙️ Initial Business Setup")
    st.info("Please enter your initial financial baseline parameters to activate the dashboard.")
    
    with st.form("setup_form"):
        business_name = st.text_input("Business Name", value="Jaffar & Tehseen Real Estate Ventures")
        col1, col2 = st.columns(2)
        with col1:
            init_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, value=10000000.0, step=100000.0)
            jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, value=5000000.0, step=100000.0)
        with col2:
            init_nw = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, value=10000000.0, step=100000.0)
            tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, value=5000000.0, step=100000.0)
            
        commission = st.number_input("Default Dealer Commission (%)", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
        
        submit = st.form_submit_button("Save & Launch Application", use_container_width=True)
        if submit:
            if not business_name.strip():
                st.error("Business Name is required.")
            else:
                update_settings(business_name, init_cash, init_nw, jaffar_nw, tehseen_nw, commission)
                st.success("Business settings saved successfully!")
                st.rerun()


# ==========================================
# PDF REPORT GENERATOR
# ==========================================
def generate_pdf_report(metrics):
    """Generate executive PDF summary report."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    
    settings = get_settings()
    b_name = settings["business_name"] if settings else "Real Estate Investment Portfolio"
    
    pdf.cell(0, 10, f"{b_name}", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Portfolio Statement & Financial Audit", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(5)
    
    # Financial Overview
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Financial Summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    
    pdf.cell(95, 7, f"Business Net Worth: {format_pkr(metrics['business_net_worth'])}", border=1)
    pdf.cell(95, 7, f"Business Cash: {format_pkr(metrics['business_cash'])}", border=1, ln=True)
    pdf.cell(95, 7, f"Money Invested: {format_pkr(metrics['active_investment'])}", border=1)
    pdf.cell(95, 7, f"Total Profit Earned: {format_pkr(metrics['total_profit'])}", border=1, ln=True)
    pdf.cell(95, 7, f"Jaffar Net Worth: {format_pkr(metrics['jaffar_net_worth'])}", border=1)
    pdf.cell(95, 7, f"Tehseen Net Worth: {format_pkr(metrics['tehseen_net_worth'])}", border=1, ln=True)
    pdf.cell(95, 7, f"Dealer Commission: {format_pkr(metrics['dealer_earnings'])}", border=1)
    pdf.cell(95, 7, f"Total Loss: {format_pkr(metrics['total_loss'])}", border=1, ln=True)
    
    pdf.ln(8)
    
    # Property Inventory Table
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Property Portfolio Inventory", ln=True)
    pdf.set_font("Helvetica", "B", 9)
    
    pdf.cell(45, 7, "Property Name", border=1)
    pdf.cell(35, 7, "Location", border=1)
    pdf.cell(30, 7, "Status", border=1)
    pdf.cell(40, 7, "Investment", border=1)
    pdf.cell(40, 7, "Profit/Loss", border=1, ln=True)
    
    pdf.set_font("Helvetica", "", 8)
    df = metrics["properties_df"]
    if not df.empty:
        for _, row in df.iterrows():
            pdf.cell(45, 6, str(row["name"])[:22], border=1)
            pdf.cell(35, 6, str(row["location"])[:18], border=1)
            pdf.cell(30, 6, str(row["status"]), border=1)
            pdf.cell(40, 6, format_pkr(row["investment"]), border=1)
            p_val = row["profit"] if row["status"] == "Sold" else 0.0
            pdf.cell(40, 6, format_pkr(p_val), border=1, ln=True)
            
    return pdf.output()


# ==========================================
# MODULE 1: DASHBOARD
# ==========================================
def render_dashboard(metrics):
    """Render main SaaS Financial Dashboard."""
    st.title("📊 Financial Dashboard")
    
    # Row 1 KPI Cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Net Worth</div>
                <div class="kpi-value" style="color: #2563eb;">{format_pkr(metrics['business_net_worth'])}</div>
                <div class="kpi-subtitle">Cash + Unsold Assets</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Cash Available</div>
                <div class="kpi-value" style="color: #059669;">{format_pkr(metrics['business_cash'])}</div>
                <div class="kpi-subtitle">Liquid Funds</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Money Invested</div>
                <div class="kpi-value" style="color: #d97706;">{format_pkr(metrics['active_investment'])}</div>
                <div class="kpi-subtitle">Active Investments</div>
            </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Current Portfolio Value</div>
                <div class="kpi-value">{format_pkr(metrics['portfolio_value'])}</div>
                <div class="kpi-subtitle">Unsold Property Value</div>
            </div>
        """, unsafe_allow_html=True)

    # Row 2 KPI Cards
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Profit</div><div class="kpi-value" style="color:#10b981;">{format_pkr(metrics['total_profit'])}</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Loss</div><div class="kpi-value" style="color:#ef4444;">{format_pkr(metrics['total_loss'])}</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Dealer Earnings</div><div class="kpi-value">{format_pkr(metrics['dealer_earnings'])}</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Jaffar Net Worth</div><div class="kpi-value" style="color:#8b5cf6;">{format_pkr(metrics['jaffar_net_worth'])}</div><div class="kpi-subtitle">Profit: {format_pkr(metrics['jaffar_profit'])}</div></div>""", unsafe_allow_html=True)
    with k5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Tehseen Net Worth</div><div class="kpi-value" style="color:#6366f1;">{format_pkr(metrics['tehseen_net_worth'])}</div><div class="kpi-subtitle">Profit: {format_pkr(metrics['tehseen_profit'])}</div></div>""", unsafe_allow_html=True)

    # Status Breakdown
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Total Properties", metrics['total_properties'])
    p2.metric("Available", metrics['available_count'])
    p3.metric("Under Construction", metrics['construction_count'])
    p4.metric("Sold", metrics['sold_count'])

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)

    # WHERE MY MONEY IS INVESTED SECTION
    st.subheader("📍 Where My Money Is Invested")
    st.markdown(f"**Total Invested Amount:** `{format_pkr(metrics['active_investment'])}`")
    st.markdown("<br>", unsafe_allow_html=True)
    
    df = metrics["properties_df"]
    if not df.empty:
        active_props = df[df["status"].isin(["Available", "Under Construction"])]
        if not active_props.empty:
            cols = st.columns(3)
            idx = 0
            for _, prop in active_props.iterrows():
                with cols[idx % 3]:
                    status_class = "status-available" if prop["status"] == "Available" else "status-construction"
                    badge_class = "badge-available" if prop["status"] == "Available" else "badge-construction"
                    pct = (prop["investment"] / metrics['active_investment'] * 100) if metrics['active_investment'] > 0 else 0
                    
                    st.markdown(f"""
                        <div class="prop-card {status_class}">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                                <h4 style="margin:0; font-size:1.1rem; color:#0f172a;">{prop['name']}</h4>
                                <span class="badge {badge_class}">{prop['status']}</span>
                            </div>
                            <p style="margin:2px 0; color:#64748b; font-size:0.85rem;">📍 Location: {prop['location']}</p>
                            <p style="margin:2px 0; color:#64748b; font-size:0.85rem;">📅 Purchased: {prop['purchase_date']}</p>
                            <hr style="margin:10px 0; border:0; border-top:1px solid #e2e8f0;">
                            <div style="display:flex; justify-content:space-between; margin-top:5px;">
                                <div>
                                    <span style="font-size:0.75rem; color:#94a3b8;">Investment</span><br>
                                    <strong style="color:#0f172a; font-size:0.95rem;">{format_pkr(prop['investment'])}</strong>
                                </div>
                                <div>
                                    <span style="font-size:0.75rem; color:#94a3b8;">Investment %</span><br>
                                    <strong style="color:#2563eb; font-size:0.95rem;">{pct:.1f}%</strong>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                idx += 1
        else:
            st.info("No active property investments currently.")
    else:
        st.info("No properties recorded in the system.")


# ==========================================
# MODULE 2: PORTFOLIO & CHARTS
# ==========================================
def render_portfolio(metrics):
    """Render interactive Plotly analytics dashboard."""
    st.title("💼 Portfolio Analytics & Allocation")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Business Cash", format_pkr(metrics["business_cash"]))
    c2.metric("Current Investments", format_pkr(metrics["active_investment"]))
    c3.metric("Current Net Worth", format_pkr(metrics["business_net_worth"]))
    
    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)
    df = metrics["properties_df"]

    # Row 1 Charts
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Cash vs Investment Allocation")
        cash_val = max(0, metrics["business_cash"])
        fig1 = px.pie(
            values=[cash_val, metrics["active_investment"]],
            names=["Cash Available", "Invested Capital"],
            color_discrete_sequence=["#10b981", "#2563eb"],
            hole=0.45
        )
        st.plotly_chart(fig1, use_container_width=True)
        
    with g2:
        st.subheader("Investment Distribution by Property")
        if not df.empty:
            fig2 = px.pie(
                df,
                values="investment",
                names="name",
                hole=0.35,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No property data available.")

    # Row 2 Charts
    g3, g4 = st.columns(2)
    with g3:
        st.subheader("Profit Distribution by Property")
        if not df.empty and not df[df["status"] == "Sold"].empty:
            sold_df = df[df["status"] == "Sold"]
            fig3 = px.bar(
                sold_df,
                x="name",
                y="profit",
                color="profit",
                color_continuous_scale="Viridis",
                labels={"profit": "Profit (PKR)", "name": "Property"}
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No sold property data available.")

    with g4:
        st.subheader("Investment Timeline")
        if not df.empty:
            df_sorted = df.sort_values("purchase_date")
            fig4 = px.line(
                df_sorted,
                x="purchase_date",
                y="investment",
                markers=True,
                labels={"purchase_date": "Purchase Date", "investment": "Investment Amount (PKR)"}
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No timeline data available.")


# ==========================================
# MODULE 3: ADD PROPERTY
# ==========================================
def render_add_property():
    """Property entry form."""
    st.title("➕ Add New Property")
    
    if st.session_state.get("role") != "Admin":
        st.error("Access Restricted: Only Admins can add new property records.")
        return

    with st.form("add_prop_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Property Name*")
            location = st.text_input("Location*")
            buying_price = st.number_input("Buying Price (PKR)*", min_value=0.0, value=0.0, step=100000.0)
            construction_cost = st.number_input("Construction Cost (PKR)", min_value=0.0, value=0.0, step=50000.0)
            property_size = st.text_input("Property Size (e.g. 10 Marla, 1 Kanal)*")
            
        with col2:
            status = st.selectbox("Status*", ["Available", "Under Construction", "Sold"])
            purchase_date = st.date_input("Purchase Date", value=date.today())
            expected_completion = st.date_input("Expected Completion Date", value=date.today())
            sold_date = st.date_input("Sold Date (If Sold)", value=date.today())
            selling_price = st.number_input("Selling Price (PKR) (If Sold)", min_value=0.0, value=0.0, step=100000.0)

        notes = st.text_area("Notes / Remarks")

        # Live Validation Warning
        total_inv = buying_price + construction_cost
        if status == "Sold" and selling_price < total_inv and selling_price > 0:
            st.warning(f"⚠️ Warning: Selling Price ({format_pkr(selling_price)}) is less than total investment ({format_pkr(total_inv)}). This transaction will record a loss.")

        submit = st.form_submit_button("Save Property", use_container_width=True)
        
        if submit:
            if not name.strip() or not location.strip() or not property_size.strip():
                st.error("Please fill in all mandatory fields (Name, Location, Property Size).")
            elif buying_price <= 0:
                st.error("Buying Price must be greater than 0.")
            else:
                conn = get_db_connection()
                conn.execute('''
                    INSERT INTO properties (
                        name, location, purchase_date, buying_price, construction_cost,
                        selling_price, property_size, status, expected_completion_date,
                        sold_date, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name.strip(), location.strip(), str(purchase_date), buying_price,
                    construction_cost, selling_price if status == "Sold" else 0.0,
                    property_size.strip(), status,
                    str(expected_completion) if status == "Under Construction" else None,
                    str(sold_date) if status == "Sold" else None, notes.strip()
                ))
                conn.commit()
                conn.close()
                st.success(f"Property '{name}' successfully saved and ledger updated!")


# ==========================================
# MODULE 4: MANAGE PROPERTIES
# ==========================================
def render_manage_properties(metrics):
    """View, Edit, Search, Filter, and Delete properties."""
    st.title("🛠️ Manage Properties")
    
    df = metrics["properties_df"]
    if df.empty:
        st.info("No properties stored in database.")
        return

    # Search and Filter Toolbar
    c_search, c_filter = st.columns([2, 1])
    with c_search:
        search = st.text_input("🔍 Search by Property Name, Location, or Date", "")
    with c_filter:
        status_filter = st.selectbox("Status Filter", ["All", "Available", "Under Construction", "Sold"])

    # Filter Logic
    filtered_df = df.copy()
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]
        
    if search.strip():
        q = search.lower()
        filtered_df = filtered_df[
            filtered_df["name"].str.lower().str.contains(q) |
            filtered_df["location"].str.lower().str.contains(q) |
            filtered_df["purchase_date"].str.contains(q)
        ]

    st.markdown(f"Showing **{len(filtered_df)}** of **{len(df)}** properties")
    st.markdown("<br>", unsafe_allow_html=True)

    is_admin = st.session_state.get("role") == "Admin"

    for _, prop in filtered_df.iterrows():
        p_id = prop["id"]
        with st.expander(f"🏠 {prop['name']} — {prop['location']} ({prop['status']})"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Buying Price:** {format_pkr(prop['buying_price'])}")
                st.write(f"**Construction Cost:** {format_pkr(prop['construction_cost'])}")
                st.write(f"**Total Investment:** {format_pkr(prop['investment'])}")
                st.write(f"**Property Size:** {prop['property_size']}")
                st.write(f"**Purchase Date:** {prop['purchase_date']}")
            with col2:
                st.write(f"**Status:** {prop['status']}")
                if prop['status'] == "Under Construction":
                    st.write(f"**Expected Completion Date:** {prop['expected_completion_date']}")
                elif prop['status'] == "Sold":
                    st.write(f"**Sold Date:** {prop['sold_date']}")
                    st.write(f"**Selling Price:** {format_pkr(prop['selling_price'])}")
                    st.write(f"**Profit Earned:** {format_pkr(prop['profit'])}")
                    st.write(f"**Dealer Commission (25%):** {format_pkr(prop['dealer_commission'])}")
                    st.write(f"**Jaffar Share (37.5%):** {format_pkr(prop['jaffar_share'])}")
                    st.write(f"**Tehseen Share (37.5%):** {format_pkr(prop['tehseen_share'])}")
                st.write(f"**Notes:** {prop['notes'] or 'N/A'}")

            # Admin Management Actions
            if is_admin:
                st.markdown("---")
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    if st.button("✏️ Edit Property", key=f"btn_edit_{p_id}"):
                        st.session_state[f"edit_mode_{p_id}"] = not st.session_state.get(f"edit_mode_{p_id}", False)
                
                with btn_col2:
                    if st.button("🗑️ Delete Property", key=f"btn_del_{p_id}"):
                        st.session_state[f"confirm_del_{p_id}"] = True

                # Delete Confirmation Prompt
                if st.session_state.get(f"confirm_del_{p_id}", False):
                    st.error(f"Are you sure you want to delete '{prop['name']}'? This action cannot be undone.")
                    y_col, n_col = st.columns(2)
                    if y_col.button("Confirm Delete", key=f"yes_{p_id}"):
                        conn = get_db_connection()
                        conn.execute("DELETE FROM properties WHERE id = ?", (p_id,))
                        conn.commit()
                        conn.close()
                        st.session_state[f"confirm_del_{p_id}"] = False
                        st.success("Property removed successfully!")
                        st.rerun()
                    if n_col.button("Cancel", key=f"no_{p_id}"):
                        st.session_state[f"confirm_del_{p_id}"] = False
                        st.rerun()

                # Inline Edit Form
                if st.session_state.get(f"edit_mode_{p_id}", False):
                    st.markdown("#### Edit Property Information")
                    with st.form(key=f"edit_form_{p_id}"):
                        e_name = st.text_input("Property Name", value=prop["name"])
                        e_loc = st.text_input("Location", value=prop["location"])
                        e_buy = st.number_input("Buying Price", min_value=0.0, value=float(prop["buying_price"]))
                        e_const = st.number_input("Construction Cost", min_value=0.0, value=float(prop["construction_cost"]))
                        e_size = st.text_input("Property Size", value=prop["property_size"])
                        
                        status_opts = ["Available", "Under Construction", "Sold"]
                        e_status = st.selectbox("Status", status_opts, index=status_opts.index(prop["status"]))
                        
                        e_sell = st.number_input("Selling Price (If Sold)", min_value=0.0, value=float(prop["selling_price"]))
                        e_notes = st.text_area("Notes", value=prop["notes"] or "")

                        update_submit = st.form_submit_button("Update Property Record")
                        if update_submit:
                            conn = get_db_connection()
                            conn.execute('''
                                UPDATE properties SET
                                    name = ?, location = ?, buying_price = ?, construction_cost = ?,
                                    property_size = ?, status = ?, selling_price = ?, notes = ?
                                WHERE id = ?
                            ''', (e_name, e_loc, e_buy, e_const, e_size, e_status, e_sell if e_status == "Sold" else 0.0, e_notes, p_id))
                            conn.commit()
                            conn.close()
                            st.session_state[f"edit_mode_{p_id}"] = False
                            st.success("Property record updated!")
                            st.rerun()


# ==========================================
# MODULE 5: REPORTS & EXPORTS
# ==========================================
def render_reports(metrics):
    """Render financial reports and download options."""
    st.title("📑 Financial Reports & Statements")
    
    df = metrics["properties_df"]
    if df.empty:
        st.info("No transaction data available for reports.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "All Properties Report", "Profit & Loss Ledger", "Dealer Commission Report",
        "Jaffar Share Report", "Tehseen Share Report"
    ])

    def format_df_display(data_frame):
        d = data_frame.copy()
        num_cols = ["buying_price", "construction_cost", "selling_price", "investment", "profit", "loss", "dealer_commission", "jaffar_share", "tehseen_share"]
        for col in num_cols:
            if col in d.columns:
                d[col] = d[col].apply(format_pkr)
        return d

    with tab1:
        st.subheader("Master Portfolio Inventory")
        st.dataframe(format_df_display(df), use_container_width=True)

    with tab2:
        st.subheader("Profit & Loss Ledger (Sold Properties)")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "location", "selling_price", "investment", "profit", "loss"]]), use_container_width=True)
        else:
            st.info("No sold properties to calculate profit/loss.")

    with tab3:
        st.subheader("Dealer Commission Earnings (25%)")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "location", "selling_price", "profit", "dealer_commission"]]), use_container_width=True)
            st.markdown(f"**Total Dealer Commission Earned:** `{format_pkr(metrics['dealer_earnings'])}`")
        else:
            st.info("No dealer commission earned yet.")

    with tab4:
        st.subheader("Jaffar Profit Share (37.5%)")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "location", "profit", "jaffar_share"]]), use_container_width=True)
            st.markdown(f"**Total Profit Earned by Jaffar:** `{format_pkr(metrics['jaffar_profit'])}`")
        else:
            st.info("No partner profit recorded yet.")

    with tab5:
        st.subheader("Tehseen Profit Share (37.5%)")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "location", "profit", "tehseen_share"]]), use_container_width=True)
            st.markdown(f"**Total Profit Earned by Tehseen:** `{format_pkr(metrics['tehseen_profit'])}`")
        else:
            st.info("No partner profit recorded yet.")

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)
    st.subheader("📥 Export Reports")

    col_csv, col_excel, col_pdf = st.columns(3)
    
    # CSV Export
    with col_csv:
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Export CSV Report",
            data=csv_data,
            file_name=f"portfolio_report_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Excel Export
    with col_excel:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Portfolio Summary')
        excel_data = output.getvalue()
        st.download_button(
            label="📊 Export Excel Report",
            data=excel_data,
            file_name=f"portfolio_report_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # PDF Statement Export
    with col_pdf:
        pdf_bytes = generate_pdf_report(metrics)
        st.download_button(
            label="📕 Export PDF Statement",
            data=bytes(pdf_bytes),
            file_name=f"portfolio_statement_{date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )


# ==========================================
# MODULE 6: BUSINESS SETTINGS
# ==========================================
def render_settings():
    """Manage System Business Settings."""
    st.title("⚙️ Business Settings")
    
    if st.session_state.get("role") != "Admin":
        st.error("Access Restricted: Only Admins can edit system settings.")
        return

    settings = get_settings()
    
    with st.form("settings_form"):
        b_name = st.text_input("Business Name", value=settings["business_name"])
        
        c1, c2 = st.columns(2)
        with c1:
            init_cash = st.number_input("Initial Business Cash (PKR)", value=float(settings["initial_business_cash"]), step=100000.0)
            jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", value=float(settings["jaffar_initial_net_worth"]), step=100000.0)
        with c2:
            init_nw = st.number_input("Initial Business Net Worth (PKR)", value=float(settings["initial_business_net_worth"]), step=100000.0)
            tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", value=float(settings["tehseen_initial_net_worth"]), step=100000.0)

        comm = st.number_input("Default Dealer Commission (%)", min_value=0.0, max_value=100.0, value=float(settings["dealer_default_commission"]), step=1.0)

        submit = st.form_submit_button("Update Business Parameters", use_container_width=True)
        if submit:
            update_settings(b_name, init_cash, init_nw, jaffar_nw, tehseen_nw, comm)
            st.success("Business settings updated successfully!")
            st.rerun()


# ==========================================
# MAIN APPLICATION ROUTER
# ==========================================
def main():
    """Main execution controller."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # 1. Login Authentication
    if not st.session_state["authenticated"]:
        login_page()
        return

    # 2. Database Initialization Check
    settings = get_settings()
    if not settings:
        initial_setup_page()
        return

    # 3. Calculate Dynamic Portfolio Metrics
    metrics = calculate_portfolio_metrics()

    # 4. Sidebar Controls & Navigation
    st.sidebar.title(f"🏢 {settings['business_name']}")
    st.sidebar.caption(f"User: **{st.session_state['username']}** | Role: **{st.session_state['role']}**")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Portfolio", "Add Property", "Manage Properties", "Reports", "Business Settings"]
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("🔒 Logout", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["role"] = None
        st.rerun()

    # 5. Route Pages
    if menu == "Dashboard":
        render_dashboard(metrics)
    elif menu == "Portfolio":
        render_portfolio(metrics)
    elif menu == "Add Property":
        render_add_property()
    elif menu == "Manage Properties":
        render_manage_properties(metrics)
    elif menu == "Reports":
        render_reports(metrics)
    elif menu == "Business Settings":
        render_settings()


if __name__ == "__main__":
    main()
