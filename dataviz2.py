import streamlit as st
import pandas as pd
import plotly.express as px

# Set page configuration for a wider layout
st.set_page_config(layout="wide")

# Function to load and cache data for performance
@st.cache_data
def load_data(file_path):
    """Loads and preprocesses the webinar data from an Excel file."""
    try:
        df = pd.read_excel(file_path)
        numeric_cols = ['Actual Duration (minutes)', 'Time in Session (minutes)']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df[numeric_cols] = df[numeric_cols].fillna(0)
        # Convert Workforce column to string to avoid errors with mixed types
        if 'Workforce' in df.columns:
            df['Workforce'] = df['Workforce'].astype(str)
        return df
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found. Please make sure the path is correct.")
        return None
    except Exception as e:
        st.error(f"An error occurred while loading the file: {e}")
        return None


# --- AREA TO PUT YOUR FILE PATH ---
file_location = "WEBINARMASTER - Copy.xlsx"
df = load_data(file_location)
# ------------------------------------


if df is not None:
    # Custom CSS for a classier look
    st.markdown("""
        <style>
            .main {
                background-color: #f5f5ff;
            }
            .stMetric {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 10px;
                padding: 15px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            .stPlotlyChart {
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
        </style>
    """, unsafe_allow_html=True)

    # --- Dashboard Title ---
    st.title('Webinar Performance Dashboard')
    st.markdown("---")

    # --- Metrics Cards ---
    st.header('Key Performance Indicators')

    nursing_facilities_workforce = [
        'Mental Health Treatment, Nursing Facility',
        'Mental Health Treatment, Nursing Facility, Substance Use Treatment',
        'Mental Health Treatment, Substance Use Treatment, Nursing Facility',
        'Nursing Facility',
        'Nursing Facility - DOH',
        'Nursing Facility - Morning Breeze',
        'Nursing Facility Corporation',
        'Nursing Facility, Mental Health Treatment',
        'Nursing Facility, Mental Health Treatment, Other',
        'Nursing Facility, Mental Health Treatment, Substance Use Treatment',
        'Nursing Facility, Other',
        'Nursing Facility, Substance Use Treatment',
        'Nursing Facility, Substance Use Treatment, Mental Health Treatment',
        'Nursing Facility,Mental Health Treatment,QIN-QIO',
        'Nursing Facility,Mental Health Treatment,Substance Use Treatment,QIN-QIO',
        'Nursing Facility,QIN-QIO',
        'Nursing Facility,QIN-QIO,Mental Health Treatment',
        'Nursing Facility,QIN-QIO,Other'
    ]
    
    registrants = df['Email'].nunique()
    attendees = df[df['Attended'] == 'Yes']['Email'].nunique()
    nursing_facility_attendees = df[(df['Attended'] == 'Yes') & (df['Workforce'].isin(nursing_facilities_workforce))]['Email'].nunique()
    non_nursing_facility_attendees = attendees - nursing_facility_attendees
    total_orgs = df['Organization'].nunique()
    nursing_facility_orgs = df[df['Workforce'].isin(nursing_facilities_workforce)]['Organization'].nunique()
    non_nursing_facility_orgs = total_orgs - nursing_facility_orgs
    avg_duration = df['Actual Duration (minutes)'].mean()
    total_engagement_hours = df[df['Attended'] == 'Yes']['Time in Session (minutes)'].sum() / 60

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Total Registrants", value=f"{registrants:,}")
        st.metric(label="Total Organizations", value=f"{total_orgs:,}")
    with col2:
        st.metric(label="Total Attendees", value=f"{attendees:,}")
        st.metric(label="Nursing Facility Orgs", value=f"{nursing_facility_orgs:,}")
    with col3:
        st.metric(label="Nursing Facility Attendees", value=f"{nursing_facility_attendees:,}")
        st.metric(label="Non-Nursing Facility Orgs", value=f"{non_nursing_facility_orgs:,}")
    with col4:
        st.metric(label="Non-Nursing Facility Attendees", value=f"{non_nursing_facility_attendees:,}")
        st.metric(label="Engagement (Hours)", value=f"{total_engagement_hours:,.2f}")

    st.metric(label="Average Webinar Duration (Minutes)", value=f"{avg_duration:,.2f}")
    st.markdown("---")

    # --- Prepare Data for Charts ---
    df['YearMonth'] = pd.to_datetime(df['Actual Start Time']).dt.to_period('M').astype(str)

    # --- Monthly Analysis ---
    st.header("Monthly Analysis")
    monthly_data = df.groupby('YearMonth').agg(Total_Registrants=('Email', 'nunique'), Total_Attendees=('Attended', lambda x: (x == 'Yes').sum())).reset_index()
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(monthly_data, x='YearMonth', y='Total_Registrants', title='Monthly Registration Distribution')
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(monthly_data, x='YearMonth', y='Total_Attendees', title='Monthly Attendance Distribution')
        st.plotly_chart(fig, use_container_width=True)
    fig = px.line(monthly_data, x='YearMonth', y=['Total_Registrants', 'Total_Attendees'], title='Monthly Registration vs. Attendance', labels={'value': 'Count', 'variable': 'Metric'})
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    # --- Region-wise Analysis ---
    st.header("Region-wise Monthly Analysis")
    region_monthly = df.groupby(['YearMonth', 'Region']).agg(Registrations=('Email', 'nunique'), Attendance=('Attended', lambda x: (x == 'Yes').sum())).reset_index()
    fig = px.bar(region_monthly, x='YearMonth', y='Registrations', color='Region', title='Monthly Region-wise Registration', barmode='group')
    st.plotly_chart(fig, use_container_width=True)
    fig = px.bar(region_monthly, x='YearMonth', y='Attendance', color='Region', title='Monthly Region-wise Attendance', barmode='group')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    # --- Simplified Workforce Analysis ---
    st.header("Nursing vs. Non-Nursing Monthly Analysis")
    df['Facility_Type'] = df['Workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else 'Non-Nursing Facility')
    workforce_monthly = df.groupby(['YearMonth', 'Facility_Type']).agg(Registrations=('Email', 'nunique'), Attendance=('Attended', lambda x: (x == 'Yes').sum())).reset_index()
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(workforce_monthly[workforce_monthly['Facility_Type'] == 'Nursing Facility'], x='YearMonth', y='Registrations', title='Monthly Nursing Facilities Registration')
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(workforce_monthly[workforce_monthly['Facility_Type'] == 'Nursing Facility'], x='YearMonth', y='Attendance', title='Monthly Nursing Facilities Attendance')
        st.plotly_chart(fig, use_container_width=True)
    # ... (rest of the simplified workforce charts are similar)
    st.markdown("---")

    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # --- THIS IS THE FINAL, INTERACTIVE SECTION ---
    st.header("Detailed Monthly Workforce Breakdown")

    # 1. Create the grouped column for cleaner categories
    df['Workforce_Grouped'] = df['Workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else x)

    # 2. Get a sorted list of all unique workforce groups for the filter
    all_workforce_groups = sorted(df['Workforce_Grouped'].unique())

    # 3. CREATE THE INTERACTIVE MULTI-SELECT WIDGET!
    selected_workforces = st.multiselect(
        'Select Workforce Categories to Display:',
        options=all_workforce_groups,
        default=all_workforce_groups  # By default, all categories are selected
    )

    # 4. Filter the main DataFrame based on the user's selection
    filtered_df = df[df['Workforce_Grouped'].isin(selected_workforces)]

    # 5. Group the *filtered* data to prepare for the chart
    workforce_detail_monthly = filtered_df.groupby(['YearMonth', 'Workforce_Grouped']).agg(
        Registrations=('Email', 'nunique'),
        Attendance=('Attended', lambda x: (x == 'Yes').sum())
    ).reset_index()

    # 6. Create the charts using the filtered and grouped data
    st.subheader("Workforce Registration")
    fig_reg = px.bar(workforce_detail_monthly, x='YearMonth', y='Registrations', color='Workforce_Grouped',
                 title='Monthly Workforce Registration Distribution', barmode='stack')
    st.plotly_chart(fig_reg, use_container_width=True)

    st.subheader("Workforce Attendance")
    fig_att = px.bar(workforce_detail_monthly, x='YearMonth', y='Attendance', color='Workforce_Grouped',
                 title='Monthly Workforce Attendance Distribution', barmode='stack')
    st.plotly_chart(fig_att, use_container_width=True)
    # --- END OF INTERACTIVE SECTION ---
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

else:
    st.warning("Data could not be loaded. Please check the file path and format.")