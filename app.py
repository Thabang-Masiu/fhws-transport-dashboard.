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
sel_dept = st.sidebar.selectbox("Department (For Analysis Tabs)", departments)

filtered = trips.copy()
if sel_dept != "All":
    filtered = filtered[filtered["department"] == sel_dept]

# ============================================================
# Tabs
# ============================================================
tab_overview, tab_consolidation, tab_costs, tab_bus, tab_nursing, tab_simulator = st.tabs(
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization", "🏥 Nursing Routes", "🧮 Strategy Simulator"]
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

# ---------------- TAB 5: NURSING ----------------
with tab_nursing:
    st.subheader("Nursing Department: Cluster Routes")
    st.info("Nursing operates on a weekly 'Cluster' model, covering multiple sites per bus.")
    
    nursing_data = costs[costs["department"] == "Nursing"].copy()
    
    if not nursing_data.empty:
        bus_counts = nursing_data["bus_size"].value_counts().reset_index()
        bus_counts.columns = ["Bus Size", "Number of Routes"]
        st.dataframe(bus_counts, use_container_width=True)

# ---------------- TAB 6: STRATEGY SIMULATOR ----------------
with tab_simulator:
    st.subheader("🧮 Transport Strategy Simulator")
    st.markdown("Simulate transport for upcoming placements. See the exact routes, times, and financial savings.")
    
    # 1. Select multiple hospitals
    all_sites = sorted(trips["site"].dropna().unique().tolist())
    selected_sites = st.multiselect(
        "1. Select Clinical Sites:", 
        options=all_sites,
        default=[all_sites[0]] if all_sites else []
    )
    
    # 2. Select student numbers
    st.markdown("### 2. Enter Student Numbers")
    col1, col2, col3 = st.columns(3)
    dems_students = col1.number_input("DEMS Students", min_value=0, value=5)
    mits_students = col2.number_input("MITS Students", min_value=0, value=5)
    nursing_students = col3.number_input("Nursing Students", min_value=0, value=5)
    
    total_students = dems_students + mits_students + nursing_students
    
    # 3. Show historical times for the selected sites
    if selected_sites:
        st.markdown("---")
        st.markdown("### 🕒 Historical Route Details for Selected Sites")
        
        # Filter trips for selected sites
        site_data = trips[trips["site"].isin(selected_sites)]
        
        for site in selected_sites:
            # Get most common times for this specific site
            site_specific = site_data[site_data["site"] == site]
            if not site_specific.empty:
                pickup = site_specific["pickup_time"].dropna().mode()
                dropoff = site_specific["collection_time"].dropna().mode()
                
                p_time = pickup[0] if not pickup.empty else "06:30"
                d_time = dropoff[0] if not dropoff.empty else "16:00"
                
                st.info(f"**{site}:** Pickup at **{p_time}** from CPUT Bellville | Return at **{d_time}**")

    # 4. Calculation and Visuals
    if selected_sites and total_students > 0:
        st.markdown("---")
        st.markdown("### 📊 Transport Simulation Results")
        
        # Current approach (separate bookings)
        current_buses = 0
        if dems_students > 0: current_buses += math.ceil(dems_students / 13)
        if mits_students > 0: current_buses += math.ceil(mits_students / 7)
        if nursing_students > 0: current_buses += math.ceil(nursing_students / 22)
        
        # Optimized approach (shared bookings)
        optimized_buses_22 = total_students // 22
        remainder = total_students % 22
        optimized_buses_13 = math.ceil(remainder / 13) if remainder > 0 else 0
        total_optimized_buses = optimized_buses_22 + optimized_buses_13
        
        # Cost calculation
        median_cost = 1200
        weeks = 3
        total_days = weeks * 5 # Mon-Fri
        current_total_cost = current_buses * median_cost * total_days
        optimized_total_cost = total_optimized_buses * median_cost * total_days
        total_savings = current_total_cost - optimized_total_cost
        
        # KPIs
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Students", total_students)
        c2.metric("Current Buses/Day", current_buses)
        c3.metric("Optimized Buses/Day", total_optimized_buses)
        
        # Visual Charts
        v1, v2 = st.columns(2)
        with v1:
            chart_data = pd.DataFrame({
                "Scenario": ["Current (Fragmented)", "Optimized (Consolidated)"],
                "Buses Required": [current_buses, total_optimized_buses]
            }).set_index("Scenario")
            st.bar_chart(chart_data)
            st.caption("Buses Required per Day")
            
        with v2:
            cost_data = pd.DataFrame({
                "Cost Type": ["Savings", "Remaining Cost"],
                "Amount": [total_savings, optimized_total_cost]
            }).set_index("Cost Type")
            st.bar_chart(cost_data)
            st.caption(f"Financial Breakdown over {weeks} weeks")
            
        # Financial Summary
        st.markdown(f"#### 💰 Financial Impact over {weeks} Weeks")
        st.markdown(f"Calculated for {total_days} travel days at R {median_cost} per trip.")
        f1, f2, f3 = st.columns(3)
        f1.metric("Cost (Current)", f"R {current_total_cost:,.0f}")
        f2.metric("Cost (Optimized)", f"R {optimized_total_cost:,.0f}")
        f3.metric("Total Savings", f"R {total_savings:,.0f}", delta=f"R {total_savings:,.0f}")
        
        # Bus Breakdown Table
        st.markdown("### 🚐 Proposed Bus Breakdown")
        breakdown_data = {
            "Bus Type": ["22-Seater Bus", "13-Seater Bus"],
            "Quantity Needed": [optimized_buses_22, optimized_buses_13]
        }
        st.table(pd.DataFrame(breakdown_data))

# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentine Mgingqizana · Faculty of Applied Sciences · CPUT")
