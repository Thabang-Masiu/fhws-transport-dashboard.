import streamlit as st
import pandas as pd
import math
from datetime import datetime, date

# ============================================================
# Page config
# ============================================================
st.set_page_config(
    page_title="FHWS Transport Dashboard",
    page_icon="🚌",
    layout="wide",
)

# ============================================================
# Data loading & PERMANENT SAVING logic
# ============================================================
@st.cache_data
def load_data():
    trips = pd.read_csv("trips_by_department.csv")
    trips["date"] = pd.to_datetime(trips["date"], errors="coerce")
    costs = pd.read_csv("routes_and_costs.csv")
    return trips, costs

trips, costs = load_data()

def save_new_booking(new_data):
    """Saves the new booking to the CSV so it is remembered forever."""
    raw_trips = pd.read_csv("trips_by_department.csv")
    updated_trips = pd.concat([raw_trips, new_data], ignore_index=True)
    updated_trips.to_csv("trips_by_department.csv", index=False)
    st.cache_data.clear()

trips["month"] = trips["date"].dt.to_period("M").astype(str)

# ============================================================
# Header & Sidebar
# ============================================================
st.title("🚌 FHWS Transport Management System")
st.caption("Faculty of Health and Wellness Sciences · Permanent Operations Hub")

st.sidebar.header("Filters")
departments = ["All"] + sorted(trips["department"].dropna().unique().tolist())
sel_dept = st.sidebar.selectbox("Department Filter", departments)

filtered = trips.copy()
if sel_dept != "All":
    filtered = filtered[filtered["department"] == sel_dept]

# ============================================================
# Tabs (Added Booking History)
# ============================================================
tab_overview, tab_consolidation, tab_costs, tab_bus, tab_nursing, tab_simulator, tab_booking, tab_history = st.tabs(
    ["📊 Overview", "🎯 Consolidation", "💰 Costs", "🚐 Bus Utilization", "🏥 Nursing Routes", "🤖 Auto-Planner", "➕ Live Booking Engine", "📋 Booking History"]
)

# ---------------- TAB 1: OVERVIEW ----------------
with tab_overview:
    st.subheader("Transport Activity Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Trips", f"{len(filtered):,}")
    c2.metric("Students Transported", f"{int(filtered['num_students'].sum()):,}")
    c3.metric("Unique Sites", f"{filtered['site'].nunique()}")
    c4.metric("Avg Students/Trip", f"{filtered['num_students'].mean():.2f}")
    
    monthly = filtered.groupby(["month", "department"], as_index=False).agg(trips=("date", "count"))
    st.bar_chart(monthly.pivot(index="month", columns="department", values="trips").fillna(0))

# ---------------- TAB 2: CONSOLIDATION ----------------
with tab_consolidation:
    duplicates = filtered.groupby(["date", "site"], as_index=False).agg(
        trips=("num_students", "count"), total_students=("num_students", "sum")
    ).query("trips > 1").sort_values(["trips", "total_students"], ascending=False)
    credible = costs[costs["cost_per_unit"] >= 100]
    median_cost = credible["cost_per_unit"].median() if not credible.empty else 1200
    excess_trips = max(duplicates["trips"].sum() - len(duplicates), 0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Days with Duplication", f"{len(duplicates):,}")
    c2.metric("Excess Trips", f"{int(excess_trips):,}")
    c3.metric("Est. Annual Saving", f"R {excess_trips * median_cost:,.0f}")

# ---------------- TAB 3: COSTS ----------------
with tab_costs:
    costs_clean = costs.dropna(subset=["cost_per_unit", "total_cost"])
    st.bar_chart(costs_clean.groupby("department")["total_cost"].sum())

# ---------------- TAB 4: BUS UTILIZATION ----------------
with tab_bus:
    student_load = filtered.groupby(["date", "site"], as_index=False).agg(students=("num_students", "sum"))
    c1, c2 = st.columns(2)
    c1.metric("Avg Students/Trip", f"{filtered['num_students'].mean():.2f}")
    c2.metric("Day+Sites with ≤5 Students", f"{(student_load['students'] <= 5).sum()}")

# ---------------- TAB 5: NURSING ----------------
with tab_nursing:
    nursing_data = costs[costs["department"] == "Nursing"].copy()
    if not nursing_data.empty:
        st.dataframe(nursing_data["bus_size"].value_counts().reset_index(), use_container_width=True)

# ---------------- TAB 6: AUTO-PLANNER ----------------
with tab_simulator:
    st.subheader("🤖 Auto-Generate Transport Dispatch Plan")
    col1, col2 = st.columns(2)
    with col1:
        all_sites = sorted(trips["site"].dropna().unique().tolist())
        selected_sites = st.multiselect("1. Select Clinical Sites:", options=all_sites, default=[all_sites[0]] if all_sites else [])
    with col2:
        dems_students = st.number_input("DEMS Students", min_value=0, value=10)
        mits_students = st.number_input("MITS Students", min_value=0, value=5)
        nursing_students = st.number_input("Nursing Students", min_value=0, value=8)
    
    total_students = dems_students + mits_students + nursing_students
    if selected_sites and total_students > 0:
        optimized_buses_22 = total_students // 22
        remainder = total_students % 22
        optimized_buses_13 = math.ceil(remainder / 13) if remainder > 0 else 0
        total_optimized_buses = optimized_buses_22 + optimized_buses_13
        
        plan_data = []
        students_per_site = math.ceil(total_students / len(selected_sites))
        for site in selected_sites:
            site_data = trips[trips["site"] == site]
            p_time = site_data["pickup_time"].dropna().mode()[0] if not site_data["pickup_time"].dropna().empty else "06:30"
            d_time = site_data["collection_time"].dropna().mode()[0] if not site_data["collection_time"].dropna().empty else "16:00"
            plan_data.append({"Destination": site, "Pickup Time": p_time, "Return Time": d_time, "Est. Students": students_per_site})
            
        dispatch_df = pd.DataFrame(plan_data)
        st.success(f"✅ **Plan Generated!** {total_students} students require **{total_optimized_buses} buses**.")
        st.dataframe(dispatch_df, use_container_width=True)
        st.download_button("📥 Download Dispatch Sheet", dispatch_df.to_csv(index=False).encode('utf-8'), "Dispatch_Plan.csv", "text/csv")

# ---------------- TAB 7: LIVE BOOKING ENGINE ----------------
with tab_booking:
    st.subheader("➕ Live Booking Engine")
    st.markdown("Use this form to log a **new transport request**. The system will instantly check if a bus is already going to that hospital on that day, saving the department money.")
    
    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        with col1:
            book_date = st.date_input("Date of Travel", min_value=date.today())
            book_dept = st.selectbox("Department", ["DEMS", "MITS", "Nursing"])
            book_site = st.selectbox("Hospital/Clinic", options=sorted(trips["site"].dropna().unique().tolist()))
        with col2:
            book_students = st.number_input("Number of Students", min_value=1, value=5)
            book_pickup = st.text_input("Pickup Time", "06:30")
            book_return = st.text_input("Return Time", "16:00")
            
        submitted = st.form_submit_button("Check Availability & Book")
        
    if submitted:
        existing = trips[(trips["date"].dt.date == book_date) & (trips["site"] == book_site)]
        st.markdown("### 🔎 Availability Check")
        
        if not existing.empty:
            current_load = existing["num_students"].sum()
            bus_capacity = 13 if current_load <= 13 else 22
            available_seats = bus_capacity - current_load
            
            if available_seats >= book_students:
                st.success(f"🎉 **GOOD NEWS:** There is already a bus going to {book_site} on {book_date} ({existing['department'].iloc[0]} department).")
                st.info(f"The existing bus has **{available_seats} seats available**. Your {book_students} students can join this bus. **Cost of this booking: R 0** (Saving R 1,200).")
            else:
                st.warning(f"⚠️ A bus is already going to {book_site}, but it only has {available_seats} seats left. You will need to book an additional vehicle.")
        else:
            st.info(f"No existing transport found for {book_site} on {book_date}. A new vehicle must be dispatched.")
            
        new_row = pd.DataFrame([{
            "department": book_dept,
            "date": pd.to_datetime(book_date),
            "week": None,
            "site": book_site,
            "route_description": f"CPUT Bellville to {book_site}",
            "num_students": book_students,
            "pickup_time": book_pickup,
            "collection_time": book_return,
            "pickup_point": "CPUT Bellville Campus",
            "bus_size": None,
            "trips": 1,
            "cost_per_unit": 1200 if existing.empty else 0,
            "units": 1,
            "total_cost": 1200 if existing.empty else 0,
            "tsqt_number": "LIVE-BOOKING",
            "source_file": "live_system.csv",
            "source_sheet": "form"
        }])
        
        save_new_booking(new_row)
        st.balloons()
        st.success("✅ **Booking Saved Successfully!** The dashboard metrics have been updated. Check the **📋 Booking History** tab to view your records.")

# ---------------- TAB 8: BOOKING HISTORY ----------------
with tab_history:
    st.subheader("📋 Permanent Booking History")
    st.markdown("This is a permanent log of all transport requests made through the Live Booking Engine.")
    
    # Filter ONLY for the live bookings we made using the system
    live_bookings = trips[trips["tsqt_number"] == "LIVE-BOOKING"].copy()
    
    if live_bookings.empty:
        st.info("No live bookings have been made yet. Go to the 'Live Booking Engine' tab to make your first booking.")
    else:
        # Clean up the display
        display_df = live_bookings[[
            "date", "department", "site", "num_students", 
            "pickup_time", "collection_time", "total_cost"
        ]].sort_values("date", ascending=False)
        
        # Format the date and cost columns
        display_df["date"] = display_df["date"].dt.strftime('%Y-%m-%d')
        display_df["total_cost"] = display_df["total_cost"].apply(lambda x: f"R {x:,.0f}")
        
        st.dataframe(display_df, use_container_width=True)
        
        # Provide a download button for the records
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Booking Records (CSV)",
            data=csv,
            file_name=f"FHWS_Booking_Records_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
        )
        
        # Show a quick summary metric
        st.metric("Total Live Bookings Made", len(display_df))

# Footer
st.markdown("---")
st.caption("Built by Masiu Thabang and Mbalentine Mgingqizana · Faculty of Applied Sciences · CPUT")
