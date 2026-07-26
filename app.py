"""
REAL ESTATE BUSINESS PORTFOLIO MANAGEMENT SYSTEM
A production-ready Streamlit application for managing a real-estate
investment business: properties, ownership splits, cash, profit sharing,
dashboards, reports and exports.

Single-file application. Data persisted in SQLite (data.db).
"""

import io
import sqlite3
import base64
from datetime import date, datetime
from contextlib import contextmanager

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# =========================================================================
# CONFIG / CONSTANTS
# =========================================================================

DB_PATH = "data.db"

DEALERS = ["Samiullah", "Sheikh Abid"]
OWNERSHIP_OPTIONS = [10, 20, 30, 40, 50, 60, 75, 100]
PROPERTY_TYPES = ["Residential Plot", "Commercial Plot", "House", "Apartment",
                   "Shop", "Farmhouse", "Agricultural Land", "Other"]
STATUS_OPTIONS = ["Available", "Under Construction", "Sold"]
DEFAULT_DEALER_COMMISSION_PCT = 25.0

STATUS_COLORS = {
    "Available": "#2563eb",
    "Under Construction": "#d97706",
    "Sold": "#16a34a",
}

PRIMARY = "#4f46e5"
GREEN = "#16a34a"
RED = "#dc2626"
AMBER = "#d97706"
BLUE = "#2563eb"
SLATE = "#64748b"

# =========================================================================
# DB LAYER
# =========================================================================

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                business_name TEXT NOT NULL,
                initial_cash REAL NOT NULL DEFAULT 0,
                initial_net_worth REAL NOT NULL DEFAULT 0,
                jaffar_initial_net_worth REAL NOT NULL DEFAULT 0,
                tehseen_initial_net_worth REAL NOT NULL DEFAULT 0,
                default_dealer_commission_pct REAL NOT NULL DEFAULT 25,
                theme TEXT NOT NULL DEFAULT 'Light',
                initialized INTEGER NOT NULL DEFAULT 0
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                property_name TEXT NOT NULL,
                location TEXT,
                property_type TEXT,
                property_size TEXT,
                purchase_date TEXT,
                buying_price REAL NOT NULL DEFAULT 0,
                construction_cost REAL NOT NULL DEFAULT 0,
                ownership_pct REAL NOT NULL DEFAULT 100,
                current_estimated_value REAL NOT NULL DEFAULT 0,
                expected_selling_price REAL NOT NULL DEFAULT 0,
                actual_selling_price REAL NOT NULL DEFAULT 0,
                sold_date TEXT,
                dealer TEXT,
                status TEXT NOT NULL DEFAULT 'Available',
                notes TEXT,
                dealer_commission_pct REAL NOT NULL DEFAULT 25,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS cash_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                property_id INTEGER,
                entry_type TEXT
            )
        """)
        conn.commit()

        row = c.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if row is None:
            c.execute("""
                INSERT INTO settings
                (id, business_name, initial_cash, initial_net_worth,
                 jaffar_initial_net_worth, tehseen_initial_net_worth,
                 default_dealer_commission_pct, theme, initialized)
                VALUES (1, '', 0, 0, 0, 0, ?, 'Light', 0)
            """, (DEFAULT_DEALER_COMMISSION_PCT,))
            conn.commit()


def get_settings():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row) if row else None


def update_settings(**kwargs):
    if not kwargs:
        return
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values())
    with get_conn() as conn:
        conn.execute(f"UPDATE settings SET {cols} WHERE id = 1", vals)


def add_property(data: dict):
    with get_conn() as conn:
        now = datetime.now().isoformat()
        cols = list(data.keys()) + ["created_at", "updated_at"]
        vals = list(data.values()) + [now, now]
        placeholders = ", ".join(["?"] * len(cols))
        conn.execute(
            f"INSERT INTO properties ({', '.join(cols)}) VALUES ({placeholders})",
            vals
        )
        prop_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        our_investment = data["buying_price"] * data["ownership_pct"] / 100.0 + \
            data["construction_cost"] * data["ownership_pct"] / 100.0
        conn.execute("""
            INSERT INTO cash_ledger (entry_date, description, amount, property_id, entry_type)
            VALUES (?, ?, ?, ?, ?)
        """, (data.get("purchase_date", date.today().isoformat()),
              f"Investment in {data['property_name']}",
              -our_investment, prop_id, "investment"))
    return prop_id


def update_property(prop_id: int, data: dict, record_sale_cash: bool = False,
                     sale_amount: float = 0.0, sale_date: str = None,
                     property_name: str = ""):
    with get_conn() as conn:
        now = datetime.now().isoformat()
        cols = list(data.keys()) + ["updated_at"]
        vals = list(data.values()) + [now]
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        conn.execute(f"UPDATE properties SET {set_clause} WHERE id = ?", vals + [prop_id])

        if record_sale_cash:
            existing = conn.execute(
                "SELECT id FROM cash_ledger WHERE property_id = ? AND entry_type = 'sale'",
                (prop_id,)
            ).fetchone()
            if existing is None:
                conn.execute("""
                    INSERT INTO cash_ledger (entry_date, description, amount, property_id, entry_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_date or date.today().isoformat(),
                      f"Sale proceeds from {property_name}",
                      sale_amount, prop_id, "sale"))
            else:
                conn.execute("""
                    UPDATE cash_ledger SET amount = ?, entry_date = ?
                    WHERE property_id = ? AND entry_type = 'sale'
                """, (sale_amount, sale_date or date.today().isoformat(), prop_id))


def delete_property(prop_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM cash_ledger WHERE property_id = ?", (prop_id,))
        conn.execute("DELETE FROM properties WHERE id = ?", (prop_id,))


def get_properties_df() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM properties ORDER BY id DESC", conn)
    return df


def get_cash_ledger_df() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query("SELECT * FROM cash_ledger ORDER BY entry_date ASC, id ASC", conn)
    return df


# =========================================================================
# BUSINESS LOGIC / CALCULATIONS
# =========================================================================

def enrich_properties(df: pd.DataFrame, dealer_commission_default: float) -> pd.DataFrame:
    """Add derived financial columns to the properties dataframe."""
    if df.empty:
        cols = ["total_property_cost", "our_investment", "our_selling_amount",
                "profit", "dealer_commission_amt", "jaffar_profit",
                "tehseen_profit", "remaining_profit", "roi_pct", "is_loss"]
        for c in cols:
            df[c] = pd.Series(dtype="float64")
        return df

    df = df.copy()
    df["total_property_cost"] = df["buying_price"] + df["construction_cost"]
    df["our_investment"] = df["total_property_cost"] * df["ownership_pct"] / 100.0

    df["our_selling_amount"] = 0.0
    df["profit"] = 0.0
    df["dealer_commission_amt"] = 0.0
    df["jaffar_profit"] = 0.0
    df["tehseen_profit"] = 0.0
    df["remaining_profit"] = 0.0
    df["is_loss"] = False

    sold_mask = df["status"] == "Sold"

    df.loc[sold_mask, "our_selling_amount"] = (
        df.loc[sold_mask, "actual_selling_price"] * df.loc[sold_mask, "ownership_pct"] / 100.0
    )
    df.loc[sold_mask, "profit"] = (
        df.loc[sold_mask, "our_selling_amount"] - df.loc[sold_mask, "our_investment"]
    )

    profit_positive = sold_mask & (df["profit"] > 0)
    profit_nonpositive = sold_mask & (df["profit"] <= 0)

    commission_pct = df["dealer_commission_pct"].fillna(dealer_commission_default)
    df.loc[profit_positive, "dealer_commission_amt"] = (
        df.loc[profit_positive, "profit"] * commission_pct[profit_positive] / 100.0
    )
    df.loc[profit_positive, "remaining_profit"] = (
        df.loc[profit_positive, "profit"] - df.loc[profit_positive, "dealer_commission_amt"]
    )
    df.loc[profit_positive, "jaffar_profit"] = df.loc[profit_positive, "remaining_profit"] / 2.0
    df.loc[profit_positive, "tehseen_profit"] = df.loc[profit_positive, "remaining_profit"] / 2.0

    df.loc[profit_nonpositive, "dealer_commission_amt"] = 0.0
    df.loc[profit_nonpositive, "jaffar_profit"] = 0.0
    df.loc[profit_nonpositive, "tehseen_profit"] = 0.0
    df.loc[profit_nonpositive, "is_loss"] = True

    # ROI: for sold -> realized ROI; for unsold -> unrealized ROI vs current estimated value
    df["roi_pct"] = 0.0
    with pd.option_context('mode.use_inf_as_na', True):
        df.loc[sold_mask & (df["our_investment"] > 0), "roi_pct"] = (
            df.loc[sold_mask, "profit"] / df.loc[sold_mask, "our_investment"] * 100.0
        )
        unsold_mask = ~sold_mask
        our_value_unsold = df.loc[unsold_mask, "current_estimated_value"] * df.loc[unsold_mask, "ownership_pct"] / 100.0
        inv = df.loc[unsold_mask, "our_investment"]
        roi_unsold = pd.Series(0.0, index=df.loc[unsold_mask].index)
        valid = inv > 0
        roi_unsold[valid] = (our_value_unsold[valid] - inv[valid]) / inv[valid] * 100.0
        df.loc[unsold_mask, "roi_pct"] = roi_unsold

    df["roi_pct"] = df["roi_pct"].fillna(0.0)
    return df


def compute_kpis(df: pd.DataFrame, settings: dict):
    cash_df = get_cash_ledger_df()
    current_cash = settings["initial_cash"] + (cash_df["amount"].sum() if not cash_df.empty else 0.0)

    active_mask = df["status"].isin(["Available", "Under Construction"]) if not df.empty else pd.Series(dtype=bool)
    sold_mask = df["status"] == "Sold" if not df.empty else pd.Series(dtype=bool)

    money_invested = df.loc[active_mask, "our_investment"].sum() if not df.empty else 0.0
    portfolio_value = (
        df.loc[active_mask, "current_estimated_value"] * df.loc[active_mask, "ownership_pct"] / 100.0
    ).sum() if not df.empty else 0.0

    total_profit = df.loc[sold_mask & (df["profit"] > 0), "profit"].sum() if not df.empty else 0.0
    total_loss = -df.loc[sold_mask & (df["profit"] < 0), "profit"].sum() if not df.empty else 0.0
    net_realized_profit = df.loc[sold_mask, "profit"].sum() if not df.empty else 0.0

    dealer_earnings = df.loc[sold_mask, "dealer_commission_amt"].sum() if not df.empty else 0.0
    jaffar_earnings = df.loc[sold_mask, "jaffar_profit"].sum() if not df.empty else 0.0
    tehseen_earnings = df.loc[sold_mask, "tehseen_profit"].sum() if not df.empty else 0.0

    jaffar_net_worth = settings["jaffar_initial_net_worth"] + jaffar_earnings
    tehseen_net_worth = settings["tehseen_initial_net_worth"] + tehseen_earnings

    business_net_worth = settings["initial_net_worth"] + net_realized_profit + (
        (df.loc[active_mask, "current_estimated_value"] * df.loc[active_mask, "ownership_pct"] / 100.0).sum()
        - df.loc[active_mask, "our_investment"].sum()
    ) if not df.empty else settings["initial_net_worth"]
    # Simpler, robust definition: net worth = cash + portfolio value (unrealized) + realized net profit already in cash
    business_net_worth = current_cash + portfolio_value

    available_count = int((df["status"] == "Available").sum()) if not df.empty else 0
    construction_count = int((df["status"] == "Under Construction").sum()) if not df.empty else 0
    sold_count = int((df["status"] == "Sold").sum()) if not df.empty else 0

    total_invested_ever = df["our_investment"].sum() if not df.empty else 0.0
    overall_roi = (net_realized_profit / total_invested_ever * 100.0) if total_invested_ever else 0.0

    return {
        "current_cash": current_cash,
        "money_invested": money_invested,
        "portfolio_value": portfolio_value,
        "total_profit": total_profit,
        "total_loss": total_loss,
        "net_realized_profit": net_realized_profit,
        "dealer_earnings": dealer_earnings,
        "jaffar_earnings": jaffar_earnings,
        "tehseen_earnings": tehseen_earnings,
        "jaffar_net_worth": jaffar_net_worth,
        "tehseen_net_worth": tehseen_net_worth,
        "business_net_worth": business_net_worth,
        "available_count": available_count,
        "construction_count": construction_count,
        "sold_count": sold_count,
        "overall_roi": overall_roi,
    }


# =========================================================================
# FORMATTING HELPERS (Pakistani Rupee / Lakh-Crore)
# =========================================================================

def format_pkr(amount) -> str:
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "PKR 0"
    negative = amount < 0
    amount = abs(amount)
    int_part = int(round(amount))
    s = str(int_part)
    if len(s) <= 3:
        formatted = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        formatted = ",".join(parts) + "," + last3
    sign = "-" if negative else ""
    return f"{sign}PKR {formatted}"


def format_pct(value) -> str:
    try:
        return f"{float(value):,.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


# =========================================================================
# STYLING
# =========================================================================

def inject_css(theme: str):
    if theme == "Dark":
        bg = "#0f1117"
        card_bg = "#181b25"
        card_border = "#262a38"
        text_primary = "#f1f5f9"
        text_secondary = "#94a3b8"
        sidebar_bg = "#12141c"
    else:
        bg = "#f5f7fb"
        card_bg = "#ffffff"
        card_border = "#e7eaf3"
        text_primary = "#0f172a"
        text_secondary = "#64748b"
        sidebar_bg = "#ffffff"

    input_bg = "#1f2330" if theme == "Dark" else "#ffffff"
    input_text = "#f1f5f9" if theme == "Dark" else "#0f172a"

    st.markdown(f"""
    <style>
        .stApp {{
            background-color: {bg};
            color: {text_primary};
        }}
        [data-testid="stSidebar"] {{
            background-color: {sidebar_bg};
            border-right: 1px solid {card_border};
        }}
        [data-testid="stSidebar"] * {{
            color: {text_primary} !important;
        }}
        .block-container {{
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }}
        h1, h2, h3, h4, h5, h6, p, span, label, div, li, a {{
            color: {text_primary};
        }}

        /* --- Form widgets: text inputs, number inputs, textareas --- */
        .stTextInput input, .stNumberInput input, .stTextArea textarea,
        .stDateInput input {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border: 1px solid {card_border} !important;
        }}
        .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
            color: {text_secondary} !important;
            opacity: 1;
        }}

        /* --- Selectbox / Multiselect (closed state) --- */
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
            border-color: {card_border} !important;
        }}
        .stSelectbox div[data-baseweb="select"] span,
        .stMultiSelect div[data-baseweb="select"] span {{
            color: {input_text} !important;
        }}

        /* --- Dropdown popover / option list (rendered in a portal) --- */
        div[data-baseweb="popover"] {{
            background-color: {input_bg} !important;
        }}
        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] div,
        ul[role="listbox"] li {{
            background-color: {input_bg} !important;
            color: {input_text} !important;
        }}
        ul[role="listbox"] li:hover {{
            background-color: {PRIMARY} !important;
            color: #ffffff !important;
        }}

        /* --- Multiselect selected tags --- */
        .stMultiSelect span[data-baseweb="tag"] {{
            background-color: {PRIMARY} !important;
            color: #ffffff !important;
        }}

        /* --- Radio / checkbox labels --- */
        .stRadio label, .stCheckbox label {{
            color: {text_primary} !important;
        }}
        .stRadio label p, .stCheckbox label p {{
            color: {text_primary} !important;
        }}

        /* --- DataFrame / table --- */
        [data-testid="stDataFrame"] {{
            background-color: {card_bg} !important;
        }}
        [data-testid="stDataFrame"] * {{
            color: {input_text} !important;
        }}

        /* --- Metric widget --- */
        [data-testid="stMetric"] label, [data-testid="stMetric"] div {{
            color: {text_primary} !important;
        }}

        /* --- Tabs --- */
        .stTabs [data-baseweb="tab"] p {{
            color: {text_primary} !important;
        }}

        /* --- Expander --- */
        .streamlit-expanderHeader, [data-testid="stExpander"] summary {{
            background-color: {card_bg} !important;
            color: {text_primary} !important;
        }}
        [data-testid="stExpander"] * {{
            color: {text_primary} !important;
        }}

        /* --- Alerts (info/success/warning/error) keep their own readable palette --- */
        [data-testid="stAlert"] p, [data-testid="stAlert"] div {{
            color: inherit !important;
        }}

        /* --- File download buttons / general buttons --- */
        .stButton button, .stDownloadButton button, .stFormSubmitButton button {{
            color: {text_primary if theme == "Dark" else "#0f172a"};
        }}
        .app-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.2rem;
        }}
        .app-title {{
            font-size: 1.65rem;
            font-weight: 800;
            color: {text_primary};
            margin: 0;
        }}
        .app-subtitle {{
            color: {text_secondary};
            font-size: 0.92rem;
            margin-top: 2px;
        }}
        .kpi-card {{
            background: {card_bg};
            border: 1px solid {card_border};
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            height: 118px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .kpi-label {{
            font-size: 0.78rem;
            font-weight: 600;
            color: {text_secondary};
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .kpi-value {{
            font-size: 1.35rem;
            font-weight: 800;
            color: {text_primary};
        }}
        .kpi-sub {{
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .section-title {{
            font-size: 1.15rem;
            font-weight: 800;
            color: {text_primary};
            margin-top: 1.6rem;
            margin-bottom: 0.6rem;
            border-left: 4px solid {PRIMARY};
            padding-left: 10px;
        }}
        .prop-card {{
            background: {card_bg};
            border: 1px solid {card_border};
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 14px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        .prop-card-title {{
            font-size: 1.05rem;
            font-weight: 800;
            color: {text_primary};
        }}
        .prop-card-sub {{
            color: {text_secondary};
            font-size: 0.85rem;
            margin-bottom: 10px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 12px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            color: white;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            padding: 4px 0;
            border-bottom: 1px dashed {card_border};
        }}
        .metric-row span:first-child {{
            color: {text_secondary};
        }}
        .metric-row span:last-child {{
            font-weight: 700;
            color: {text_primary};
        }}
        .progress-outer {{
            background: {card_border};
            border-radius: 999px;
            height: 8px;
            width: 100%;
            margin-top: 8px;
            overflow: hidden;
        }}
        .progress-inner {{
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, {PRIMARY}, #7c3aed);
        }}
        div[data-testid="stMetricValue"] {{
            font-size: 1.3rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: {card_bg};
            border: 1px solid {card_border};
            border-radius: 10px 10px 0 0;
            padding: 8px 16px;
        }}
    </style>
    """, unsafe_allow_html=True)


def kpi_card(label, value, sub=None, sub_color=None):
    sub_html = f'<div class="kpi-sub" style="color:{sub_color or SLATE}">{sub}</div>' if sub else '<div class="kpi-sub">&nbsp;</div>'
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
        </div>
    """, unsafe_allow_html=True)


# =========================================================================
# EXPORT HELPERS
# =========================================================================

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def df_to_excel_bytes(sheets: dict) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe_name = name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
    return output.getvalue()


def simple_pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    """Very small dependency-free PDF generator (single-page table, text based)."""
    lines = [title, "=" * len(title), ""]
    if df.empty:
        lines.append("No data available.")
    else:
        cols = list(df.columns)
        lines.append(" | ".join(cols))
        lines.append("-" * 100)
        for _, row in df.iterrows():
            lines.append(" | ".join(str(row[c]) for c in cols))

    text = "\n".join(lines)
    # Minimal valid PDF with a single text stream (courier font, wrapped naively)
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    chunks = escaped.split("\n")
    content_stream = "BT /F1 8 Tf 20 800 Td 10 TL\n"
    for line in chunks:
        content_stream += f"({line[:180]}) Tj T*\n"
    content_stream += "ET"

    pdf = f"""%PDF-1.4
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 1200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>endobj
4 0 obj<< /Length {len(content_stream)} >>stream
{content_stream}
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj
xref
0 6
0000000000 65535 f 
trailer<< /Size 6 /Root 1 0 R >>
startxref
0
%%EOF"""
    return pdf.encode("latin-1", errors="replace")


def download_button_row(df: pd.DataFrame, base_name: str, key_prefix: str, pdf_title: str = None):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("⬇️ CSV", df_to_csv_bytes(df), file_name=f"{base_name}.csv",
                            mime="text/csv", key=f"{key_prefix}_csv", use_container_width=True)
    with c2:
        excel_bytes = df_to_excel_bytes({base_name[:31]: df})
        st.download_button("⬇️ Excel", excel_bytes, file_name=f"{base_name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"{key_prefix}_xlsx", use_container_width=True)
    with c3:
        pdf_bytes = simple_pdf_bytes(pdf_title or base_name, df)
        st.download_button("⬇️ PDF", pdf_bytes, file_name=f"{base_name}.pdf",
                            mime="application/pdf", key=f"{key_prefix}_pdf", use_container_width=True)


# =========================================================================
# APP SETUP
# =========================================================================

st.set_page_config(
    page_title="Real Estate Portfolio Manager",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
settings = get_settings()

if "theme" not in st.session_state:
    st.session_state.theme = settings.get("theme", "Light") if settings else "Light"

inject_css(st.session_state.theme)

# =========================================================================
# FIRST RUN SETUP WIZARD
# =========================================================================

if not settings or not settings.get("initialized"):
    st.markdown('<div class="app-title">🏢 Welcome — Let\'s set up your business</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">This runs only once. You can change everything later in Business Settings.</div>', unsafe_allow_html=True)
    st.write("")

    with st.form("setup_form"):
        c1, c2 = st.columns(2)
        with c1:
            business_name = st.text_input("Business Name*", placeholder="e.g. Jaffar & Tehseen Estates")
            initial_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, step=100000.0, value=0.0)
            initial_net_worth = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, step=100000.0, value=0.0)
        with c2:
            jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, step=100000.0, value=0.0)
            tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, step=100000.0, value=0.0)
            default_commission = st.number_input("Default Dealer Commission (%)", min_value=0.0, max_value=100.0,
                                                   value=DEFAULT_DEALER_COMMISSION_PCT, step=1.0)

        submitted = st.form_submit_button("🚀 Launch Business Dashboard", use_container_width=True, type="primary")
        if submitted:
            if not business_name.strip():
                st.error("Business Name is required.")
            else:
                update_settings(
                    business_name=business_name.strip(),
                    initial_cash=initial_cash,
                    initial_net_worth=initial_net_worth,
                    jaffar_initial_net_worth=jaffar_nw,
                    tehseen_initial_net_worth=tehseen_nw,
                    default_dealer_commission_pct=default_commission,
                    initialized=1,
                )
                st.success("Business created! Loading dashboard...")
                st.rerun()
    st.stop()


# =========================================================================
# SIDEBAR NAVIGATION
# =========================================================================

with st.sidebar:
    st.markdown(f"""
        <div style="padding: 10px 0 20px 0;">
            <div style="font-size:1.3rem; font-weight:800;">🏢 {settings['business_name']}</div>
            <div style="font-size:0.8rem; color:#64748b;">Portfolio Management System</div>
        </div>
    """, unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "➕ Add Property", "🗂️ Manage Properties", "💼 Portfolio",
         "📑 Reports", "⚙️ Business Settings"],
        label_visibility="collapsed",
    )

    st.write("")
    st.markdown("---")
    theme_choice = st.selectbox("Theme", ["Light", "Dark"],
                                 index=0 if st.session_state.theme == "Light" else 1)
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        update_settings(theme=theme_choice)
        st.rerun()

    st.markdown("---")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y, %I:%M %p')}")


# Refresh settings/data each run
settings = get_settings()
raw_df = get_properties_df()
df = enrich_properties(raw_df, settings["default_dealer_commission_pct"])
kpis = compute_kpis(df, settings)


# =========================================================================
# PAGE: DASHBOARD
# =========================================================================

def page_dashboard():
    st.markdown(f"""
        <div class="app-header">
            <div>
                <p class="app-title">📊 Dashboard</p>
                <p class="app-subtitle">Live overview of {settings['business_name']}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- KPI ROW 1 ---
    row1 = st.columns(5)
    with row1[0]:
        kpi_card("Business Net Worth", format_pkr(kpis["business_net_worth"]))
    with row1[1]:
        kpi_card("Business Cash", format_pkr(kpis["current_cash"]))
    with row1[2]:
        kpi_card("Money Invested (Active)", format_pkr(kpis["money_invested"]))
    with row1[3]:
        kpi_card("Portfolio Value", format_pkr(kpis["portfolio_value"]))
    with row1[4]:
        roi_color = GREEN if kpis["overall_roi"] >= 0 else RED
        kpi_card("Overall ROI", format_pct(kpis["overall_roi"]),
                  "Realized return on capital", roi_color)

    row2 = st.columns(5)
    with row2[0]:
        kpi_card("Total Realized Profit", format_pkr(kpis["total_profit"]), "From sold properties", GREEN)
    with row2[1]:
        kpi_card("Total Loss", format_pkr(kpis["total_loss"]), "From sold properties", RED)
    with row2[2]:
        kpi_card("Dealer Earnings", format_pkr(kpis["dealer_earnings"]))
    with row2[3]:
        kpi_card("Jaffar Net Worth", format_pkr(kpis["jaffar_net_worth"]))
    with row2[4]:
        kpi_card("Tehseen Net Worth", format_pkr(kpis["tehseen_net_worth"]))

    row3 = st.columns(4)
    with row3[0]:
        kpi_card("Available Properties", str(kpis["available_count"]), "Status: Available", BLUE)
    with row3[1]:
        kpi_card("Under Construction", str(kpis["construction_count"]), "In progress", AMBER)
    with row3[2]:
        kpi_card("Sold Properties", str(kpis["sold_count"]), "Completed deals", GREEN)
    with row3[3]:
        kpi_card("Total Properties", str(len(df)), "All properties tracked")

    # --- PORTFOLIO SUMMARY ---
    st.markdown('<div class="section-title">Portfolio Summary</div>', unsafe_allow_html=True)
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        kpi_card("Current Cash", format_pkr(kpis["current_cash"]))
    with pc2:
        kpi_card("Investment Utilization",
                  format_pct((kpis["money_invested"] / kpis["business_net_worth"] * 100)
                             if kpis["business_net_worth"] else 0),
                  "Invested vs Net Worth")
    with pc3:
        total_cash_base = settings["initial_cash"] if settings["initial_cash"] else 1
        cash_util = (1 - kpis["current_cash"] / total_cash_base) * 100 if total_cash_base else 0
        kpi_card("Cash Utilization", format_pct(cash_util), "vs initial cash")
    with pc4:
        base_nw = settings["initial_net_worth"] if settings["initial_net_worth"] else 1
        growth = (kpis["business_net_worth"] - settings["initial_net_worth"]) / base_nw * 100 if base_nw else 0
        kpi_card("Portfolio Growth", format_pct(growth),
                  "vs initial net worth", GREEN if growth >= 0 else RED)

    # --- WHERE MY MONEY IS INVESTED ---
    st.markdown('<div class="section-title">💰 Where My Money Is Invested</div>', unsafe_allow_html=True)
    active_df = df[df["status"].isin(["Available", "Under Construction"])] if not df.empty else df

    if active_df.empty:
        st.info("No active investments yet. Add a property to get started.")
    else:
        total_active_investment = active_df["our_investment"].sum()
        st.markdown(f"""
            <div style="background:linear-gradient(135deg,{PRIMARY},#7c3aed); border-radius:16px;
                        padding:20px 24px; color:white; margin-bottom:18px;">
                <div style="font-size:0.85rem; opacity:0.85; font-weight:600; text-transform:uppercase;">
                    Total Active Investment
                </div>
                <div style="font-size:1.8rem; font-weight:800;">{format_pkr(total_active_investment)}</div>
            </div>
        """, unsafe_allow_html=True)

        cols_per_row = 3
        rows_of_props = [active_df.iloc[i:i + cols_per_row] for i in range(0, len(active_df), cols_per_row)]
        for chunk in rows_of_props:
            cols = st.columns(cols_per_row)
            for i, (_, prop) in enumerate(chunk.iterrows()):
                with cols[i]:
                    render_property_card(prop, total_active_investment)

    # --- CHARTS ---
    render_charts(df)


def render_property_card(prop, total_active_investment):
    status = prop["status"]
    color = STATUS_COLORS.get(status, SLATE)
    portfolio_share = (prop["our_investment"] / total_active_investment * 100) if total_active_investment else 0
    progress_pct = min(max(prop["roi_pct"] + 50, 0), 100)  # visual only, centered around 50
    roi_color = GREEN if prop["roi_pct"] >= 0 else RED

    st.markdown(f"""
        <div class="prop-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <div class="prop-card-title">{prop['property_name']}</div>
                    <div class="prop-card-sub">📍 {prop['location'] or '—'}</div>
                </div>
                <span class="status-badge" style="background:{color};">{status}</span>
            </div>
            <div class="metric-row"><span>Dealer</span><span>{prop['dealer'] or '—'}</span></div>
            <div class="metric-row"><span>Purchase Date</span><span>{prop['purchase_date'] or '—'}</span></div>
            <div class="metric-row"><span>Property Cost</span><span>{format_pkr(prop['total_property_cost'])}</span></div>
            <div class="metric-row"><span>Ownership</span><span>{prop['ownership_pct']:.0f}%</span></div>
            <div class="metric-row"><span>Our Investment</span><span>{format_pkr(prop['our_investment'])}</span></div>
            <div class="metric-row"><span>Current Est. Value</span><span>{format_pkr(prop['current_estimated_value'])}</span></div>
            <div class="metric-row"><span>Expected Selling Price</span><span>{format_pkr(prop['expected_selling_price'])}</span></div>
            <div class="metric-row"><span>ROI</span><span style="color:{roi_color};">{format_pct(prop['roi_pct'])}</span></div>
            <div class="metric-row" style="border-bottom:none;"><span>Portfolio Share</span><span>{format_pct(portfolio_share)}</span></div>
            <div class="progress-outer"><div class="progress-inner" style="width:{progress_pct}%;"></div></div>
        </div>
    """, unsafe_allow_html=True)


def render_charts(df: pd.DataFrame):
    st.markdown('<div class="section-title">📈 Analytics</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("Add properties to see charts and analytics.")
        return

    plot_theme = "plotly_dark" if st.session_state.theme == "Dark" else "plotly_white"

    # Row 1: Cash vs Investment | Investment by Property
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        cash_df = get_cash_ledger_df()
        cash_now = settings["initial_cash"] + (cash_df["amount"].sum() if not cash_df.empty else 0.0)
        invested_now = df[df["status"].isin(["Available", "Under Construction"])]["our_investment"].sum()
        fig = go.Figure(data=[go.Bar(
            x=["Business Cash", "Money Invested"],
            y=[cash_now, invested_now],
            marker_color=[BLUE, PRIMARY],
            text=[format_pkr(cash_now), format_pkr(invested_now)],
            textposition="outside",
        )])
        fig.update_layout(title="Cash vs Investment", template=plot_theme, height=340,
                           margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with r1c2:
        inv_by_prop = df[["property_name", "our_investment"]].sort_values("our_investment", ascending=False)
        fig = px.bar(inv_by_prop, x="property_name", y="our_investment",
                     title="Investment by Property", template=plot_theme,
                     labels={"property_name": "Property", "our_investment": "Investment (PKR)"},
                     color_discrete_sequence=[PRIMARY])
        fig.update_layout(height=340, margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Row 2: Profit by Property | Property Status
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        sold_df = df[df["status"] == "Sold"]
        if sold_df.empty:
            st.info("No sold properties yet — profit chart will appear here.")
        else:
            colors = [GREEN if p >= 0 else RED for p in sold_df["profit"]]
            fig = go.Figure(data=[go.Bar(
                x=sold_df["property_name"], y=sold_df["profit"],
                marker_color=colors,
                text=[format_pkr(p) for p in sold_df["profit"]],
                textposition="outside",
            )])
            fig.update_layout(title="Profit by Property (Sold)", template=plot_theme, height=340,
                               margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with r2c2:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig = px.pie(status_counts, names="status", values="count", title="Property Status",
                     template=plot_theme, hole=0.45,
                     color="status", color_discrete_map=STATUS_COLORS)
        fig.update_layout(height=340, margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Row 3: Dealer Distribution | Ownership Distribution
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        dealer_counts = df[df["dealer"].notna() & (df["dealer"] != "")]["dealer"].value_counts().reset_index()
        dealer_counts.columns = ["dealer", "count"]
        if dealer_counts.empty:
            st.info("No dealer data yet.")
        else:
            fig = px.pie(dealer_counts, names="dealer", values="count", title="Dealer Distribution",
                         template=plot_theme, hole=0.45,
                         color_discrete_sequence=[PRIMARY, AMBER])
            fig.update_layout(height=340, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with r3c2:
        own_counts = df["ownership_pct"].value_counts().reset_index()
        own_counts.columns = ["ownership_pct", "count"]
        own_counts = own_counts.sort_values("ownership_pct")
        fig = px.bar(own_counts, x="ownership_pct", y="count", title="Ownership Distribution",
                     template=plot_theme, labels={"ownership_pct": "Ownership %", "count": "Properties"},
                     color_discrete_sequence=[PRIMARY])
        fig.update_layout(height=340, margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # Row 4: Business Net Worth Growth (cumulative) | Cash Flow
    r4c1, r4c2 = st.columns(2)
    cash_df = get_cash_ledger_df()
    with r4c1:
        if cash_df.empty:
            st.info("No cash flow yet.")
        else:
            cf = cash_df.copy()
            cf["entry_date"] = pd.to_datetime(cf["entry_date"], errors="coerce")
            cf = cf.sort_values("entry_date")
            cf["cumulative_cash"] = settings["initial_cash"] + cf["amount"].cumsum()
            fig = px.line(cf, x="entry_date", y="cumulative_cash", title="Business Net Worth / Cash Growth",
                          template=plot_theme, markers=True,
                          labels={"entry_date": "Date", "cumulative_cash": "Cash (PKR)"})
            fig.update_traces(line_color=PRIMARY)
            fig.update_layout(height=340, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)

    with r4c2:
        if cash_df.empty:
            st.info("No cash flow yet.")
        else:
            cf2 = cash_df.copy()
            cf2["type_label"] = cf2["entry_type"].map({"investment": "Investment (Out)", "sale": "Sale Proceeds (In)"}).fillna("Other")
            grouped = cf2.groupby("type_label")["amount"].sum().reset_index()
            colors_map = {"Investment (Out)": RED, "Sale Proceeds (In)": GREEN, "Other": SLATE}
            fig = go.Figure(data=[go.Bar(
                x=grouped["type_label"], y=grouped["amount"],
                marker_color=[colors_map.get(t, SLATE) for t in grouped["type_label"]],
                text=[format_pkr(a) for a in grouped["amount"]],
                textposition="outside",
            )])
            fig.update_layout(title="Cash Flow (In / Out)", template=plot_theme, height=340,
                               margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)


# =========================================================================
# PAGE: ADD PROPERTY
# =========================================================================

def page_add_property():
    st.markdown('<p class="app-title">➕ Add Property</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Register a new property investment. Cash updates automatically.</p>', unsafe_allow_html=True)
    st.write("")

    with st.form("add_property_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            property_name = st.text_input("Property Name*")
            location = st.text_input("Location")
            property_type = st.selectbox("Property Type", PROPERTY_TYPES)
            property_size = st.text_input("Property Size", placeholder="e.g. 5 Marla, 1 Kanal")
        with c2:
            purchase_date = st.date_input("Purchase Date", value=date.today())
            buying_price = st.number_input("Buying Price (PKR)*", min_value=0.0, step=100000.0)
            construction_cost = st.number_input("Construction Cost (PKR)", min_value=0.0, step=100000.0, value=0.0)
            ownership_pct = st.selectbox("Ownership Percentage*", OWNERSHIP_OPTIONS, index=len(OWNERSHIP_OPTIONS) - 1)
        with c3:
            current_estimated_value = st.number_input("Current Estimated Value (PKR)", min_value=0.0, step=100000.0)
            expected_selling_price = st.number_input("Expected Selling Price (PKR)", min_value=0.0, step=100000.0)
            dealer = st.selectbox("Dealer", DEALERS)
            status = st.selectbox("Status", STATUS_OPTIONS)

        commission_pct = st.number_input("Dealer Commission for this property (%)",
                                          min_value=0.0, max_value=100.0,
                                          value=float(settings["default_dealer_commission_pct"]), step=1.0)
        notes = st.text_area("Notes", placeholder="Any additional details...")

        total_cost_preview = buying_price + construction_cost
        our_investment_preview = total_cost_preview * ownership_pct / 100.0
        st.info(f"**Total Property Cost:** {format_pkr(total_cost_preview)}  |  "
                f"**Our Investment ({ownership_pct}%):** {format_pkr(our_investment_preview)}")

        submitted = st.form_submit_button("💾 Save Property", type="primary", use_container_width=True)

        if submitted:
            if not property_name.strip():
                st.error("Property Name is required.")
            elif buying_price <= 0:
                st.error("Buying Price must be greater than 0.")
            else:
                data = {
                    "property_name": property_name.strip(),
                    "location": location.strip(),
                    "property_type": property_type,
                    "property_size": property_size.strip(),
                    "purchase_date": purchase_date.isoformat(),
                    "buying_price": buying_price,
                    "construction_cost": construction_cost,
                    "ownership_pct": float(ownership_pct),
                    "current_estimated_value": current_estimated_value,
                    "expected_selling_price": expected_selling_price,
                    "actual_selling_price": 0.0,
                    "sold_date": None,
                    "dealer": dealer,
                    "status": status,
                    "notes": notes.strip(),
                    "dealer_commission_pct": commission_pct,
                }
                add_property(data)
                st.success(f"✅ Property '{property_name}' added. "
                           f"{format_pkr(our_investment_preview)} deducted from Business Cash.")
                st.rerun()


# =========================================================================
# PAGE: MANAGE PROPERTIES
# =========================================================================

def page_manage_properties():
    st.markdown('<p class="app-title">🗂️ Manage Properties</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Search, view, edit, and delete properties.</p>', unsafe_allow_html=True)
    st.write("")

    if df.empty:
        st.info("No properties yet. Add one from the 'Add Property' page.")
        return

    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        search = st.text_input("🔍 Search by name, location, or dealer")
    with fc2:
        status_filter = st.multiselect("Status", STATUS_OPTIONS)
    with fc3:
        dealer_filter = st.multiselect("Dealer", DEALERS)

    filtered = df.copy()
    if search:
        s = search.lower()
        filtered = filtered[
            filtered["property_name"].str.lower().str.contains(s, na=False) |
            filtered["location"].str.lower().str.contains(s, na=False) |
            filtered["dealer"].str.lower().str.contains(s, na=False)
        ]
    if status_filter:
        filtered = filtered[filtered["status"].isin(status_filter)]
    if dealer_filter:
        filtered = filtered[filtered["dealer"].isin(dealer_filter)]

    display_df = filtered[[
        "id", "property_name", "dealer", "location", "ownership_pct", "our_investment",
        "current_estimated_value", "actual_selling_price", "profit", "dealer_commission_amt",
        "jaffar_profit", "tehseen_profit", "roi_pct", "status"
    ]].rename(columns={
        "id": "ID", "property_name": "Property", "dealer": "Dealer", "location": "Location",
        "ownership_pct": "Ownership %", "our_investment": "Our Investment",
        "current_estimated_value": "Current Value", "actual_selling_price": "Selling Price",
        "profit": "Profit", "dealer_commission_amt": "Dealer Commission",
        "jaffar_profit": "Jaffar Profit", "tehseen_profit": "Tehseen Profit",
        "roi_pct": "ROI %", "status": "Status"
    })

    money_cols = ["Our Investment", "Current Value", "Selling Price", "Profit",
                  "Dealer Commission", "Jaffar Profit", "Tehseen Profit"]
    styled_df = display_df.copy()
    for c in money_cols:
        styled_df[c] = styled_df[c].apply(format_pkr)
    styled_df["Ownership %"] = styled_df["Ownership %"].apply(lambda v: f"{v:.0f}%")
    styled_df["ROI %"] = styled_df["ROI %"].apply(format_pct)

    st.dataframe(styled_df, use_container_width=True, hide_index=True, height=380)

    st.markdown('<div class="section-title">Property Actions</div>', unsafe_allow_html=True)
    prop_options = {f"#{row.id} — {row.property_name}": row.id for row in filtered.itertuples()}
    if not prop_options:
        st.info("No properties match your filters.")
        return

    selected_label = st.selectbox("Select a property to view / edit / delete", list(prop_options.keys()))
    selected_id = prop_options[selected_label]
    selected_row = df[df["id"] == selected_id].iloc[0]

    tab_view, tab_edit, tab_delete = st.tabs(["👁️ View", "✏️ Edit", "🗑️ Delete"])

    with tab_view:
        v1, v2, v3 = st.columns(3)
        with v1:
            st.markdown(f"**Property Name:** {selected_row['property_name']}")
            st.markdown(f"**Location:** {selected_row['location'] or '—'}")
            st.markdown(f"**Property Type:** {selected_row['property_type'] or '—'}")
            st.markdown(f"**Size:** {selected_row['property_size'] or '—'}")
            st.markdown(f"**Dealer:** {selected_row['dealer'] or '—'}")
        with v2:
            st.markdown(f"**Purchase Date:** {selected_row['purchase_date'] or '—'}")
            st.markdown(f"**Buying Price:** {format_pkr(selected_row['buying_price'])}")
            st.markdown(f"**Construction Cost:** {format_pkr(selected_row['construction_cost'])}")
            st.markdown(f"**Total Property Cost:** {format_pkr(selected_row['total_property_cost'])}")
            st.markdown(f"**Ownership:** {selected_row['ownership_pct']:.0f}%")
        with v3:
            st.markdown(f"**Our Investment:** {format_pkr(selected_row['our_investment'])}")
            st.markdown(f"**Current Estimated Value:** {format_pkr(selected_row['current_estimated_value'])}")
            st.markdown(f"**Expected Selling Price:** {format_pkr(selected_row['expected_selling_price'])}")
            status_color = GREEN if not selected_row["is_loss"] else RED
            st.markdown(f"**Status:** {selected_row['status']}")
            if selected_row["status"] == "Sold":
                profit_color = GREEN if selected_row["profit"] >= 0 else RED
                st.markdown(f"**Profit:** <span style='color:{profit_color}; font-weight:700;'>"
                            f"{format_pkr(selected_row['profit'])}</span>", unsafe_allow_html=True)
        if selected_row["notes"]:
            st.markdown(f"**Notes:** {selected_row['notes']}")

    with tab_edit:
        with st.form(f"edit_form_{selected_id}"):
            e1, e2, e3 = st.columns(3)
            with e1:
                property_name = st.text_input("Property Name*", value=selected_row["property_name"])
                location = st.text_input("Location", value=selected_row["location"] or "")
                property_type = st.selectbox("Property Type", PROPERTY_TYPES,
                                              index=PROPERTY_TYPES.index(selected_row["property_type"])
                                              if selected_row["property_type"] in PROPERTY_TYPES else 0)
                property_size = st.text_input("Property Size", value=selected_row["property_size"] or "")
            with e2:
                p_date = pd.to_datetime(selected_row["purchase_date"]).date() if selected_row["purchase_date"] else date.today()
                purchase_date = st.date_input("Purchase Date", value=p_date)
                buying_price = st.number_input("Buying Price (PKR)*", min_value=0.0, step=100000.0,
                                                value=float(selected_row["buying_price"]))
                construction_cost = st.number_input("Construction Cost (PKR)", min_value=0.0, step=100000.0,
                                                      value=float(selected_row["construction_cost"]))
                ownership_pct = st.selectbox("Ownership Percentage*", OWNERSHIP_OPTIONS,
                                              index=OWNERSHIP_OPTIONS.index(int(selected_row["ownership_pct"]))
                                              if int(selected_row["ownership_pct"]) in OWNERSHIP_OPTIONS else 7)
            with e3:
                current_estimated_value = st.number_input("Current Estimated Value (PKR)", min_value=0.0,
                                                            step=100000.0, value=float(selected_row["current_estimated_value"]))
                expected_selling_price = st.number_input("Expected Selling Price (PKR)", min_value=0.0,
                                                           step=100000.0, value=float(selected_row["expected_selling_price"]))
                dealer = st.selectbox("Dealer", DEALERS,
                                       index=DEALERS.index(selected_row["dealer"]) if selected_row["dealer"] in DEALERS else 0)
                status = st.selectbox("Status", STATUS_OPTIONS,
                                       index=STATUS_OPTIONS.index(selected_row["status"])
                                       if selected_row["status"] in STATUS_OPTIONS else 0)

            commission_pct = st.number_input("Dealer Commission (%)", min_value=0.0, max_value=100.0,
                                              value=float(selected_row["dealer_commission_pct"]), step=1.0)

            actual_selling_price = 0.0
            sold_date_val = None
            if status == "Sold":
                st.markdown("**Sale Details**")
                s1, s2 = st.columns(2)
                with s1:
                    actual_selling_price = st.number_input("Actual Selling Price (PKR)*", min_value=0.0,
                                                             step=100000.0,
                                                             value=float(selected_row["actual_selling_price"]))
                with s2:
                    sd_default = pd.to_datetime(selected_row["sold_date"]).date() if selected_row["sold_date"] else date.today()
                    sold_date_val = st.date_input("Sold Date", value=sd_default)

            notes = st.text_area("Notes", value=selected_row["notes"] or "")

            update_submitted = st.form_submit_button("💾 Update Property", type="primary", use_container_width=True)

            if update_submitted:
                if not property_name.strip():
                    st.error("Property Name is required.")
                elif status == "Sold" and actual_selling_price <= 0:
                    st.error("Actual Selling Price is required when status is Sold.")
                else:
                    new_data = {
                        "property_name": property_name.strip(),
                        "location": location.strip(),
                        "property_type": property_type,
                        "property_size": property_size.strip(),
                        "purchase_date": purchase_date.isoformat(),
                        "buying_price": buying_price,
                        "construction_cost": construction_cost,
                        "ownership_pct": float(ownership_pct),
                        "current_estimated_value": current_estimated_value,
                        "expected_selling_price": expected_selling_price,
                        "actual_selling_price": actual_selling_price if status == "Sold" else 0.0,
                        "sold_date": sold_date_val.isoformat() if status == "Sold" and sold_date_val else None,
                        "dealer": dealer,
                        "status": status,
                        "notes": notes.strip(),
                        "dealer_commission_pct": commission_pct,
                    }

                    record_sale_cash = status == "Sold"
                    sale_amount = actual_selling_price * ownership_pct / 100.0 if status == "Sold" else 0.0

                    update_property(
                        selected_id, new_data,
                        record_sale_cash=record_sale_cash,
                        sale_amount=sale_amount,
                        sale_date=sold_date_val.isoformat() if sold_date_val else None,
                        property_name=property_name.strip(),
                    )
                    st.success(f"✅ Property '{property_name}' updated.")
                    st.rerun()

    with tab_delete:
        st.warning(f"⚠️ You are about to permanently delete **{selected_row['property_name']}**. "
                   "This will also remove its cash ledger entries. This cannot be undone.")
        confirm = st.checkbox("I understand this action is permanent.")
        if st.button("🗑️ Delete Property", type="primary", disabled=not confirm):
            delete_property(selected_id)
            st.success("Property deleted.")
            st.rerun()


# =========================================================================
# PAGE: PORTFOLIO
# =========================================================================

def page_portfolio():
    st.markdown('<p class="app-title">💼 Portfolio</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Consolidated view of your entire real-estate portfolio.</p>', unsafe_allow_html=True)
    st.write("")

    if df.empty:
        st.info("No properties yet. Add one from the 'Add Property' page.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Current Cash", format_pkr(kpis["current_cash"]))
    with c2:
        kpi_card("Money Invested", format_pkr(kpis["money_invested"]))
    with c3:
        kpi_card("Portfolio Value", format_pkr(kpis["portfolio_value"]))
    with c4:
        kpi_card("Business Net Worth", format_pkr(kpis["business_net_worth"]))

    st.markdown('<div class="section-title">By Status</div>', unsafe_allow_html=True)
    tabs = st.tabs(["🟦 Available", "🟧 Under Construction", "🟩 Sold", "📋 All"])
    status_map = {0: "Available", 1: "Under Construction", 2: "Sold", 3: None}

    for i, tab in enumerate(tabs):
        with tab:
            status_val = status_map[i]
            sub_df = df if status_val is None else df[df["status"] == status_val]
            if sub_df.empty:
                st.info(f"No properties with status: {status_val or 'Any'}")
                continue
            cols_per_row = 3
            rows_of_props = [sub_df.iloc[j:j + cols_per_row] for j in range(0, len(sub_df), cols_per_row)]
            total_inv = sub_df["our_investment"].sum()
            for chunk in rows_of_props:
                cs = st.columns(cols_per_row)
                for k, (_, prop) in enumerate(chunk.iterrows()):
                    with cs[k]:
                        render_property_card(prop, total_inv if total_inv else 1)

    render_charts(df)


# =========================================================================
# PAGE: REPORTS
# =========================================================================

def page_reports():
    st.markdown('<p class="app-title">📑 Reports</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Generate and export detailed business reports.</p>', unsafe_allow_html=True)
    st.write("")

    if df.empty:
        st.info("No properties yet. Add one from the 'Add Property' page.")
        return

    report_names = [
        "Property Report", "Investment Report", "Profit Report", "Loss Report",
        "Dealer Report", "Jaffar Report", "Tehseen Report", "Portfolio Report",
        "Cash Flow Report", "Net Worth Report",
    ]
    report_choice = st.selectbox("Select Report", report_names)
    st.write("")

    sold_df = df[df["status"] == "Sold"]
    active_df = df[df["status"].isin(["Available", "Under Construction"])]

    def money_format(d, cols):
        d = d.copy()
        for c in cols:
            if c in d.columns:
                d[c] = d[c].apply(format_pkr)
        return d

    if report_choice == "Property Report":
        report_df = df[["property_name", "location", "property_type", "status", "dealer",
                         "purchase_date", "buying_price", "construction_cost",
                         "total_property_cost", "ownership_pct", "our_investment"]].rename(columns={
            "property_name": "Property", "location": "Location", "property_type": "Type",
            "status": "Status", "dealer": "Dealer", "purchase_date": "Purchase Date",
            "buying_price": "Buying Price", "construction_cost": "Construction Cost",
            "total_property_cost": "Total Cost", "ownership_pct": "Ownership %",
            "our_investment": "Our Investment"
        })
        st.dataframe(money_format(report_df, ["Buying Price", "Construction Cost", "Total Cost", "Our Investment"]),
                     use_container_width=True, hide_index=True)
        download_button_row(report_df, "property_report", "prop_rep", "Property Report")

    elif report_choice == "Investment Report":
        report_df = active_df[["property_name", "status", "buying_price", "construction_cost",
                                "ownership_pct", "our_investment", "current_estimated_value"]].rename(columns={
            "property_name": "Property", "status": "Status", "buying_price": "Buying Price",
            "construction_cost": "Construction Cost", "ownership_pct": "Ownership %",
            "our_investment": "Our Investment", "current_estimated_value": "Current Value"
        })
        total_row = pd.DataFrame([{
            "Property": "TOTAL", "Status": "", "Buying Price": report_df["Buying Price"].sum(),
            "Construction Cost": report_df["Construction Cost"].sum(), "Ownership %": "",
            "Our Investment": report_df["Our Investment"].sum(),
            "Current Value": report_df["Current Value"].sum()
        }]) if not report_df.empty else pd.DataFrame()
        full = pd.concat([report_df, total_row], ignore_index=True) if not report_df.empty else report_df
        st.dataframe(money_format(full, ["Buying Price", "Construction Cost", "Our Investment", "Current Value"]),
                     use_container_width=True, hide_index=True)
        download_button_row(report_df, "investment_report", "inv_rep", "Investment Report")

    elif report_choice == "Profit Report":
        profit_df = sold_df[sold_df["profit"] > 0][[
            "property_name", "actual_selling_price", "our_selling_amount", "our_investment",
            "profit", "dealer_commission_amt", "jaffar_profit", "tehseen_profit", "sold_date"
        ]].rename(columns={
            "property_name": "Property", "actual_selling_price": "Selling Price",
            "our_selling_amount": "Our Selling Amount", "our_investment": "Our Investment",
            "profit": "Profit", "dealer_commission_amt": "Dealer Commission",
            "jaffar_profit": "Jaffar Profit", "tehseen_profit": "Tehseen Profit",
            "sold_date": "Sold Date"
        })
        if profit_df.empty:
            st.info("No profitable sales yet.")
        else:
            st.dataframe(money_format(profit_df, ["Selling Price", "Our Selling Amount", "Our Investment",
                                                    "Profit", "Dealer Commission", "Jaffar Profit", "Tehseen Profit"]),
                         use_container_width=True, hide_index=True)
        download_button_row(profit_df, "profit_report", "profit_rep", "Profit Report")

    elif report_choice == "Loss Report":
        loss_df = sold_df[sold_df["profit"] < 0][[
            "property_name", "actual_selling_price", "our_selling_amount", "our_investment",
            "profit", "sold_date"
        ]].rename(columns={
            "property_name": "Property", "actual_selling_price": "Selling Price",
            "our_selling_amount": "Our Selling Amount", "our_investment": "Our Investment",
            "profit": "Loss", "sold_date": "Sold Date"
        })
        if loss_df.empty:
            st.success("No losses recorded. 🎉")
        else:
            styled = money_format(loss_df, ["Selling Price", "Our Selling Amount", "Our Investment", "Loss"])
            st.dataframe(styled, use_container_width=True, hide_index=True)
        download_button_row(loss_df, "loss_report", "loss_rep", "Loss Report")

    elif report_choice == "Dealer Report":
        if sold_df.empty:
            st.info("No sold properties yet.")
            dealer_df = pd.DataFrame(columns=["Dealer", "Properties Sold", "Total Commission"])
        else:
            dealer_df = sold_df.groupby("dealer").agg(
                Properties_Sold=("id", "count"),
                Total_Commission=("dealer_commission_amt", "sum")
            ).reset_index().rename(columns={"dealer": "Dealer", "Properties_Sold": "Properties Sold",
                                             "Total_Commission": "Total Commission"})
        st.dataframe(money_format(dealer_df, ["Total Commission"]), use_container_width=True, hide_index=True)
        download_button_row(dealer_df, "dealer_report", "dealer_rep", "Dealer Report")

    elif report_choice == "Jaffar Report":
        jaffar_df = sold_df[sold_df["jaffar_profit"] != 0][[
            "property_name", "sold_date", "profit", "jaffar_profit"
        ]].rename(columns={"property_name": "Property", "sold_date": "Sold Date",
                            "profit": "Total Profit", "jaffar_profit": "Jaffar Share"})
        total = jaffar_df["Jaffar Share"].sum() if not jaffar_df.empty else 0
        st.metric("Total Jaffar Earnings (Realized)", format_pkr(total))
        st.dataframe(money_format(jaffar_df, ["Total Profit", "Jaffar Share"]) if not jaffar_df.empty else jaffar_df,
                     use_container_width=True, hide_index=True)
        download_button_row(jaffar_df, "jaffar_report", "jaffar_rep", "Jaffar Report")

    elif report_choice == "Tehseen Report":
        tehseen_df = sold_df[sold_df["tehseen_profit"] != 0][[
            "property_name", "sold_date", "profit", "tehseen_profit"
        ]].rename(columns={"property_name": "Property", "sold_date": "Sold Date",
                            "profit": "Total Profit", "tehseen_profit": "Tehseen Share"})
        total = tehseen_df["Tehseen Share"].sum() if not tehseen_df.empty else 0
        st.metric("Total Tehseen Earnings (Realized)", format_pkr(total))
        st.dataframe(money_format(tehseen_df, ["Total Profit", "Tehseen Share"]) if not tehseen_df.empty else tehseen_df,
                     use_container_width=True, hide_index=True)
        download_button_row(tehseen_df, "tehseen_report", "tehseen_rep", "Tehseen Report")

    elif report_choice == "Portfolio Report":
        report_df = df[["property_name", "status", "dealer", "ownership_pct", "our_investment",
                         "current_estimated_value", "roi_pct"]].rename(columns={
            "property_name": "Property", "status": "Status", "dealer": "Dealer",
            "ownership_pct": "Ownership %", "our_investment": "Our Investment",
            "current_estimated_value": "Current Value", "roi_pct": "ROI %"
        })
        styled = money_format(report_df, ["Our Investment", "Current Value"])
        styled["ROI %"] = styled["ROI %"].apply(format_pct)
        st.dataframe(styled, use_container_width=True, hide_index=True)
        download_button_row(report_df, "portfolio_report", "portfolio_rep", "Portfolio Report")

    elif report_choice == "Cash Flow Report":
        cash_df = get_cash_ledger_df()
        if cash_df.empty:
            st.info("No cash flow entries yet.")
        else:
            display = cash_df[["entry_date", "description", "entry_type", "amount"]].rename(columns={
                "entry_date": "Date", "description": "Description", "entry_type": "Type", "amount": "Amount"
            })
            styled = display.copy()
            styled["Amount"] = styled["Amount"].apply(format_pkr)
            st.dataframe(styled, use_container_width=True, hide_index=True)
            download_button_row(display, "cash_flow_report", "cash_rep", "Cash Flow Report")

    elif report_choice == "Net Worth Report":
        nw_data = pd.DataFrame([
            {"Metric": "Business Net Worth", "Value": kpis["business_net_worth"]},
            {"Metric": "Business Cash", "Value": kpis["current_cash"]},
            {"Metric": "Portfolio Value (Active)", "Value": kpis["portfolio_value"]},
            {"Metric": "Money Invested (Active)", "Value": kpis["money_invested"]},
            {"Metric": "Total Realized Profit", "Value": kpis["total_profit"]},
            {"Metric": "Total Loss", "Value": kpis["total_loss"]},
            {"Metric": "Dealer Earnings", "Value": kpis["dealer_earnings"]},
            {"Metric": "Jaffar Net Worth", "Value": kpis["jaffar_net_worth"]},
            {"Metric": "Tehseen Net Worth", "Value": kpis["tehseen_net_worth"]},
        ])
        styled = nw_data.copy()
        styled["Value"] = styled["Value"].apply(format_pkr)
        st.dataframe(styled, use_container_width=True, hide_index=True)
        download_button_row(nw_data, "net_worth_report", "nw_rep", "Net Worth Report")


# =========================================================================
# PAGE: BUSINESS SETTINGS
# =========================================================================

def page_business_settings():
    st.markdown('<p class="app-title">⚙️ Business Settings</p>', unsafe_allow_html=True)
    st.markdown('<p class="app-subtitle">Update your business configuration.</p>', unsafe_allow_html=True)
    st.write("")

    with st.form("settings_form"):
        c1, c2 = st.columns(2)
        with c1:
            business_name = st.text_input("Business Name*", value=settings["business_name"])
            initial_cash = st.number_input("Initial Business Cash (PKR)", min_value=0.0, step=100000.0,
                                            value=float(settings["initial_cash"]))
            initial_net_worth = st.number_input("Initial Business Net Worth (PKR)", min_value=0.0, step=100000.0,
                                                 value=float(settings["initial_net_worth"]))
        with c2:
            jaffar_nw = st.number_input("Jaffar Initial Net Worth (PKR)", min_value=0.0, step=100000.0,
                                         value=float(settings["jaffar_initial_net_worth"]))
            tehseen_nw = st.number_input("Tehseen Initial Net Worth (PKR)", min_value=0.0, step=100000.0,
                                          value=float(settings["tehseen_initial_net_worth"]))
            default_commission = st.number_input("Default Dealer Commission (%)", min_value=0.0, max_value=100.0,
                                                   value=float(settings["default_dealer_commission_pct"]), step=1.0)

        submitted = st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True)
        if submitted:
            if not business_name.strip():
                st.error("Business Name is required.")
            else:
                update_settings(
                    business_name=business_name.strip(),
                    initial_cash=initial_cash,
                    initial_net_worth=initial_net_worth,
                    jaffar_initial_net_worth=jaffar_nw,
                    tehseen_initial_net_worth=tehseen_nw,
                    default_dealer_commission_pct=default_commission,
                )
                st.success("✅ Settings updated.")
                st.rerun()

    st.markdown('<div class="section-title">⚠️ Danger Zone</div>', unsafe_allow_html=True)
    with st.expander("Reset all data (properties + cash ledger)"):
        st.warning("This deletes ALL properties and cash ledger entries permanently. Settings are kept.")
        confirm_reset = st.checkbox("I understand this will permanently delete all property data.")
        if st.button("🗑️ Reset All Property Data", disabled=not confirm_reset):
            with get_conn() as conn:
                conn.execute("DELETE FROM cash_ledger")
                conn.execute("DELETE FROM properties")
            st.success("All property data has been reset.")
            st.rerun()


# =========================================================================
# ROUTER
# =========================================================================

if page == "📊 Dashboard":
    page_dashboard()
elif page == "➕ Add Property":
    page_add_property()
elif page == "🗂️ Manage Properties":
    page_manage_properties()
elif page == "💼 Portfolio":
    page_portfolio()
elif page == "📑 Reports":
    page_reports()
elif page == "⚙️ Business Settings":
    page_business_settings()
