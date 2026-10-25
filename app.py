import streamlit as st
import pandas as pd
import math
from datetime import datetime

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
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization", "🏥 Nursing Routes", "🤖 Auto-Planner"]
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
    monthly = filtered.groupby(["month", "department"], as_index=False).agg(trips=("date", "count"))
    monthly_pivot = monthly.pivot(index="month", columns="department", values="trips").fillna(0)
    st.bar_chart(monthly_pivot)

# ---------------- TAB 2: CONSOLIDATION ----------------
with tab_consolidation:
    st.subheader("Route Consolidation Opportunities")
    duplicates = filtered.groupby(["date", "site"], as_index=False).agg(
        trips=("num_students", "count"), total_students=("num_students", "sum")
    ).query("trips > 1").sort_values(["trips", "total_students"], ascending=False)

    credible = costs[costs["cost_per_unit"] >= 100]
    median_cost = credible["cost_per_unit"].median() if not credible.empty else 1200
    excess_trips = max(duplicates["trips"].sum() - len(duplicates), 0)
    saving = excess_trips * median_cost

    c1, c2, c3 = st.columns(3)
    c1.metric("Days with Duplication", f"{len(duplicates):,}")
    c2.metric("Excess Trips", f"{int(excess_trips):,}")
    c3.metric("Estimated Annual Saving", f"R {saving:,.0f}")

    st.markdown("### Top Consolidation Targets")
    targets = duplicates.groupby("site", as_index=False).agg(
        duplicate_days=("date", "count"), excess_trips=("trips", lambda x: (x - 1).sum())
    ).sort_values("excess_trips", ascending=False).head(10)
    targets["potential_saving_R"] = targets["excess_trips"] * median_cost
    st.dataframe(targets, use_container_width=True)

# ---------------- TAB 3: COSTS ----------------
with tab_costs:
    st.subheader("Cost Breakdown (AY2024)")
    costs_clean = costs.dropna(subset=["cost_per_unit", "total_cost"])
    by_dept = costs_clean.groupby("department", as_index=False).agg(total_cost=("total_cost", "sum")).set_index("department")
    st.bar_chart(by_dept)

# ---------------- TAB 4: BUS UTILIZATION ----------------
with tab_bus:
    st.subheader("Bus Size Utilization")
    student_load = filtered.groupby(["date", "site"], as_index=False).agg(students=("num_students", "sum"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Students/Trip", f"{filtered['num_students'].mean():.2f}")
    under_5 = (student_load["students"] <= 5).sum()
    pct = 100 * under_5 / len(student_load) if len(student_load) else 0
    c3.metric("Day+Sites with ≤5 Students", f"{under_5} ({pct:.1f}%)")

# ---------------- TAB 5: NURSING ----------------
with tab_nursing:
    st.subheader("Nursing Department: Cluster Routes")
    nursing_data = costs[costs["department"] == "Nursing"].copy()
    if not nursing_data.empty:
        bus_counts = nursing_data["bus_size"].value_counts().reset_index()
        bus_counts.columns = ["Bus Size", "Number of Routes"]
        st.dataframe(bus_counts, use_container_width=True)

# ---------------- TAB 6: AUTO-PLANNER ----------------
with tab_simulator:
    st.subheader("🤖 Auto-Generate Transport Dispatch Plan")
    st.markdown("This smart tool instantly builds an optimized transport schedule. Select the hospitals and student numbers, and it will generate the exact bus breakdown, times, and downloadable dispatch sheet for the service provider.")
    
    col1, col2 = st.columns(2)
    with col1:
        all_sites = sorted(trips["site"].dropna().unique().tolist())
        selected_sites = st.multiselect(
            "1. Select Clinical Sites:", 
            options=all_sites,
            default=[all_sites[0]] if all_sites else []
        )
    with col2:
        st.markdown("**2. Enter Total Students per Department**")
        dems_students = st.number_input("DEMS Students", min_value=0, value=10)
        mits_students = st.number_input("MITS Students", min_value=0, value=5)
        nursing_students = st.number_input("Nursing Students", min_value=0, value=8)
    
    total_students = dems_students + mits_students + nursing_students
    
    if selected_sites and total_students > 0:
        st.markdown("---")
        
        # --- SMART ALGORITHM ---
        # 1. Bus Calculation
        optimized_buses_22 = total_students // 22
        remainder = total_students % 22
        optimized_buses_13 = math.ceil(remainder / 13) if remainder > 0 else 0
        total_optimized_buses = optimized_buses_22 + optimized_buses_13
        
        # 2. Generate the Dispatch Plan Table
        plan_data = []
        
        # Distribute students evenly across the selected sites for the schedule
        students_per_site = math.ceil(total_students / len(selected_sites))
        
        for site in selected_sites:
            # Find historical times
            site_data = trips[trips["site"] == site]
            p_time = site_data["pickup_time"].dropna().mode()[0] if not site_data["pickup_time"].dropna().empty else "06:30"
            d_time = site_data["collection_time"].dropna().mode()[0] if not site_data["collection_time"].dropna().empty else "16:00"
            
            plan_data.append({
                "Destination": site,
                "Pickup Time": p_time,
                "Return Time": d_time,
                "Est. Students": students_per_site
            })
            
        dispatch_df = pd.DataFrame(plan_data)
        
        # --- SHOW THE RESULTS ---
        st.success(f"✅ **Plan Generated!** {total_students} students across {len(selected_sites)} sites require **{total_optimized_buses} buses** (instead of {len(selected_sites) * 2} if booked separately).")
        
        # Visual 1: KPI Cards
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Students", total_students)
        c2.metric("Optimized Buses", total_optimized_buses)
        
        median_cost = 1200
        total_days = 15 # 3 weeks
        optimized_cost = total_optimized_buses * median_cost * total_days
        c3.metric("Est. 3-Week Cost", f"R {optimized_cost:,.0f}")
        
        # Visual 2: The Route Schedule
        st.markdown("### 🗺️ Optimized Route Schedule")
        st.dataframe(dispatch_df, use_container_width=True)
        
        # Visual 3: Download Button
        csv = dispatch_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Transport Dispatch Sheet (CSV)",
            data=csv,
            file_name=f"FHWS_Dispatch_Plan_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
        )
        
        st.info("💡 **Time Saved:** Instead of manually cross-referencing 5 different Excel sheets, the coordinator can now download this exact sheet and email it directly to the transport provider.")

# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentine Mgingqizana · Faculty of Applied Sciences · CPUT")
