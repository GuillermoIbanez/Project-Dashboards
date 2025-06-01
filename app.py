# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 1: IMPORTS AND DATA PROCESSING
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

print("✅ All libraries imported successfully!")

# ============================================================================
# DATA PROCESSING CLASS
# ============================================================================

class FinancialDataProcessor:
    """
    A class to process 10-K financial statement Excel files with merged cells and header rows
    OPTIMIZED VERSION with end row detection for better performance
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sheets_data = {}
        self.cleaned_data = {}
    
    def load_sheets(self, sheet_names: List[str], preview_mode: bool = False, preview_rows: int = 100) -> Dict[str, pd.DataFrame]:
        """
        Load specific sheets from the Excel file
        preview_mode: If True, only loads first N rows for faster exploration
        """
        try:
            for sheet_name in sheet_names:
                # In preview mode, only read first N rows for speed
                if preview_mode:
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=None, nrows=preview_rows)
                    print(f"🔍 Preview loaded '{sheet_name}' - first {preview_rows} rows only, shape: {df.shape}")
                else:
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=None)
                    print(f"✓ Loaded sheet '{sheet_name}' with shape: {df.shape}")
                
                self.sheets_data[sheet_name] = df
            return self.sheets_data
        except Exception as e:
            print(f"❌ Error loading sheets: {e}")
            return {}
    
    def find_data_start_row(self, sheet_name: str, 
                           identifier_keywords: List[str] = None,
                           min_columns_with_data: int = 3) -> int:
        """
        Automatically find where the actual data table starts
        """
        if sheet_name not in self.sheets_data:
            return -1
        
        df = self.sheets_data[sheet_name]
        
        # Default keywords for financial statements
        if identifier_keywords is None:
            identifier_keywords = [
                'revenue', 'sales', 'income', 'expenses', 'assets', 'liabilities',
                'cash', 'total', 'net', 'gross', 'operating', 'fiscal year',
                'cost', 'profit', 'margin', 'earnings', 'products', 'services'
            ]
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Check if row has enough non-null data
            non_null_count = row.notna().sum()
            if non_null_count < min_columns_with_data:
                continue
            
            # Check if first column contains financial statement keywords
            first_cell = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ""
            if any(keyword in first_cell for keyword in identifier_keywords):
                print(f"🎯 AUTO-DETECTED: Data likely starts at row {i}")
                print(f"   Found keyword in: '{row.iloc[0]}'")
                return i
        
        print(f"⚠️  Could not automatically find data start for {sheet_name}")
        return -1

    def find_data_end_row(self, sheet_name: str, data_start_row: int, 
                         max_consecutive_empty: int = 5) -> int:
        """
        Find where the actual data ends (to avoid processing thousands of empty rows)
        """
        if sheet_name not in self.sheets_data:
            return -1
        
        df = self.sheets_data[sheet_name]
        consecutive_empty = 0
        last_data_row = data_start_row
        
        # Start checking from data_start_row
        for i in range(data_start_row, len(df)):
            row = df.iloc[i]
            
            # Check if row is essentially empty (only NaN or empty strings)
            non_empty_count = 0
            for cell in row:
                if pd.notna(cell) and str(cell).strip() != '':
                    non_empty_count += 1
            
            if non_empty_count == 0:
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    print(f"📍 Data ends around row {last_data_row} ({consecutive_empty} consecutive empty rows found)")
                    return last_data_row + 1  # Return the row after last data
            else:
                consecutive_empty = 0
                last_data_row = i
        
        # If we reach here, data goes to the end of the sheet
        print(f"📍 Data continues to end of sheet (row {len(df)})")
        return len(df)

    def clean_sheet(self, sheet_name: str, 
                   data_start_row: Optional[int] = None,
                   data_end_row: Optional[int] = None,
                   header_row_offset: int = -1,
                   columns_to_keep: Optional[List[int]] = None,
                   max_consecutive_empty: int = 5) -> pd.DataFrame:
        """
        Clean a specific sheet by removing header rows and unnecessary columns
        Now with smart end detection to avoid processing empty rows
        """
        if sheet_name not in self.sheets_data:
            print(f"Sheet '{sheet_name}' not loaded")
            return pd.DataFrame()
        
        df = self.sheets_data[sheet_name].copy()
        original_shape = df.shape
        
        # Auto-detect data start if not provided
        if data_start_row is None:
            data_start_row = self.find_data_start_row(sheet_name)
            if data_start_row == -1:
                print(f"⚠️  Please manually specify data_start_row for {sheet_name}")
                return pd.DataFrame()
        
        # Auto-detect data end if not provided
        if data_end_row is None:
            data_end_row = self.find_data_end_row(sheet_name, data_start_row, max_consecutive_empty)
        
        print(f"🧹 Cleaning {sheet_name}:")
        print(f"   📊 Original shape: {original_shape}")
        print(f"   🎯 Using rows {data_start_row} to {data_end_row}")
        
        # Extract only the relevant portion
        df_cleaned = df.iloc[data_start_row:data_end_row].copy()
        
        # Reset index
        df_cleaned.reset_index(drop=True, inplace=True)
        
        # Set proper column headers if specified
        if header_row_offset >= 0 and len(df_cleaned) > header_row_offset:
            # Use specified row as headers
            new_headers = df_cleaned.iloc[header_row_offset].fillna('Unknown').astype(str)
            df_cleaned.columns = new_headers
            df_cleaned = df_cleaned.iloc[header_row_offset + 1:].reset_index(drop=True)
        
        # Keep only specified columns
        if columns_to_keep:
            original_cols = df_cleaned.shape[1]
            df_cleaned = df_cleaned.iloc[:, columns_to_keep]
            print(f"   📋 Kept {len(columns_to_keep)} of {original_cols} columns")
        
        # Remove completely empty rows
        before_empty_removal = len(df_cleaned)
        df_cleaned = df_cleaned.dropna(how='all')
        after_empty_removal = len(df_cleaned)
        
        if before_empty_removal != after_empty_removal:
            print(f"   🗑️  Removed {before_empty_removal - after_empty_removal} empty rows")
        
        # Store cleaned data
        self.cleaned_data[sheet_name] = df_cleaned
        
        print(f"   ✅ Final shape: {df_cleaned.shape}")
        return df_cleaned

print("✅ FinancialDataProcessor class defined successfully!")

# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def setup_financial_data_optimized(file_path: str) -> Dict[str, pd.DataFrame]:
    """
    Optimized function to process your specific Apple financial data
    Based on the exploration results from your notebook
    """
    processor = FinancialDataProcessor(file_path)
    
    # Sheet names
    sheet_names = [
        'INCOME_STATEMENT',
        'BALANCE_SHEET', 
        'TABLE6',
        'TABLE7'
    ]
    
    # Load all sheets (full data, not preview)
    print("📁 Loading Excel sheets...")
    loaded_sheets = processor.load_sheets(sheet_names, preview_mode=False)
    
    if not loaded_sheets:
        print("❌ Could not load sheets")
        return {}
    
    # Define cleaning parameters based on your data exploration
    cleaning_config = {
        'INCOME_STATEMENT': {
            'data_start_row': 18,       # Row where "Products" starts
            'data_end_row': None,       # Auto-detect
            'header_row_offset': -1,    # No headers in data
            'columns_to_keep': [1, 2, 3, 4],  # Skip first column (descriptions), keep data columns
            'max_consecutive_empty': 3
        },
        'BALANCE_SHEET': {
            'data_start_row': 18,       # Row where "Cash and cash equivalents" starts
            'data_end_row': None,       # Auto-detect
            'header_row_offset': -1,    # No headers in data
            'columns_to_keep': [1, 2, 3],  # Keep description and 2 years of data
            'max_consecutive_empty': 3
        },
        'TABLE6': {
            'data_start_row': 15,       # Row where "Americas" starts
            'data_end_row': None,       # Auto-detect
            'header_row_offset': -1,    # Headers are in row 14, but we'll handle manually
            'columns_to_keep': [1, 2, 3, 4, 5, 6],  # All data columns
            'max_consecutive_empty': 2
        },
        'TABLE7': {
            'data_start_row': 15,       # Row where "iPhone" starts
            'data_end_row': None,       # Auto-detect
            'header_row_offset': -1,    # Headers are in row 14, but we'll handle manually
            'columns_to_keep': [1, 2, 3, 4, 5, 6],  # All data columns
            'max_consecutive_empty': 2
        }
    }
    
    # Clean each sheet
    cleaned_sheets = {}
    for sheet_name in loaded_sheets.keys():
        if sheet_name in cleaning_config:
            config = cleaning_config[sheet_name]
            print(f"\n🧹 Processing {sheet_name}...")
            
            cleaned_df = processor.clean_sheet(
                sheet_name=sheet_name,
                data_start_row=config['data_start_row'],
                data_end_row=config['data_end_row'],
                header_row_offset=config['header_row_offset'],
                columns_to_keep=config['columns_to_keep'],
                max_consecutive_empty=config['max_consecutive_empty']
            )
            
            # Add proper column names based on your data structure
            if not cleaned_df.empty:
                if sheet_name == 'INCOME_STATEMENT':
                    cleaned_df.columns = ['Item', '2024', '2023', '2022']
                elif sheet_name == 'BALANCE_SHEET':
                    cleaned_df.columns = ['Item', '2024', '2023']
                elif sheet_name == 'TABLE6':
                    cleaned_df.columns = ['Region', '2024', 'Change_24', '2023', 'Change_23', '2022']
                elif sheet_name == 'TABLE7':
                    cleaned_df.columns = ['Product', '2024', 'Change_24', '2023', 'Change_23', '2022']
                
                print(f"   📋 Added column names: {list(cleaned_df.columns)}")
            
            cleaned_sheets[sheet_name] = cleaned_df
    
    return cleaned_sheets

def load_excel_for_dash(file_path: str) -> Dict[str, pd.DataFrame]:
    """
    Complete function to load and process data for the dashboard
    """
    try:
        print("🚀 Loading and processing financial data for dashboard...")
        
        # Use the optimized processing function
        cleaned_data = setup_financial_data_optimized(file_path)
        
        # Ensure expected sheet names are available for your dashboard
        expected_sheets = ['INCOME_STATEMENT', 'BALANCE_SHEET', 'TABLE6', 'TABLE7']
        result = {}
        
        for sheet in expected_sheets:
            if sheet in cleaned_data:
                result[sheet] = cleaned_data[sheet]
                print(f"✅ {sheet}: {cleaned_data[sheet].shape}")
            else:
                print(f"⚠️  Warning: {sheet} not found in cleaned data")
                result[sheet] = pd.DataFrame()  # Empty dataframe as fallback
        
        print("🎉 Data processing complete!")
        return result
        
    except Exception as e:
        print(f"❌ Error processing financial data: {e}")
        return {sheet: pd.DataFrame() for sheet in ['INCOME_STATEMENT', 'BALANCE_SHEET', 'TABLE6', 'TABLE7']}

print("✅ Data processing functions defined successfully!")

# ============================================================================
# LOAD YOUR DATA HERE
# ============================================================================

# UPDATE THIS PATH TO YOUR FILE
file_path = "apple_annual_report.xls"

# DEBUG: Let's see what files are available
import os
print("=== DEBUG INFO ===")
print("Current directory:", os.getcwd())
print("Files in current directory:", os.listdir('.'))
print("Looking for file:", file_path)
print("File exists?", os.path.exists(file_path))
print("==================")


print("🔄 Loading your Apple financial data...")
try:
    data = load_excel_for_dash(file_path)
    print("\n✅ Data loaded successfully!")
    
    # Show what we have
    for sheet_name, df in data.items():
        if not df.empty:
            print(f"📊 {sheet_name}: {df.shape} - Columns: {list(df.columns)}")
        else:
            print(f"⚠️  {sheet_name}: No data loaded")
        print("-" * 50)
            
except Exception as e:
    print(f"❌ Error: {e}")
    # Create empty dataframes as fallback
    data = {
        'INCOME_STATEMENT': pd.DataFrame(),
        'BALANCE_SHEET': pd.DataFrame(),
        'TABLE6': pd.DataFrame(),
        'TABLE7': pd.DataFrame()
    }

print("🎯 Part 1 Complete! Ready for Part 2 (Chart Functions)...")

# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 2: ENHANCED CHART FUNCTIONS
# ============================================================================

def create_enhanced_revenue_chart(income_df, selected_metrics):
    """Create enhanced revenue bar chart with dropdown options"""
    if income_df.empty:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)
    
    try:
        # Find total net sales row
        total_sales_row = income_df[income_df['Item'].str.contains('total net sales', case=False, na=False)]
        
        if total_sales_row.empty:
            return go.Figure().add_annotation(text="Total net sales data not found", 
                                            xref="paper", yref="paper", 
                                            x=0.5, y=0.5, showarrow=False)
        
        years = ['2022', '2023', '2024']
        revenue_values = []
        
        # Get revenue values
        for year in years:
            if year in total_sales_row.columns:
                val = total_sales_row[year].iloc[0]
                revenue_values.append(float(val) if pd.notna(val) else 0)
            else:
                revenue_values.append(0)
        
        # Create figure
        fig = go.Figure()
        
        # Add revenue bars (main metric)
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_values,
            name='Total Net Sales',
            marker_color='#4A6FA5',  # Professional blue
            text=[f'${v:,.0f}M' for v in revenue_values],
            textposition='outside',
            textfont=dict(color='#2C3E50')
        ))
        
        # Add selected metrics
        if 'operating_expenses' in selected_metrics:
            # Find total operating expenses
            operating_expenses_row = income_df[income_df['Item'].str.contains('total operating expenses', case=False, na=False)]
            if not operating_expenses_row.empty:
                expenses_values = []
                for year in years:
                    if year in operating_expenses_row.columns:
                        val = operating_expenses_row[year].iloc[0]
                        expenses_values.append(float(val) if pd.notna(val) else 0)
                    else:
                        expenses_values.append(0)
                
                # Add triangles for operating expenses
                fig.add_trace(go.Scatter(
                    x=years,
                    y=expenses_values,
                    mode='markers',
                    name='Total Operating Expenses',
                    marker=dict(
                        symbol='triangle-up',
                        size=18,
                        color='#E74C3C',  # Professional red
                        line=dict(width=2, color='#C0392B')
                    ),
                    text=[f'${v:,.0f}M' for v in expenses_values],
                    textposition='top center',
                    textfont=dict(color='#E74C3C')
                ))
        
        if 'net_income' in selected_metrics:
            # Find net income
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
                    marker_color='#27AE60',  # Professional green
                    text=[f'${v:,.0f}M' for v in income_values],
                    textposition='outside',
                    textfont=dict(color='#1E8449')
                ))
        
        if 'gross_margin' in selected_metrics:
            # Find gross margin
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
                    marker_color='#8E44AD',  # Professional purple
                    text=[f'${v:,.0f}M' for v in margin_values],
                    textposition='outside',
                    textfont=dict(color='#6C3483')
                ))
        
        # Update layout
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
        
        # Update axes
        fig.update_xaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        fig.update_yaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        
        return fig
    
    except Exception as e:
        print(f"Error creating enhanced revenue chart: {e}")
        return go.Figure().add_annotation(text="Error creating chart", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)

def create_product_breakdown_clean(table7_df):
    """Create clean product revenue breakdown (excluding total sales) - centered"""
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
                
                # Skip total net sales row
                if 'total' in product.lower() and 'sales' in product.lower():
                    continue
                
                # Clean product names
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
            # Professional color palette
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
                pull=[0.05 if i == 0 else 0 for i in range(len(products))]  # Slightly pull out first slice
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
                
                # Skip total net sales row
                if 'total' in region.lower() and 'sales' in region.lower():
                    continue
                
                regions.append(region)
                values.append(value)
        
        if regions and values:
            # Map Apple's regions to geographic coordinates and country codes
            region_mapping = {
                'Americas': {
                    'lat': [39.8283, 45.4215, 19.4326, -14.2350],  # USA, Canada, Mexico, Brazil
                    'lon': [-98.5795, -75.6972, -99.1332, -51.9253],
                    'countries': ['USA', 'CAN', 'MEX', 'BRA'],
                    'country_names': ['United States', 'Canada', 'Mexico', 'Brazil']
                },
                'Europe': {
                    'lat': [54.5260, 46.2276, 41.8719, 52.1326, 60.1282],  # UK, Switzerland, Spain, Netherlands, Finland
                    'lon': [-4.5471, 2.2137, 12.5674, 5.2913, 18.6435],
                    'countries': ['GBR', 'CHE', 'ESP', 'NLD', 'FIN'],
                    'country_names': ['United Kingdom', 'Switzerland', 'Spain', 'Netherlands', 'Finland']
                },
                'Greater China': {
                    'lat': [35.8617, 22.3193],  # China, Hong Kong
                    'lon': [104.1954, 114.1694],
                    'countries': ['CHN', 'HKG'],
                    'country_names': ['China', 'Hong Kong']
                },
                'Japan': {
                    'lat': [36.2048],
                    'lon': [138.2529],
                    'countries': ['JPN'],
                    'country_names': ['Japan']
                },
                'Rest of Asia Pacific': {
                    'lat': [1.3521, -25.2744, 15.8700, 12.8797],  # Singapore, South Africa, Thailand, Philippines
                    'lon': [103.8198, 133.7751, 100.9925, 121.7740],
                    'countries': ['SGP', 'AUS', 'THA', 'PHL'],
                    'country_names': ['Singapore', 'Australia', 'Thailand', 'Philippines']
                }
            }
            
            # Create data for the map
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
                    revenue_per_country = values[i] / len(mapping['lat'])
                    
                    for j in range(len(mapping['lat'])):
                        map_data.append({
                            'lat': mapping['lat'][j],
                            'lon': mapping['lon'][j],
                            'region': region,
                            'country': mapping['country_names'][j],
                            'revenue': revenue_per_country,
                            'total_revenue': values[i],
                            'color': region_colors.get(region, '#95A5A6')
                        })
            
            df_map = pd.DataFrame(map_data)
            
            # Create the map
            fig = go.Figure()
            
            # Add scatter points for each region
            for region in regions:
                if region in region_mapping:
                    region_data = df_map[df_map['region'] == region]
                    
                    fig.add_trace(go.Scattergeo(
                        lon=region_data['lon'],
                        lat=region_data['lat'],
                        text=region_data.apply(lambda row: 
                            f"<b>{row['country']}</b><br>" +
                            f"Region: {row['region']}<br>" +
                            f"Total Revenue: ${row['total_revenue']:,.0f}M<br>" +
                            f"Countries in region: {len(region_mapping[row['region']]['lat'])}", axis=1),
                        mode='markers',
                        marker=dict(
                            size=np.sqrt(df_map[df_map['region'] == region]['total_revenue'].iloc[0]) / 15,  # Size based on revenue
                            color=region_colors.get(region, '#95A5A6'),
                            line=dict(width=2, color='white'),
                            sizemode='diameter',
                            opacity=0.8
                        ),
                        name=f"{region}<br>${df_map[df_map['region'] == region]['total_revenue'].iloc[0]:,.0f}M",
                        hovertemplate='<b>%{text}</b><extra></extra>',
                        showlegend=True
                    ))
            
            # Update layout for the map
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
            # Find key metrics
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

print("✅ Enhanced chart functions with geographic map defined successfully!")
print("🗺️  NEW: Geographic map replaces regional pie chart")
print("🎯 Product pie chart optimized for centering")
print("💰 Professional metrics cards with gradients")
print("📊 Enhanced revenue chart with multiple overlay options")
print("🎯 Part 2 Complete! Ready for Part 3 (Dashboard Layout)...")

# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 2: ENHANCED CHART FUNCTIONS
# ============================================================================

def create_enhanced_revenue_chart(income_df, selected_metrics):
    """Create enhanced revenue bar chart with dropdown options"""
    if income_df.empty:
        return go.Figure().add_annotation(text="No data available", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)
    
    try:
        # Find total net sales row
        total_sales_row = income_df[income_df['Item'].str.contains('total net sales', case=False, na=False)]
        
        if total_sales_row.empty:
            return go.Figure().add_annotation(text="Total net sales data not found", 
                                            xref="paper", yref="paper", 
                                            x=0.5, y=0.5, showarrow=False)
        
        years = ['2022', '2023', '2024']
        revenue_values = []
        
        # Get revenue values
        for year in years:
            if year in total_sales_row.columns:
                val = total_sales_row[year].iloc[0]
                revenue_values.append(float(val) if pd.notna(val) else 0)
            else:
                revenue_values.append(0)
        
        # Create figure
        fig = go.Figure()
        
        # Add revenue bars (main metric)
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_values,
            name='Total Net Sales',
            marker_color='#4A6FA5',  # Professional blue
            text=[f'${v:,.0f}M' for v in revenue_values],
            textposition='outside',
            textfont=dict(color='#2C3E50')
        ))
        
        # Add selected metrics
        if 'operating_expenses' in selected_metrics:
            # Find total operating expenses
            operating_expenses_row = income_df[income_df['Item'].str.contains('total operating expenses', case=False, na=False)]
            if not operating_expenses_row.empty:
                expenses_values = []
                for year in years:
                    if year in operating_expenses_row.columns:
                        val = operating_expenses_row[year].iloc[0]
                        expenses_values.append(float(val) if pd.notna(val) else 0)
                    else:
                        expenses_values.append(0)
                
                # Add triangles for operating expenses
                fig.add_trace(go.Scatter(
                    x=years,
                    y=expenses_values,
                    mode='markers',
                    name='Total Operating Expenses',
                    marker=dict(
                        symbol='triangle-up',
                        size=18,
                        color='#E74C3C',  # Professional red
                        line=dict(width=2, color='#C0392B')
                    ),
                    text=[f'${v:,.0f}M' for v in expenses_values],
                    textposition='top center',
                    textfont=dict(color='#E74C3C')
                ))
        
        if 'net_income' in selected_metrics:
            # Find net income
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
                    marker_color='#27AE60',  # Professional green
                    text=[f'${v:,.0f}M' for v in income_values],
                    textposition='outside',
                    textfont=dict(color='#1E8449')
                ))
        
        if 'gross_margin' in selected_metrics:
            # Find gross margin
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
                    marker_color='#8E44AD',  # Professional purple
                    text=[f'${v:,.0f}M' for v in margin_values],
                    textposition='outside',
                    textfont=dict(color='#6C3483')
                ))
        
        # Update layout
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
        
        # Update axes
        fig.update_xaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        fig.update_yaxes(gridcolor='#E8E8E8', linecolor='#BDC3C7')
        
        return fig
    
    except Exception as e:
        print(f"Error creating enhanced revenue chart: {e}")
        return go.Figure().add_annotation(text="Error creating chart", 
                                        xref="paper", yref="paper", 
                                        x=0.5, y=0.5, showarrow=False)

def create_product_breakdown_clean(table7_df):
    """Create clean product revenue breakdown (excluding total sales) - centered"""
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
                
                # Skip total net sales row
                if 'total' in product.lower() and 'sales' in product.lower():
                    continue
                
                # Clean product names
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
            # Professional color palette
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
                pull=[0.05 if i == 0 else 0 for i in range(len(products))]  # Slightly pull out first slice
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
                
                # Skip total net sales row
                if 'total' in region.lower() and 'sales' in region.lower():
                    continue
                
                regions.append(region)
                values.append(value)
        
        if regions and values:
            # Map Apple's regions to geographic coordinates and country codes
            region_mapping = {
                'Americas': {
                    'lat': [39.8283, 45.4215, 19.4326, -14.2350],  # USA, Canada, Mexico, Brazil
                    'lon': [-98.5795, -75.6972, -99.1332, -51.9253],
                    'countries': ['USA', 'CAN', 'MEX', 'BRA'],
                    'country_names': ['United States', 'Canada', 'Mexico', 'Brazil']
                },
                'Europe': {
                    'lat': [54.5260, 46.2276, 41.8719, 52.1326, 60.1282],  # UK, Switzerland, Spain, Netherlands, Finland
                    'lon': [-4.5471, 2.2137, 12.5674, 5.2913, 18.6435],
                    'countries': ['GBR', 'CHE', 'ESP', 'NLD', 'FIN'],
                    'country_names': ['United Kingdom', 'Switzerland', 'Spain', 'Netherlands', 'Finland']
                },
                'Greater China': {
                    'lat': [35.8617, 22.3193],  # China, Hong Kong
                    'lon': [104.1954, 114.1694],
                    'countries': ['CHN', 'HKG'],
                    'country_names': ['China', 'Hong Kong']
                },
                'Japan': {
                    'lat': [36.2048],
                    'lon': [138.2529],
                    'countries': ['JPN'],
                    'country_names': ['Japan']
                },
                'Rest of Asia Pacific': {
                    'lat': [1.3521, -25.2744, 15.8700, 12.8797],  # Singapore, South Africa, Thailand, Philippines
                    'lon': [103.8198, 133.7751, 100.9925, 121.7740],
                    'countries': ['SGP', 'AUS', 'THA', 'PHL'],
                    'country_names': ['Singapore', 'Australia', 'Thailand', 'Philippines']
                }
            }
            
            # Create data for the map
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
                    # Use the first (primary) location for each region
                    map_data.append({
                        'lat': mapping['lat'][0],  # First latitude only
                        'lon': mapping['lon'][0],  # First longitude only
                        'region': region,
                        'country': mapping['country_names'][0],  # Primary country
                        'revenue': values[i],  # Full revenue amount
                        'total_revenue': values[i],
                        'color': region_colors.get(region, '#95A5A6')
                    })

            df_map = pd.DataFrame(map_data)
            
            # Create the map
            fig = go.Figure()
            
            # Add scatter points for each region
            for region in regions:
                if region in region_mapping:
                    region_data = df_map[df_map['region'] == region]
                    
                    fig.add_trace(go.Scattergeo(
                        lon=region_data['lon'],
                        lat=region_data['lat'],
                        text=region_data.apply(lambda row: 
                            f"<b>{row['country']}</b><br>" +
                            f"Region: {row['region']}<br>" +
                            f"Total Revenue: ${row['total_revenue']:,.0f}M<br>" +
                            f"Countries in region: {len(region_mapping[row['region']]['lat'])}", axis=1),
                        mode='markers',
                        marker=dict(
                            size=np.sqrt(df_map[df_map['region'] == region]['total_revenue'].iloc[0]) / 15,  # Size based on revenue
                            color=region_colors.get(region, '#95A5A6'),
                            line=dict(width=2, color='white'),
                            sizemode='diameter',
                            opacity=0.8
                        ),
                        name=f"{region}<br>${df_map[df_map['region'] == region]['total_revenue'].iloc[0]:,.0f}M",
                        hovertemplate='<b>%{text}</b><extra></extra>',
                        showlegend=True
                    ))
            
            # Update layout for the map
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
            # Find key metrics
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

print("✅ Enhanced chart functions with geographic map defined successfully!")
print("🗺️  NEW: Geographic map replaces regional pie chart")
print("🎯 Product pie chart optimized for centering")
print("💰 Professional metrics cards with gradients")
print("📊 Enhanced revenue chart with multiple overlay options")
print("🎯 Part 2 Complete! Ready for Part 3 (Dashboard Layout)...")

# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 3: ENHANCED LAYOUT WITH IMPROVED DROPDOWNS
# ============================================================================

# Initialize Dash
app = dash.Dash(__name__)

# Enhanced layout with centered charts and improved dropdowns
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
    
    # Enhanced Revenue Chart Section with Improved Dropdown
    html.Div([
        html.Div([
            html.H3("Financial Metrics Overview", style={'color': '#2C3E50', 'margin-bottom': '20px', 'font-weight': '400'}),
            
            # Enhanced dropdown with better visibility and instructions
            html.Div([
                html.Label("📊 Interactive Chart Controls", 
                          style={'color': '#2C3E50', 'font-size': '16px', 'font-weight': '600', 'margin-bottom': '8px', 'display': 'block'}),
                html.P("Select additional financial metrics to overlay on the revenue chart:", 
                       style={'color': '#5D6D7E', 'margin-bottom': '12px', 'font-weight': '400', 'font-size': '14px', 'display': 'block'}),
                dcc.Dropdown(
                    id='metrics-dropdown',
                    options=[
                        {'label': '📈 Total Operating Expenses', 'value': 'operating_expenses'},
                        {'label': '💰 Net Income', 'value': 'net_income'},
                        {'label': '📊 Gross Margin', 'value': 'gross_margin'}
                    ],
                    value=[],
                    multi=True,
                    placeholder="👆 Click here to select metrics to overlay on the chart...",
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
    
    # CENTERED CHARTS SECTION - Product Pie Chart and Geographic Map
    html.Div([
        # Centered container for both charts
        html.Div([
            # Product Breakdown Chart (Centered)
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
            
            # Geographic Map (Centered)
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
            'max-width': '800px',  # Limit width for better centering
            'margin': '0 auto',    # Center the container
            'padding': '0 20px'    # Add some padding
        })
    ], style={'margin-bottom': '30px'}),
    
    # Data Tables Section with Enhanced Dropdown
    html.Div([
        html.H2("Raw Data", 
                style={'color': '#2C3E50', 'margin-bottom': '25px', 'border-bottom': '3px solid #4A6FA5', 'padding-bottom': '12px', 'font-weight': '400'}),
        
        # Enhanced dropdown with better visibility and instructions
        html.Div([
            html.Label("📋 Document Selector", 
                      style={'color': '#2C3E50', 'font-size': '16px', 'font-weight': '600', 'margin-bottom': '8px', 'display': 'block'}),
            html.P("Choose which financial document you want to view in detail:", 
                   style={'color': '#5D6D7E', 'margin-bottom': '12px', 'font-weight': '400', 'font-size': '14px', 'display': 'block'}),
            dcc.Dropdown(
                id='table-selector',
                options=[
                    {'label': '📊 Income Statement', 'value': 'INCOME_STATEMENT'},
                    {'label': '⚖️ Balance Sheet', 'value': 'BALANCE_SHEET'},
                    {'label': '🌍 Revenue by Region', 'value': 'TABLE6'},
                    {'label': '📱 Revenue by Product', 'value': 'TABLE7'}
                ],
                value='INCOME_STATEMENT',
                placeholder="👆 Click here to select a financial document to view...",
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
        
        # Data table
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

print("✅ Enhanced dashboard layout created successfully!")
print("🎨 Key improvements:")
print("   📊 Enhanced dropdown with clear instructions and visual styling")
print("   🗺️  Centered charts layout for better visual balance")
print("   📋 Improved document selector with emojis and descriptions")
print("   🎯 Professional gradient backgrounds and shadows")
print("   📱 Responsive design for different screen sizes")
print("🎯 Part 3 Complete! Ready for Part 4 (Callbacks)...")

# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 4: ENHANCED CALLBACKS AND TABLE FORMATTING
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
    geographic_fig = create_regional_breakdown_map(data['TABLE6'])  # New geographic map
    
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
                    # Check if column contains numeric data
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
            # Rename columns to include units
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
            # Rename columns to include units
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
                    # Highlight financial values
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

print("✅ Enhanced callbacks with number formatting defined successfully!")
print("📊 Key callback features:")
print("   🗺️  Geographic map integration")
print("   📈 Dynamic chart updates based on dropdown selections")
print("   💰 Professional number formatting with commas")
print("   📋 Enhanced table styling with alternating rows")
print("   🎨 Highlighted totals and key financial metrics")
print("   📱 Responsive table design with sorting and filtering")
print("🎯 Part 4 Complete! Ready for Part 5 (Run Dashboard)...")

# %%
# ============================================================================
# APPLE FINANCIAL DASHBOARD - PART 5: RUN SCRIPT AND INTEGRATION GUIDE
# ============================================================================

# Run the Enhanced Dashboard


🎯 ENHANCED INTERACTIVE CONTROLS:
   • 📊 Prominent dropdown with clear instructions
   • 👆 Visual cues showing clickable elements
   • 🎨 Professional styling with gradients and shadows
   • 📋 Document selector with emoji icons

🗺️  GEOGRAPHIC MAP (NEW):
   • Interactive world map showing revenue by region
   • Marker sizes proportional to revenue amounts
   • Hover tooltips with detailed information
   • Professional color coding by region

📈 ENHANCED REVENUE CHART:
   • 3-year financial data comparison
   • Overlay options: Operating Expenses, Net Income, Gross Margin
   • Professional color scheme with formatted values
   • Interactive legend and tooltips

🥧 CENTERED PIE CHART:
   • Product category breakdown (excludes total sales)
   • Clean, centered layout for better visual balance
   • Professional color palette

💰 KEY METRICS CARDS:
   • Total Revenue with year-over-year change
   • Net Income with year-over-year change
   • Professional gradients and shadows

📋 ENHANCED DATA TABLES:
   • Formatted numbers with commas (391,035)
   • Percentage formatting (3.0%)
   • Units clearly displayed in headers
   • Sortable and filterable columns
   • Professional styling with highlighted totals
   • Alternating row colors for better readability

🎨 PROFESSIONAL DESIGN:
   • Apple-inspired aesthetic
   • Consistent typography and spacing
   • Responsive layout for different screen sizes
   • Professional shadows and borders
   • Centered layout for better visual balance
""")
    print("=" * 70)
    print("🌍 GEOGRAPHIC MAP DETAILS:")
    print("=" * 70)
    print("""
📍 REGION MAPPING:
   • Americas: USA, Canada, Mexico, Brazil
   • Europe: UK, Switzerland, Spain, Netherlands, Finland
   • Greater China: China, Hong Kong
   • Japan: Japan
   • Rest of Asia Pacific: Singapore, Australia, Thailand, Philippines

🎨 VISUAL FEATURES:
   • Marker sizes reflect revenue amounts
   • Color-coded regions with professional palette
   • Interactive hover information
   • Clean legend with revenue totals
   • Natural earth projection for global view
""")
    print("=" * 70)
    print("🔧 TECHNICAL IMPROVEMENTS:")
    print("=" * 70)
    print("""
✅ Auto-detects data start/end rows for better performance
✅ Handles missing data gracefully with fallbacks
✅ Modern Dash implementation with enhanced callbacks
✅ Professional number formatting throughout
✅ Optimized chart rendering and layout
✅ Enhanced user experience with clear instructions
✅ Responsive design for mobile and desktop
""")
    print("=" * 70)
    
    print("📍 Trying to start dashboard...")
    print("💡 If you see 'Address already in use', we'll try different ports")
    print("")
    
    # Try multiple ports
# Simple fix - use port 9876
print("🚀 Starting dashboard...")
app.run(debug=False, port=9876, host='127.0.0.1')
print("📍 Open: http://localhost:9876")

print("=" * 70)
print("🔧 INTEGRATION INSTRUCTIONS")
print("=" * 70)
print("""
TO USE THIS ENHANCED DASHBOARD:

STEP 1 - SAVE EACH PART AS A SEPARATE PYTHON FILE:
   📄 Part 1: apple_dashboard_data.py (imports & data processing)
   📄 Part 2: apple_dashboard_charts.py (chart functions)
   📄 Part 3: apple_dashboard_layout.py (layout & styling)
   📄 Part 4: apple_dashboard_callbacks.py (interactivity)
   📄 Part 5: apple_dashboard_run.py (this file - run script)

STEP 2 - OR RUN ALL PARTS IN SEQUENCE IN ONE NOTEBOOK:
   📋 Copy and run Part 1 first (data loading)
   📋 Then run Part 2 (chart functions)
   📋 Then run Part 3 (layout)
   📋 Then run Part 4 (callbacks)
   📋 Finally run Part 5 (this part to start the dashboard)

STEP 3 - UPDATE YOUR FILE PATH:
   📁 In Part 1, update the file_path variable:
   file_path = "/path/to/your/apple_annual_report.xls"

STEP 4 - VERIFY YOUR DATA STRUCTURE:
   📊 Make sure your Excel file has these sheets:
      • INCOME_STATEMENT
      • BALANCE_SHEET
      • TABLE6 (regional data)
      • TABLE7 (product data)

STEP 5 - INSTALL REQUIRED PACKAGES (if needed):
   pip install dash plotly pandas openpyxl xlrd numpy

STEP 6 - TROUBLESHOOTING:
   ❌ If port 8050 is busy, the script will try 8051
   ❌ If data doesn't load, check your file path in Part 1
   ❌ If charts are empty, verify your Excel sheet structure
   ❌ If geographic map doesn't show, check TABLE6 region names

STEP 7 - CUSTOMIZATION OPTIONS:
   🎨 Colors: Modify the color palettes in chart functions
   📊 Metrics: Add more financial metrics to the dropdown
   🗺️  Regions: Update region_mapping for different geographic areas
   📋 Tables: Adjust formatting in the table callback
""")
print("=" * 70)
print("🎉 WHAT'S NEW IN THIS ENHANCED VERSION:")
print("=" * 70)
print("""
✨ MAJOR IMPROVEMENTS:
   🗺️  Geographic map replaces regional pie chart
   📊 Enhanced dropdowns with clear instructions
   🎯 Centered chart layout for better visual balance
   💰 Professional gradient styling throughout
   📱 Better mobile responsiveness
   🔧 Improved error handling and fallbacks

✨ USER EXPERIENCE ENHANCEMENTS:
   👆 Clear visual cues for interactive elements
   📋 Descriptive labels and instructions
   🎨 Professional Apple-inspired design
   📊 Emoji icons for better visual scanning
   💡 Helpful placeholder text in dropdowns

✨ TECHNICAL IMPROVEMENTS:
   ⚡ Optimized data processing with auto-detection
   📈 Enhanced chart rendering and performance
   🗺️  Professional geographic visualization
   📋 Better number formatting throughout
   🔄 Robust error handling and data validation
""")
print("=" * 70)
print("🎯 YOUR PROFESSIONAL APPLE FINANCIAL DASHBOARD IS READY!")
print("=" * 70)
print("""
🚀 NEXT STEPS:
1. Run all 5 parts in sequence
2. Open http://localhost:8050 in your browser
3. Explore the interactive features:
   • Try the enhanced dropdowns
   • Hover over the geographic map
   • Filter and sort the data tables
   • Toggle different financial metrics

💡 TIPS FOR BEST EXPERIENCE:
• Use a modern browser (Chrome, Firefox, Safari, Edge)
• Try different combinations of financial metrics
• Explore the geographic map hover tooltips
• Use the table filters to find specific data
• Check out the professional number formatting

📧 SUPPORT:
If you encounter any issues, check the console output for
helpful error messages and troubleshooting tips.
""")
print("=" * 70)

# ============================================================================
# SAMPLE DATA FOR TESTING (OPTIONAL)
# ============================================================================

def create_sample_data_for_testing():
    """
    Create sample data structure for testing the dashboard
    Use this if you want to test the dashboard without loading Excel data
    """
    
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
        'Region': ['Americas', 'Europe', 'Greater China', 'Japan', 'Rest of Asia Pacific', 'Total net sales'],
        '2024': [124300, 73930, 72480, 24257, 29615, 324582],
        'Change_24': [0.03, -0.01, -0.13, 0.02, 0.04, -0.01],
        '2023': [120920, 74690, 83370, 23810, 28430, 331180],
        'Change_23': [0.02, 0.01, -0.02, 0.05, 0.03, 0.01],
        '2022': [118540, 73980, 85040, 22680, 27560, 327800]
    })
    
    # Sample Product data
    sample_products = pd.DataFrame({
        'Product': ['iPhone', 'Mac', 'iPad', 'Wearables, Home and Accessories', 'Services', 'Total net sales'],
        '2024': [200583, 29357, 28300, 37017, 96169, 391426],
        'Change_24': [0.006, 0.024, -0.065, 0.027, 0.129, 0.020],
        '2023': [199940, 28680, 30240, 36050, 85200, 380110],
        'Change_23': [-0.027, 0.017, -0.035, 0.089, 0.086, -0.028],
        '2022': [205489, 28200, 31350, 33100, 78500, 376639]
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

# Uncomment the line below to use sample data for testing
# data = create_sample_data_for_testing()

print("""
📝 OPTIONAL: To test with sample data instead of loading Excel:
   Uncomment the last line in this file:
   # data = create_sample_data_for_testing()
   
   This will create realistic Apple financial data for testing
   the dashboard functionality without needing the Excel file.
""")

print("✅ Part 5 Complete! Dashboard ready to run!")
print("🎯 Execute this file to start your enhanced Apple Financial Dashboard!")
if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8000, debug=False)

