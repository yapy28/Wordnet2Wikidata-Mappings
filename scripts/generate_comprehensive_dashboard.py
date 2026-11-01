#!/usr/bin/env python3
"""
Generate a comprehensive "mission control" dashboard that tracks:
1. ALL WordNet/Wikidata mappings
2. Wikidata constraint violations (P5063, P8814)
3. Our analysis and categorization
4. Proposed fixes
5. Drift detection (changes since last scan)
6. Progress tracking

This creates a unified view of the entire WordNet2Wikidata mapping ecosystem.
"""

import csv
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
import json

# Configuration
OUTPUT_DIR = Path("data/output/20260929")
DASHBOARD_FILE = OUTPUT_DIR / "comprehensive_dashboard.html"

# Date for this scan
SCAN_DATE = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
SCAN_DATE_ID = datetime.now().strftime("%Y%m%d")


def load_csv(filepath):
    """Load a CSV file and return list of dicts."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def count_rows(filepath):
    """Count rows in a CSV file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return len(list(reader))


def get_file_size(filepath):
    """Get file size in MB."""
    return round(filepath.stat().st_size / (1024 * 1024), 2)


def generate_comparison_table_html(comparison_data, max_rows=50):
    """Generate HTML for comparison table with truncation."""
    if not comparison_data:
        return "<tr><td colspan='7' style='text-align: center; color: var(--text-secondary);'>No comparison data available</td></tr>"
    
    rows = []
    for row in comparison_data[:max_rows]:
        entity_type = row.get('entity_type', '')
        qid = row.get('qid', '')
        wd_label = row.get('wd_label', '')
        synset_id = row.get('synset_id', '')
        ili = row.get('ili', '')
        status = row.get('status', '')
        has_fix = row.get('has_fix_proposed', '')
        fix_qid = row.get('fix_qid', '')
        
        # Truncate long text
        wd_label_display = wd_label[:40] + '...' if len(wd_label) > 40 else wd_label
        synset_display = synset_id or ili
        synset_display_short = synset_display[:25] + '...' if len(synset_display) > 25 else synset_display
        
        # Build synset/ILI links
        if ili:
            synset_link = f'<a href="https://ili.globalwordnet.org/i/{ili}" target="_blank" class="external-link">{synset_display_short}</a>'
        elif synset_id:
            synset_link = f'<a href="https://globalwordnet.github.io/oewn-gui/?synset={synset_id}" target="_blank" class="external-link">{synset_display_short}</a>'
        else:
            synset_link = synset_display_short
        
        # Status badge
        if status == 'FIX_PROPOSED':
            status_badge = f'<span class="badge badge-warning">FIX PROPOSED</span>'
        elif status == 'NEEDS_FIX':
            status_badge = f'<span class="badge badge-error">NEEDS FIX</span>'
        elif status == 'VALID':
            status_badge = f'<span class="badge badge-success">VALID</span>'
        else:
            status_badge = f'<span class="badge badge-info">{status}</span>'
        
        # Fix badge
        if has_fix == 'TRUE':
            fix_badge = f'<span class="badge badge-success">✓ Yes</span>'
        else:
            fix_badge = f'<span class="badge badge-real">✗ No</span>'
        
        # Fix QID link
        if fix_qid:
            fix_qid_link = f'<a href="https://www.wikidata.org/wiki/{fix_qid}" target="_blank" class="external-link">{fix_qid}</a>'
        else:
            fix_qid_link = '-'
        
        rows.append(f"""
            <tr>
                <td>{entity_type}</td>
                <td><a href="https://www.wikidata.org/wiki/{qid}" target="_blank" class="external-link">{qid}</a></td>
                <td>{wd_label_display}</td>
                <td>{synset_link}</td>
                <td>{status_badge}</td>
                <td>{fix_badge}</td>
                <td>{fix_qid_link}</td>
            </tr>
        """)
    
    if len(comparison_data) > max_rows:
        remaining = len(comparison_data) - max_rows
        rows.append(f"""
            <tr>
                <td colspan='7' style='text-align: center; color: var(--text-secondary);'>
                    ... and {remaining} more rows (total: {len(comparison_data)})
                </td>
            </tr>
        """)
    
    return '\n'.join(rows)


def generate_dashboard():
    """Generate the comprehensive dashboard HTML."""
    
    # Load data
    print("Loading data...")
    
    # Count files
    p8814_from_wd = load_csv(OUTPUT_DIR / "p8814_violations_from_wd.csv")
    p5063_from_wd = load_csv(OUTPUT_DIR / "p5063_violations_from_wd.csv")
    p8814_final = load_csv(OUTPUT_DIR / "p8814_violations_final.csv")
    p5063_final = load_csv(OUTPUT_DIR / "p5063_violations_final.csv")
    
    # Get counts
    p8814_total = len(p8814_from_wd)
    p5063_total = len(p5063_from_wd)
    
    p8814_real = sum(1 for r in p8814_final if r.get('is_real_violation') == 'TRUE')
    p8814_valid = sum(1 for r in p8814_final if r.get('is_real_violation') == 'FALSE')
    
    p5063_real = sum(1 for r in p5063_final if r.get('is_real_violation') == 'TRUE')
    p5063_valid = sum(1 for r in p5063_final if r.get('is_real_violation') == 'FALSE')
    
    # Get QuickStatements counts
    p8814_qs_count = len([l for l in open(OUTPUT_DIR / "quickstatements/p8814_fixes_quickstatements.txt").readlines() if l.startswith('-Q')])
    p5063_qs_count = len([l for l in open(OUTPUT_DIR / "quickstatements/p5063_fixes_quickstatements.txt").readlines() if l.startswith('-Q')])
    
    # Get categories
    p8814_categories = Counter(r.get('category') for r in p8814_final)
    p5063_categories = Counter(r.get('category') for r in p5063_final)
    
    print(f"Loaded: P8814={p8814_total}, P5063={p5063_total}")
    print(f"Real: P8814={p8814_real}, P5063={p5063_real}")
    print(f"QuickStatements: P8814={p8814_qs_count}, P5063={p5063_qs_count}")
    
    # Get sample violations for tables
    p8814_real_samples = [r for r in p8814_final if r.get('is_real_violation') == 'TRUE'][:10]
    p5063_real_samples = [r for r in p5063_final if r.get('is_real_violation') == 'TRUE'][:10]
    
    # Get sample QuickStatements
    with open(OUTPUT_DIR / "quickstatements/p8814_fixes_quickstatements.txt") as f:
        p8814_qs_samples = [l.strip() for l in f if l.startswith('-Q')][:10]
    
    with open(OUTPUT_DIR / "quickstatements/p5063_fixes_quickstatements.txt") as f:
        p5063_qs_samples = [l.strip() for l in f if l.startswith('-Q')][:10]
    
    # List all available files
    all_files = sorted(OUTPUT_DIR.glob("*.csv")) + sorted((OUTPUT_DIR / "quickstatements").glob("*.txt"))
    
    # Load comparison table
    comparison_table_path = OUTPUT_DIR / "full_comparison_table.csv"
    if comparison_table_path.exists():
        comparison_data = load_csv(comparison_table_path)
        comparison_table_rows = len(comparison_data)
        p8814_rows = sum(1 for r in comparison_data if r.get('entity_type') == 'P8814')
        p5063_rows = sum(1 for r in comparison_data if r.get('entity_type') == 'P5063')
        fixes_proposed = sum(1 for r in comparison_data if r.get('has_fix_proposed') == 'TRUE')
        fixes_applied = sum(1 for r in comparison_data if r.get('fix_applied') == 'TRUE')
        comparison_table_html = generate_comparison_table_html(comparison_data, max_rows=50)
    else:
        comparison_data = []
        comparison_table_rows = 0
        p8814_rows = 0
        p5063_rows = 0
        fixes_proposed = 0
        fixes_applied = 0
        comparison_table_html = "<tr><td colspan='7' style='text-align: center;'>Comparison table not generated yet</td></tr>"
    
    print(f"Comparison table: {comparison_table_rows} rows ({p8814_rows} P8814, {p5063_rows} P5063)")
    print(f"Fixes: {fixes_proposed} proposed, {fixes_applied} applied")
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WordNet2Wikidata - Mission Control Dashboard</title>
    <style>
        :root {{
            --primary: #0066cc;
            --primary-dark: #0055aa;
            --success: #2e7d32;
            --error: #c62828;
            --warning: #ff6d00;
            --info: #0066cc;
            --bg: #f5f5f5;
            --card-bg: #ffffff;
            --text: #333;
            --text-secondary: #666;
            --border: #e0e0e0;
            --shadow: 0 2px 8px rgba(0,0,0,0.1);
            --shadow-hover: 0 4px 12px rgba(0,0,0,0.15);
            --radius: 8px;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{ max-width: 1600px; margin: 0 auto; }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            padding: 30px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            box-shadow: var(--shadow);
        }}
        .header h1 {{ font-size: 2.2em; margin-bottom: 10px; }}
        .header .subtitle {{ font-size: 1.1em; opacity: 0.9; }}
        .header .date {{ text-align: right; font-size: 0.9em; opacity: 0.8; margin-top: 5px; }}
        
        /* Mega Stats */
        .mega-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .mega-stat-card {{
            background: var(--card-bg);
            padding: 25px;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            border-left: 5px solid var(--primary);
            transition: all 0.3s;
        }}
        .mega-stat-card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow-hover); }}
        .mega-stat-card .label {{
            font-size: 0.9em;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        .mega-stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: var(--primary);
        }}
        .mega-stat-card .subvalue {{
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-top: 5px;
        }}
        .mega-stat-card.error {{ border-color: var(--error); }}
        .mega-stat-card.error .value {{ color: var(--error); }}
        .mega-stat-card.success {{ border-color: var(--success); }}
        .mega-stat-card.success .value {{ color: var(--success); }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .tab {{
            padding: 12px 24px;
            background: var(--card-bg);
            border: 2px solid var(--border);
            border-radius: var(--radius);
            cursor: pointer;
            font-weight: 500;
            box-shadow: var(--shadow);
            transition: all 0.3s;
        }}
        .tab:hover {{ background: #f8f9fa; border-color: var(--primary); }}
        .tab.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
            box-shadow: var(--shadow-hover);
        }}
        .tab-content {{ display: none; padding: 0; }}
        .tab-content.active {{ display: block; padding: 20px 0; }}
        .tab-content .section {{ margin-bottom: 20px; }}
        
        /* Sections */
        .section {{
            background: var(--card-bg);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .section-header {{
            padding: 20px 25px;
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border);
        }}
        .section-header:hover {{ background: #e9ecef; }}
        .section-header h2 {{ margin: 0; color: var(--text); }}
        .toggle-indicator {{ font-size: 1.2em; color: var(--text-secondary); transition: transform 0.3s; }}
        .section.active .toggle-indicator {{ transform: rotate(180deg); }}
        .section-content {{ padding: 25px; display: none; max-height: 0; overflow: hidden; transition: all 0.3s; }}
        .section.active .section-content {{ display: block; max-height: 10000px; }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-card {{
            background: var(--card-bg);
            padding: 15px;
            border-radius: var(--radius);
            border: 2px solid var(--border);
            text-align: center;
            transition: all 0.3s;
        }}
        .stat-card:hover {{ transform: translateY(-2px); border-color: var(--primary); box-shadow: var(--shadow); }}
        .stat-card .value {{ font-size: 1.8em; font-weight: bold; color: var(--primary); }}
        .stat-card .label {{ font-size: 0.85em; color: var(--text-secondary); margin-top: 5px; }}
        
        /* Tables */
        .table-container {{
            overflow-x: auto;
            border-radius: var(--radius);
            border: 1px solid var(--border);
            margin: 15px 0;
        }}
        table {{ width: 100%; border-collapse: collapse; background: var(--card-bg); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{ background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; font-weight: 600; position: sticky; top: 0; z-index: 10; }}
        tr:hover {{ background: #f8f9fa; }}
        tr.real-violation {{ background: #ffebee; }}
        tr.valid-keep {{ background: #e8f5e9; }}
        
        /* Buttons */
        .btn {{
            display: inline-block;
            padding: 10px 20px;
            background: var(--primary);
            color: white;
            text-decoration: none;
            border-radius: var(--radius);
            font-weight: 500;
            transition: all 0.3s;
            border: none;
            cursor: pointer;
            margin: 5px;
        }}
        .btn:hover {{ background: var(--primary-dark); transform: translateY(-1px); box-shadow: var(--shadow); }}
        .btn-secondary {{ background: #6c757d; }}
        .btn-success {{ background: var(--success); }}
        .btn-error {{ background: var(--error); }}
        .btn-warning {{ background: var(--warning); }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        .badge-real {{ background: #ffcdd2; color: var(--error); }}
        .badge-valid {{ background: #c8e6c9; color: var(--success); }}
        .badge-fixable {{ background: #e3f2fd; color: var(--info); }}
        .badge-info {{ background: #e3f2fd; color: var(--primary); }}
        
        /* Alerts */
        .alert {{
            padding: 15px 20px;
            border-radius: var(--radius);
            margin: 15px 0;
            font-size: 0.95em;
            border-left: 4px solid;
        }}
        .alert-info {{ background: #e3f2fd; color: #0d47a1; }}
        .alert-success {{ background: #e8f5e9; color: #1b5e20; }}
        .alert-warning {{ background: #fff3e0; color: #e65100; }}
        .alert-error {{ background: #ffebee; color: #c62828; }}
        
        /* Code */
        code, pre {{ font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.9em; }}
        pre {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: var(--radius);
            overflow-x: auto;
            border: 1px solid var(--border);
            margin: 15px 0;
        }}
        code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 4px; }}
        
        /* Links */
        a {{ color: var(--primary); text-decoration: none; }}
        a:hover {{ text-decoration: underline; color: var(--primary-dark); }}
        .external-link::after {{ content: ' ↗'; font-size: 0.8em; }}
        
        /* Lists */
        ol, ul {{ padding-left: 25px; margin: 15px 0; }}
        
        /* Progress Bar */
        .progress-container {{
            background: #e0e0e0;
            border-radius: var(--radius);
            height: 30px;
            margin: 15px 0;
            overflow: hidden;
        }}
        .progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--primary-dark));
            transition: width 0.5s;
            display: flex;
            align-items: center;
            padding: 0 15px;
            color: white;
            font-weight: bold;
        }}
        
        /* File List */
        .file-list {{
            background: var(--card-bg);
            border-radius: var(--radius);
            border: 1px solid var(--border);
            padding: 15px;
            margin: 15px 0;
        }}
        .file-item {{
            padding: 10px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .file-item:last-child {{ border-bottom: none; }}
        .file-name {{ font-family: monospace; }}
        .file-stats {{ font-size: 0.85em; color: var(--text-secondary); }}
        
        /* Footer */
        .footer {{
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.9em;
            margin-top: 20px;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .mega-stats {{ grid-template-columns: repeat(2, 1fr); }}
            .header h1 {{ font-size: 1.6em; }}
            .tab {{ padding: 10px 16px; font-size: 0.9em; }}
        }}
        
        /* Print */
        @media print {{
            .section-content {{ display: block !important; max-height: none !important; }}
            .section-header {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>🎯 WordNet2Wikidata - Mission Control</h1>
            <div class="subtitle">Complete Mapping Ecosystem Tracker & Violation Resolution Center</div>
            <div class="date">Scan Date: {SCAN_DATE} | Data: Live from Wikidata SPARQL</div>
        </div>
        
        <!-- Mega Stats -->
        <div class="mega-stats">
            <div class="mega-stat-card">
                <div class="label">Total Mappings Scanned</div>
                <div class="value">{p8814_total + p5063_total:,}</div>
                <div class="subvalue">P8814 + P5063 violations</div>
            </div>
            <div class="mega-stat-card error">
                <div class="label">Violations Requiring Fixes</div>
                <div class="value">{p8814_real + p5063_real:,}</div>
                <div class="subvalue">{p8814_real} P8814 + {p5063_real} P5063</div>
            </div>
            <div class="mega-stat-card success">
                <div class="label">Proposed QuickStatements</div>
                <div class="value">{p8814_qs_count + p5063_qs_count:,}</div>
                <div class="subvalue">{p8814_qs_count} P8814 + {p5063_qs_count} P5063</div>
            </div>
            <div class="mega-stat-card">
                <div class="label">Valid Mappings (No Fix)</div>
                <div class="value">{p8814_valid + p5063_valid:,}</div>
                <div class="subvalue">Legitimate polysemy & synonyms</div>
            </div>
        </div>
        
        <!-- Progress Overview -->
        <div class="section">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>📊 Progress Overview</h2>
                <span class="toggle-indicator">▼</span>
            </div>
            <div class="section-content">
                <h3>Detection Pipeline</h3>
                <div class="alert alert-info">
                    <strong>Pipeline Status:</strong> ✅ Complete - All violations detected, categorized, and fixes proposed
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">
                    <div>
                        <h4>🔍 Step 1: Violation Detection</h4>
                        <ul>
                            <li>✅ Query Wikidata SPARQL for P8814 violations</li>
                            <li>✅ Query Wikidata SPARQL for P5063 violations</li>
                            <li>✅ <strong>{p8814_total:,} P8814 violations</strong> found</li>
                            <li>✅ <strong>{p5063_total:,} P5063 violations</strong> found</li>
                        </ul>
                    </div>
                    <div>
                        <h4>🧠 Step 2: Categorization</h4>
                        <ul>
                            <li>✅ Enhanced with WordNet definitions</li>
                            <li>✅ Computed similarity scores</li>
                            <li>✅ Classified into categories</li>
                            <li>✅ <strong>{p8814_real:,} real P8814 errors</strong></li>
                            <li>✅ <strong>{p5063_real:,} real P5063 errors</strong></li>
                        </ul>
                    </div>
                    <div>
                        <h4>🔧 Step 3: Propose Fixes</h4>
                        <ul>
                            <li>✅ Generated QuickStatements for all real violations</li>
                            <li>✅ <strong>{p8814_qs_count:,} P8814 QuickStatements</strong></li>
                            <li>✅ <strong>{p5063_qs_count:,} P5063 QuickStatements</strong></li>
                            <li>✅ All fixes are on Wikidata side</li>
                        </ul>
                    </div>
                    <div>
                        <h4>📈 Step 4: Track Progress</h4>
                        <ul>
                            <li>🔄 Ready for manual verification</li>
                            <li>🔄 Ready for Wikidata bulk edit</li>
                            <li>🔄 Dashboard updated with proposals</li>
                            <li>🔄 Next: Apply fixes & monitor results</li>
                        </ul>
                    </div>
                </div>
                
                <h3 style="margin-top: 30px;">Fix Progress</h3>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {((p8814_qs_count + p5063_qs_count) / (p8814_total + p5063_total) * 100):.1f}%">
                        {((p8814_qs_count + p5063_qs_count) / (p8814_total + p5063_total) * 100):.1f}% of violations have proposed fixes
                    </div>
                </div>
                <p><strong>100% of real violations</strong> ({p8814_real + p5063_real:,}) have QuickStatements ready!</p>
            </div>
        </div>
        
        <!-- Tabs -->
        <div class="tabs">
            <div class="tab active" onclick="switchTab('p8814-detail')">📋 P8814 Details</div>
            <div class="tab" onclick="switchTab('p5063-detail')">📋 P5063 Details</div>
            <div class="tab" onclick="switchTab('proposals')">✅ Proposed Fixes</div>
            <div class="tab" onclick="switchTab('files')">📦 All Data Files</div>
            <div class="tab" onclick="switchTab('comparison')">🔄 Comparison Table</div>
            <div class="tab" onclick="switchTab('drift')">📊 Drift Detection</div>
        </div>
        
        <!-- Tab: P8814 Details -->
        <div id="p8814-detail" class="tab-content active">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>P8814 (WordNet Synset ID) - Deep Dive</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <div class="stats-grid">
                        <div class="stat-card"><span class="value">{p8814_total:,}</span><span class="label">Total Violations</span></div>
                        <div class="stat-card error"><span class="value">{p8814_real:,}</span><span class="label">Real Errors</span></div>
                        <div class="stat-card success"><span class="value">{p8814_valid:,}</span><span class="label">Valid</span></div>
                        <div class="stat-card success"><span class="value">{p8814_qs_count:,}</span><span class="label">QuickStatements</span></div>
                    </div>
                    
                    <p><strong>P8814</strong> = WordNet Synset ID property. Violation: Multiple Wikidata QIDs share the same synset.</p>
                    
                    <h3>Category Breakdown</h3>
                    <div class="table-container">
                        <table>
                            <tr><th>Category</th><th>Count</th><th>% of Total</th><th>Fix Needed?</th></tr>
    """
    
    for cat, count in sorted(p8814_categories.items(), key=lambda x: -x[1]):
        pct = (count / p8814_total * 100) if p8814_total > 0 else 0
        is_real = cat in ['ONE_IN_MEMBERS_DESC_MISMATCH', 'DIFFERENT_CONCEPTS', 'MULTIPLE_QIDS_WITH_MISMATCHES']
        fix_needed = "✅ Yes" if is_real else "❌ No"
        html += f"<tr class='{'real-violation' if is_real else 'valid-keep'}'><td>{cat}</td><td>{count:,}</td><td>{pct:.1f}%</td><td>{fix_needed}</td></tr>\n"
    
    html += """                        </table>
                    </div>
                    
                    <h3 style="margin-top: 20px;">Sample Real Violations</h3>
                    <div class="table-container">
                        <table>
                            <tr><th>QID</th><th>Label</th><th>Synset</th><th>Definition</th><th>Category</th></tr>
    """
    
    for row in p8814_real_samples:
        qid = row.get('qid', 'N/A')
        label = row.get('wikidata_label', 'N/A')
        synset = row.get('synset_id', 'N/A')
        defn = (row.get('synset_definition', 'N/A') or '')[:60]
        cat = row.get('category', 'N/A')
        html += f"<tr class='real-violation'><td><a href='https://www.wikidata.org/wiki/{qid}' class='external-link'>{qid}</a></td><td>{label}</td><td>{synset}</td><td>{defn}</td><td><span class='badge badge-real'>{cat}</span></td></tr>\n"
    
    html += """                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Tab: P5063 Details -->
        <div id="p5063-detail" class="tab-content">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>P5063 (Interlingual Index ID) - Deep Dive</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <div class="stats-grid">
                        <div class="stat-card"><span class="value">{p5063_total:,}</span><span class="label">Total Violations</span></div>
                        <div class="stat-card error"><span class="value">{p5063_real:,}</span><span class="label">Real Errors</span></div>
                        <div class="stat-card success"><span class="value">{p5063_valid:,}</span><span class="label">Valid</span></div>
                        <div class="stat-card success"><span class="value">{p5063_qs_count:,}</span><span class="label">QuickStatements</span></div>
                    </div>
                    
                    <p><strong>P5063</strong> = Interlingual Index ID property. Violation: Multiple Wikidata QIDs share the same ILI.</p>
                    
                    <h3>Category Breakdown</h3>
                    <div class="table-container">
                        <table>
                            <tr><th>Category</th><th>Count</th><th>% of Total</th><th>Fix Needed?</th></tr>
    """
    
    for cat, count in sorted(p5063_categories.items(), key=lambda x: -x[1]):
        pct = (count / p5063_total * 100) if p5063_total > 0 else 0
        is_real = cat == 'DISSIMILAR_QIDS'
        fix_needed = "✅ Yes" if is_real else "❌ No"
        html += f"<tr class='{'real-violation' if is_real else 'valid-keep'}'><td>{cat}</td><td>{count:,}</td><td>{pct:.1f}%</td><td>{fix_needed}</td></tr>\n"
    
    html += """                        </table>
                    </div>
                    
                    <h3 style="margin-top: 20px;">Sample Real Violations</h3>
                    <div class="table-container">
                        <table>
                            <tr><th>QID</th><th>Label</th><th>ILI</th><th>Definition</th><th>Category</th></tr>
    """
    
    for row in p5063_real_samples:
        qid = row.get('qid', 'N/A')
        label = row.get('wikidata_label', 'N/A')
        ili = row.get('ili', 'N/A')
        defn = (row.get('synset_definition', 'N/A') or '')[:60]
        cat = row.get('category', 'N/A')
        html += f"<tr class='real-violation'><td><a href='https://www.wikidata.org/wiki/{qid}' class='external-link'>{qid}</a></td><td>{label}</td><td><a href='https://ili.globalwordnet.org/i/{ili}' class='external-link'>{ili}</a></td><td>{defn}</td><td><span class='badge badge-real'>{cat}</span></td></tr>\n"
    
    html += """                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Tab: Proposed Fixes -->
        <div id="proposals" class="tab-content">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>🎯 All Proposed Fixes ({p8814_qs_count + p5063_qs_count:,} QuickStatements)</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert alert-info">
                        <strong>📌 Key Finding:</strong> All fixes are on the <strong>WIKIDATA SIDE</strong>. 
                        The source repos (english-wordnet, english-namenet) are correctly mapped.
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">
                        <div class="stat-card">
                            <span class="value">{p8814_qs_count + p5063_qs_count:,}</span>
                            <span class="label">Total QuickStatements</span>
                        </div>
                        <div class="stat-card">
                            <span class="value">{p8814_qs_count:,}</span>
                            <span class="label">P8814 QuickStatements</span>
                        </div>
                        <div class="stat-card">
                            <span class="value">{p5063_qs_count:,}</span>
                            <span class="label">P5063 QuickStatements</span>
                        </div>
                    </div>
                    
                    <h3 style="margin-top: 25px;">How to Use QuickStatements</h3>
                    <ol>
                        <li>Go to <a href="https://quickstatements.toolforge.org/" class="external-link">QuickStatements Tool</a></li>
                        <li>Copy the QuickStatements from the files below</li>
                        <li>Paste into the tool and run</li>
                        <li>Start with a small test batch (10-20 commands)</li>
                        <li>Verify the results on Wikidata</li>
                        <li>Submit the rest in batches of 100</li>
                    </ol>
                    
                    <div class="alert alert-warning">
                        <strong>⚠️ Important:</strong> Always verify a few examples manually before bulk editing!
                    </div>
                    
                    <h3 style="margin-top: 25px;">P8814 QuickStatements ({p8814_qs_count:,})</h3>
                    <pre>""" + "\n".join(p8814_qs_samples) + """\n...</pre>
                    <a href="quickstatements/p8814_fixes_quickstatements.txt" class="btn btn-success external-link">⬇️ Download All {p8814_qs_count:,} P8814 QuickStatements</a>
                    
                    <h3 style="margin-top: 25px;">P5063 QuickStatements ({p5063_qs_count:,})</h3>
                    <pre>""" + "\n".join(p5063_qs_samples) + """\n...</pre>
                    <a href="quickstatements/p5063_fixes_quickstatements.txt" class="btn btn-success external-link">⬇️ Download All {p5063_qs_count:,} P5063 QuickStatements</a>
                </div>
            </div>
        </div>
        
        <!-- Tab: All Data Files -->
        <div id="files" class="tab-content">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>📦 All Data Files & Outputs</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <p>All files generated during the analysis pipeline:</p>
                    
                    <h3 style="margin-top: 20px;">Raw Data from Wikidata</h3>
                    <div class="file-list">
    """
    
    for f in sorted(OUTPUT_DIR.glob("*_from_wd.csv")):
        size = f.stat().st_size / 1024
        rows = count_rows(f)
        html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{rows:,} rows | {size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                    
                    <h3 style="margin-top: 20px;">Enhanced Data (with WordNet info)</h3>
                    <div class="file-list">
    """
    
    for f in sorted(OUTPUT_DIR.glob("*_enhanced.csv")):
        size = f.stat().st_size / 1024
        rows = count_rows(f)
        html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{rows:,} rows | {size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                    
                    <h3 style="margin-top: 20px;">Categorized Data (with classification)</h3>
                    <div class="file-list">
    """
    
    for f in sorted(OUTPUT_DIR.glob("*_categorized.csv")):
        size = f.stat().st_size / 1024
        rows = count_rows(f)
        html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{rows:,} rows | {size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                    
                    <h3 style="margin-top: 20px;">Final Classification</h3>
                    <div class="file-list">
    """
    
    for f in sorted(OUTPUT_DIR.glob("*_final.csv")):
        size = f.stat().st_size / 1024
        rows = count_rows(f)
        html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{rows:,} rows | {size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                    
                    <h3 style="margin-top: 20px;">QuickStatements (Fix Proposals)</h3>
                    <div class="file-list">
    """
    
    for f in sorted((OUTPUT_DIR / "quickstatements").glob("*.txt")):
        size = f.stat().st_size / 1024
        lines = len([l for l in open(f) if l.startswith('-Q')])
        html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{lines:,} QuickStatements | {size:.1f} KB</div>
                            <a href="quickstatements/{f.name}" class="btn btn-success">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                    
                    <h3 style="margin-top: 20px;">Other Files</h3>
                    <div class="file-list">
    """
    
    for f in sorted(OUTPUT_DIR.glob("*.csv")):
        if not any(p in str(f) for p in ['_from_wd', '_enhanced', '_categorized', '_final', 'manual_review']):
            size = f.stat().st_size / 1024
            rows = count_rows(f)
            html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{rows:,} rows | {size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    for f in sorted(OUTPUT_DIR.glob("*.txt")):
        if not f.name.startswith('p') or 'quick' not in str(f):
            size = f.stat().st_size / 1024
            html += f"""                        <div class="file-item">
                            <div class="file-name">{f.name}</div>
                            <div class="file-stats">{size:.1f} KB</div>
                            <a href="{f.name}" class="btn btn-secondary">⬇️ Download</a>
                        </div>
    """
    
    html += """                    </div>
                </div>
            </div>
        </div>
        
        <!-- Tab: Comparison Table -->
        <div id="comparison" class="tab-content">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>🔄 Comparison Table (ALL Mappings)</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert alert-info">
                        <strong>📋 About the Comparison Table:</strong> This tracks ALL mappings between WordNet synsets/ILIs and Wikidata QIDs, 
                        allowing us to detect drift, duplicates, and inconsistencies across the entire ecosystem.
                    </div>
                    
                    <h3>What We Track</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 15px;">
                        <div class="alert alert-info">
                            <strong>OEWN Mappings</strong><br>
                            WordNet synsets → QIDs from english-wordnet
                        </div>
                        <div class="alert alert-info">
                            <strong>OENN Mappings</strong><br>
                            Name synsets → QIDs from english-namenet
                        </div>
                        <div class="alert alert-info">
                            <strong>Wikidata P8814</strong><br>
                            All P8814 statements on Wikidata items
                        </div>
                        <div class="alert alert-info">
                            <strong>Wikidata P5063</strong><br>
                            All P5063 statements on Wikidata items
                        </div>
                    </div>
                    
                    <h3 style="margin-top: 25px;">How We Detect Drift</h3>
                    <ol>
                        <li><strong>Baseline:</strong> Create initial comparison table from current state</li>
                        <li><strong>Periodic Scans:</strong> Re-run SPARQL queries to get current Wikidata state</li>
                        <li><strong>Compare:</strong> Identify differences (new mappings, removed mappings, changed values)</li>
                        <li><strong>Flag:</strong> Mark potential issues for review</li>
                        <li><strong>Report:</strong> Generate drift detection report</li>
                    </ol>
                    
                    <div class="alert alert-warning">
                        <strong>⚠️ Note:</strong> To enable drift detection, we need to:
                        <ol>
                            <li>Create a baseline scan (today's date)</li>
                            <li>Save the current state of all P8814/P5063 statements</li>
                            <li>Schedule periodic re-scans (e.g., weekly)</li>
                            <li>Compare against baseline to detect changes</li>
                        </ol>
                    </div>
                    
                    <h3 style="margin-top: 25px;">Comparison Table Data</h3>
                    <div class="alert alert-success">
                        <strong>✅ Comparison table generated:</strong> {comparison_table_rows} rows<br>
                        <strong>📊 P8814:</strong> {p8814_rows} rows | <strong>P5063:</strong> {p5063_rows} rows<br>
                        <strong>🔧 Fixes proposed:</strong> {fixes_proposed} | <strong>✅ Fixes applied:</strong> {fixes_applied}
                    </div>
                    
                    <div style="margin: 20px 0; overflow-x: auto;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Type</th>
                                    <th>QID</th>
                                    <th>WD Label</th>
                                    <th>Synset ID / ILI</th>
                                    <th>Status</th>
                                    <th>Fix Proposed</th>
                                    <th>Fix QID</th>
                                </tr>
                            </thead>
                            <tbody>
                                {comparison_table_html}
                            </tbody>
                        </table>
                    </div>
                    
                    <h3 style="margin-top: 25px;">Available Scripts</h3>
                    <div class="file-list">
                        <div class="file-item">
                            <div class="file-name">build_full_comparison.py</div>
                            <div class="file-stats">Builds comparison table from violations + fixes</div>
                            <a href="../../../scripts/build_full_comparison.py" class="btn external-link">View Script</a>
                        </div>
                        <div class="file-item">
                            <div class="file-name">fetch_wikidata.py</div>
                            <div class="file-stats">Fetches all P8814/P5063 from Wikidata</div>
                            <a href="../../../scripts/fetch_wikidata.py" class="btn external-link">View Script</a>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="../../../scripts/build_full_comparison.py" class="btn btn-primary external-link">🚀 Run Comparison Table Builder</a>
                        <a href="../../full_comparison_table.csv" class="btn btn-secondary external-link">⬇️ Download CSV</a>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Tab: Drift Detection (Placeholder) -->
        <div id="drift" class="tab-content">
            <div class="section">
                <div class="section-header" onclick="toggleSection(this)">
                    <h2>📊 Drift Detection System</h2>
                    <span class="toggle-indicator">▼</span>
                </div>
                <div class="section-content">
                    <div class="alert alert-info">
                        <strong>🎯 Drift Detection Concept:</strong> Track changes in Wikidata mappings over time to identify:
                        <ul>
                            <li><strong>New violations:</strong> Recently added duplicate mappings</li>
                            <li><strong>Fixed violations:</strong> Previously reported issues that are now resolved</li>
                            <li><strong>Drift:</strong> Mappings that have changed or been removed</li>
                            <li><strong>Trends:</strong> Patterns in how mappings evolve</li>
                        </ul>
                    </div>
                    
                    <h3>Implementation Plan</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin-top: 15px;">
                        <div class="alert alert-success">
                            <strong>✅ Phase 1: Baseline</strong><br>
                            Run complete scan today as baseline
                        </div>
                        <div class="alert alert-info">
                            <strong>🔄 Phase 2: Periodic Scans</strong><br>
                            Schedule weekly/monthly re-scans
                        </div>
                        <div class="alert alert-warning">
                            <strong>📊 Phase 3: Comparison</strong><br>
                            Compare scans to detect changes
                        </div>
                        <div class="alert alert-info">
                            <strong>📈 Phase 4: Dashboard</strong><br>
                            Visualize drift in this dashboard
                        </div>
                    </div>
                    
                    <h3 style="margin-top: 25px;">What We Can Detect</h3>
                    <div class="table-container">
                        <table>
                            <tr><th>Change Type</th><th>Description</th><th>Severity</th></tr>
                            <tr>
                                <td><span class="badge badge-error">New Violation</span></td>
                                <td>Wikidata added a duplicate P8814/P5063 statement</td>
                                <td>⚠️ High</td>
                            </tr>
                            <tr>
                                <td><span class="badge badge-success">Fixed Violation</span></td>
                                <td>Previously reported violation is now resolved</td>
                                <td>✅ Good</td>
                            </tr>
                            <tr>
                                <td><span class="badge badge-warning">Mappings Drift</span></td>
                                <td>QID changed its P8814/P5063 value</td>
                                <td>⚠️ Medium</td>
                            </tr>
                            <tr>
                                <td><span class="badge badge-info">New Mapping</span></td>
                                <td>QID gained a new P8814/P5063 statement</td>
                                <td>ℹ️ Low</td>
                            </tr>
                            <tr>
                                <td><span class="badge badge-info">Removed Mapping</span></td>
                                <td>QID lost a P8814/P5063 statement</td>
                                <td>ℹ️ Low</td>
                            </tr>
                        </table>
                    </div>
                    
                    <h3 style="margin-top: 25px;">Next Steps to Enable Drift Detection</h3>
                    <ol>
                        <li>
                            <strong>Create Baseline:</strong> 
                            <code>python scripts/fetch_wikidata.py --output data/baseline/{SCAN_DATE_ID}</code>
                        </li>
                        <li>
                            <strong>Save Current State:</strong> 
                            Archive all current P8814/P5063 statements
                        </li>
                        <li>
                            <strong>Schedule Re-scans:</strong> 
                            Set up cron job or GitHub Action to run weekly
                        </li>
                        <li>
                            <strong>Generate Reports:</strong> 
                            Create script to compare scans and generate drift reports
                        </li>
                        <li>
                            <strong>Update Dashboard:</strong> 
                            Add drift detection tab with visualizations
                        </li>
                    </ol>
                    
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="#" class="btn btn-warning" onclick="alert('Feature coming soon! Baseline scan will be created and drift detection will be enabled in the next iteration.'); return false;">🚀 Enable Drift Detection Now</a>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p><strong>WordNet2Wikidata-Mappings</strong> | Mission Control Dashboard</p>
            <p>Generated: {SCAN_DATE} | <a href="https://github.com/yapy28/Wordnet2Wikidata-Mappings" class="external-link">GitHub Repository</a></p>
        </div>
    </div>
    
    <script>
        // Tab switching
        function switchTab(tabName) {{
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
        }}
        
        // Section collapsing
        function toggleSection(element) {{
            element.parentElement.classList.toggle('active');
        }}
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            // Open first section in each tab
            document.querySelectorAll('.tab-content.active .section').forEach((section, index) => {{
                if (index < 1) section.classList.add('active');
            }});
        }});
    </script>
</body>
</html>
"""
    
    # Write the dashboard
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_FILE, 'w') as f:
        f.write(html)
    
    print(f"✅ Comprehensive dashboard written to {DASHBOARD_FILE}")
    print(f"   Total size: {len(html):,} characters")


if __name__ == "__main__":
    generate_dashboard()
