# ============================================================================
# APPLE FINANCIAL DASHBOARD - IMPORTS AND DATA PROCESSING
# ============================================================================

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Optional, Tuple

# Dashboard libraries
import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class FinancialDataProcessor:
    """
    A class to process 10-K financial statement Excel files with merged cells and header rows
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sheets_data = {}
        self.cleaned_data = {}
    
    def load_sheets(self, sheet_names: List[str], preview_mode: bool = False, preview_rows: int = 100) -> Dict[str, pd.DataFrame]:
        """Load specific sheets from the Excel file"""
        try:
            for sheet_name in sheet_names:
                if preview_mode:
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=None, nrows=preview_rows)
                else:
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=None)
                
                self.sheets_data[sheet_name] = df
            return self.sheets_data
        except Exception as e:
            print(f"Error loading sheets: {e}")
            return {}
    
    def find_data_start_row(self, sheet_name: str, 
                           identifier_keywords: List[str] = None,
                           min_columns_with_data: int = 3) -> int:
        """Automatically find where the actual data table starts"""
        if sheet_name not in self.sheets_data:
            return -1
        
        df = self.sheets_data[sheet_name]
        
        if identifier_keywords is None:
            identifier_keywords = [
                'revenue', 'sales', 'income', 'expenses', 'assets', 'liabilities',
                'cash', 'total', 'net', 'gross', 'operating', 'fiscal year',
                'cost', 'profit', 'margin', 'earnings', 'products', 'services'
            ]
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            non_null_count = row.notna().sum()
            if non_null_count < min_columns_with_data:
                continue
            
            first_cell = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ""
            if any(keyword in first_cell for keyword in identifier_keywords):
                return i
        
        return -1

    def find_data_end_row(self, sheet_name: str, data_start_row: int, 
                         max_consecutive_empty: int = 5) -> int:
        """Find where the actual data ends"""
        if sheet_name not in self.sheets_data:
            return -1
        
        df = self.sheets_data[sheet_name]
        consecutive_empty = 0
        last_data_row = data_start_row
        
        for i in range(data_start_row, len(df)):
            row = df.iloc[i]
            
            non_empty_count = 0
            for cell in row:
                if pd.notna(cell) and str(cell).strip() != '':
                    non_empty_count += 1
            
            if non_empty_count == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    return last_data_row + 1
            else:
                consecutive_empty = 0
                last_data_row = i
        
        return len(df)

    def clean_sheet(self, sheet_name: str, 
                   data_start_row: Optional[int] = None,
                   data_end_row: Optional[int] = None,
                   header_row_offset: int = -1,
                   columns_to_keep: Optional[List[int]] = None,
                   max_consecutive_empty: int = 5) -> pd.DataFrame:
        """Clean a specific sheet by removing header rows and unnecessary columns"""
        if sheet_name not in self.sheets_data:
            return pd.DataFrame()
        
        df = self.sheets_data[sheet_name].copy()
        
        if data_start_row is None:
            data_start_row = self.find_data_start_row(sheet_name)
            if data_start_row == -1:
                return pd.DataFrame()
        
        if data_end_row is None:
            data_end_row = self.find_data_end_row(sheet_name, data_start_row, max_consecutive_empty)
        
        df_cleaned = df.iloc[data_start_row:data_end_row].copy()
        df_cleaned.reset_index(drop=True, inplace=True)
        
        if header_row_offset >= 0 and len(df_cleaned) > header_row_offset:
            new_headers = df_cleaned.iloc[header_row_offset].fillna('Unknown').astype(str)
            df_cleaned.columns = new_headers
            df_cleaned = df_cleaned.iloc[header_row_offset + 1:].reset_index(drop=True)
        
        if columns_to_keep:
            df_cleaned = df_cleaned.iloc[:, columns_to_keep]
        
        df_cleaned = df_cleaned.dropna(how='all')
        self.cleaned_data[sheet_name] = df_cleaned
        
        return df_cleaned

def setup_financial_data_optimized(file_path: str) -> Dict[str, pd.DataFrame]:
    """Optimized function to process Apple financial data"""
    processor = FinancialDataProcessor(file_path)
    
    sheet_names = [
        'INCOME_STATEMENT',
        'BALANCE_SHEET', 
        'TABLE6',
        'TABLE7'
    ]
    
    loaded_sheets = processor.load_sheets(sheet_names, preview_mode=False)
    
    if not loaded_sheets:
        return {}
    
    cleaning_config = {
        'INCOME_STATEMENT': {
            'data_start_row': 18,
            'data_end_row': None,
            'header_row_offset': -1,
            'columns_to_keep': [1, 2, 3, 4],
            'max_consecutive_empty': 3
        },
        'BALANCE_SHEET': {
            'data_start_row': 18,
            'data_end_row': None,
            'header_row_offset': -1,
            'columns_to_keep': [1, 2, 3],
            'max_consecutive_empty': 3
        },
        'TABLE6': {
            'data_start_row': 15,
            'data_end_row': None,
            'header_row_offset': -1,
            'columns_to_keep': [1, 2, 3, 4, 5, 6],
            'max_consecutive_empty': 2
        },
        'TABLE7': {
            'data_start_row': 15,
            'data_end_row': None,
            'header_row_offset': -1,
            'columns_to_keep': [1, 2, 3, 4, 5, 6],
            'max_consecutive_empty': 2
        }
    }
    
    cleaned_sheets = {}
    for sheet_name in loaded_sheets.keys():
        if sheet_name in cleaning_config:
            config = cleaning_config[sheet_name]
            
            cleaned_df = processor.clean_sheet(
                sheet_name=sheet_name,
                data_start_row=config['data_start_row'],
                data_end_row=config['data_end_row'],
                header_row_offset=config['header_row_offset'],
                columns_to_keep=config['columns_to_keep'],
                max_consecutive_empty=config['max_consecutive_empty']
            )
            
            if not cleaned_df.empty:
                if sheet_name == 'INCOME_STATEMENT':
                    cleaned_df.columns = ['Item', '2024', '2023', '2022']
                elif sheet_name == 'BALANCE_SHEET':
                    cleaned_df.columns = ['Item', '2024', '2023']
                elif sheet_name == 'TABLE6':
                    cleaned_df.columns = ['Region', '2024', 'Change_24', '2023', 'Change_23', '2022']
                elif sheet_name == 'TABLE7':
                    cleaned_df.columns = ['Product', '2024', 'Change_24', '2023', 'Change_23', '2022']
            
            cleaned_sheets[sheet_name] = cleaned_df
    
    return cleaned_sheets

def load_excel_for_dash(file_path: str) -> Dict[str, pd.DataFrame]:
    """Complete function to load and process data for the dashboard"""
    try:
        cleaned_data = setup_financial_data_optimized(file_path)
        
        expected_sheets = ['INCOME_STATEMENT', 'BALANCE_SHEET', 'TABLE6', 'TABLE7']
        result = {}
        
        for sheet in expected_sheets:
            if sheet in cleaned_data:
                result[sheet] = cleaned_data[sheet]
            else:
                result[sheet] = pd.DataFrame()
        
        return result
        
    except Exception as e:
        print(f"Error processing financial data: {e}")
        return {sheet: pd.DataFrame() for sheet in ['INCOME_STATEMENT', 'BALANCE_SHEET', 'TABLE6', 'TABLE7']}

# ============================================================================
# LOAD DATA - WITH ERROR HANDLING
# ============================================================================

def create_sample_data():
    """Create sample data when Excel file is not available"""
    
    # Sample Income Statement data
    sample_income = pd.DataFrame({
        'Item': [
            'Products',
            'Services', 
            'Total net sales',
            'Cost of sales',
            'Gross margin',
            'Operating expenses',
            'Total operating expenses',
            'Operating income',
            'Net income'
        ],
        '2024': [300000, 96000, 391035, 210352, 180683, 61775, 61775, 118908, 93736],
        '2023': [298085, 85200, 383285, 214137, 169148, 55013, 55013, 114135, 96995],
        '2022': [316199, 78129, 394328, 223546, 170782, 51344, 51344, 119437, 99803]
    })
    
    # Sample Regional data
    sample_regions = pd.DataFrame({
        'Region': ['Americas', 'Europe', 'Greater China', 'Japan', 'Rest of Asia Pacific'],
        '2024': [124300, 73930, 72480, 24257, 29615],
        'Change_24': [0.03, -0.01, -0.13, 0.02, 0.04],
        '2023': [120920, 74690, 83370, 23810, 28430],
        'Change_23': [0.02, 0.01, -0.02, 0.05, 0.03],
        '2022': [118540, 73980, 85040, 22680, 27560]
    })
    
    # Sample Product data
    sample_products = pd.DataFrame({
        'Product': ['iPhone', 'Mac', 'iPad', 'Wearables, Home and Accessories', 'Services'],
        '2024': [200583, 29357, 28300, 37017, 96169],
        'Change_24': [0.006, 0.024, -0.065, 0.027, 0.129],
        '2023': [199940, 28680, 30240, 36050, 85200],
        'Change_23': [-0.027, 0.017, -0.035, 0.089, 0.086],
        '2022': [205489, 28200, 31350, 33100, 78500]
    })
    
    # Sample Balance Sheet data
    sample_balance = pd.DataFrame({
        'Item': [
            'Cash and cash equivalents',
            'Total current assets',
            'Total assets',
            'Total current liabilities',
            'Total liabilities',
            'Total shareholders equity'
        ],
        '2024': [67150, 143566, 364840, 137550, 308030, 56810],
        '2023': [61555, 143630, 352755, 133973, 290020, 62735]
    })
    
    return {
        'INCOME_STATEMENT': sample_income,
        'BALANCE_SHEET': sample_balance,
        'TABLE6': sample_regions,
        'TABLE7': sample_products
    }

file_path = "apple_annual_report.xls"

# Check if file exists, if not create sample data
if os.path.exists(file_path):
    try:
        data = load_excel_for_dash(file_path)
        print("Excel file loaded successfully")
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        data = create_sample_data()
else:
    print(f"Excel file {file_path} not found, using sample data")
    data = create_sample_data()
    # ============================================================================
# CHART FUNCTIONS
# ============================================================================

def create_enhanced_revenue_chart(income_df, selected_metrics):
    """Create enhanced revenue bar chart with dropdown options"""
    if income_df.empty:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)
    
    try:
        total_sales_row = income_df[income_df['Item'].str.contains('total net sales', case=False, na=False)]
        
        if total_sales_row.empty:
            return go.Figure().add_annotation(text="Total net sales data not found", 
                                            xref="paper", yref="paper", 
                                            x=0.5, y=0.5, showarrow=False)
        
        years = ['2022', '2023', '2024']
        revenue_values = []
        
        for year in years:
            if year in total_sales_row.columns:
                val = total_sales_row[year].iloc[0]
                revenue_values.append(float(val) if pd.notna(val) else 0)
            else:
                revenue_values.append(0)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_values,
            name='Total Net Sales',
            marker_color='#4A6FA5',
            text=[f'${v:,.0f}M' for v in revenue_values],
            textposition='outside',
            textfont=dict(color='#2C3E50')
        ))
        
        if 'operating_expenses' in selected_metrics:
            operating_expenses_row = income_df[income_df['Item'].str.contains('total operating expenses', case=False, na=False)]
            if not operating_expenses_row.empty:
                expenses_values = []
                for year in years:
                    if year in operating_expenses_row.columns:
                        val = operating_expenses_row[year].iloc[0]
                        expenses_values.append(float(val) if pd.notna(val) else 0)
                    else:
                        expenses_values.append(0)
                
                fig.add_trace(go.Scatter(
                    x=years,
                    y=expenses_values,
                    mode='markers',
                    name='Total Operating Expenses',
                    marker=dict(
                        symbol='triangle-up',
                        size=18,
                        color='#E74C3C',
                        line=dict(width=2, color='#C0392B')
                    ),
                    text=[f'${v:,.0f}M' for v in expenses_values],
                    textposition='top center',
                    textfont=dict(color='#E74C3C')
                ))
        
        if 'net_income' in selected_metrics:
            net_income_row = income_df[income_df['Item'].str.contains('net income', case=False, na=False)]
            if not net_income_row.empty:
                income_values = []
                for year in years:
                    if year in net_income_row.columns:
                        val = net_income_row[year].iloc[0]
                        income_values.append(float(val) if pd.notna(val) else 0)
                    else:
                        income_values.append(0)
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=income_values,
                    name='Net Income',
                    marker_color='#27AE60',
                    text=[f'${v:,.0f}M' for v in income_values],
                    textposition='outside',
                    textfont=dict(color='#1E8449')
                ))
        
        if 'gross_margin' in selected_metrics:
            gross_margin_row = income_df[income_df['Item'].str.contains('gross margin', case=False, na=False)]
            if not gross_margin_row.empty:
                margin_values = []
                for year in years:
                    if year in gross_margin_row.columns:
                        val = gross_margin_row[year].iloc[0]
                        margin_values.append(float(val) if pd.notna(val) else 0)
                    else:
                        margin_values.append(0)
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=margin_values,
                    name='Gross Margin',
                    marker_color='#8E44AD',
                    text=[f'${v:,.0f}M' for v in margin_values],
                    textposition='outside',
                    textfont=dict(color='#6C3483')
                ))
        
        fig.update_layout(
            title=dict(
                text='Apple Financial Metrics (3 Years)',
                font=dict(size=18, color='#2C3E50'),
                x=0.5
            ),
            xaxis_title='Year',
            yaxis_title='Amount (millions USD)',
            plot_bgcolor='#FAFAFA',
            paper_bgcolor='white',
            height=500,
            barmode='group',
            font=dict(color='#2C3E50'),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color='#2C3E50')
            )
        )
        
        fig.update_xaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        fig.update_yaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        
        return fig
    
    except Exception as e:
        print(f"Error creating enhanced revenue chart: {e}")
        return go.Figure().add_annotation(text="Error creating chart", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)

def create_product_breakdown_clean(table7_df):
    """Create clean product revenue breakdown"""
    if table7_df.empty:
        return go.Figure().add_annotation(text="No product data available", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)
    
    try:
        products = []
        values = []
        
        for _, row in table7_df.iterrows():
            if pd.notna(row['Product']) and pd.notna(row['2024']):
                product = str(row['Product'])
                value = float(row['2024'])
                
                if 'total' in product.lower() and 'sales' in product.lower():
                    continue
                
                if 'iphone' in product.lower():
                    products.append('iPhone')
                elif 'mac' in product.lower():
                    products.append('Mac')
                elif 'ipad' in product.lower():
                    products.append('iPad')
                elif 'wearables' in product.lower():
                    products.append('Wearables & Accessories')
                elif 'services' in product.lower():
                    products.append('Services')
                else:
                    products.append(product)
                
                values.append(value)
        
        if products and values:
            colors = ['#4A6FA5', '#27AE60', '#E74C3C', '#F39C12', '#8E44AD']
            
            fig = go.Figure(data=[go.Pie(
                labels=products,
                values=values,
                hole=0.4,
                marker=dict(
                    colors=colors[:len(products)],
                    line=dict(color='white', width=2)
                ),
                textinfo='percent+label',
                textposition='inside',
                textfont=dict(color='white', size=10, family="SF Pro Display, Arial"),
                pull=[0.05 if i == 0 else 0 for i in range(len(products))]
            )])
            
            fig.update_layout(
                title=dict(
                    text='2024 Revenue by Product Category',
                    font=dict(size=16, color='#2C3E50'),
                    x=0.5,
                    y=0.95
                ),
                plot_bgcolor='#FAFAFA',
                paper_bgcolor='white',
                height=450,
                font=dict(color='#2C3E50'),
                showlegend=False,
                margin=dict(t=60, b=30, l=30, r=30)
            )
            
            return fig
    except Exception as e:
        print(f"Error creating product chart: {e}")
    
    return go.Figure().add_annotation(text="Error creating chart", 
                                    xref="paper", yref="paper", 
                                    x=0.5, y=0.5, showarrow=False)

def create_regional_breakdown_map(table6_df):
    """Create geographic map showing Apple's revenue by region"""
    if table6_df.empty:
        return go.Figure().add_annotation(text="No regional data available", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)
    
    try:
        regions = []
        values = []
        
        for _, row in table6_df.iterrows():
            if pd.notna(row['Region']) and pd.notna(row['2024']):
                region = str(row['Region'])
                value = float(row['2024'])
                
                if 'total' in region.lower() and 'sales' in region.lower():
                    continue
                
                regions.append(region)
                values.append(value)
        
        if regions and values:
            region_mapping = {
                'Americas': {
                    'lat': [39.8283],
                    'lon': [-98.5795],
                    'countries': ['USA'],
                    'country_names': ['United States']
                },
                'Europe': {
                    'lat': [54.5260],
                    'lon': [-4.5471],
                    'countries': ['GBR'],
                    'country_names': ['United Kingdom']
                },
                'Greater China': {
                    'lat': [35.8617],
                    'lon': [104.1954],
                    'countries': ['CHN'],
                    'country_names': ['China']
                },
                'Japan': {
                    'lat': [36.2048],
                    'lon': [138.2529],
                    'countries': ['JPN'],
                    'country_names': ['Japan']
                },
                'Rest of Asia Pacific': {
                    'lat': [1.3521],
                    'lon': [103.8198],
                    'countries': ['SGP'],
                    'country_names': ['Singapore']
                }
            }
            
            map_data = []
            region_colors = {
                'Americas': '#4A6FA5',
                'Europe': '#27AE60', 
                'Greater China': '#E74C3C',
                'Japan': '#F39C12',
                'Rest of Asia Pacific': '#8E44AD'
            }
            
            for i, region in enumerate(regions):
                if region in region_mapping:
                    mapping = region_mapping[region]
                    map_data.append({
                        'lat': mapping['lat'][0],
                        'lon': mapping['lon'][0],
                        'region': region,
                        'country': mapping['country_names'][0],
                        'revenue': values[i],
                        'total_revenue': values[i],
                        'color': region_colors.get(region, '#95A5A6')
                    })

            df_map = pd.DataFrame(map_data)
            
            fig = go.Figure()
            
            for region in regions:
                if region in region_mapping:
                    region_data = df_map[df_map['region'] == region]
                    
                    fig.add_trace(go.Scattergeo(
                        lon=region_data['lon'],
                        lat=region_data['lat'],
                        text=region_data.apply(lambda row: 
                            f"<b>{row['country']}</b><br>" +
                            f"Region: {row['region']}<br>" +
                            f"Total Revenue: ${row['total_revenue']:,.0f}M", axis=1),
                        mode='markers',
                        marker=dict(
                            size=np.sqrt(df_map[df_map['region'] == region]['total_revenue'].iloc[0]) / 15,
                            color=region_colors.get(region, '#95A5A6'),
                            line=dict(width=2, color='white'),
                            sizemode='diameter',
                            opacity=0.8
                        ),
                        name=f"{region}<br>${df_map[df_map['region'] == region]['total_revenue'].iloc[0]:,.0f}M",
                        hovertemplate='<b>%{text}</b><extra></extra>',
                        showlegend=True
                    ))
            
            fig.update_layout(
                title=dict(
                    text='2024 Revenue by Geographic Region',
                    font=dict(size=16, color='#2C3E50'),
                    x=0.5,
                    y=0.95
                ),
                geo=dict(
                    projection_type='natural earth',
                    showland=True,
                    landcolor='rgb(243, 243, 243)',
                    coastlinecolor='rgb(204, 204, 204)',
                    showocean=True,
                    oceancolor='rgb(230, 245, 255)',
                    showlakes=True,
                    lakecolor='rgb(230, 245, 255)',
                    showrivers=True,
                    rivercolor='rgb(230, 245, 255)',
                    showframe=False,
                    showcoastlines=True
                ),
                height=450,
                font=dict(color='#2C3E50'),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="rgba(0,0,0,0.2)",
                    borderwidth=1
                ),
                margin=dict(t=60, b=30, l=30, r=30),
                plot_bgcolor='#FAFAFA',
                paper_bgcolor='white'
            )
            
            return fig
            
    except Exception as e:
        print(f"Error creating geographic map: {e}")
    
    return go.Figure().add_annotation(text="Error creating map", 
                                    xref="paper", yref="paper", 
                                    x=0.5, y=0.5, showarrow=False)

def create_key_metrics_cards_clean(income_df):
    """Create professional key financial metrics cards"""
    cards = []
    
    if not income_df.empty:
        try:
            total_sales_row = income_df[income_df['Item'].str.contains('total net sales', case=False, na=False)]
            net_income_row = income_df[income_df['Item'].str.contains('net income', case=False, na=False)]
            
            if not total_sales_row.empty:
                revenue_2024 = total_sales_row['2024'].iloc[0]
                revenue_2023 = total_sales_row['2023'].iloc[0]
                change_pct = ((float(revenue_2024)/float(revenue_2023)-1)*100)
                
                cards.append(
                    html.Div([
                        html.H3("Total Revenue", style={'color': 'white', 'margin-bottom': '10px', 'font-weight': '400'}),
                        html.H2(f"${float(revenue_2024):,.0f}M", style={'color': 'white', 'font-size': '2.2rem', 'margin-bottom': '8px', 'font-weight': '500'}),
                        html.P(f"2024 vs 2023: {change_pct:+.1f}%", 
                               style={'color': 'rgba(255,255,255,0.9)', 'font-weight': '300', 'font-size': '14px'})
                    ], style={
                        'background': 'linear-gradient(135deg, #4A6FA5, #3B5998)',
                        'color': 'white',
                        'padding': '25px',
                        'border-radius': '10px',
                        'flex': '1',
                        'min-width': '200px',
                        'text-align': 'center',
                        'box-shadow': '0 4px 12px rgba(74, 111, 165, 0.3)',
                        'border': '1px solid rgba(74, 111, 165, 0.2)'
                    })
                )
            
            if not net_income_row.empty:
                income_2024 = net_income_row['2024'].iloc[0]
                income_2023 = net_income_row['2023'].iloc[0]
                change_pct = ((float(income_2024)/float(income_2023)-1)*100)
                
                cards.append(
                    html.Div([
                        html.H3("Net Income", style={'color': 'white', 'margin-bottom': '10px', 'font-weight': '400'}),
                        html.H2(f"${float(income_2024):,.0f}M", style={'color': 'white', 'font-size': '2.2rem', 'margin-bottom': '8px', 'font-weight': '500'}),
                        html.P(f"2024 vs 2023: {change_pct:+.1f}%", 
                               style={'color': 'rgba(255,255,255,0.9)', 'font-weight': '300', 'font-size': '14px'})
                    ], style={
                        'background': 'linear-gradient(135deg, #27AE60, #1E8449)',
                        'color': 'white',
                        'padding': '25px',
                        'border-radius': '10px',
                        'flex': '1',
                        'min-width': '200px',
                        'text-align': 'center',
                        'margin': '10px',
                        'box-shadow': '0 4px 12px rgba(39, 174, 96, 0.3)',
                        'border': '1px solid rgba(39, 174, 96, 0.2)'
                    })
                )
        except Exception as e:
            print(f"Error creating metrics: {e}")
    
    return cards
# ============================================================================
# DASHBOARD LAYOUT
# ============================================================================

# Initialize Dash
app = dash.Dash(__name__)

# Dashboard layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Apple Inc. Financial Dashboard", 
                style={'text-align': 'center', 'color': '#2C3E50', 'font-size': '2.8rem', 'margin-bottom': '10px', 'font-weight': '400'}),
        html.P("Interactive analysis of Apple's financial performance with geographic insights", 
               style={'text-align': 'center', 'color': '#5D6D7E', 'font-size': '1.2rem', 'font-weight': '300'})
    ], style={'background': 'white', 'padding': '35px', 'border-radius': '12px', 
              'margin-bottom': '30px', 'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 'border': '1px solid #E8E8E8'}),
    
    # Key Metrics Cards
    html.Div([
        html.H2("Key Financial Metrics", 
                style={'color': '#2C3E50', 'margin-bottom': '25px', 'border-bottom': '3px solid #4A6FA5', 'padding-bottom': '12px', 'font-weight': '400'}),
        html.Div(id="metrics-cards", style={'display': 'flex', 'gap': '20px', 'flex-wrap': 'wrap', 'justify-content': 'center'})
    ], style={'background': 'white', 'padding': '30px', 'border-radius': '12px', 
              'margin-bottom': '30px', 'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 'border': '1px solid #E8E8E8'}),
    
    # Enhanced Revenue Chart Section
    html.Div([
        html.Div([
            html.H3("Financial Metrics Overview", style={'color': '#2C3E50', 'margin-bottom': '20px', 'font-weight': '400'}),
            
            # Enhanced dropdown controls
            html.Div([
                html.Label("Interactive Chart Controls", 
                          style={'color': '#2C3E50', 'font-size': '16px', 'font-weight': '600', 'margin-bottom': '8px', 'display': 'block'}),
                html.P("Select additional financial metrics to overlay on the revenue chart:", 
                       style={'color': '#5D6D7E', 'margin-bottom': '12px', 'font-weight': '400', 'font-size': '14px', 'display': 'block'}),
                dcc.Dropdown(
                    id='metrics-dropdown',
                    options=[
                        {'label': 'Total Operating Expenses', 'value': 'operating_expenses'},
                        {'label': 'Net Income', 'value': 'net_income'},
                        {'label': 'Gross Margin', 'value': 'gross_margin'}
                    ],
                    value=[],
                    multi=True,
                    placeholder="Click here to select metrics to overlay on the chart...",
                    style={
                        'margin-bottom': '25px', 
                        'font-family': 'SF Pro Display, Arial',
                        'border': '2px solid #4A6FA5',
                        'border-radius': '8px',
                        'box-shadow': '0 2px 8px rgba(74, 111, 165, 0.15)'
                    }
                ),
            ], style={
                'background': 'linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%)',
                'padding': '20px',
                'border-radius': '10px',
                'border': '1px solid #DEE2E6',
                'margin-bottom': '25px'
            }),
            
            dcc.Graph(id="enhanced-revenue-chart")
        ])
    ], style={'background': 'white', 'padding': '25px', 'border-radius': '12px', 
              'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 'margin-bottom': '30px', 'border': '1px solid #E8E8E8'}),
    
    # Centered Charts Section - Product Pie Chart and Geographic Map
    html.Div([
        html.Div([
            # Product Breakdown Chart
            html.Div([
                dcc.Graph(id="product-chart")
            ], style={
                'background': 'white', 
                'padding': '20px', 
                'border-radius': '12px', 
                'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 
                'border': '1px solid #E8E8E8',
                'margin-bottom': '30px',
                'width': '100%'
            }),
            
            # Geographic Map
            html.Div([
                dcc.Graph(id="geographic-map")
            ], style={
                'background': 'white', 
                'padding': '20px', 
                'border-radius': '12px', 
                'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 
                'border': '1px solid #E8E8E8',
                'width': '100%'
            })
        ], style={
            'max-width': '800px',
            'margin': '0 auto',
            'padding': '0 20px'
        })
    ], style={'margin-bottom': '30px'}),
    
    # Data Tables Section
    html.Div([
        html.H2("Raw Data", 
                style={'color': '#2C3E50', 'margin-bottom': '25px', 'border-bottom': '3px solid #4A6FA5', 'padding-bottom': '12px', 'font-weight': '400'}),
        
        # Enhanced dropdown for table selection
        html.Div([
            html.Label("Document Selector", 
                      style={'color': '#2C3E50', 'font-size': '16px', 'font-weight': '600', 'margin-bottom': '8px', 'display': 'block'}),
            html.P("Choose which financial document you want to view in detail:", 
                   style={'color': '#5D6D7E', 'margin-bottom': '12px', 'font-weight': '400', 'font-size': '14px', 'display': 'block'}),
            dcc.Dropdown(
                id='table-selector',
                options=[
                    {'label': 'Income Statement', 'value': 'INCOME_STATEMENT'},
                    {'label': 'Balance Sheet', 'value': 'BALANCE_SHEET'},
                    {'label': 'Revenue by Region', 'value': 'TABLE6'},
                    {'label': 'Revenue by Product', 'value': 'TABLE7'}
                ],
                value='INCOME_STATEMENT',
                placeholder="Click here to select a financial document to view...",
                style={
                    'margin-bottom': '25px', 
                    'font-family': 'SF Pro Display, Arial',
                    'border': '2px solid #4A6FA5',
                    'border-radius': '8px',
                    'box-shadow': '0 2px 8px rgba(74, 111, 165, 0.15)'
                }
            ),
        ], style={
            'background': 'linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%)',
            'padding': '20px',
            'border-radius': '10px',
            'border': '1px solid #DEE2E6',
            'margin-bottom': '25px'
        }),
        
        # Data table container
        html.Div(id="data-table-container")
    ], style={'background': 'white', 'padding': '30px', 'border-radius': '12px', 
              'margin-top': '0px', 'box-shadow': '0 4px 15px rgba(0,0,0,0.08)', 'border': '1px solid #E8E8E8'})
], style={
    'font-family': 'SF Pro Display, -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif',
    'max-width': '1300px',
    'margin': '0 auto',
    'padding': '25px',
    'background': 'linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%)',
    'font-weight': '300',
    'min-height': '100vh'
})
# ============================================================================
# DASHBOARD CALLBACKS
# ============================================================================

# Enhanced callbacks with geographic map
@app.callback(
    [Output('metrics-cards', 'children'),
     Output('enhanced-revenue-chart', 'figure'),
     Output('product-chart', 'figure'),
     Output('geographic-map', 'figure')],
    [Input('table-selector', 'value'),
     Input('metrics-dropdown', 'value')]
)
def update_charts(_, selected_metrics):
    """Update all charts and metrics including the new geographic map"""
    
    # Create metrics cards
    metrics = create_key_metrics_cards_clean(data['INCOME_STATEMENT'])
    
    # Create charts
    revenue_fig = create_enhanced_revenue_chart(data['INCOME_STATEMENT'], selected_metrics)
    product_fig = create_product_breakdown_clean(data['TABLE7'])
    geographic_fig = create_regional_breakdown_map(data['TABLE6'])
    
    return metrics, revenue_fig, product_fig, geographic_fig

@app.callback(
    Output('data-table-container', 'children'),
    [Input('table-selector', 'value')]
)
def update_table(selected_table):
    """Update the data table based on selection with formatted numbers"""
    
    if selected_table in data and not data[selected_table].empty:
        df = data[selected_table].copy()
        
        # Format numeric columns with commas
        numeric_columns = []
        for col in df.columns:
            if col not in ['Item', 'Region', 'Product', 'Product Category']:
                try:
                    pd.to_numeric(df[col], errors='coerce')
                    numeric_columns.append(col)
                except:
                    pass
        
        # Apply formatting to numeric columns
        for col in numeric_columns:
            if 'Change' in col or '%' in col:
                # Format percentage columns
                df[col] = df[col].apply(lambda x: f"{float(x):.1f}%" if pd.notna(x) else "—")
            else:
                # Format currency/number columns with commas
                df[col] = df[col].apply(lambda x: f"{float(x):,.0f}" if pd.notna(x) else "—")
        
        # Add units based on table type
        if selected_table == 'INCOME_STATEMENT':
            title = "Income Statement"
            subtitle = "(All amounts in millions of USD, except per share data)"
            
        elif selected_table == 'BALANCE_SHEET':
            title = "Balance Sheet"
            subtitle = "(All amounts in millions of USD)"
            
        elif selected_table == 'TABLE6':
            title = "Revenue by Region"
            subtitle = "(Revenue in millions of USD, Changes in percentage)"
            df = df.rename(columns={
                'Region': 'Region',
                '2024': '2024 (USD Millions)',
                'Change_24': '2024 Change (%)',
                '2023': '2023 (USD Millions)', 
                'Change_23': '2023 Change (%)',
                '2022': '2022 (USD Millions)'
            })
            
        elif selected_table == 'TABLE7':
            title = "Revenue by Product"
            subtitle = "(Revenue in millions of USD, Changes in percentage)"
            df = df.rename(columns={
                'Product': 'Product Category',
                '2024': '2024 (USD Millions)',
                'Change_24': '2024 Change (%)',
                '2023': '2023 (USD Millions)',
                'Change_23': '2023 Change (%)', 
                '2022': '2022 (USD Millions)'
            })
        else:
            title = selected_table.replace('_', ' ').title()
            subtitle = ""
        
        # Create table with header
        return html.Div([
            # Table title and subtitle
            html.Div([
                html.H3(title, style={
                    'color': '#2C3E50', 
                    'margin-bottom': '5px', 
                    'font-weight': '500',
                    'font-size': '1.4rem'
                }),
                html.P(subtitle, style={
                    'color': '#5D6D7E', 
                    'margin-bottom': '20px',
                    'font-style': 'italic',
                    'font-size': '14px'
                }) if subtitle else html.Div()
            ]),
            
            # Data table with enhanced formatting
            dash_table.DataTable(
                data=df.to_dict('records'),
                columns=[{"name": i, "id": i} for i in df.columns],
                style_cell={
                    'textAlign': 'left',
                    'padding': '12px',
                    'fontFamily': 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
                    'fontSize': '14px',
                    'color': '#2C3E50',
                    'backgroundColor': 'white',
                    'whiteSpace': 'normal',
                    'height': 'auto',
                    'minWidth': '120px'
                },
                style_header={
                    'backgroundColor': '#F1F2F6',
                    'fontWeight': '600',
                    'border': '1px solid #D5DBDB',
                    'color': '#2C3E50',
                    'textAlign': 'center',
                    'fontSize': '13px'
                },
                style_data={
                    'backgroundColor': 'white',
                    'border': '1px solid #E8E8E8'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': '#F8F9FA'
                    },
                    {
                        'if': {
                            'filter_query': '{Item} contains "Total" || {Item} contains "Net"',
                        },
                        'backgroundColor': '#EBF3FD',
                        'color': '#2C3E50',
                        'fontWeight': '600'
                    }
                ],
                style_table={
                    'overflowX': 'auto'
                },
                page_size=25,
                sort_action="native",
                filter_action="native",
                
                # Format numeric columns with proper alignment
                style_cell_conditional=[
                    {
                        'if': {'column_id': c},
                        'textAlign': 'right',
                        'fontFamily': 'SF Mono, Monaco, monospace',
                        'fontWeight': '500'
                    } for c in ['2024', '2023', '2022', '2024 (USD Millions)', '2023 (USD Millions)', '2022 (USD Millions)']
                ] + [
                    {
                        'if': {'column_id': c},
                        'textAlign': 'center',
                        'fontFamily': 'SF Mono, Monaco, monospace',
                        'fontWeight': '500'
                    } for c in ['2024 Change (%)', '2023 Change (%)']
                ]
            ),
            
            # Footer note
            html.Div([
                html.P("Note: Figures are as reported in Apple's official financial statements.", 
                       style={
                           'color': '#85929E',
                           'font-size': '12px',
                           'margin-top': '15px',
                           'font-style': 'italic',
                           'text-align': 'center'
                       })
            ])
        ])
    else:
        return html.Div([
            html.Div([
                html.H3(f"{selected_table.replace('_', ' ').title()}", style={
                    'color': '#2C3E50', 
                    'margin-bottom': '10px', 
                    'font-weight': '500'
                }),
                html.P(f"No data available for {selected_table.replace('_', ' ').lower()}.", 
                       style={
                           'text-align': 'center', 
                           'color': '#5D6D7E', 
                           'padding': '40px',
                           'font-size': '16px'
                       }),
                html.P("Please check that your data loaded correctly in Part 1.",
                       style={
                           'text-align': 'center', 
                           'color': '#85929E', 
                           'font-size': '14px',
                           'font-style': 'italic'
                       })
            ])
        ])
# ============================================================================
# RUN DASHBOARD - CRITICAL FIXES FOR AWS APP RUNNER
# ============================================================================

# CRITICAL: Expose the server for AWS App Runner
server = app.server

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8000, debug=False)


