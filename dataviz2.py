import streamlit as st
import pandas as pd
import plotly.express as px

# Set page configuration for a wider layout
st.set_page_config(layout="wide")

# Function to load and cache data for performance
@st.cache_data
def load_data(file_path):
    """Loads and preprocesses the webinar data from a CSV file."""
    try:
        # Reading from a clean CSV file
        df = pd.read_csv(file_path)
        
        df.columns = df.columns.str.strip()

        numeric_cols = ['Actual Duration (minutes)', 'Time in Session (minutes)']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df[numeric_cols] = df[numeric_cols].fillna(0)
        
        if 'Workforce' in df.columns:
            df['Workforce'] = df['Workforce'].astype(str)
        return df
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found. Please make sure the path is correct.")
        return None
    except Exception as e:
        st.error(f"An error occurred while loading the file: {e}")
        return None


# --- Point to your new CSV file ---
file_location = r"D:\ALIANT DATA\multi_consolidated_report3.csv"
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
        'Nursing Facility,QIN-QIO,Other',
        'Other, Nursing Facility',
        'QIN-QIO,Mental Health Treatment,Nursing Facility,Substance Use Treatment',
        'QIN-QIO,Substance Use Treatment,Mental Health Treatment,Nursing Facility',
        'Substance Use Treatment, Nursing Facility'
    ]
    
    # --- THIS IS THE ONLY LINE THAT HAS BEEN MODIFIED ---
    # For each unique webinar session (defined by ID and start time),
    # get its registration count and sum them all up for a grand total.
    registrants = df.drop_duplicates(subset=['Webinar ID', 'Actual Start Time'])['Registered'].sum()
    
    attendee_filtered_df = df[
        (df['attendee type'] == 'ATTENDEE') & 
        (df['Attended'] == 'Yes')
    ]
    attendees = attendee_filtered_df.shape[0]
    
    nursing_facility_attendees = attendee_filtered_df[
        attendee_filtered_df['Workforce'].isin(nursing_facilities_workforce)
    ].shape[0]

    non_nursing_facility_attendees = attendee_filtered_df[
        ~attendee_filtered_df['Workforce'].isin(nursing_facilities_workforce)
    ].shape[0]

    total_engagement_hours = attendee_filtered_df['Time in Session (minutes)'].sum() / 60
    total_orgs = df['Organization'].nunique()
    nursing_facility_orgs = df[df['Workforce'].isin(nursing_facilities_workforce)]['Organization'].nunique()
    non_nursing_facility_orgs = total_orgs - nursing_facility_orgs
    total_webinar_duration = df.groupby('Webinar ID')['Actual Duration (minutes)'].unique().apply(sum).sum() / 60
    
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

    st.metric(label="Total Unique Session Duration (Minutes)", value=f"{total_webinar_duration:,.2f}")
    st.markdown("---")

    # Date preparation for monthly analysis
    try:
        df['Year'] = df['Year'].astype(str)
        df['Month'] = df['Month'].astype(str)
        date_series = df['Year'] + '-' + df['Month']
        df['YearMonth'] = pd.to_datetime(date_series, format='mixed').dt.to_period('M').astype(str)
    except KeyError:
        st.error("Error: Could not find 'Year' and 'Month' columns. Please check your Excel file.")
        st.stop()
    
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

    st.header("Region-wise Monthly Analysis")
    region_monthly = df.groupby(['YearMonth', 'Region']).agg(Registrations=('Email', 'nunique'), Attendance=('Attended', lambda x: (x == 'Yes').sum())).reset_index()
    fig = px.bar(region_monthly, x='YearMonth', y='Registrations', color='Region', title='Monthly Region-wise Registration', barmode='group')
    st.plotly_chart(fig, use_container_width=True)
    fig = px.bar(region_monthly, x='YearMonth', y='Attendance', color='Region', title='Monthly Region-wise Attendance', barmode='group')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")
    
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
    st.markdown("---")

    st.header("Detailed Monthly Workforce Breakdown")
    df['Workforce_Grouped'] = df['Workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else x)
    all_workforce_groups = sorted(df['Workforce_Grouped'].dropna().unique())
    selected_workforces = st.multiselect(
        'Select Workforce Categories to Display:',
        options=all_workforce_groups,
        default=all_workforce_groups
    )
    filtered_df = df[df['Workforce_Grouped'].isin(selected_workforces)]
    workforce_detail_monthly = filtered_df.groupby(['YearMonth', 'Workforce_Grouped']).agg(
        Registrations=('Email', 'nunique'),
        Attendance=('Attended', lambda x: (x == 'Yes').sum())
    ).reset_index()
    st.subheader("Workforce Registration")
    fig_reg = px.bar(workforce_detail_monthly, x='YearMonth', y='Registrations', color='Workforce_Grouped',
                     title='Monthly Workforce Registration Distribution', barmode='stack')
    st.plotly_chart(fig_reg, use_container_width=True)
    st.subheader("Workforce Attendance")
    fig_att = px.bar(workforce_detail_monthly, x='YearMonth', y='Attendance', color='Workforce_Grouped',
                     title='Monthly Workforce Attendance Distribution', barmode='stack')
    st.plotly_chart(fig_att, use_container_width=True)
    st.markdown("---")

    st.header("Overall Performance by Region")
    
    if 'Region' in df.columns and 'Attended' in df.columns:
        # Group by Region and calculate total registrations and attendees
        regional_performance = df.groupby('Region').agg(
            Registrations=('Attended', 'count'),
            Attendees=('Attended', lambda x: (x == 'Yes').sum())
        ).reset_index()
        
        # Shorten region names for cleaner chart labels
        regional_performance['Region'] = regional_performance['Region'].str.split('-').str[0].str.strip()
        
        # Melt the DataFrame to prepare for a grouped bar chart
        regional_performance_melted = regional_performance.melt(
            id_vars='Region', 
            value_vars=['Registrations', 'Attendees'],
            var_name='Metric', 
            value_name='Count'
        )

        # Create the grouped bar chart
        fig = px.bar(
            regional_performance_melted,
            x='Region',
            y='Count',
            color='Metric',
            barmode='group',
            title='Total Registrations vs. Attendees by Region'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("One or more required columns ('Region', 'Attended') not found for the regional performance chart.")
    
    st.markdown("---")

    st.header("Registrations vs. Attendance Comparison by Region")

    # Check for the columns needed for this new logic
    if 'Region' in df.columns and 'attendee type' in df.columns and 'YearMonth' in df.columns and 'Attended' in df.columns:
        
        region_list = sorted(df['Region'].dropna().unique())

        selected_region_comp = st.selectbox(
            'Select a Region for Comparison:',
            options=region_list,
            key='region_comparison_selectbox'
        )
        
        # Filter data by selected region and attendee type
        comp_df = df[
            (df['Region'] == selected_region_comp) &
            (df['attendee type'] == 'ATTENDEE')
        ].copy()

        if not comp_df.empty:
            # Group by the existing 'YearMonth' column
            monthly_comp = comp_df.groupby('YearMonth').agg(
                Registrations=('Attended', 'count'),
                Attendees=('Attended', lambda x: (x == 'Yes').sum())
            ).reset_index()
            
            # Melt the DataFrame to prepare for grouped bar chart
            monthly_comp_melted = monthly_comp.melt(
                id_vars='YearMonth', 
                value_vars=['Registrations', 'Attendees'],
                var_name='Metric', 
                value_name='Count'
            )

            fig = px.bar(
                monthly_comp_melted,
                x='YearMonth',
                y='Count',
                color='Metric',
                barmode='group',
                title=f'Monthly Registrations vs. Attendees for {selected_region_comp}',
                labels={'YearMonth': 'Month'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No 'ATTENDEE' data found for '{selected_region_comp}'.")
            
    else:
        st.error("One or more required columns ('Region', 'attendee type', 'YearMonth', 'Attended') not found for the regional comparison.")


else:
    st.warning("Data could not be loaded. Please check the file path and format.")
