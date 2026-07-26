import sqlite3
import io
from datetime import date, datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

# ==========================================
# PAGE CONFIGURATION & INJECTED STYLES
# ==========================================
st.set_page_config(
    page_title="Property Investment & Business Portfolio Management Dashboard",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for SaaS Financial Dashboard styling (Zoho / Monday style)
st.markdown("""
<style>
    /* Main Layout Aesthetics */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    
    /* SaaS KPI Card Styling */
    .kpi-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .kpi-title {
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.45rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .kpi-subtitle {
        font-size: 0.75rem;
        color: #94a3b8;
    }
    
    /* Active Investment Card Styling */
    .prop-card {
        border-radius: 12px;
        border-left: 6px solid #2563eb;
        background-color: #ffffff;
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
        padding: 20px;
        margin-bottom: 18px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .status-available { border-left-color: #2563eb !important; }
    .status-construction { border-left-color: #f59e0b !important; }
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
    
    /* Custom Dividers */
    .hr-divider {
        margin: 2rem 0;
        border: 0;
        border-top: 1px solid #e2e8f0;
    }
    
    /* Progress bar custom wrapper */
    .progress-bg {
        background-color: #e2e8f0;
        border-radius: 8px;
        height: 8px;
        width: 100%;
        margin-top: 8px;
        overflow: hidden;
    }
    .progress-fill {
        background-color: #2563eb;
        height: 100%;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# DATABASE INITIALIZATION & BACKEND ENGINE
# ==========================================
DB_FILE = "portfolio_management.db"

def get_db_connection():
    """Establish connection to SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schemas for business settings and property portfolio."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table 1: Settings
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
    
    # Table 2: Properties
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            buying_price REAL NOT NULL,
            construction_cost REAL NOT NULL,
            selling_price REAL DEFAULT 0,
            expected_selling_price REAL DEFAULT 0,
            property_size TEXT NOT NULL,
            property_type TEXT NOT NULL,
            status TEXT NOT NULL,
            broker_name TEXT,
            completion_date TEXT,
            sold_date TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()


# ==========================================
# PAKISTANI CURRENCY FORMATTING ENGINE
# ==========================================
def format_pkr(amount):
    """Format numbers into Pakistani Rupee format (e.g. PKR 1,80,00,000)."""
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
# FINANCIAL CALCULATIONS ENGINE
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
    - Investment = Buying Price + Construction Cost
    - Profit = Selling Price - Investment
    - Dealer Commission = 25% of Profit
    - Jaffar Profit = 37.5% of Profit
    - Tehseen Profit = 37.5% of Profit
    - Business Cash = Initial Cash - All Active Property Investments + Selling Price of Sold Properties
    - Business Net Worth = Business Cash + Unsold Property Values (Expected / Investment) + Realized Profits
    """
    settings = get_settings()
    if not settings:
        return None

    init_cash = float(settings["initial_business_cash"])
    init_nw = float(settings["initial_business_net_worth"])
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

    jaffar_participated_count = 0
    tehseen_participated_count = 0

    for _, prop in df.iterrows():
        buying = float(prop["buying_price"])
        const = float(prop["construction_cost"])
        selling = float(prop["selling_price"])
        exp_selling = float(prop["expected_selling_price"])
        status = prop["status"]
        investment = buying + const

        if status in ["Available", "Under Construction"]:
            total_active_investment += investment
            curr_val = exp_selling if exp_selling > 0 else investment
            total_unsold_current_value += curr_val
            cash_flow_adjustments -= investment  # Deduct investment from active cash
            
            profit = 0.0
            loss = 0.0
            dealer_comm = 0.0
            jaffar_share = 0.0
            tehseen_share = 0.0
        else:  # Status == "Sold"
            cash_flow_adjustments -= investment # Initial deduction
            cash_flow_adjustments += selling    # Re-inject selling revenue back into cash
            
            jaffar_participated_count += 1
            tehseen_participated_count += 1

            if selling > investment:
                profit = selling - investment
                loss = 0.0
                dealer_comm = profit * default_comm_pct
                remaining_profit = profit - dealer_comm
                jaffar_share = remaining_profit * 0.50   # 37.5% of total profit
                tehseen_share = remaining_profit * 0.50  # 37.5% of total profit
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
        p_dict["current_value"] = exp_selling if status != "Sold" and exp_selling > 0 else (selling if status == "Sold" else investment)
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

    # ROI & Growth Metrics
    roi = ((total_realized_profit - total_realized_loss) / total_active_investment * 100) if total_active_investment > 0 else 0.0
    net_growth = ((current_business_net_worth - init_nw) / init_nw * 100) if init_nw > 0 else 0.0

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
        "jaffar_participated": jaffar_participated_count,
        "tehseen_net_worth": tehseen_current_net_worth,
        "tehseen_profit": total_tehseen_earned,
        "tehseen_participated": tehseen_participated_count,
        "roi": roi,
        "net_growth": net_growth,
        "properties_df": proc_df,
        "total_properties": len(df),
        "available_count": len(df[df["status"] == "Available"]) if not df.empty else 0,
        "construction_count": len(df[df["status"] == "Under Construction"]) if not df.empty else 0,
        "sold_count": len(df[df["status"] == "Sold"]) if not df.empty else 0,
        "initial_cash": init_cash,
        "initial_nw": init_nw
    }


# ==========================================
# INITIAL BUSINESS SETUP SETUP
# ==========================================
def initial_setup_page():
    """Form shown on first launch to setup business initial state."""
    st.markdown("<h2 style='text-align: center;'>🏢 Property Investment & Portfolio Setup</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b;'>Welcome! Please set up your business initial baseline parameters to activate the management system.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("setup_form"):
            st.subheader("⚙️ Business Initial Baseline")
            business_name = st.text_input("Business Name*", value="Jaffar & Tehseen Real Estate Ventures")
            
            c_a, c_b = st.columns(2)
            with c_a:
                init_cash = st.number_input("Initial Business Cash (PKR)*", min_value=0.0, value=10000000.0, step=500000.0)
                jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)*", min_value=0.0, value=5000000.0, step=250000.0)
            with c_b:
                init_nw = st.number_input("Initial Business Net Worth (PKR)*", min_value=0.0, value=10000000.0, step=500000.0)
                tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)*", min_value=0.0, value=5000000.0, step=250000.0)
                
            commission = st.number_input("Default Dealer Commission (%)*", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            
            submit = st.form_submit_button("🚀 Initialize System Dashboard", use_container_width=True)
            if submit:
                if not business_name.strip():
                    st.error("Business Name is required.")
                else:
                    update_settings(business_name, init_cash, init_nw, jaffar_nw, tehseen_nw, commission)
                    st.success("Business settings saved successfully!")
                    st.rerun()


# ==========================================
# PDF STATEMENT GENERATOR
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
    
    # Financial Overview Table
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
# MODULE 1: MAIN SaaS DASHBOARD
# ==========================================
def render_dashboard(metrics):
    """Render modern Zoho / Monday / PowerBI style SaaS dashboard."""
    st.title("🏠 Executive Financial Dashboard")
    
    # TOP KPI CARDS ROW 1
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Net Worth</div>
                <div class="kpi-value" style="color: #2563eb;">{format_pkr(metrics['business_net_worth'])}</div>
                <div class="kpi-subtitle">Growth: {metrics['net_growth']:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Business Cash Available</div>
                <div class="kpi-value" style="color: #059669;">{format_pkr(metrics['business_cash'])}</div>
                <div class="kpi-subtitle">Liquid Capital</div>
            </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Money Currently Invested</div>
                <div class="kpi-value" style="color: #d97706;">{format_pkr(metrics['active_investment'])}</div>
                <div class="kpi-subtitle">Active Deployments</div>
            </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">Portfolio Value</div>
                <div class="kpi-value">{format_pkr(metrics['portfolio_value'])}</div>
                <div class="kpi-subtitle">Unsold Property Value</div>
            </div>
        """, unsafe_allow_html=True)

    # TOP KPI CARDS ROW 2
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Profit</div><div class="kpi-value" style="color:#10b981;">{format_pkr(metrics['total_profit'])}</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Total Loss</div><div class="kpi-value" style="color:#ef4444;">{format_pkr(metrics['total_loss'])}</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Dealer Earnings</div><div class="kpi-value">{format_pkr(metrics['dealer_earnings'])}</div></div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Jaffar Net Worth</div><div class="kpi-value" style="color:#8b5cf6;">{format_pkr(metrics['jaffar_net_worth'])}</div></div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-title">Tehseen Net Worth</div><div class="kpi-value" style="color:#6366f1;">{format_pkr(metrics['tehseen_net_worth'])}</div></div>""", unsafe_allow_html=True)

    # PROPERTY METRIC STRIP
    p1, p2, p3, p4, p5, p6 = st.columns(6)
    p1.metric("Total Properties", metrics['total_properties'])
    p2.metric("Available", metrics['available_count'])
    p3.metric("Under Construction", metrics['construction_count'])
    p4.metric("Sold Properties", metrics['sold_count'])
    p5.metric("Portfolio ROI %", f"{metrics['roi']:.1f}%")
    p6.metric("Net Growth %", f"{metrics['net_growth']:.1f}%")

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)

    # SECOND ROW: LARGE PORTFOLIO SUMMARY CARD
    st.subheader("📊 Portfolio Capital Breakdown")
    with st.container():
        total_cap = metrics['business_cash'] + metrics['active_investment']
        cash_util = (metrics['business_cash'] / total_cap * 100) if total_cap > 0 else 0
        inv_util = (metrics['active_investment'] / total_cap * 100) if total_cap > 0 else 0

        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.markdown(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:20px;">
                <h4 style="margin-top:0; color:#0f172a;">Capital Allocation Overview</h4>
                <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <span><strong>Current Net Worth:</strong> {format_pkr(metrics['business_net_worth'])}</span>
                    <span><strong>Current Cash:</strong> {format_pkr(metrics['business_cash'])}</span>
                </div>
                <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                    <span><strong>Active Investment:</strong> {format_pkr(metrics['active_investment'])}</span>
                    <span><strong>Portfolio Value:</strong> {format_pkr(metrics['portfolio_value'])}</span>
                </div>
                <div style="margin-bottom:8px; font-size:0.85rem; color:#64748b;">
                    Cash Utilization: {cash_util:.1f}% | Investment Utilization: {inv_util:.1f}%
                </div>
                <div class="progress-bg">
                    <div class="progress-fill" style="width: {inv_util}%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_right:
            fig_mini = px.pie(
                values=[max(0, metrics['business_cash']), metrics['active_investment']],
                names=["Cash", "Invested"],
                color_discrete_sequence=["#10b981", "#2563eb"],
                hole=0.6
            )
            fig_mini.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=140, showlegend=False)
            st.plotly_chart(fig_mini, use_container_width=True)

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)

    # SECTION: WHERE MY MONEY IS INVESTED
    st.subheader("📍 Where My Money Is Invested")
    st.markdown(f"**Total Active Investment Amount:** `{format_pkr(metrics['active_investment'])}`")
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
                                <h4 style="margin:0; font-size:1.1rem; color:#0f172a;">🏢 {prop['name']}</h4>
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
                                    <span style="font-size:0.75rem; color:#94a3b8;">Current Value</span><br>
                                    <strong style="color:#059669; font-size:0.95rem;">{format_pkr(prop['current_value'])}</strong>
                                </div>
                                <div>
                                    <span style="font-size:0.75rem; color:#94a3b8;">Portfolio Share</span><br>
                                    <strong style="color:#2563eb; font-size:0.95rem;">{pct:.1f}%</strong>
                                </div>
                            </div>
                            <div class="progress-bg">
                                <div class="progress-fill" style="width: {pct}%;"></div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                idx += 1
        else:
            st.info("No active property investments currently.")
    else:
        st.info("No property records found in system.")


# ==========================================
# MODULE 2: PORTFOLIO ANALYTICS & CHARTS
# ==========================================
def render_portfolio(metrics):
    """Render interactive Plotly analytics dashboard."""
    st.title("📊 Portfolio Analytics & Visualizations")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Business Cash", format_pkr(metrics["business_cash"]))
    c2.metric("Total Investment", format_pkr(metrics["active_investment"]))
    c3.metric("Current Portfolio Value", format_pkr(metrics["portfolio_value"]))
    c4.metric("Business Net Worth", format_pkr(metrics["business_net_worth"]))

    df = metrics["properties_df"]
    if df.empty:
        st.info("No property data available for analytics.")
        return

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)

    # Highlights Row
    h1, h2, h3, h4, h5 = st.columns(5)
    
    top_inv_prop = df.loc[df['investment'].idxmax()] if not df.empty else None
    sold_df = df[df['status'] == 'Sold']
    top_prof_prop = sold_df.loc[sold_df['profit'].idxmax()] if not sold_df.empty and sold_df['profit'].max() > 0 else None
    worst_loss_prop = sold_df.loc[sold_df['loss'].idxmax()] if not sold_df.empty and sold_df['loss'].max() > 0 else None

    h1.info(f"**Highest Investment**\n\n{top_inv_prop['name'] if top_inv_prop is not None else 'N/A'}")
    h2.success(f"**Highest Profit**\n\n{top_prof_prop['name'] if top_prof_prop is not None else 'N/A'}")
    h3.error(f"**Highest Loss**\n\n{worst_loss_prop['name'] if worst_loss_prop is not None else 'None'}")
    h4.warning(f"**Top Performing**\n\n{top_prof_prop['name'] if top_prof_prop is not None else 'N/A'}")
    h5.secondary(f"**Total Properties**\n\n{len(df)}")

    st.markdown("<hr class='hr-divider'>", unsafe_allow_html=True)

    # ROW 1 CHARTS
    g1, g2, g3 = st.columns(3)
    with g1:
        st.subheader("Cash vs Investment")
        fig1 = px.pie(
            values=[max(0, metrics["business_cash"]), metrics["active_investment"]],
            names=["Cash Available", "Invested Capital"],
            color_discrete_sequence=["#10b981", "#2563eb"],
            hole=0.45
        )
        st.plotly_chart(fig1, use_container_width=True)

    with g2:
        st.subheader("Investment by Property")
        fig2 = px.pie(
            df,
            values="investment",
            names="name",
            hole=0.35,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig2, use_container_width=True)

    with g3:
        st.subheader("Property Status Breakdown")
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig3 = px.pie(
            status_counts,
            values="Count",
            names="Status",
            color_discrete_sequence=["#2563eb", "#f59e0b", "#10b981"]
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ROW 2 CHARTS
    g4, g5 = st.columns(2)
    with g4:
        st.subheader("Profit Realization by Property")
        if not sold_df.empty:
            fig4 = px.bar(
                sold_df,
                x="name",
                y="profit",
                color="profit",
                color_continuous_scale="Viridis",
                labels={"profit": "Profit (PKR)", "name": "Property"}
            )
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No sold property data to display profit chart.")

    with g5:
        st.subheader("Investment Comparison Across Portfolio")
        fig5 = px.bar(
            df,
            x="name",
            y="investment",
            color="status",
            labels={"investment": "Investment Amount (PKR)", "name": "Property"}
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ROW 3 TIMELINE CHARTS
    g6, g7 = st.columns(2)
    with g6:
        st.subheader("Net Worth Growth Trajectory")
        df_sorted = df.sort_values("purchase_date").copy()
        df_sorted["cumulative_profit"] = df_sorted["profit"].cumsum()
        df_sorted["estimated_net_worth"] = metrics["initial_nw"] + df_sorted["cumulative_profit"]
        fig6 = px.line(
            df_sorted,
            x="purchase_date",
            y="estimated_net_worth",
            markers=True,
            labels={"purchase_date": "Date", "estimated_net_worth": "Business Net Worth (PKR)"}
        )
        st.plotly_chart(fig6, use_container_width=True)

    with g7:
        st.subheader("Cash Flow Timeline")
        fig7 = px.line(
            df_sorted,
            x="purchase_date",
            y="investment",
            markers=True,
            line_shape="linear",
            labels={"purchase_date": "Purchase Date", "investment": "Capital Outflow (PKR)"}
        )
        st.plotly_chart(fig7, use_container_width=True)


# ==========================================
# MODULE 3: ADD PROPERTY
# ==========================================
def render_add_property():
    """Form to record new property investments."""
    st.title("➕ Add New Property Investment")
    st.markdown("Record a new property acquisition into the system portfolio.")
    
    with st.form("add_prop_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Property Name*")
            location = st.text_input("Location*")
            buying_price = st.number_input("Buying Price (PKR)*", min_value=0.0, value=0.0, step=100000.0)
            construction_cost = st.number_input("Construction Cost (PKR)", min_value=0.0, value=0.0, step=50000.0)
            property_size = st.text_input("Property Size (e.g. 10 Marla, 1 Kanal)*")
            property_type = st.selectbox("Property Type*", ["Residential Plot", "Commercial Plot", "House / Villa", "Apartment", "Plaza", "Agricultural Land"])
            
        with col2:
            status = st.selectbox("Status*", ["Available", "Under Construction", "Sold"])
            purchase_date = st.date_input("Purchase Date", value=date.today())
            expected_selling_price = st.number_input("Expected Selling Price (PKR)", min_value=0.0, value=0.0, step=100000.0)
            broker_name = st.text_input("Broker / Dealer Name")
            completion_date = st.date_input("Completion Date (If Under Construction)", value=date.today())
            sold_date = st.date_input("Sold Date (If Sold)", value=date.today())
            selling_price = st.number_input("Actual Selling Price (PKR) (If Sold)", min_value=0.0, value=0.0, step=100000.0)

        notes = st.text_area("Purchase Notes / Remarks")

        # Live Validation Warning
        total_inv = buying_price + construction_cost
        if status == "Sold" and selling_price < total_inv and selling_price > 0:
            st.warning(f"⚠️ Warning: Selling Price ({format_pkr(selling_price)}) is lower than total investment ({format_pkr(total_inv)}). This transaction will record a loss.")

        submit = st.form_submit_button("💾 Save Property Record", use_container_width=True)
        
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
                        selling_price, expected_selling_price, property_size, property_type,
                        status, broker_name, completion_date, sold_date, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name.strip(), location.strip(), str(purchase_date), buying_price,
                    construction_cost, selling_price if status == "Sold" else 0.0,
                    expected_selling_price, property_size.strip(), property_type, status,
                    broker_name.strip(),
                    str(completion_date) if status == "Under Construction" else None,
                    str(sold_date) if status == "Sold" else None, notes.strip()
                ))
                conn.commit()
                conn.close()
                st.success(f"Property '{name}' successfully saved and cash flow updated!")


# ==========================================
# MODULE 4: MANAGE PROPERTIES
# ==========================================
def render_manage_properties(metrics):
    """Data table view with Search, Filter, Edit, and Delete functionality."""
    st.title("🏢 Property Portfolio Ledger")
    
    df = metrics["properties_df"]
    if df.empty:
        st.info("No properties stored in database.")
        return

    # SEARCH & FILTER TOOLBAR
    c_search, c_status, c_loc = st.columns([2, 1, 1])
    with c_search:
        search = st.text_input("🔍 Search Property, Location, Broker, Date", "")
    with c_status:
        status_filter = st.selectbox("Status Filter", ["All", "Available", "Under Construction", "Sold"])
    with c_loc:
        locations = ["All"] + list(df["location"].unique())
        location_filter = st.selectbox("Location Filter", locations)

    # FILTERING LOGIC
    filtered_df = df.copy()
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["status"] == status_filter]
        
    if location_filter != "All":
        filtered_df = filtered_df[filtered_df["location"] == location_filter]

    if search.strip():
        q = search.lower()
        filtered_df = filtered_df[
            filtered_df["name"].str.lower().str.contains(q) |
            filtered_df["location"].str.lower().str.contains(q) |
            filtered_df["broker_name"].fillna("").str.lower().str.contains(q) |
            filtered_df["purchase_date"].str.contains(q)
        ]

    st.markdown(f"Displaying **{len(filtered_df)}** of **{len(df)}** properties")
    st.markdown("<br>", unsafe_allow_html=True)

    # PROPERTY CARDS & EDIT EXPANDERS
    for _, prop in filtered_df.iterrows():
        p_id = prop["id"]
        with st.expander(f"🏠 {prop['name']} — {prop['location']} ({prop['status']})"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Type:** {prop['property_type']}")
                st.write(f"**Size:** {prop['property_size']}")
                st.write(f"**Buying Price:** {format_pkr(prop['buying_price'])}")
                st.write(f"**Construction Cost:** {format_pkr(prop['construction_cost'])}")
                st.write(f"**Total Investment:** {format_pkr(prop['investment'])}")
            with col2:
                st.write(f"**Status:** {prop['status']}")
                st.write(f"**Purchase Date:** {prop['purchase_date']}")
                st.write(f"**Broker Name:** {prop['broker_name'] or 'N/A'}")
                st.write(f"**Expected Price:** {format_pkr(prop['expected_selling_price'])}")
            with col3:
                if prop['status'] == "Sold":
                    st.write(f"**Sold Date:** {prop['sold_date']}")
                    st.write(f"**Selling Price:** {format_pkr(prop['selling_price'])}")
                    st.write(f"**Profit Realized:** {format_pkr(prop['profit'])}")
                    st.write(f"**Dealer Comm (25%):** {format_pkr(prop['dealer_commission'])}")
                    st.write(f"**Jaffar Share (37.5%):** {format_pkr(prop['jaffar_share'])}")
                    st.write(f"**Tehseen Share (37.5%):** {format_pkr(prop['tehseen_share'])}")

            st.write(f"**Notes:** {prop['notes'] or 'N/A'}")

            st.markdown("---")
            btn_col1, btn_col2 = st.columns(2)
            
            with btn_col1:
                if st.button("✏️ Edit Record", key=f"btn_edit_{p_id}"):
                    st.session_state[f"edit_mode_{p_id}"] = not st.session_state.get(f"edit_mode_{p_id}", False)
            
            with btn_col2:
                if st.button("🗑️ Delete Record", key=f"btn_del_{p_id}"):
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
                    
                    e_exp = st.number_input("Expected Selling Price", min_value=0.0, value=float(prop["expected_selling_price"]))
                    e_sell = st.number_input("Selling Price (If Sold)", min_value=0.0, value=float(prop["selling_price"]))
                    e_broker = st.text_input("Broker Name", value=prop["broker_name"] or "")
                    e_notes = st.text_area("Notes", value=prop["notes"] or "")

                    update_submit = st.form_submit_button("Update Property Record")
                    if update_submit:
                        conn = get_db_connection()
                        conn.execute('''
                            UPDATE properties SET
                                name = ?, location = ?, buying_price = ?, construction_cost = ?,
                                property_size = ?, status = ?, expected_selling_price = ?,
                                selling_price = ?, broker_name = ?, notes = ?
                            WHERE id = ?
                        ''', (e_name, e_loc, e_buy, e_const, e_size, e_status, e_exp, e_sell if e_status == "Sold" else 0.0, e_broker, e_notes, p_id))
                        conn.commit()
                        conn.close()
                        st.session_state[f"edit_mode_{p_id}"] = False
                        st.success("Property record updated!")
                        st.rerun()


# ==========================================
# MODULE 5: ACCOUNTS & WALLETS (JAFFAR, TEHSEEN, DEALER)
# ==========================================
def render_accounts(metrics, account_type):
    """Render individual partner or dealer account statements."""
    df = metrics["properties_df"]
    sold_df = df[df["status"] == "Sold"] if not df.empty else pd.DataFrame()

    if account_type == "jaffar":
        st.title("👤 Jaffar Account Statement")
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Net Worth", format_pkr(metrics["jaffar_net_worth"]))
        c2.metric("Total Profit Earned", format_pkr(metrics["jaffar_profit"]))
        c3.metric("Properties Participated", metrics["jaffar_participated"])
        
        st.subheader("Profit Distribution Ledger (37.5%)")
        if not sold_df.empty:
            st.dataframe(sold_df[["name", "location", "selling_price", "profit", "jaffar_share"]].rename(columns={
                "name": "Property", "selling_price": "Selling Price", "profit": "Total Profit", "jaffar_share": "Jaffar Share"
            }), use_container_width=True)
        else:
            st.info("No profit history available.")

    elif account_type == "tehseen":
        st.title("👤 Tehseen Account Statement")
        c1, c2, c3 = st.columns(3)
        c1.metric("Current Net Worth", format_pkr(metrics["tehseen_net_worth"]))
        c2.metric("Total Profit Earned", format_pkr(metrics["tehseen_profit"]))
        c3.metric("Properties Participated", metrics["tehseen_participated"])
        
        st.subheader("Profit Distribution Ledger (37.5%)")
        if not sold_df.empty:
            st.dataframe(sold_df[["name", "location", "selling_price", "profit", "tehseen_share"]].rename(columns={
                "name": "Property", "selling_price": "Selling Price", "profit": "Total Profit", "tehseen_share": "Tehseen Share"
            }), use_container_width=True)
        else:
            st.info("No profit history available.")

    elif account_type == "dealer":
        st.title("🤝 Dealer Commission Ledger")
        c1, c2 = st.columns(2)
        c1.metric("Total Dealer Earnings", format_pkr(metrics["dealer_earnings"]))
        c2.metric("Properties Closed", len(sold_df))
        
        st.subheader("Commission History Ledger (25%)")
        if not sold_df.empty:
            st.dataframe(sold_df[["name", "location", "broker_name", "selling_price", "profit", "dealer_commission"]].rename(columns={
                "name": "Property", "broker_name": "Broker", "selling_price": "Selling Price", "profit": "Total Profit", "dealer_commission": "Commission Earned"
            }), use_container_width=True)
        else:
            st.info("No commission history recorded.")


# ==========================================
# MODULE 6: REPORTS & EXPORTS
# ==========================================
def render_reports(metrics):
    """Financial reports generator and file downloader."""
    st.title("📑 Financial Reports & Statements")
    
    df = metrics["properties_df"]
    if df.empty:
        st.info("No transaction data available for reports.")
        return

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Profit Report", "Loss Report", "Investment Report",
        "Dealer Report", "Jaffar Share", "Tehseen Share"
    ])

    def format_df_display(data_frame):
        d = data_frame.copy()
        num_cols = ["buying_price", "construction_cost", "selling_price", "investment", "profit", "loss", "dealer_commission", "jaffar_share", "tehseen_share"]
        for col in num_cols:
            if col in d.columns:
                d[col] = d[col].apply(format_pkr)
        return d

    with tab1:
        st.subheader("Profit Report (Sold Properties)")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "location", "selling_price", "investment", "profit"]]), use_container_width=True)
        else:
            st.info("No sold properties.")

    with tab2:
        st.subheader("Loss Report")
        loss_df = df[(df["status"] == "Sold") & (df["loss"] > 0)]
        if not loss_df.empty:
            st.dataframe(format_df_display(loss_df[["name", "location", "investment", "selling_price", "loss"]]), use_container_width=True)
        else:
            st.info("No properties sold at a loss.")

    with tab3:
        st.subheader("Investment Report")
        st.dataframe(format_df_display(df[["name", "location", "status", "buying_price", "construction_cost", "investment"]]), use_container_width=True)

    with tab4:
        st.subheader("Dealer Commission Report")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "broker_name", "profit", "dealer_commission"]]), use_container_width=True)

    with tab5:
        st.subheader("Jaffar Share Report")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "profit", "jaffar_share"]]), use_container_width=True)

    with tab6:
        st.subheader("Tehseen Share Report")
        sold_df = df[df["status"] == "Sold"]
        if not sold_df.empty:
            st.dataframe(format_df_display(sold_df[["name", "profit", "tehseen_share"]]), use_container_width=True)

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
# MODULE 7: BUSINESS SETTINGS
# ==========================================
def render_settings():
    """Manage Business Baseline Parameters."""
    st.title("⚙️ Business Settings")
    
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

        submit = st.form_submit_button("Update Business Settings", use_container_width=True)
        if submit:
            update_settings(b_name, init_cash, init_nw, jaffar_nw, tehseen_nw, comm)
            st.success("Business settings updated successfully!")
            st.rerun()


# ==========================================
# MAIN ROUTER & SIDEBAR NAVIGATION
# ==========================================
def main():
    """Main Application Execution Controller."""
    # 1. Database Check for Initial Setup
    settings = get_settings()
    if not settings:
        initial_setup_page()
        return

    # 2. Calculate Real-Time Dynamic Metrics
    metrics = calculate_portfolio_metrics()

    # 3. Sidebar Navigation Panel
    st.sidebar.title(f"🏢 {settings['business_name']}")
    st.sidebar.caption("Property Investment & Portfolio Management")
    st.sidebar.markdown("---")

    menu = st.sidebar.radio(
        "Main Navigation",
        [
            "🏠 Dashboard",
            "📊 Portfolio",
            "🏢 Properties",
            "➕ Add Property",
            "👤 Jaffar Account",
            "👤 Tehseen Account",
            "🤝 Dealer Account",
            "📑 Reports",
            "⚙ Business Settings"
        ]
    )

    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Automation Engine:** All cash flows, profits, commissions, and net worth calculations update in real-time.")

    # 4. Route Pages
    if menu == "🏠 Dashboard":
        render_dashboard(metrics)
    elif menu == "📊 Portfolio":
        render_portfolio(metrics)
    elif menu == "🏢 Properties":
        render_manage_properties(metrics)
    elif menu == "➕ Add Property":
        render_add_property()
    elif menu == "👤 Jaffar Account":
        render_accounts(metrics, "jaffar")
    elif menu == "👤 Tehseen Account":
        render_accounts(metrics, "tehseen")
    elif menu == "🤝 Dealer Account":
        render_accounts(metrics, "dealer")
    elif menu == "📑 Reports":
        render_reports(metrics)
    elif menu == "⚙ Business Settings":
        render_settings()


if __name__ == "__main__":
    main()
