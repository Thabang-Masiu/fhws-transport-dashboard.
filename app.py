import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ============================================================
# Page config
# ============================================================
st.set_page_config(
    page_title="FHWS Transport Dashboard",
    page_icon="🚌",
    layout="wide",
)

# ============================================================
# Data loading
# ============================================================
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    trips = pd.read_csv(DATA_DIR / "trips_by_department.csv", parse_dates=["date"])
    costs = pd.read_csv(DATA_DIR / "routes_and_costs.csv")
    return trips, costs

trips, costs = load_data()

# Compute derived columns
trips["month"] = trips["date"].dt.to_period("M").astype(str)
trips["weekday"] = trips["date"].dt.day_name()

# ============================================================
# Header & Sidebar
# ============================================================
st.title("🚌 FHWS Student Transport Dashboard")
st.caption("Faculty of Health and Wellness Sciences · CPUT")

st.sidebar.header("Filters")
departments = ["All"] + sorted(trips["department"].dropna().unique().tolist())
sel_dept = st.sidebar.selectbox("Department", departments)

filtered = trips.copy()
if sel_dept != "All":
    filtered = filtered[filtered["department"] == sel_dept]

# ============================================================
# Tabs
# ============================================================
tab_overview, tab_consolidation, tab_costs, tab_bus = st.tabs(
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization"]
)

# ---------------- TAB 1: OVERVIEW ----------------
with tab_overview:
    st.subheader("Transport Activity Overview")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trips", f"{len(filtered):,}")
    c2.metric("Students Transported", f"{int(filtered['num_students'].sum()):,}")
    c3.metric("Unique Sites", f"{filtered['site'].nunique()}")
    c4.metric("Avg Students/Trip", f"{filtered['num_students'].mean():.2f}")

    st.markdown("### Trips per Month by Department")
    monthly = filtered.groupby(["month", "department"], as_index=False).agg(
        trips=("date", "count"))
    fig = px.line(monthly, x="month", y="trips", color="department", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Top 15 Clinical Sites")
    top_sites = filtered.groupby("site", as_index=False).size().rename(
        columns={"size": "trips"}).sort_values("trips", ascending=False).head(15)
    fig = px.bar(top_sites, x="trips", y="site", orientation="h")
    fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- TAB 2: CONSOLIDATION ----------------
with tab_consolidation:
    st.subheader("Route Consolidation Opportunities")
    
    duplicates = filtered.groupby(["date", "site"], as_index=False).agg(
        trips=("num_students", "count"),
        total_students=("num_students", "sum"),
    ).query("trips > 1").sort_values(["trips", "total_students"], ascending=False)

    credible = costs[costs["cost_per_unit"] >= 100]
    median_cost = credible["cost_per_unit"].median() if not credible.empty else 1200
    excess_trips = max(duplicates["trips"].sum() - len(duplicates), 0)
    saving = excess_trips * median_cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Days with Duplication", f"{len(duplicates):,}")
    c2.metric("Excess Trips", f"{int(excess_trips):,}")
    c3.metric("Estimated Annual Saving", f"R {saving:,.0f}")
    
    st.info(f"Based on a median cost of **R {median_cost:,.0f}** per trip (from AY2024 financial data).")

    st.markdown("### Top Consolidation Targets")
    targets = duplicates.groupby("site", as_index=False).agg(
        duplicate_days=("date", "count"),
        excess_trips=("trips", lambda x: (x - 1).sum()),
    ).sort_values("excess_trips", ascending=False).head(15)
    targets["potential_saving_R"] = targets["excess_trips"] * median_cost
    st.dataframe(targets, use_container_width=True)

# ---------------- TAB 3: COSTS ----------------
with tab_costs:
    st.subheader("Cost Breakdown (AY2024)")
    costs_clean = costs.dropna(subset=["cost_per_unit", "total_cost"])
    
    c1, c2 = st.columns(2)
    with c1:
        by_dept = costs_clean.groupby("department", as_index=False).agg(
            total_cost=("total_cost", "sum"))
        fig = px.pie(by_dept, names="department", values="total_cost", title="Cost by Department")
        st.plotly_chart(fig, use_container_width=True)
    
    with c2:
        top_routes = costs_clean.groupby("route_description", as_index=False).agg(
            total_cost=("total_cost", "sum")).sort_values("total_cost", ascending=False).head(10)
        fig = px.bar(top_routes, x="total_cost", y="route_description", orientation="h",
                     title="Top 10 Routes by Cost")
        fig.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Full Cost Table")
    st.dataframe(costs_clean, use_container_width=True)

# ---------------- TAB 4: BUS UTILIZATION ----------------
with tab_bus:
    st.subheader("Bus Size Utilization")
    
    student_load = filtered.groupby(["date", "site"], as_index=False).agg(
        students=("num_students", "sum"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Students/Trip", f"{filtered['num_students'].mean():.2f}")
    c2.metric("Median Students/Trip", f"{filtered['num_students'].median():.0f}")
    under_5 = (student_load["students"] <= 5).sum()
    pct = 100 * under_5 / len(student_load) if len(student_load) else 0
    c3.metric("Day+Sites with ≤5 Students", f"{under_5} ({pct:.1f}%)")

    st.markdown("### Distribution of Students per Day-Site")
    fig = px.histogram(student_load, x="students", nbins=30)
    st.plotly_chart(fig, use_container_width=True)

    st.info("**Insight:** If most trips carry fewer than 5 students, the faculty may be over-provisioning larger buses. Consider downshifting to 7-seaters where load permits.")

# Footer
st.markdown("---")
st.caption("Built by the Mathematics Technology Programme · Faculty of Applied Sciences · CPUT")