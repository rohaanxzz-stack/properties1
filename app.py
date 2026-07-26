import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="Property Investment Dashboard",
    page_icon="🏢",
    layout="wide"
)

st.title("🏢 Property Investment, Profit & Loss Dashboard")
st.markdown("Manage your properties, investments and profits.")

# ---------------------------------------------
# Initialize Session State
# ---------------------------------------------
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame({
        "Date": [date.today()],
        "Property Name": [""],
        "Buying Price": [0.0],
        "Construction Cost": [0.0],
        "Selling Price": [0.0]
    })

# ---------------------------------------------
# Editable Table
# ---------------------------------------------
st.subheader("Property Records")

edited_df = st.data_editor(
    st.session_state.data,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True
)

# ---------------------------------------------
# Auto Calculations
# ---------------------------------------------
df = edited_df.copy()

for col in ["Buying Price", "Construction Cost", "Selling Price"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

df["Total Investment"] = (
    df["Buying Price"] +
    df["Construction Cost"]
)

df["Total Profit"] = (
    df["Selling Price"] -
    df["Total Investment"]
)

df["Dealer Profit (25%)"] = (
    df["Total Profit"] * 0.25
)

df["Remaining Profit"] = (
    df["Total Profit"] -
    df["Dealer Profit (25%)"]
)

df["Jaffar Profit"] = (
    df["Remaining Profit"] / 2
)

df["Tehseen Profit"] = (
    df["Remaining Profit"] / 2
)

st.session_state.data = edited_df

# ---------------------------------------------
# Show Final Table
# ---------------------------------------------
st.subheader("Calculated Results")

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

# ---------------------------------------------
# Summary Cards
# ---------------------------------------------
st.divider()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Total Investment",
        f"PKR {df['Total Investment'].sum():,.0f}"
    )

with c2:
    st.metric(
        "Total Profit",
        f"PKR {df['Total Profit'].sum():,.0f}"
    )

with c3:
    st.metric(
        "Dealer Profit",
        f"PKR {df['Dealer Profit (25%)'].sum():,.0f}"
    )

with c4:
    st.metric(
        "Jaffar + Tehseen",
        f"PKR {(df['Jaffar Profit'].sum()+df['Tehseen Profit'].sum()):,.0f}"
    )

st.divider()

# ---------------------------------------------
# Individual Profit Cards
# ---------------------------------------------
c1, c2, c3 = st.columns(3)

with c1:
    st.success(
        f"""
### Dealer

**Total Profit**

PKR {df['Dealer Profit (25%)'].sum():,.0f}
"""
    )

with c2:
    st.info(
        f"""
### Jaffar

**Total Profit**

PKR {df['Jaffar Profit'].sum():,.0f}
"""
    )

with c3:
    st.warning(
        f"""
### Tehseen

**Total Profit**

PKR {df['Tehseen Profit'].sum():,.0f}
"""
    )

st.divider()

# ---------------------------------------------
# Profit / Loss Records
# ---------------------------------------------
profit_df = df[df["Total Profit"] >= 0]
loss_df = df[df["Total Profit"] < 0]

col1, col2 = st.columns(2)

with col1:
    st.subheader("✅ Profitable Properties")
    st.dataframe(
        profit_df,
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.subheader("❌ Loss Properties")
    st.dataframe(
        loss_df,
        use_container_width=True,
        hide_index=True
    )

st.divider()

# ---------------------------------------------
# CSV Download
# ---------------------------------------------
csv = df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇ Download CSV",
    data=csv,
    file_name="Property_Investment_Report.csv",
    mime="text/csv"
)

st.divider()

st.caption("Developed with Streamlit")
