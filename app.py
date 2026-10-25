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
tab_overview, tab_consolidation, tab_costs, tab_bus, tab_nursing, tab_planner = st.tabs(
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization", "Nursing Routes", "🗺️ Route Planner"]
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
# ---------------- TAB 6: ROUTE PLANNER ----------------
with tab_planner:
    st.subheader("Student Transport Route Planner")
    st.info("Simulate a booking by selecting a clinical site. The dashboard will suggest historical routes, times, and bus sizes based on previous trips.")
    
    # Get a list of all unique sites we have data for
    all_sites = sorted(trips["site"].dropna().unique().tolist())
    
    # Dropdown for the user to select a hospital
    selected_site = st.selectbox("Select a Clinical Site:", all_sites)
    
    if selected_site:
        # Filter historical data for this site
        site_data = trips[trips["site"] == selected_site]
        
        st.markdown(f"### Planning for: **{selected_site}**")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 📍 Route Details")
            # Find the most common route description (if available)
            route_desc = site_data["route_description"].mode()
            if not route_desc.empty and pd.notna(route_desc[0]):
                st.write(f"**Historical Route:** {route_desc[0]}")
            else:
                st.write(f"**Historical Route:** CPUT Bellville Campus to {selected_site}")
            
            # Show the most common pick-up point
            pickup = site_data["pickup_point"].mode()
            pickup_text = pickup[0] if not pickup.empty and pd.notna(pickup[0]) else "CPUT Bellville Campus"
            st.write(f"**Pick-up Point:** {pickup_text}")

        with c2:
            st.markdown("#### ⏰ Timing Details")
            # Show most common pick up and return times
            times = site_data[["pickup_time", "collection_time"]].dropna()
            if not times.empty:
                st.write(f"**Typical Departure:** {times['pickup_time'].mode()[0]}")
                st.write(f"**Typical Return:** {times['collection_time'].mode()[0]}")
            else:
                st.write("**Typical Departure:** 06:00 (Estimated)")
                st.write("**Typical Return:** 16:00 (Estimated)")

        st.markdown("---")
        st.markdown("#### 🚐 Available Bus & Capacity")
        
        # Show the bus sizes used for this site historically
        buses_used = site_data["bus_size"].dropna().unique()
        if len(buses_used) > 0:
            st.write(f"**Buses typically assigned to this route:** {', '.join(buses_used)}")
        else:
            st.write("**Buses typically assigned to this route:** 7-seater or 13-seater (Standard)")
            
        # Number of students input to calculate remaining capacity
        num_students = st.number_input("Number of students requiring transport:", min_value=1, max_value=50, value=5)
        
        st.success(f"A **13-seater bus** is recommended. It can accommodate **{num_students} students** and has **{13 - num_students} seats remaining** for consolidation.")
        
        # Optional: Show a mini map or a table of other students going there today
        with st.expander("View Historical Trips to this Site"):
            st.dataframe(site_data[["date", "num_students", "department"]].sort_values("date", ascending=False).head(10), use_container_width=True)
# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentle Mgingqizana · Faculty of Applied Sciences · CPUT")
