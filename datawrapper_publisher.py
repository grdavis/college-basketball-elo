"""
Datawrapper Publisher Module

Handles publishing prediction tables to Datawrapper for interactive display.
Provides functions to create/update charts and generate embeddable HTML pages.
"""

import os
import sys
import html
import contextlib
from datawrapper import Datawrapper
import pandas as pd

# Configuration from environment variables
DW_API_TOKEN = os.environ.get('DATAWRAPPER_API_TOKEN')
PREDICTIONS_CHART_ID = os.environ.get('DW_PREDICTIONS_CHART_ID', None)
RANKINGS_CHART_ID = os.environ.get('DW_RANKINGS_CHART_ID', None)

@contextlib.contextmanager
def suppress_stdout():
    """Context manager to suppress stdout/stderr"""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = devnull
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def get_datawrapper_client():
    """Initialize and return Datawrapper client"""
    if not DW_API_TOKEN:
        raise ValueError("DATAWRAPPER_API_TOKEN environment variable not set")
    return Datawrapper(access_token=DW_API_TOKEN)

def create_or_update_predictions_table(predictions_df, date_str, elo_date):
    """
    Create or update the daily predictions table in Datawrapper
    
    Args:
        predictions_df: DataFrame with prediction data
        date_str: Date string for the title (e.g., "2025-11-29")
        elo_date: Date string for ELO ratings (e.g., "20251128")
    
    Returns:
        Tuple of (chart_id, public_url)
    """
    dw = get_datawrapper_client()
    
    # Chart title with date
    title = f"NCAAM ELO Game Predictions for {date_str}"
    
    if PREDICTIONS_CHART_ID:
        # Update existing chart
        chart_id = PREDICTIONS_CHART_ID
        try:
            with suppress_stdout():
                dw.update_chart(chart_id, title=title)
        except Exception as e:
            print(f"Warning: Could not update chart title: {e}")
    else:
        # Create new chart
        try:
            with suppress_stdout():
                chart_info = dw.create_chart(
                    title=title,
                    chart_type='tables',
                    data=predictions_df
                )
            chart_id = chart_info['id']
            print(f"\n✓ Created new predictions chart with ID: {chart_id}")
            print(f"  Add this to GitHub Secrets as DW_PREDICTIONS_CHART_ID")
        except Exception as e:
            raise Exception(f"Failed to create Datawrapper chart: {e}")
    
    # Upload data
    try:
        with suppress_stdout():
            dw.add_data(chart_id, predictions_df)
    except Exception as e:
        raise Exception(f"Failed to upload data to Datawrapper: {e}")
    
    # Configure chart metadata and appearance
    try:
        with suppress_stdout():
            dw.update_metadata(chart_id, {
                'describe': {
                    'intro': f"Below are predictions for today's Men's college basketball games using an ELO rating methodology. Ratings are through {elo_date}. Teams with * are new to the model and predictions are more uncertain.",
                    'source-name': 'college-basketball-elo',
                    'source-url': 'https://github.com/grdavis/college-basketball-elo',
                    'byline': '@grdavis'
                },
                'visualize': {
                    'table': {
                        'sorting': 'enable',  # Enable column sorting
                        'striped': True,      # Alternating row colors
                    }
                }
            })
    except Exception as e:
        print(f"Warning: Could not update chart metadata: {e}")
    
    # Publish the chart
    try:
        with suppress_stdout():
            response = dw.publish_chart(chart_id)
        
        public_url = response.get('data', {}).get('publicUrl') or response.get('publicUrl')
        if not public_url:
            # Fallback: construct URL from chart ID
            public_url = f"https://datawrapper.dwcdn.net/{chart_id}/1/"
        return chart_id, public_url
    except Exception as e:
        raise Exception(f"Failed to publish Datawrapper chart: {e}")

def create_or_update_rankings_table(rankings_df):
    """
    Create or update the top 100 rankings table in Datawrapper
    
    Args:
        rankings_df: DataFrame with top 100 team rankings
    
    Returns:
        Tuple of (chart_id, public_url)
    """
    dw = get_datawrapper_client()
    
    title = "Top 100 Teams by ELO Rating"
    
    if RANKINGS_CHART_ID:
        # Update existing chart
        chart_id = RANKINGS_CHART_ID
        try:
            with suppress_stdout():
                dw.update_chart(chart_id, title=title)
        except Exception as e:
            print(f"Warning: Could not update chart title: {e}")
    else:
        # Create new chart
        try:
            with suppress_stdout():
                chart_info = dw.create_chart(
                    title=title,
                    chart_type='tables',
                    data=rankings_df
                )
            chart_id = chart_info['id']
            print(f"\n✓ Created new rankings chart with ID: {chart_id}")
            print(f"  Add this to GitHub Secrets as DW_RANKINGS_CHART_ID")
        except Exception as e:
            raise Exception(f"Failed to create Datawrapper chart: {e}")
    
    # Upload data
    try:
        with suppress_stdout():
            dw.add_data(chart_id, rankings_df)
    except Exception as e:
        raise Exception(f"Failed to upload data to Datawrapper: {e}")
    
    # Configure chart
    try:
        with suppress_stdout():
            dw.update_metadata(chart_id, {
                'describe': {
                    'source-name': 'college-basketball-elo',
                    'source-url': 'https://github.com/grdavis/college-basketball-elo',
                    'byline': '@grdavis'
                },
                'visualize': {
                    'table': {
                        'sorting': 'enable',
                        'striped': True,
                    }
                }
            })
    except Exception as e:
        print(f"Warning: Could not update chart metadata: {e}")
    
    # Publish the chart
    try:
        with suppress_stdout():
            response = dw.publish_chart(chart_id)
        
        public_url = response.get('data', {}).get('publicUrl') or response.get('publicUrl')
        if not public_url:
            # Fallback: construct URL from chart ID
            public_url = f"https://datawrapper.dwcdn.net/{chart_id}/1/"
        return chart_id, public_url
    except Exception as e:
        raise Exception(f"Failed to publish Datawrapper chart: {e}")

def save_datawrapper_embeds(predictions_url, rankings_url, date_str, markdown_content=None):
    """
    Generate an HTML page with embedded Datawrapper charts
    
    Args:
        predictions_url: Public URL of predictions chart
        rankings_url: Public URL of rankings chart
        date_str: Date string for the page
        markdown_content: Optional markdown string to include in a hidden div
    """
    
    markdown_section = ""
    if markdown_content:
        # We use a visually hidden div to store the markdown content.
        # This makes it accessible to tools that read the DOM/text content but might ignore script tags.
        # We escape the HTML content to ensure it doesn't break the page structure.
        escaped_markdown = html.escape(markdown_content)
        markdown_section = f"""
    <!-- Raw markdown content for machine consumption -->
    <div id="raw-markdown" class="visually-hidden">
<pre>
{escaped_markdown}
</pre>
    </div>
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NCAAM ELO Predictions - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .info {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .visually-hidden {{
            position: absolute;
            width: 1px;
            height: 1px;
            margin: -1px;
            padding: 0;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            border: 0;
        }}
    </style>
</head>
<body>
    {markdown_section}
    <h1>NCAAM ELO Game Predictions - {date_str}</h1>
    
    <div class="info">
        <p>Below are predictions for today's Men's college basketball games using an ELO rating methodology.</p>
        <p><strong>Interactive features:</strong> Click on any column header to sort by that column. Tables are fully responsive and work on mobile devices.</p>
        <p>Note: Teams with * or those written as abbreviations (e.g. BREC) are likely new to the model (i.e. they haven't played any/many D1 games) and predictions are more uncertain.</p>
        <p>Check out the full <a href="https://github.com/grdavis/college-basketball-elo">college-basketball-elo</a> repository on GitHub to see methodology and more.</p>
    </div>
    
    <div class="chart-container">
        <h2>Today's Game Predictions</h2>
        <iframe title="Daily Predictions" aria-label="Table" src="{predictions_url}" 
                scrolling="no" frameborder="0" style="width: 100%; min-height: 600px; border: none;"></iframe>
    </div>
    
    <div class="chart-container">
        <h2>Top 100 Teams by ELO Rating</h2>
        <iframe title="Rankings" aria-label="Table" src="{rankings_url}" 
                scrolling="no" frameborder="0" style="width: 100%; min-height: 800px; border: none;"></iframe>
    </div>
    
    <script type="text/javascript">
        // Datawrapper responsive iframe script
        !function(){{"use strict";window.addEventListener("message",(function(a){{if(void 0!==a.data["datawrapper-height"]){{var e=document.querySelectorAll("iframe");for(var t in a.data["datawrapper-height"])for(var r=0;r<e.length;r++)if(e[r].contentWindow===a.source){{var i=a.data["datawrapper-height"][t]+"px";e[r].style.height=i}}}}}}))}}();
    </script>
</body>
</html>
"""
    
    # Save to docs folder for GitHub Pages
    docs_folder = 'docs/'
    os.makedirs(docs_folder, exist_ok=True)
    
    with open(f'{docs_folder}index.html', 'w') as f:
        f.write(html_content)
    
    print(f"✓ Saved interactive HTML page to docs/index.html")

def save_fallback_html(predictions_df, rankings_df, date_str, markdown_content):
    """
    Generate a fallback HTML page with standard HTML tables when Datawrapper fails.
    
    Args:
        predictions_df: DataFrame with prediction data
        rankings_df: DataFrame with rankings data
        date_str: Date string for the page
        markdown_content: Markdown string to include in a hidden div
    """
    
    # Convert DataFrames to HTML tables
    # Use some basic bootstrap styling classes if we were using bootstrap, 
    # but here we'll just use the same CSS as before + some simple table styles
    
    pred_html = predictions_df.to_html(index=False, border=0, classes="styled-table", escape=False)
    rank_html = rankings_df.to_html(index=True, border=0, classes="styled-table", escape=False)
    
    escaped_markdown = html.escape(markdown_content)
    markdown_section = f"""
    <!-- Raw markdown content for machine consumption -->
    <div id="raw-markdown" class="visually-hidden">
<pre>
{escaped_markdown}
</pre>
    </div>
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NCAAM ELO Predictions - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        .info {{
            background: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        
        /* Basic Table Styles */
        .styled-table {{
            border-collapse: collapse;
            margin: 25px 0;
            font-size: 0.9em;
            font-family: sans-serif;
            min-width: 400px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
            width: 100%;
        }}
        .styled-table thead tr {{
            background-color: #0066cc;
            color: #ffffff;
            text-align: left;
        }}
        .styled-table th, .styled-table td {{
            padding: 12px 15px;
        }}
        .styled-table tbody tr {{
            border-bottom: 1px solid #dddddd;
        }}
        .styled-table tbody tr:nth-of-type(even) {{
            background-color: #f3f3f3;
        }}
        .styled-table tbody tr:last-of-type {{
            border-bottom: 2px solid #0066cc;
        }}
        .visually-hidden {{
            position: absolute;
            width: 1px;
            height: 1px;
            margin: -1px;
            padding: 0;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            border: 0;
        }}
    </style>
</head>
<body>
    {markdown_section}
    <h1>NCAAM ELO Game Predictions - {date_str}</h1>
    
    <div class="info">
        <p>Below are predictions for today's Men's college basketball games using an ELO rating methodology.</p>
        <p>Note: Teams with * or those written as abbreviations (e.g. BREC) are likely new to the model (i.e. they haven't played any/many D1 games) and predictions are more uncertain.</p>
        <p><strong>Note:</strong> This is a static version of the predictions page generated because the interactive charts service is currently unavailable.</p>
        <p>Check out the full <a href="https://github.com/grdavis/college-basketball-elo">college-basketball-elo</a> repository on GitHub to see methodology and more.</p>
    </div>
    
    <div class="chart-container">
        <h2>Today's Game Predictions</h2>
        {pred_html}
    </div>
    
    <div class="chart-container">
        <h2>Top 100 Teams by ELO Rating</h2>
        {rank_html}
    </div>

</body>
</html>
"""
    
    # Save to docs folder for GitHub Pages
    docs_folder = 'docs/'
    os.makedirs(docs_folder, exist_ok=True)
    
    with open(f'{docs_folder}index.html', 'w') as f:
        f.write(html_content)
    
    print(f"✓ Saved fallback HTML page to docs/index.html")




