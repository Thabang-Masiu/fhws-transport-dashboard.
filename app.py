import streamlit as st
import pandas as pd
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
    trips = pd.read_csv("trips_by_department.csv", parse_dates=["date"])
    costs = pd.read_csv("routes_and_costs.csv")
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
tab_overview, tab_consolidation, tab_costs, tab_bus, tab_nursing = st.tabs(
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization", "Nursing Routes"]
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
    
    # Pivot for built-in bar chart
    monthly_pivot = monthly.pivot(index="month", columns="department", values="trips").fillna(0)
    st.bar_chart(monthly_pivot)

    st.markdown("### Top 15 Clinical Sites")
    top_sites = filtered.groupby("site", as_index=False).size().rename(
        columns={"size": "trips"}).sort_values("trips", ascending=True).head(15)
    st.bar_chart(top_sites.set_index("site")["trips"])

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
    
    by_dept = costs_clean.groupby("department", as_index=False).agg(
        total_cost=("total_cost", "sum")).set_index("department")
    st.markdown("### Total Cost by Department")
    st.bar_chart(by_dept)

    st.markdown("### Top 10 Expensive Routes")
    top_routes = costs_clean.groupby("route_description", as_index=False).agg(
        total_cost=("total_cost", "sum")).sort_values("total_cost", ascending=True).tail(10)
    st.bar_chart(top_routes.set_index("route_description")["total_cost"])

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
    hist_values = pd.cut(student_load['students'], bins=[0,2,5,10,15,20,25,30])
    hist_df = hist_values.value_counts().reset_index()
    hist_df.columns = ["Students per Trip", "Number of Days"]
    hist_df["Students per Trip"] = hist_df["Students per Trip"].astype(str)
    st.dataframe(hist_df, use_container_width=True)

    st.info("**Insight:** If most trips carry fewer than 5 students, the faculty may be over-provisioning larger buses. Consider downshifting to 7-seaters where load permits.")
# ---------------- TAB 5: NURSING ----------------
with tab_nursing:
    st.subheader("Nursing Department: Cluster Routes")
    st.info("Nursing operates on a weekly 'Cluster' model, covering multiple sites per bus. This data is sourced from the route schedules.")
    
    nursing_data = costs[costs["department"] == "Nursing"].copy()
    
    if not nursing_data.empty:
        # 1. Bus Size Breakdown
        st.markdown("### Bus Size Utilization")
        bus_counts = nursing_data["bus_size"].value_counts().reset_index()
        bus_counts.columns = ["Bus Size", "Number of Routes"]
        st.dataframe(bus_counts, use_container_width=True)
        
        # 2. Route Breakdown
        st.markdown("### Detailed Nursing Routes")
        # Clean up the weeks and routes for display
        nursing_display = nursing_data[["week", "route_description", "bus_size"]].dropna()
        st.dataframe(nursing_display, use_container_width=True)
    else:
        st.write("No Nursing data available.")
# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentle Mgingqizana · Faculty of Applied Sciences · CPUT")
