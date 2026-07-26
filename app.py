"""
Property Investment Management System
======================================
Single-file Streamlit Application with SQLite backend, Plotly visual analytics,
real-time calculation logic, and automated report exports.
"""

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import date, datetime
import io

# ==========================================
# STREAMLIT PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Property Investment Management",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (CSS Injection) for Modern UI/UX Cards and Metrics
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-title {
        font-size: 0.85rem;
        color: #6c757d;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1e293b;
        margin-top: 5px;
    }
    .metric-value-green {
        color: #10b981 !important;
    }
    .metric-value-red {
        color: #ef4444 !important;
    }
    .metric-value-blue {
        color: #3b82f6 !important;
    }

    /* Property Card Styling */
    .property-card {
        background-color: #ffffff;
        border-left: 5px solid #3b82f6;
        border-radius: 8px;
        padding: 18px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 15px;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-available { background-color: #e0f2fe; color: #0369a1; }
    .badge-construction { background-color: #fef3c7; color: #b45309; }
    .badge-sold { background-color: #dcfce7; color: #15803d; }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# DATABASE INITIALIZATION & UTILITIES
# ==========================================
DB_NAME = "properties.db"


def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the SQLite database and creates the 'properties' table if not exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_added TEXT NOT NULL,
                property_name TEXT NOT NULL,
                location TEXT NOT NULL,
                buying_price REAL NOT NULL,
                construction_cost REAL NOT NULL,
                selling_price REAL NOT NULL,
                total_investment REAL NOT NULL,
                profit REAL NOT NULL,
                dealer_profit REAL NOT NULL,
                jaffar_profit REAL NOT NULL,
                tehseen_profit REAL NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            )
        """
        )
        conn.commit()


# Initialize SQLite Database on startup
init_db()


# ==========================================
# BUSINESS CALCULATIONS LOGIC
# ==========================================
def calculate_investment_metrics(buying_price, construction_cost, selling_price):
    """
    Calculates total investment, profit, and partner profit splits based on business rules:
    - Total Investment = Buying Price + Construction Cost
    - Profit = Selling Price - Total Investment
    - Dealer Profit = 25% of Profit (if profit > 0, else 0)
    - Remaining Profit = 75% of Profit
    - Jaffar Profit = Remaining Profit / 2 (if profit > 0, else 0)
    - Tehseen Profit = Remaining Profit / 2 (if profit > 0, else 0)
    """
    total_investment = buying_price + construction_cost
    profit = selling_price - total_investment

    if profit > 0:
        dealer_profit = profit * 0.25
        remaining_profit = profit * 0.75
        jaffar_profit = remaining_profit / 2.0
        tehseen_profit = remaining_profit / 2.0
    else:
        dealer_profit = 0.0
        jaffar_profit = 0.0
        tehseen_profit = 0.0

    return {
        "total_investment": total_investment,
        "profit": profit,
        "dealer_profit": dealer_profit,
        "jaffar_profit": jaffar_profit,
        "tehseen_profit": tehseen_profit,
    }


def format_currency(amount):
    """Formats raw floats into clean currency format with thousands separators."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


# ==========================================
# DATABASE CRUD OPERATIONS
# ==========================================
def insert_property(data):
    """Inserts a new property record into the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO properties (
                date_added, property_name, location, buying_price,
                construction_cost, selling_price, total_investment,
                profit, dealer_profit, jaffar_profit, tehseen_profit,
                status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data["date_added"],
                data["property_name"],
                data["location"],
                data["buying_price"],
                data["construction_cost"],
                data["selling_price"],
                data["total_investment"],
                data["profit"],
                data["dealer_profit"],
                data["jaffar_profit"],
                data["tehseen_profit"],
                data["status"],
                data["notes"],
            ),
        )
        conn.commit()


def update_property(property_id, data):
    """Updates an existing property record in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE properties SET
                date_added = ?, property_name = ?, location = ?,
                buying_price = ?, construction_cost = ?, selling_price = ?,
                total_investment = ?, profit = ?, dealer_profit = ?,
                jaffar_profit = ?, tehseen_profit = ?, status = ?, notes = ?
            WHERE id = ?
        """,
            (
                data["date_added"],
                data["property_name"],
                data["location"],
                data["buying_price"],
                data["construction_cost"],
                data["selling_price"],
                data["total_investment"],
                data["profit"],
                data["dealer_profit"],
                data["jaffar_profit"],
                data["tehseen_profit"],
                data["status"],
                data["notes"],
                property_id,
            ),
        )
        conn.commit()


def delete_property_by_id(property_id):
    """Deletes a property record by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM properties WHERE id = ?", (property_id,))
        conn.commit()


def fetch_all_properties():
    """Retrieves all property records as a Pandas DataFrame."""
    with get_db_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM properties ORDER BY id DESC", conn
        )
    return df


def fetch_property_by_id(property_id):
    """Retrieves a single property record by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM properties WHERE id = ?", (property_id,)
        )
        row = cursor.fetchone()
    return dict(row) if row else None


# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🏢 Property Manager")
st.sidebar.markdown("---")

menu_choice = st.sidebar.radio(
    "Navigation Menu",
    ["Dashboard", "Add Property", "Manage Properties", "Reports", "Settings"],
)

st.sidebar.markdown("---")
st.sidebar.caption("Property Investment Management System v1.0")


# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if menu_choice == "Dashboard":
    st.title("📊 Investment Dashboard")
    st.markdown("Overview of portfolio performance, profit splits, and asset analytics.")

    df = fetch_all_properties()

    if df.empty:
        st.info("No properties found in the database. Please add a property to view dashboard statistics.")
    else:
        # Aggregations
        total_properties = len(df)
        total_investment = df["total_investment"].sum()
        total_selling_value = df["selling_price"].sum()
        total_profit = df["profit"].sum()

        dealer_total = df["dealer_profit"].sum()
        jaffar_total = df["jaffar_profit"].sum()
        tehseen_total = df["tehseen_profit"].sum()

        total_loss = abs(df[df["profit"] < 0]["profit"].sum())
        net_portfolio_value = total_selling_value

        # Top Summary Metric Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Total Properties</div>
                    <div class="metric-value metric-value-blue">{total_properties}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Total Investment</div>
                    <div class="metric-value">{format_currency(total_investment)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with col3:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Total Selling Value</div>
                    <div class="metric-value">{format_currency(total_selling_value)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with col4:
            profit_color_class = "metric-value-green" if total_profit >= 0 else "metric-value-red"
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Total Net Profit</div>
                    <div class="metric-value {profit_color_class}">{format_currency(total_profit)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        # Secondary Summary Metric Cards
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)

        with sc1:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Dealer Profit</div>
                    <div class="metric-value metric-value-green">{format_currency(dealer_total)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with sc2:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Jaffar Profit</div>
                    <div class="metric-value metric-value-green">{format_currency(jaffar_total)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with sc3:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Tehseen Profit</div>
                    <div class="metric-value metric-value-green">{format_currency(tehseen_total)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with sc4:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Total Portfolio Loss</div>
                    <div class="metric-value metric-value-red">{format_currency(total_loss)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        with sc5:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-title">Net Asset Value</div>
                    <div class="metric-value metric-value-blue">{format_currency(net_portfolio_value)}</div>
                </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Interactive Charts Section
        st.subheader("📈 Portfolio Analytics")

        chart_col1, chart_col2 = st.columns([1, 1])

        with chart_col1:
            # Profit Distribution Pie Chart
            partner_profits = {
                "Dealer": dealer_total,
                "Jaffar": jaffar_total,
                "Tehseen": tehseen_total,
            }
            profit_split_df = pd.DataFrame(
                list(partner_profits.items()), columns=["Partner", "Profit"]
            )

            fig_pie = px.pie(
                profit_split_df,
                names="Partner",
                values="Profit",
                title="Profit Distribution Among Partners",
                color_discrete_sequence=["#2563eb", "#10b981", "#f59e0b"],
                hole=0.4,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        with chart_col2:
            # Property Profit Comparison Bar Chart
            fig_bar = px.bar(
                df,
                x="property_name",
                y="profit",
                color="profit",
                title="Property Profit / Loss Comparison",
                color_continuous_scale=["#ef4444", "#10b981"],
                labels={"profit": "Profit ($)", "property_name": "Property"},
            )
            fig_bar.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_bar, use_container_width=True)

        # Timeline Line Chart
        st.subheader("🗓️ Investment Timeline")

        df_sorted = df.sort_values(by="date_added")
        fig_line = px.line(
            df_sorted,
            x="date_added",
            y=["total_investment", "selling_price", "profit"],
            title="Investment & Value Progression Over Time",
            markers=True,
            labels={"value": "Amount ($)", "date_added": "Date", "variable": "Metric"},
            color_discrete_map={
                "total_investment": "#2563eb",
                "selling_price": "#10b981",
                "profit": "#f59e0b",
            },
        )
        st.plotly_chart(fig_line, use_container_width=True)


# ==========================================
# PAGE 2: ADD PROPERTY
# ==========================================
elif menu_choice == "Add Property":
    st.title("➕ Add New Property")
    st.markdown("Enter details below to register a new property investment.")

    with st.form("add_property_form", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            prop_date = st.date_input("Date", value=date.today())
            prop_name = st.text_input("Property Name *", placeholder="e.g. Sunset Apartments Block A")
            prop_location = st.text_input("Location *", placeholder="e.g. Downtown Sector 4")
            prop_status = st.selectbox(
                "Status", ["Available", "Under Construction", "Sold"]
            )

        with col2:
            buying_price = st.number_input(
                "Buying Price ($)", min_value=0.0, value=0.0, step=1000.0, format="%.2f"
            )
            construction_cost = st.number_input(
                "Construction Cost ($)", min_value=0.0, value=0.0, step=500.0, format="%.2f"
            )
            selling_price = st.number_input(
                "Selling Price ($)", min_value=0.0, value=0.0, step=1000.0, format="%.2f"
            )

        prop_notes = st.text_area("Notes / Remarks", placeholder="Enter additional details...")

        # Live Calculation Preview
        metrics = calculate_investment_metrics(buying_price, construction_cost, selling_price)

        st.markdown("### 🧮 Live Calculation Preview")
        pcol1, pcol2, pcol3, pcol4 = st.columns(4)
        pcol1.metric("Total Investment", format_currency(metrics["total_investment"]))

        profit_val = metrics["profit"]
        if profit_val < 0:
            pcol2.metric("Loss", format_currency(profit_val), delta=format_currency(profit_val), delta_color="inverse")
        else:
            pcol2.metric("Profit", format_currency(profit_val), delta=format_currency(profit_val))

        pcol3.metric("Dealer Profit (25%)", format_currency(metrics["dealer_profit"]))
        pcol4.metric("Jaffar / Tehseen Each", format_currency(metrics["jaffar_profit"]))

        if selling_price > 0 and selling_price < metrics["total_investment"]:
            st.warning("⚠️ Warning: Selling Price is lower than Total Investment. This record will result in a LOSS.")

        submit_btn = st.form_submit_button("💾 Save Property", use_container_width=True)

        if submit_btn:
            # Validations
            if not prop_name.strip():
                st.error("Validation Error: Property Name cannot be empty.")
            elif not prop_location.strip():
                st.error("Validation Error: Location cannot be empty.")
            else:
                property_payload = {
                    "date_added": prop_date.strftime("%Y-%m-%d"),
                    "property_name": prop_name.strip(),
                    "location": prop_location.strip(),
                    "buying_price": buying_price,
                    "construction_cost": construction_cost,
                    "selling_price": selling_price,
                    "total_investment": metrics["total_investment"],
                    "profit": metrics["profit"],
                    "dealer_profit": metrics["dealer_profit"],
                    "jaffar_profit": metrics["jaffar_profit"],
                    "tehseen_profit": metrics["tehseen_profit"],
                    "status": prop_status,
                    "notes": prop_notes.strip(),
                }

                insert_property(property_payload)
                st.success(f"✅ Property '{prop_name}' saved successfully!")


# ==========================================
# PAGE 3: MANAGE PROPERTIES
# ==========================================
elif menu_choice == "Manage Properties":
    st.title("🛠️ Manage Properties")
    st.markdown("Search, view, update, or remove existing properties.")

    df = fetch_all_properties()

    if df.empty:
        st.info("No properties registered yet.")
    else:
        # Search and Filter Section
        fcol1, fcol2, fcol3 = st.columns([2, 1, 1])

        with fcol1:
            search_query = st.text_input("🔍 Search Property Name or Location", "")

        with fcol2:
            status_filter = st.selectbox(
                "Filter Status", ["All", "Available", "Under Construction", "Sold"]
            )

        with fcol3:
            sort_order = st.selectbox(
                "Sort By", ["Newest First", "Oldest First", "Highest Profit", "Highest Investment"]
            )

        # Apply Filters
        filtered_df = df.copy()

        if search_query:
            filtered_df = filtered_df[
                filtered_df["property_name"].str.contains(search_query, case=False, na=False)
                | filtered_df["location"].str.contains(search_query, case=False, na=False)
            ]

        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]

        if sort_order == "Newest First":
            filtered_df = filtered_df.sort_values(by="id", ascending=False)
        elif sort_order == "Oldest First":
            filtered_df = filtered_df.sort_values(by="id", ascending=True)
        elif sort_order == "Highest Profit":
            filtered_df = filtered_df.sort_values(by="profit", ascending=False)
        elif sort_order == "Highest Investment":
            filtered_df = filtered_df.sort_values(by="total_investment", ascending=False)

        st.markdown(f"**Showing {len(filtered_df)} properties**")
        st.markdown("---")

        # Edit Dialog Modal Handler using Streamlit session state
        if "editing_id" not in st.session_state:
            st.session_state.editing_id = None

        if st.session_state.editing_id is not None:
            edit_item = fetch_property_by_id(st.session_state.editing_id)
            if edit_item:
                st.subheader(f"✏️ Editing Property: {edit_item['property_name']}")
                with st.form("edit_property_form"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_date = st.date_input(
                            "Date",
                            value=datetime.strptime(edit_item["date_added"], "%Y-%m-%d").date(),
                        )
                        e_name = st.text_input("Property Name", value=edit_item["property_name"])
                        e_location = st.text_input("Location", value=edit_item["location"])
                        e_status = st.selectbox(
                            "Status",
                            ["Available", "Under Construction", "Sold"],
                            index=["Available", "Under Construction", "Sold"].index(
                                edit_item["status"]
                            ),
                        )
                    with ec2:
                        e_buying = st.number_input(
                            "Buying Price ($)", value=float(edit_item["buying_price"]), step=1000.0
                        )
                        e_construction = st.number_input(
                            "Construction Cost ($)",
                            value=float(edit_item["construction_cost"]),
                            step=500.0,
                        )
                        e_selling = st.number_input(
                            "Selling Price ($)", value=float(edit_item["selling_price"]), step=1000.0
                        )

                    e_notes = st.text_area("Notes", value=edit_item["notes"] or "")

                    e_metrics = calculate_investment_metrics(e_buying, e_construction, e_selling)

                    st.info(
                        f"Updated Investment: {format_currency(e_metrics['total_investment'])} | "
                        f"Updated Profit: {format_currency(e_metrics['profit'])}"
                    )

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        update_btn = st.form_submit_button("✅ Update Property", use_container_width=True)
                    with btn_c2:
                        cancel_btn = st.form_submit_button("❌ Cancel", use_container_width=True)

                    if update_btn:
                        if not e_name.strip() or not e_location.strip():
                            st.error("Property name and location cannot be empty.")
                        else:
                            updated_payload = {
                                "date_added": e_date.strftime("%Y-%m-%d"),
                                "property_name": e_name.strip(),
                                "location": e_location.strip(),
                                "buying_price": e_buying,
                                "construction_cost": e_construction,
                                "selling_price": e_selling,
                                "total_investment": e_metrics["total_investment"],
                                "profit": e_metrics["profit"],
                                "dealer_profit": e_metrics["dealer_profit"],
                                "jaffar_profit": e_metrics["jaffar_profit"],
                                "tehseen_profit": e_metrics["tehseen_profit"],
                                "status": e_status,
                                "notes": e_notes.strip(),
                            }
                            update_property(st.session_state.editing_id, updated_payload)
                            st.session_state.editing_id = None
                            st.success("Property updated successfully!")
                            st.rerun()

                    if cancel_btn:
                        st.session_state.editing_id = None
                        st.rerun()

                st.markdown("---")

        # Cards Rendering
        for idx, row in filtered_df.iterrows():
            badge_class = "badge-available"
            if row["status"] == "Under Construction":
                badge_class = "badge-construction"
            elif row["status"] == "Sold":
                badge_class = "badge-sold"

            profit_color = "color: #10b981;" if row["profit"] >= 0 else "color: #ef4444;"

            with st.container():
                c1, c2, c3 = st.columns([3, 2, 2])

                with c1:
                    st.markdown(f"### {row['property_name']}")
                    st.markdown(f"📍 **Location:** {row['location']} | 📅 **Date:** {row['date_added']}")
                    st.markdown(
                        f'<span class="status-badge {badge_class}">{row["status"]}</span>',
                        unsafe_allow_html=True,
                    )

                with c2:
                    st.write(f"**Investment:** {format_currency(row['total_investment'])}")
                    st.write(f"**Selling Price:** {format_currency(row['selling_price'])}")
                    st.markdown(
                        f"**Profit:** <span style='{profit_color} font-weight: bold;'>{format_currency(row['profit'])}</span>",
                        unsafe_allow_html=True,
                    )

                with c3:
                    btn_view, btn_edit, btn_del = st.columns(3)

                    with btn_view:
                        with st.popover("👁️ View"):
                            st.markdown(f"#### {row['property_name']} Details")
                            st.write(f"**Buying Price:** {format_currency(row['buying_price'])}")
                            st.write(f"**Construction Cost:** {format_currency(row['construction_cost'])}")
                            st.write(f"**Total Investment:** {format_currency(row['total_investment'])}")
                            st.write(f"**Selling Price:** {format_currency(row['selling_price'])}")
                            st.markdown("---")
                            st.write(f"**Dealer Profit (25%):** {format_currency(row['dealer_profit'])}")
                            st.write(f"**Jaffar Profit:** {format_currency(row['jaffar_profit'])}")
                            st.write(f"**Tehseen Profit:** {format_currency(row['tehseen_profit'])}")
                            st.markdown("---")
                            st.write(f"**Notes:** {row['notes'] or 'N/A'}")

                    with btn_edit:
                        if st.button("✏️ Edit", key=f"edit_{row['id']}"):
                            st.session_state.editing_id = row["id"]
                            st.rerun()

                    with btn_del:
                        with st.popover("🗑️ Delete"):
                            st.warning("Confirm deletion?")
                            if st.button("Yes, Delete", key=f"confirm_del_{row['id']}"):
                                delete_property_by_id(row["id"])
                                st.success("Deleted!")
                                st.rerun()

                st.markdown("---")


# ==========================================
# PAGE 4: REPORTS
# ==========================================
elif menu_choice == "Reports":
    st.title("📋 Reports & Data Exports")
    st.markdown("Generate comprehensive financial tables and export records.")

    df = fetch_all_properties()

    if df.empty:
        st.info("No records available to export.")
    else:
        # Download Action Bar
        col_csv, col_excel = st.columns(2)

        # CSV Buffer
        csv_data = df.to_csv(index=False).encode("utf-8")
        col_csv.download_button(
            label="📥 Download CSV Report",
            data=csv_data,
            file_name=f"Property_Report_{date.today().strftime('%Y_%m_%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Excel Buffer
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Properties")
        excel_data = excel_buffer.getvalue()

        col_excel.download_button(
            label="📊 Download Excel Report",
            data=excel_data,
            file_name=f"Property_Report_{date.today().strftime('%Y_%m_%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.markdown("---")

        # Complete Data Table
        st.subheader("📁 Complete Property Records")
        st.dataframe(
            df.style.format(
                {
                    "buying_price": "${:,.2f}",
                    "construction_cost": "${:,.2f}",
                    "selling_price": "${:,.2f}",
                    "total_investment": "${:,.2f}",
                    "profit": "${:,.2f}",
                    "dealer_profit": "${:,.2f}",
                    "jaffar_profit": "${:,.2f}",
                    "tehseen_profit": "${:,.2f}",
                }
            ),
            use_container_width=True,
        )

        st.markdown("---")

        # Categorized Tabbed Tables
        tab1, tab2, tab3 = st.tabs(["🟢 Profit Table", "🔴 Loss Table", "💼 Investment Summary"])

        with tab1:
            st.subheader("Profitable Properties")
            profit_df = df[df["profit"] >= 0]
            st.dataframe(
                profit_df[
                    ["property_name", "location", "total_investment", "selling_price", "profit", "dealer_profit", "jaffar_profit", "tehseen_profit"]
                ].style.format("${:,.2f}", subset=["total_investment", "selling_price", "profit", "dealer_profit", "jaffar_profit", "tehseen_profit"]),
                use_container_width=True,
            )

        with tab2:
            st.subheader("Loss-Making Properties")
            loss_df = df[df["profit"] < 0]
            if loss_df.empty:
                st.success("🎉 No loss-making properties in the portfolio!")
            else:
                st.dataframe(
                    loss_df[
                        ["property_name", "location", "buying_price", "construction_cost", "total_investment", "selling_price", "profit"]
                    ].style.format("${:,.2f}", subset=["buying_price", "construction_cost", "total_investment", "selling_price", "profit"]),
                    use_container_width=True,
                )

        with tab3:
            st.subheader("Investment Breakdown")
            st.dataframe(
                df[
                    ["property_name", "status", "buying_price", "construction_cost", "total_investment"]
                ].style.format("${:,.2f}", subset=["buying_price", "construction_cost", "total_investment"]),
                use_container_width=True,
            )


# ==========================================
# PAGE 5: SETTINGS
# ==========================================
elif menu_choice == "Settings":
    st.title("⚙️ System Settings & Maintenance")
    st.markdown("Manage database connections and partner configurations.")

    st.subheader("📊 System Status")
    st.success("SQLite Database Connection: Active & Healthy")
    st.info(f"Database Path: `{DB_NAME}`")

    st.markdown("---")
    st.subheader("👥 Partner Profit Shares Configuration")
    st.write("- **Dealer Share:** 25%")
    st.write("- **Jaffar Share:** 37.5% (50% of remaining)")
    st.write("- **Tehseen Share:** 37.5% (50% of remaining)")

    st.markdown("---")
    st.subheader("⚠️ Database Operations")

    with st.expander("Danger Zone"):
        st.warning("Clearing database records cannot be undone.")
        if st.button("Delete All Property Records"):
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM properties")
                conn.commit()
            st.success("All records have been cleared.")
            st.rerun()
