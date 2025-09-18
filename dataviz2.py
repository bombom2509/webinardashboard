import streamlit as st
import pandas as pd
import plotly.express as px
import io
from fpdf import FPDF
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches

# --- Page and App Configuration ---
st.set_page_config(layout="wide")

# Color Palette from Your Logo
LOGO_COLORS = {
    "primary_blue": "#0072CE",
    "accent_green": "#5DBB46"
}

# --- Data Loading Function (Cached) ---
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_excel(file_path, sheet_name=0)
        df.columns = df.columns.str.strip().str.lower()
        numeric_cols = ['actual duration (minutes)', 'time in session (minutes)']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df[numeric_cols] = df[numeric_cols].fillna(0)
        if 'workforce' in df.columns:
            df['workforce'] = df['workforce'].astype(str)
        # Shorten region names globally for consistency
        if 'region' in df.columns:
            df['region'] = df['region'].str.split('-').str[0].str.strip()
        return df
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while loading data: {e}")
        return None

# --- PDF Generation Function (Cached for Performance) ---
@st.cache_data
def create_full_report_pdf(df, logo_path, nursing_facilities_workforce, report_date_str):
    """
    Generates a comprehensive, multi-page PDF report using Matplotlib.
    This function is cached to ensure the app loads quickly.
    """
    pdf = FPDF(orientation='L')
    page_width = pdf.w
    page_height = pdf.h

    # --- Helper function to save Matplotlib figures to the PDF ---
    def save_mpl_fig_to_pdf(fig, pdf_obj, x=10, y=30, w=None):
        if w is None:
            w = page_width - 20
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        pdf_obj.image(buf, x=x, y=y, w=w)
        plt.close(fig)

    # --- Data Preparation ---
    try:
        df['yearmonth'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str)).dt.to_period('M').astype(str)
        df['facility_type'] = df['workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else 'Non-Nursing Facility')
    except KeyError:
        return None # Return None on error

    # --- 1. Create the Title Page ---
    pdf.add_page()
    pdf.image(logo_path, x=(page_width - 80) / 2, y=20, w=80)
    pdf.ln(70)
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "Webinar Performance Dashboard", ln=True, align='C')
    pdf.set_font("Arial", '', 14)
    pdf.cell(0, 10, f"Report Generated on: {report_date_str}", ln=True, align='C')

    # --- 2. Monthly Analysis Chart (WITH UPDATED CALCULATION) ---
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "Monthly Analysis", ln=True)
    monthly_data = df.groupby('yearmonth').agg(
        total_registrants=('attendee type', lambda ser: (ser.str.lower() == 'attendee').sum()),
        total_attendees=('attended', lambda x: (x == 'Yes').sum())
    ).reset_index()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(monthly_data['yearmonth'], monthly_data['total_registrants'], label='Total Registrants', color=LOGO_COLORS["primary_blue"], marker='o')
    ax.plot(monthly_data['yearmonth'], monthly_data['total_attendees'], label='Total Attendees', color=LOGO_COLORS["accent_green"], marker='o')
    ax.set_title('Monthly Registration vs. Attendance'); ax.set_ylabel('Count'); ax.tick_params(axis='x', rotation=45); ax.legend(); ax.grid(True, linestyle='--', alpha=0.6); fig.tight_layout()
    save_mpl_fig_to_pdf(fig, pdf)

    # --- 3. Detailed Monthly Workforce Breakdown Chart ---
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "Detailed Monthly Workforce Breakdown", ln=True)
    workforce_detail_monthly = df[df['attended'] == 'Yes'].groupby(['yearmonth', 'facility_type']).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 5))
    workforce_detail_monthly.plot(kind='bar', stacked=True, ax=ax, color=[LOGO_COLORS["accent_green"], '#D9534F'])
    ax.set_title('Monthly Workforce Attendance Distribution'); ax.set_ylabel('Attendance Count'); ax.set_xlabel('Month'); ax.tick_params(axis='x', rotation=45); ax.legend(title='Facility Type'); ax.grid(True, linestyle='--', alpha=0.6); fig.tight_layout()
    save_mpl_fig_to_pdf(fig, pdf)

    # --- 4. Overall Performance by Region Chart ---
    pdf.add_page(); pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, "Overall Performance by Region", ln=True)
    regional_performance = df.groupby('region').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    sorted_regions = sorted(regional_performance['region'].unique(), key=lambda r: int(r.replace('Region ', '')))
    labels = sorted_regions
    registrations = [regional_performance[regional_performance['region'] == r]['registrations'].sum() for r in labels]
    attendees = [regional_performance[regional_performance['region'] == r]['attendees'].sum() for r in labels]
    x = np.arange(len(labels)); width = 0.35
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width/2, registrations, width, label='Registrations', color=LOGO_COLORS["primary_blue"])
    ax.bar(x + width/2, attendees, width, label='Attendees', color=LOGO_COLORS["accent_green"])
    ax.set_ylabel('Count'); ax.set_title('Total Registrations vs. Attendees by Region'); ax.set_xticks(x); ax.set_xticklabels(labels, rotation=45, ha="right"); ax.legend(); ax.grid(True, linestyle='--', alpha=0.6); fig.tight_layout()
    save_mpl_fig_to_pdf(fig, pdf)

    # --- Helper for positioning charts in a grid ---
    def plot_grid(pdf_obj, charts_data, plot_function, legend_info=None):
        pdf_obj.add_page()
        pdf_obj.set_font("Arial", 'B', 16)
        pdf_obj.cell(0, 10, charts_data['title'], ln=True)
        pdf_obj.ln(5)

        sorted_regions = sorted(df['region'].dropna().unique(), key=lambda r: int(r.replace('Region ', '')))

        margin = 10
        charts_per_row = 4
        chart_dim_mm = 50
        chart_dim_inches = chart_dim_mm / 25.4
        
        available_width = pdf_obj.w - (2 * margin)
        spacing_x = (available_width - (charts_per_row * chart_dim_mm)) / (charts_per_row - 1) if charts_per_row > 1 else 0
        spacing_y = 15
        y_start = 25

        for i, region in enumerate(sorted_regions):
            row = i // charts_per_row
            col = i % charts_per_row
            x_pos = margin + col * (chart_dim_mm + spacing_x)
            y_pos = y_start + row * (chart_dim_mm + spacing_y)
            
            fig = plot_function(region, chart_dim_inches, chart_dim_inches)
            if fig:
                save_mpl_fig_to_pdf(fig, pdf_obj, x=x_pos, y=y_pos, w=chart_dim_mm)
        
        if legend_info:
            legend_fig, legend_ax = plt.subplots(figsize=(2, 0.5))
            patches = [mpatches.Patch(color=c, label=l) for l, c in zip(legend_info['labels'], legend_info['colors'])]
            legend_ax.legend(handles=patches, loc='center', ncol=len(legend_info['labels']), frameon=False, fontsize=9)
            legend_ax.axis('off')
            
            legend_width_mm = 50
            legend_height_mm = 10
            legend_x = pdf_obj.w - margin - legend_width_mm
            legend_y = pdf_obj.h - margin - legend_height_mm
            
            save_mpl_fig_to_pdf(legend_fig, pdf_obj, x=legend_x, y=legend_y, w=legend_width_mm)

    # --- 5. Plotting function for Doughnut Charts ---
    def create_doughnut_chart(region, fig_w, fig_h):
        df_region = df[(df['region'] == region) & (df['attended'] == 'Yes')]
        if df_region.empty:
            return None
        
        breakdown = df_region['facility_type'].value_counts()
        workforce_color_map = {'Nursing Facility': LOGO_COLORS["accent_green"], 'Non-Nursing Facility': LOGO_COLORS["primary_blue"]}
        
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.pie(breakdown, labels=None, autopct='%1.1f%%',
               colors=[workforce_color_map.get(x, '#CCCCCC') for x in breakdown.index], 
               startangle=90, wedgeprops=dict(width=0.4, edgecolor='w'), 
               textprops={'fontsize': 8, 'color': 'black'})
        ax.set_title(f'{region}', fontsize=10)
        ax.set_aspect('equal')
        return fig

    # --- 6. Plotting function for Bar Charts ---
    def create_bar_chart(region, fig_w, fig_h):
        comp_df = df[(df['region'] == region) & (df['attendee type'].str.title().isin(['Attendee', 'Guest']))].copy()
        if comp_df.empty:
            return None

        monthly_comp = comp_df.groupby('yearmonth').agg(
            registrations=('attended', 'count'), 
            attendees=('attended', lambda x: (x == 'Yes').sum())
        ).reset_index()
        
        labels = monthly_comp['yearmonth']
        registrations = monthly_comp['registrations']
        attendees = monthly_comp['attendees']
        x = np.arange(len(labels))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.bar(x - width/2, registrations, width, label='Regs', color=LOGO_COLORS["primary_blue"])
        ax.bar(x + width/2, attendees, width, label='Atts', color=LOGO_COLORS["accent_green"])
        
        ax.set_ylabel('Count', fontsize=7)
        ax.set_title(f'Monthly - {region}', fontsize=10)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=90, ha="right", fontsize=3)
        ax.tick_params(axis='y', labelsize=7)
        ax.legend(fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.6)
        fig.tight_layout(pad=0.5)
        return fig

    # --- Call grid plotters for sections 5 and 6 ---
    workforce_legend_info = {
        'labels': ['Nursing Facility', 'Non-Nursing Facility'],
        'colors': [LOGO_COLORS["accent_green"], '#D9534F']
    }
    plot_grid(pdf, {'title': "Region-wise Nursing vs Non-Nursing Attendance"}, create_doughnut_chart, legend_info=workforce_legend_info)
    plot_grid(pdf, {'title': "Registrations vs. Attendance Comparison by Region"}, create_bar_chart)

    return bytes(pdf.output())


# --- Main App Logic ---
file_location = "MASTERDASH_updated_20250917-081847.xlsx"
logo_path = "logo.jpeg"

df = load_data(file_location)

if df is not None:
    # --- Sidebar and CSS ---
    st.sidebar.image(logo_path, use_container_width=True)
    st.sidebar.title("Navigation")
    headers = [
        'Key Performance Indicators', 'Monthly Analysis', 'Detailed Monthly Workforce Breakdown',
        'Overall Performance by Region', 'Region-wise Nursing vs Non Nursing Attendance',
        'Registrations vs. Attendance Comparison by Region'
    ]
    for header in headers:
        anchor = header.lower().replace(' ', '-').replace('.', '')
        st.sidebar.markdown(f'<a href="#{anchor}" class="nav-button" data-target="{anchor}">{header}</a>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <style>
        .main {{ background-color: #f5f5ff; }}
        h1, h2 {{ color: {LOGO_COLORS['primary_blue']}; scroll-margin-top: 80px; }}
        a.nav-button {{ display: block; padding: 12px 15px; margin-bottom: 8px; background-color: #fff; color: #333; text-align: left; text-decoration: none !important; border-radius: 10px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,.05); transition: all .3s ease-in-out; font-weight: 500; }}
        a.nav-button:hover {{ background-color: {LOGO_COLORS['accent_green']}; color: #fff; box-shadow: 0 4px 8px rgba(0,0,0,.15); transform: translateY(-2px); }}
        a.nav-button.active {{ background-color: {LOGO_COLORS['primary_blue']} !important; color: #fff !important; box-shadow: 0 4px 12px rgba(0,114,206,.4); border-color: {LOGO_COLORS['primary_blue']}; font-weight: 600; }}
        a.nav-button.active:hover {{ background-color: #005a9e !important; transform: translateY(-1px); }}
        .stMetric {{ background-color: #fff; border: 1px solid #e0e0e0; border-left: 5px solid {LOGO_COLORS['primary_blue']}; border-radius: 10px; padding: 15px; box-shadow: 0 4px 8px rgba(0,0,0,.1); }}
        .stPlotlyChart {{ border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,.1); }}
        h2[id] {{ position: relative; }}
        .stMetric [data-testid="stMetricLabel"] {{ color: {LOGO_COLORS['primary_blue']}; }}
        .stMetric [data-testid="stMetricValue"] {{ color: #31333F; }}
    </style>
    """, unsafe_allow_html=True)

    # --- Header with Title and Download Button ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title('Webinar Performance Dashboard')

    with col2:
        st.markdown("<div style='height: 2.5rem;'></div>", unsafe_allow_html=True)
        
        nursing_list = [
            'Mental Health Treatment, Nursing Facility','Mental Health Treatment, Nursing Facility, Substance Use Treatment','Mental Health Treatment, Substance Use Treatment, Nursing Facility',
            'Nursing Facility', 'Nursing Facility, Mental Health Treatment','Nursing Facility, Mental Health Treatment, Other','Nursing Facility, Mental Health Treatment, Substance Use Treatment',
            'Nursing Facility, Other', 'Nursing Facility, Substance Use Treatment','Nursing Facility, Substance Use Treatment, Mental Health Treatment','Nursing Facility,Mental Health Treatment,QIN-QIO',
            'Nursing Facility,Mental Health Treatment,Substance Use Treatment,QIN-QIO','Nursing Facility,QIN-QIO', 'Nursing Facility,QIN-QIO,Mental Health Treatment',
            'Nursing Facility,QIN-QIO,Other', 'Other, Nursing Facility','Substance Use Treatment, Nursing Facility'
        ]
        
        report_date = pd.Timestamp.now().strftime('%Y-%m-%d')
        pdf_bytes = create_full_report_pdf(df.copy(), logo_path, nursing_list, report_date)

        if pdf_bytes:
            st.download_button(
                label="Download Report (PDF)",
                data=pdf_bytes,
                file_name=f"webinar_report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.error("PDF could not be generated.")

    st.markdown("---")
    
    # --- KPIs and Dashboard Content ---
    st.header('Key Performance Indicators')
    registrants = df.drop_duplicates(subset=['webinar id', 'actual start time'])['registrations'].sum()
    attendee_filtered_df = df[(df['attendee type'].str.title().isin(['Attendee', 'Guest'])) & (df['attended'] == 'Yes')]
    attendees = attendee_filtered_df.shape[0]
    nursing_facility_attendees = attendee_filtered_df[attendee_filtered_df['workforce'].isin(nursing_list)].shape[0]
    non_nursing_facility_attendees = attendee_filtered_df[~attendee_filtered_df['workforce'].isin(nursing_list)].shape[0]
    total_engagement_hours = attendee_filtered_df['time in session (minutes)'].sum() / 60
    total_orgs = df['organization'].nunique()
    nursing_facility_orgs = df[df['workforce'].isin(nursing_list)]['organization'].nunique()
    non_nursing_facility_orgs = total_orgs - nursing_facility_orgs
    total_webinar_duration = df.groupby('webinar id')['actual duration (minutes)'].first().sum() / 60
    
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.metric(label="Total Registrants", value=f"{registrants:,.0f}")
        st.metric(label="Total Organizations", value=f"{total_orgs:,}")
    with kpi_col2:
        st.metric(label="Total Attendees", value=f"{attendees:,}")
        st.metric(label="Nursing Facility Orgs", value=f"{nursing_facility_orgs:,}")
    with kpi_col3:
        st.metric(label="Nursing Facility Attendees", value=f"{nursing_facility_attendees:,}")
        st.metric(label="Non-Nursing Facility Orgs", value=f"{non_nursing_facility_orgs:,}")
    with kpi_col4:
        st.metric(label="Non-Nursing Facility Attendees", value=f"{non_nursing_facility_attendees:,}")
        st.metric(label="Engagement (Hours)", value=f"{total_engagement_hours:,.2f}")
    
    st.metric(label="Total Unique Session Duration (Hours)", value=f"{total_webinar_duration:,.2f}")
    st.markdown("---")

    try:
        df['yearmonth'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str), format='mixed').dt.to_period('M').astype(str)
        df['facility_type'] = df['workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_list else 'Non-Nursing Facility')
    except KeyError:
        st.error("Error: Could not find 'year' and 'month' columns for dashboard charts."); st.stop()

    # --- Monthly Analysis Section ---
    st.header("Monthly Analysis")
    monthly_data = df.groupby('yearmonth').agg(
        total_registrants=('attendee type', lambda ser: (ser.str.lower() == 'attendee').sum()),
        total_attendees=('attended', lambda x: (x == 'Yes').sum())
    ).reset_index()

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        fig_bar1 = px.bar(monthly_data, x='yearmonth', y='total_registrants', title='Monthly Registration Distribution', color_discrete_sequence=[LOGO_COLORS["primary_blue"]])
        st.plotly_chart(fig_bar1, use_container_width=True)
    with chart_col2:
        fig_bar2 = px.bar(monthly_data, x='yearmonth', y='total_attendees', title='Monthly Attendance Distribution', color_discrete_sequence=[LOGO_COLORS["accent_green"]])
        st.plotly_chart(fig_bar2, use_container_width=True)
    
    fig_line = px.line(monthly_data, x='yearmonth', y=['total_registrants', 'total_attendees'], title='Monthly Registration vs. Attendance', labels={'value': 'Count', 'variable': 'Metric'}, color_discrete_sequence=[LOGO_COLORS["primary_blue"], LOGO_COLORS["accent_green"]])
    st.plotly_chart(fig_line, use_container_width=True)
    st.markdown("---")

    # --- MODIFIED DETAILED MONTHLY WORKFORCE BREAKDOWN ---
    st.header("Detailed Monthly Workforce Breakdown")
    
    # Create a pre-filtered DataFrame for the attendance calculation
    attendee_guest_df = df[df['attendee type'].str.title().isin(['Attendee', 'Guest'])]
    
    # Perform aggregations
    registrations_by_workforce = df.groupby(['yearmonth', 'facility_type'])['attendee type'].apply(lambda ser: (ser.str.lower() == 'attendee').sum()).reset_index(name='registrations')
    attendance_by_workforce = attendee_guest_df[attendee_guest_df['attended'] == 'Yes'].groupby(['yearmonth', 'facility_type']).size().reset_index(name='attendance')

    # Merge the two results together for charting
    workforce_detail_monthly = pd.merge(registrations_by_workforce, attendance_by_workforce, on=['yearmonth', 'facility_type'], how='left').fillna(0)
    
   workforce_color_map = {'Nursing Facility': LOGO_COLORS["accent_green"], 'Non-Nursing Facility': LOGO_COLORS["primary_blue"]}
    
    st.subheader("Workforce Registration")
    fig_reg = px.bar(workforce_detail_monthly, x='yearmonth', y='registrations', color='facility_type', title='Monthly Workforce Registration Distribution', barmode='stack', color_discrete_map=workforce_color_map)
    st.plotly_chart(fig_reg, use_container_width=True)
    
    st.subheader("Workforce Attendance")
    fig_att = px.bar(workforce_detail_monthly, x='yearmonth', y='attendance', color='facility_type', title='Monthly Workforce Attendance Distribution', barmode='stack', color_discrete_map=workforce_color_map)
    st.plotly_chart(fig_att, use_container_width=True)
    st.markdown("---")

    st.header("Overall Performance by Region")
    if 'region' in df.columns:
        regional_performance = df.groupby('region').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
        regional_performance_melted = regional_performance.melt(id_vars='region', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
        sorted_regions_plotly = sorted(regional_performance_melted['region'].unique(), key=lambda r: int(r.replace('Region ', '')))
        fig_region = px.bar(regional_performance_melted, x='region', y='count', color='metric', barmode='group', title='Total Registrations vs. Attendees by Region', color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]}, category_orders={'region': sorted_regions_plotly})
        st.plotly_chart(fig_region, use_container_width=True)
    else:
        st.error("Column 'region' not found.")
    st.markdown("---")

    st.header("Region-wise Nursing vs Non Nursing Attendance")
    if 'region' in df.columns:
        region_list_for_doughnut = sorted(df['region'].dropna().unique(), key=lambda r: int(r.replace('Region ', '')))
        selected_region_doughnut = st.selectbox('Select a Region to Display:', options=region_list_for_doughnut, key='region_doughnut_selectbox')
        region_doughnut_df = df[(df['region'] == selected_region_doughnut) & (df['attended'] == 'Yes')]
        if not region_doughnut_df.empty:
            attendance_breakdown = region_doughnut_df['facility_type'].value_counts().reset_index()
            attendance_breakdown.columns = ['facility_type', 'count']
            fig_doughnut = px.pie(attendance_breakdown, names='facility_type', values='count', title=f'Nursing vs. Non-Nursing Attendance in {selected_region_doughnut}', hole=0.4, color='facility_type', color_discrete_map=workforce_color_map)
            fig_doughnut.update_traces(textinfo='percent+label', pull=[0.05, 0])
            fig_doughnut.update_layout(legend_title_text='Facility Type')
            st.plotly_chart(fig_doughnut, use_container_width=True)
        else:
            st.warning(f"No attendance data found for '{selected_region_doughnut}'.")
    else:
        st.error("Column 'region' not found.")
    st.markdown("---")

    st.header("Registrations vs. Attendance Comparison by Region")
    if 'region' in df.columns and 'attendee type' in df.columns and 'yearmonth' in df.columns:
        region_list_comp = sorted(df['region'].dropna().unique(), key=lambda r: int(r.replace('Region ', '')))
        selected_region_comp = st.selectbox('Select a Region for Comparison:', options=region_list_comp, key='region_comparison_selectbox')
        comp_df = df[(df['region'] == selected_region_comp) & (df['attendee type'].str.title().isin(['Attendee', 'Guest']))].copy()
        if not comp_df.empty:
            monthly_comp = comp_df.groupby('yearmonth').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
            monthly_comp_melted = monthly_comp.melt(id_vars='yearmonth', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
            fig_comp = px.bar(monthly_comp_melted, x='yearmonth', y='count', color='metric', barmode='group', title=f'Monthly Registrations vs. Attendees for {selected_region_comp}', labels={'yearmonth': 'Month'}, color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]})
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.warning(f"No 'Attendee' or 'Guest' data found for '{selected_region_comp}'.")
    else:
        st.error("One or more required columns not found for regional comparison.")
    
    # JavaScript for Navigation with Blue Highlighting
    st.components.v1.html("""
    <script>
    function initializeNavigation() {
        console.log('Initializing navigation...');
        
        function setupHeaderIds() {
            const headers = parent.document.querySelectorAll('h2');
            headers.forEach(header => {
                if (!header.id) {
                    const text = header.textContent || header.innerText;
                    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
                    header.id = id;
                }
            });
        }
        
        function highlightActiveSection() {
            const headers = Array.from(parent.document.querySelectorAll('h2[id]'));
            const navButtons = Array.from(parent.document.querySelectorAll('.nav-button'));
            
            if (headers.length === 0 || navButtons.length === 0) return;
            
            let activeHeaderId = '';
            const scrollPosition = parent.window.scrollY + 100;
            
            for (let i = headers.length - 1; i >= 0; i--) {
                const header = headers[i];
                const headerTop = header.offsetTop;
                
                if (scrollPosition >= headerTop) {
                    activeHeaderId = header.id;
                    break;
                }
            }
            
            if (!activeHeaderId && headers.length > 0) {
                activeHeaderId = headers[0].id;
            }
            
            navButtons.forEach(button => {
                const targetId = button.getAttribute('data-target');
                if (targetId === activeHeaderId) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
            });
        }
        
        function setupSmoothScrolling() {
            const navButtons = parent.document.querySelectorAll('.nav-button');
            navButtons.forEach(button => {
                button.removeEventListener('click', handleNavClick);
                button.addEventListener('click', handleNavClick);
            });
        }
        
        function handleNavClick(e) {
            e.preventDefault();
            const targetId = this.getAttribute('data-target');
            const targetElement = parent.document.getElementById(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                
                setTimeout(() => {
                    const allNavButtons = parent.document.querySelectorAll('.nav-button');
                    allNavButtons.forEach(btn => btn.classList.remove('active'));
                    this.classList.add('active');
                }, 100);
            }
        }
        
        function debounce(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
        
        setupHeaderIds();
        setupSmoothScrolling();
        highlightActiveSection();
        
        const debouncedHighlight = debounce(highlightActiveSection, 100);
        parent.window.addEventListener('scroll', debouncedHighlight);
    }

    if (parent.document.readyState === 'loading') {
        parent.document.addEventListener('DOMContentLoaded', initializeNavigation);
    } else {
        initializeNavigation();
    }
    </script>
    """, height=0)

else:
    st.warning("Data could not be loaded. Please check the file path and format.")


