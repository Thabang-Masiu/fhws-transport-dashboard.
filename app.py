import streamlit as st
import pandas as pd
import math

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
@st.cache_data
def load_data():
    trips = pd.read_csv("trips_by_department.csv")
    trips["date"] = pd.to_datetime(trips["date"], errors="coerce")
    costs = pd.read_csv("routes_and_costs.csv")
    return trips, costs

trips, costs = load_data()

# Compute derived columns
trips["month"] = trips["date"].dt.to_period("M").astype(str)
trips["weekday"] = trips["date"].dt.day_name()

# ============================================================
# Header
# ============================================================
st.title("🚌 FHWS Student Transport Dashboard")
st.caption("Faculty of Health and Wellness Sciences · CPUT")

# ============================================================
# Tabs
# ============================================================
tab_overview, tab_analysis, tab_consolidation, tab_costs, tab_nursing = st.tabs(
    ["📊 Overview", "📈 Visual Analysis", "🎯 Consolidation", "💰 Costs", "🏥 Departmental Routes"]
)

# ---------------- TAB 1: OVERVIEW ----------------
with tab_overview:
    st.subheader("Transport Activity Overview")
    
    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trips", f"{len(trips):,}")
    c2.metric("Students Transported", f"{int(trips['num_students'].sum()):,}")
    c3.metric("Unique Sites", f"{trips['site'].nunique()}")
    c4.metric("Avg Students/Trip", f"{trips['num_students'].mean():.2f}")
    
    st.markdown("### Trips per Month by Department")
    monthly = trips.groupby(["month", "department"], as_index=False).agg(trips=("date", "count"))
    st.bar_chart(monthly.pivot(index="month", columns="department", values="trips").fillna(0))

# ---------------- TAB 2: VISUAL ANALYSIS ----------------
with tab_analysis:
    st.subheader("📈 Data Analysis & Trends")
    
    # 1. Bus Over-provisioning
    st.markdown("### 1. Bus Size Over-Provisioning")
    st.markdown("The vast majority of trips carry only 1 to 3 students, indicating we are dispatching large buses that are mostly empty.")
    hist_values = pd.cut(trips['num_students'], bins=[0,1,2,3,5,10,15,22,50])
    hist_df = hist_values.value_counts().sort_index().reset_index()
    hist_df.columns = ["Students on Bus", "Number of Trips"]
    hist_df["Students on Bus"] = hist_df["Students on Bus"].astype(str)
    st.bar_chart(hist_df.set_index("Students on Bus"))
    
    st.markdown("---")
    
    # 2. Weekday Volume
    st.markdown("### 2. Trip Volume by Day of Week")
    st.markdown("Transport peaks on Friday, Saturday, and Sunday due to DEMS night duty and weekend shifts.")
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_counts = trips.groupby("weekday").size().reset_index(name="Trips")
    weekday_counts["weekday"] = pd.Categorical(weekday_counts["weekday"], categories=weekday_order, ordered=True)
    st.bar_chart(weekday_counts.sort_values("weekday").set_index("weekday"))

    st.markdown("---")

    # 3. Top 10 Expensive Routes
    st.markdown("### 3. Top 10 Most Expensive Routes")
    st.markdown("Long-distance routes like Stellenbosch and Paarl consume the majority of the transport budget.")
    costs_clean = costs.dropna(subset=["total_cost"])
    top_routes = costs_clean.groupby("route_description")["total_cost"].sum().nlargest(10).reset_index()
    st.bar_chart(top_routes.set_index("route_description")["total_cost"])

# ---------------- TAB 3: CONSOLIDATION ----------------
with tab_consolidation:
    st.subheader("🎯 Route Consolidation Opportunities")
    st.markdown("By grouping trips by date and site, we identified days where multiple separate vehicles were dispatched to the exact same destination.")
    
    duplicates = trips.groupby(["date", "site"], as_index=False).agg(
        trips=("num_students", "count"), total_students=("num_students", "sum")
    ).query("trips > 1").sort_values(["trips", "total_students"], ascending=False)
    
    credible = costs[costs["cost_per_unit"] >= 100]
    median_cost = credible["cost_per_unit"].median() if not credible.empty else 1200
    excess_trips = max(duplicates["trips"].sum() - len(duplicates), 0)
    saving = excess_trips * median_cost
    
    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Days with Duplication", f"{len(duplicates):,}")
    c2.metric("Excess Trips", f"{int(excess_trips):,}")
    c3.metric("Est. Annual Saving", f"R {saving:,.0f}")

    st.markdown("### Top Consolidation Targets")
    targets = duplicates.groupby("site", as_index=False).agg(
        duplicate_days=("date", "count"),
        excess_trips=("trips", lambda x: (x - 1).sum()),
    ).sort_values("excess_trips", ascending=False).head(10)
    targets["potential_saving_R"] = targets["excess_trips"] * median_cost
    st.dataframe(targets, use_container_width=True)

# ---------------- TAB 4: COSTS ----------------
with tab_costs:
    st.subheader("💰 Cost Breakdown (AY2024)")
    costs_clean = costs.dropna(subset=["cost_per_unit", "total_cost"])
    by_dept = costs_clean.groupby("department")["total_cost"].sum()
    
    st.markdown("### Total Cost by Department")
    st.bar_chart(by_dept)

# ---------------- TAB 5: DEPARTMENTAL ROUTES ----------------
with tab_nursing:
    st.subheader("🏥 Departmental Routes & Fleet")
    st.markdown("A breakdown of the specific buses assigned to the Nursing cluster routes.")
    
    nursing_data = costs[costs["department"] == "Nursing"].copy()
    
    if not nursing_data.empty:
        st.markdown("### Bus Size Utilization")
        bus_counts = nursing_data["bus_size"].value_counts().reset_index()
        bus_counts.columns = ["Bus Size", "Number of Routes"]
        st.dataframe(bus_counts, use_container_width=True)
        
        st.markdown("### Detailed Routes")
        display_df = nursing_data[["week", "route_description", "bus_size"]].dropna()
        st.dataframe(display_df, use_container_width=True)
    else:
        st.write("No route data available.")

# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentine Mgingqizana · Faculty of Applied Sciences · CPUT")
