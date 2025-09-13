import streamlit as st
import pandas as pd
import plotly.express as px
import io
from fpdf import FPDF

# Set page configuration for a wider layout
st.set_page_config(layout="wide")

# --- Color Palette from Your Logo ---
LOGO_COLORS = {
    "primary_blue": "#0072CE",
    "accent_green": "#5DBB46"
}
COLOR_PALETTE = [LOGO_COLORS["primary_blue"], LOGO_COLORS["accent_green"], "#FFC107", "#17A2B8", "#FD7E14", "#6610F2"]

# --- Data Loading Function ---
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
        return df
    except FileNotFoundError:
        st.error(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None

# --- PDF Generation Function ---
def create_full_report_pdf(df, logo_path, nursing_facilities_workforce):
    """
    Generates a comprehensive, multi-page PDF report in LANDSCAPE with a title page
    and all charts from the dashboard.
    """
    pdf = FPDF(orientation='L')
    page_width = pdf.w
    
    # Create required columns inside the function to make it self-contained
    try:
        df['yearmonth'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str), format='mixed').dt.to_period('M').astype(str)
    except KeyError:
        st.error("Could not generate PDF because 'year' or 'month' columns are missing in the data.")
        return None
    df['facility_type'] = df['workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else 'Non-Nursing Facility')

    # --- 1. Create the Title Page ---
    pdf.add_page()
    pdf.image(logo_path, x=(page_width - 80) / 2, y=20, w=80)
    pdf.ln(70)
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "Webinar Performance Dashboard", ln=True, align='C')
    pdf.set_font("Arial", '', 14)
    pdf.cell(0, 10, f"Report Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d')}", ln=True, align='C')

    # --- 2. Add "Monthly Analysis" Charts ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Monthly Analysis", ln=True)
    monthly_data = df.groupby('yearmonth').agg(total_registrants=('email id', 'nunique'), total_attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    
    # FIX: Added the missing color argument to the line chart
    fig_monthly_line = px.line(monthly_data, x='yearmonth', y=['total_registrants', 'total_attendees'], title='Monthly Registration vs. Attendance', 
                               labels={'value': 'Count', 'variable': 'Metric'}, color_discrete_sequence=[LOGO_COLORS["primary_blue"], LOGO_COLORS["accent_green"]])
    pdf.image(io.BytesIO(fig_monthly_line.to_image(format="png", width=1000, height=400, scale=2)), x=10, y=30, w=page_width - 20)

    # --- 3. Add "Detailed Monthly Workforce Breakdown" Charts ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Detailed Monthly Workforce Breakdown", ln=True)
    workforce_detail_monthly = df.groupby(['yearmonth', 'facility_type']).agg(attendance=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    workforce_color_map = {'Nursing Facility': LOGO_COLORS["accent_green"], 'Non-Nursing Facility': '#D9534F'}
    fig_work_att = px.bar(workforce_detail_monthly, x='yearmonth', y='attendance', color='facility_type', title='Monthly Workforce Attendance Distribution', barmode='stack', color_discrete_map=workforce_color_map)
    pdf.image(io.BytesIO(fig_work_att.to_image(format="png", width=1000, height=400, scale=2)), x=10, y=30, w=page_width - 20)

    # --- 4. Add "Overall Performance by Region" Chart ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Overall Performance by Region", ln=True)
    regional_performance = df.groupby('region').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    regional_performance['region'] = regional_performance['region'].str.split('-').str[0].str.strip()
    regional_performance_melted = regional_performance.melt(id_vars='region', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
    unique_regions = regional_performance_melted['region'].unique()
    sorted_regions = sorted(unique_regions, key=lambda r: int(r.replace('Region ', '')))
    fig_region = px.bar(regional_performance_melted, x='region', y='count', color='metric', barmode='group', title='Total Registrations vs. Attendees by Region', color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]}, category_orders={'region': sorted_regions})
    pdf.image(io.BytesIO(fig_region.to_image(format="png", width=1000, height=450, scale=2)), x=10, y=30, w=page_width - 20)

    # --- 5. Loop and Add ALL "Region-wise...Doughnut" Charts ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Region-wise Nursing vs Non Nursing Attendance", ln=True); pdf.ln(5)
    region_list_doughnut = sorted(df['region'].dropna().unique())
    x_pos = [10, page_width / 2 + 5]; y_pos = 25; chart_idx = 0
    for region in region_list_doughnut:
        if chart_idx > 0 and chart_idx % 2 == 0: pdf.add_page(orientation='L'); y_pos = 25
        df_region = df[(df['region'] == region) & (df['attended'] == 'Yes')]
        if not df_region.empty:
            breakdown = df_region['facility_type'].value_counts().reset_index(); breakdown.columns = ['facility_type', 'count']
            fig_doughnut = px.pie(breakdown, names='facility_type', values='count', title=f'Attendance in {region}', hole=0.4, color='facility_type', color_discrete_map=workforce_color_map)
            fig_doughnut.update_traces(textinfo='percent+label', pull=[0.05, 0])
            pdf.image(io.BytesIO(fig_doughnut.to_image(format="png", width=500, height=400, scale=2)), x=x_pos[chart_idx % 2], y=y_pos, w=(page_width/2) - 20)
            chart_idx +=1
            
    # --- 6. Loop and Add ALL "Registrations vs. Attendance...by Region" Charts ---
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Registrations vs. Attendance Comparison by Region", ln=True)

    region_list_comp = sorted(df['region'].dropna().unique())
    for region in region_list_comp:
        pdf.add_page()
        comp_df = df[(df['region'] == region) & (df['attendee type'].str.title().isin(['Attendee', 'Guest']))].copy()
        if not comp_df.empty:
            monthly_comp = comp_df.groupby('yearmonth').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
            monthly_comp_melted = monthly_comp.melt(id_vars='yearmonth', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
            fig_comp = px.bar(monthly_comp_melted, x='yearmonth', y='count', color='metric', barmode='group', title=f'Monthly Registrations vs. Attendees for {region}', color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]})
            pdf.image(io.BytesIO(fig_comp.to_image(format="png", width=1000, height=450, scale=2)), x=10, y=30, w=page_width - 20)

    return bytes(pdf.output())

# --- Main App Logic ---
file_location = "MASTERDASH_updated_20250912-204444.xlsx"
df = load_data(file_location)

if df is not None:
    logo_path = "logo.jpeg"
    try:
        st.sidebar.image(logo_path, use_container_width=True)
    except Exception as e:
        st.sidebar.error(f"Logo not found: {logo_path}")

    st.sidebar.title("Navigation")
    headers = [
        'Key Performance Indicators', 'Monthly Analysis', 'Detailed Monthly Workforce Breakdown',
        'Overall Performance by Region', 'Region-wise Nursing vs Non Nursing Attendance',
        'Registrations vs. Attendance Comparison by Region'
    ]
    for header in headers:
        anchor = header.lower().replace(' ', '-').replace('.', '')
        st.sidebar.markdown(f'<a href="#{anchor}" class="nav-button" data-target="{anchor}">{header}</a>', unsafe_allow_html=True)
    
    st.markdown(f"""<style>.main{{background-color:#f5f5ff}}h1,h2{{color:{LOGO_COLORS['primary_blue']};scroll-margin-top:80px}}a.nav-button{{display:block;padding:12px 15px;margin-bottom:8px;background-color:#fff;color:#333;text-align:left;text-decoration:none !important;border-radius:10px;border:1px solid #e0e0e0;box-shadow:0 2px 4px rgba(0,0,0,.05);transition:all .3s ease-in-out;font-weight:500}}a.nav-button:hover{{background-color:{LOGO_COLORS['accent_green']};color:#fff;box-shadow:0 4px 8px rgba(0,0,0,.15);transform:translateY(-2px)}}a.nav-button.active{{background-color:{LOGO_COLORS['primary_blue']} !important;color:#fff !important;box-shadow:0 4px 12px rgba(0,114,206,.4);border-color:{LOGO_COLORS['primary_blue']};font-weight:600}}a.nav-button.active:hover{{background-color:#005a9e !important;transform:translateY(-1px)}}.stMetric{{background-color:#fff;border:1px solid #e0e0e0;border-left:5px solid {LOGO_COLORS['primary_blue']};border-radius:10px;padding:15px;box-shadow:0 4px 8px rgba(0,0,0,.1)}}.stMetric>div>div:first-child{{color:{LOGO_COLORS['primary_blue']}}}.stPlotlyChart{{border-radius:10px;box-shadow:0 4px 8px rgba(0,0,0,.1)}}h2[id]{{position:relative}}</style>""", unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.title('Webinar Performance Dashboard')

    with col2:
        st.markdown("<div style='height: 2.5rem;'></div>", unsafe_allow_html=True)
        if st.button("Generate Report (PDF)"):
            with st.spinner("Generating PDF, please wait..."):
                nursing_list = [
                    'Mental Health Treatment, Nursing Facility','Mental Health Treatment, Nursing Facility, Substance Use Treatment','Mental Health Treatment, Substance Use Treatment, Nursing Facility',
                    'Nursing Facility', 'Nursing Facility, Mental Health Treatment','Nursing Facility, Mental Health Treatment, Other','Nursing Facility, Mental Health Treatment, Substance Use Treatment',
                    'Nursing Facility, Other', 'Nursing Facility, Substance Use Treatment','Nursing Facility, Substance Use Treatment, Mental Health Treatment','Nursing Facility,Mental Health Treatment,QIN-QIO',
                    'Nursing Facility,Mental Health Treatment,Substance Use Treatment,QIN-QIO','Nursing Facility,QIN-QIO', 'Nursing Facility,QIN-QIO,Mental Health Treatment',
                    'Nursing Facility,QIN-QIO,Other', 'Other, Nursing Facility','Substance Use Treatment, Nursing Facility'
                ]
                pdf_bytes = create_full_report_pdf(df.copy(), logo_path, nursing_list)
                st.session_state.pdf_report_bytes = pdf_bytes
                st.rerun()
    
    if 'pdf_report_bytes' in st.session_state and st.session_state.pdf_report_bytes:
        with col2:
            st.download_button(
                label="Download PDF",
                data=st.session_state.pdf_report_bytes,
                file_name=f"webinar_report_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
            if st.button("Clear Download", key="clear_pdf"):
                st.session_state.pdf_report_bytes = None
                st.rerun()

    st.markdown("---")
    
    st.header('Key Performance Indicators')
    nursing_facilities_workforce = [
        'Mental Health Treatment, Nursing Facility','Mental Health Treatment, Nursing Facility, Substance Use Treatment','Mental Health Treatment, Substance Use Treatment, Nursing Facility',
        'Nursing Facility', 'Nursing Facility, Mental Health Treatment','Nursing Facility, Mental Health Treatment, Other','Nursing Facility, Mental Health Treatment, Substance Use Treatment',
        'Nursing Facility, Other', 'Nursing Facility, Substance Use Treatment','Nursing Facility, Substance Use Treatment, Mental Health Treatment','Nursing Facility,Mental Health Treatment,QIN-QIO',
        'Nursing Facility,Mental Health Treatment,Substance Use Treatment,QIN-QIO','Nursing Facility,QIN-QIO', 'Nursing Facility,QIN-QIO,Mental Health Treatment',
        'Nursing Facility,QIN-QIO,Other', 'Other, Nursing Facility','Substance Use Treatment, Nursing Facility'
    ]
    registrants = df.drop_duplicates(subset=['webinar id', 'actual start time'])['registrations'].sum()
    attendee_filtered_df = df[(df['attendee type'].str.title().isin(['Attendee', 'Guest'])) & (df['attended'] == 'Yes')]
    attendees = attendee_filtered_df.shape[0]
    nursing_facility_attendees = attendee_filtered_df[attendee_filtered_df['workforce'].isin(nursing_facilities_workforce)].shape[0]
    non_nursing_facility_attendees = attendee_filtered_df[~attendee_filtered_df['workforce'].isin(nursing_facilities_workforce)].shape[0]
    total_engagement_hours = attendee_filtered_df['time in session (minutes)'].sum() / 60
    total_orgs = df['organization'].nunique()
    nursing_facility_orgs = df[df['workforce'].isin(nursing_facilities_workforce)]['organization'].nunique()
    non_nursing_facility_orgs = total_orgs - nursing_facility_orgs
    total_webinar_duration = df.groupby('webinar id')['actual duration (minutes)'].unique().apply(sum).sum() / 60
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="Total Registrants", value=f"{registrants:,.0f}"); st.metric(label="Total Organizations", value=f"{total_orgs:,}")
    with col2: st.metric(label="Total Attendees", value=f"{attendees:,}"); st.metric(label="Nursing Facility Orgs", value=f"{nursing_facility_orgs:,}")
    with col3: st.metric(label="Nursing Facility Attendees", value=f"{nursing_facility_attendees:,}"); st.metric(label="Non-Nursing Facility Orgs", value=f"{non_nursing_facility_orgs:,}")
    with col4: st.metric(label="Non-Nursing Facility Attendees", value=f"{non_nursing_facility_attendees:,}"); st.metric(label="Engagement (Hours)", value=f"{total_engagement_hours:,.2f}")
    st.metric(label="Total Unique Session Duration (Hours)", value=f"{total_webinar_duration:,.2f}"); st.markdown("---")

    try:
        df['yearmonth'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str), format='mixed').dt.to_period('M').astype(str)
        df['facility_type'] = df['workforce'].apply(lambda x: 'Nursing Facility' if x in nursing_facilities_workforce else 'Non-Nursing Facility')
    except KeyError:
        st.error("Error: Could not find 'year' and 'month' columns."); st.stop()

    st.header("Monthly Analysis")
    monthly_data = df.groupby('yearmonth').agg(total_registrants=('email id', 'nunique'), total_attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(monthly_data, x='yearmonth', y='total_registrants', title='Monthly Registration Distribution', color_discrete_sequence=[LOGO_COLORS["primary_blue"]]); st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = px.bar(monthly_data, x='yearmonth', y='total_attendees', title='Monthly Attendance Distribution', color_discrete_sequence=[LOGO_COLORS["accent_green"]]); st.plotly_chart(fig, use_container_width=True)
    fig = px.line(monthly_data, x='yearmonth', y=['total_registrants', 'total_attendees'], title='Monthly Registration vs. Attendance', labels={'value': 'Count', 'variable': 'Metric'}, color_discrete_sequence=[LOGO_COLORS["primary_blue"], LOGO_COLORS["accent_green"]]); st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

    st.header("Detailed Monthly Workforce Breakdown")
    workforce_detail_monthly = df.groupby(['yearmonth', 'facility_type']).agg(registrations=('email id', 'nunique'), attendance=('attended', lambda x: (x == 'Yes').sum())).reset_index()
    workforce_color_map = {'Nursing Facility': LOGO_COLORS["accent_green"], 'Non-Nursing Facility': '#D9534F'}
    st.subheader("Workforce Registration"); fig_reg = px.bar(workforce_detail_monthly, x='yearmonth', y='registrations', color='facility_type', title='Monthly Workforce Registration Distribution', barmode='stack', color_discrete_map=workforce_color_map); st.plotly_chart(fig_reg, use_container_width=True)
    st.subheader("Workforce Attendance"); fig_att = px.bar(workforce_detail_monthly, x='yearmonth', y='attendance', color='facility_type', title='Monthly Workforce Attendance Distribution', barmode='stack', color_discrete_map=workforce_color_map); st.plotly_chart(fig_att, use_container_width=True)
    st.markdown("---")

    st.header("Overall Performance by Region")
    if 'region' in df.columns:
        regional_performance = df.groupby('region').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
        regional_performance['region'] = regional_performance['region'].str.split('-').str[0].str.strip()
        regional_performance_melted = regional_performance.melt(id_vars='region', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
        unique_regions = regional_performance_melted['region'].unique()
        sorted_regions = sorted(unique_regions, key=lambda r: int(r.replace('Region ', '')))
        fig = px.bar(regional_performance_melted, x='region', y='count', color='metric', barmode='group', title='Total Registrations vs. Attendees by Region', color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]}, category_orders={'region': sorted_regions})
        st.plotly_chart(fig, use_container_width=True)
    else: st.error("Column 'region' not found.")
    st.markdown("---")

    st.header("Region-wise Nursing vs Non Nursing Attendance")
    if 'region' in df.columns:
        region_list_for_doughnut = sorted(df['region'].dropna().unique())
        selected_region_doughnut = st.selectbox('Select a Region to Display:', options=region_list_for_doughnut, key='region_doughnut_selectbox')
        region_doughnut_df = df[(df['region'] == selected_region_doughnut) & (df['attended'] == 'Yes')]
        if not region_doughnut_df.empty:
            attendance_breakdown = region_doughnut_df['facility_type'].value_counts().reset_index(); attendance_breakdown.columns = ['facility_type', 'count']
            fig_doughnut = px.pie(attendance_breakdown, names='facility_type', values='count', title=f'Nursing vs. Non-Nursing Attendance in {selected_region_doughnut}', hole=0.4, color='facility_type', color_discrete_map=workforce_color_map)
            fig_doughnut.update_traces(textinfo='percent+label', pull=[0.05, 0]); fig_doughnut.update_layout(legend_title_text='Facility Type'); st.plotly_chart(fig_doughnut, use_container_width=True)
        else: st.warning(f"No attendance data found for '{selected_region_doughnut}'.")
    else: st.error("Column 'region' not found.")
    st.markdown("---")

    st.header("Registrations vs. Attendance Comparison by Region")
    if 'region' in df.columns and 'attendee type' in df.columns and 'yearmonth' in df.columns:
        region_list_comp = sorted(df['region'].dropna().unique())
        selected_region_comp = st.selectbox('Select a Region for Comparison:', options=region_list_comp, key='region_comparison_selectbox')
        comp_df = df[(df['region'] == selected_region_comp) & (df['attendee type'].str.title().isin(['Attendee', 'Guest']))].copy()
        if not comp_df.empty:
            monthly_comp = comp_df.groupby('yearmonth').agg(registrations=('attended', 'count'), attendees=('attended', lambda x: (x == 'Yes').sum())).reset_index()
            monthly_comp_melted = monthly_comp.melt(id_vars='yearmonth', value_vars=['registrations', 'attendees'], var_name='metric', value_name='count')
            fig = px.bar(monthly_comp_melted, x='yearmonth', y='count', color='metric', barmode='group', title=f'Monthly Registrations vs. Attendees for {selected_region_comp}', labels={'yearmonth': 'Month'}, color_discrete_map={'registrations': LOGO_COLORS["primary_blue"], 'attendees': LOGO_COLORS["accent_green"]})
            st.plotly_chart(fig, use_container_width=True)
        else: st.warning(f"No 'Attendee' or 'Guest' data found for '{selected_region_comp}'.")
    else: st.error("One or more required columns not found.")
    
    # Enhanced JavaScript that works with Streamlit's dynamic loading
    st.components.v1.html("""
    <script>
    function initializeNavigation() {
        console.log('Initializing navigation...');
        
        // Function to setup header IDs
        function setupHeaderIds() {
            const headers = parent.document.querySelectorAll('h2');
            headers.forEach(header => {
                if (!header.id) {
                    const text = header.textContent || header.innerText;
                    const id = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
                    header.id = id;
                    console.log('Created header ID:', id);
                }
            });
        }
        
        // Function to highlight active section
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
            
            console.log('Active section:', activeHeaderId);
            
            navButtons.forEach(button => {
                const targetId = button.getAttribute('data-target');
                if (targetId === activeHeaderId) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
            });
        }
        
        // Function to setup smooth scrolling
        function setupSmoothScrolling() {
            const navButtons = parent.document.querySelectorAll('.nav-button');
            navButtons.forEach(button => {
                button.removeEventListener('click', handleNavClick); // Remove existing listeners
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
                
                // Update active state immediately
                setTimeout(() => {
                    const allNavButtons = parent.document.querySelectorAll('.nav-button');
                    allNavButtons.forEach(btn => btn.classList.remove('active'));
                    this.classList.add('active');
                }, 100);
                
                console.log('Scrolling to:', targetId);
            }
        }
        
        // Debounce function
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
        
        // Initialize everything
        setupHeaderIds();
        setupSmoothScrolling();
        highlightActiveSection();
        
        // Add scroll listener
        const debouncedHighlight = debounce(highlightActiveSection, 100);
        parent.window.addEventListener('scroll', debouncedHighlight);
        
        console.log('Navigation initialized successfully');
    }
    
    // Run initialization with multiple attempts to ensure Streamlit content is loaded
    setTimeout(initializeNavigation, 500);
    setTimeout(initializeNavigation, 1500);
    setTimeout(initializeNavigation, 3000);
    
    // Also try to initialize on parent document ready
    if (parent.document.readyState === 'loading') {
        parent.document.addEventListener('DOMContentLoaded', initializeNavigation);
    } else {
        initializeNavigation();
    }
    </script>
    """, height=0)

else:
    st.warning("Data could not be loaded. Please check the file path and format.")
