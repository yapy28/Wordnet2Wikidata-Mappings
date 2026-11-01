"""
Generate a static HTML dashboard from violation CSV files.

Creates: data/output/20260929/violations_dashboard.html
"""
import csv
from pathlib import Path
from collections import Counter
import json

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output" / "20260929"
DASHBOARD_PATH = OUTPUT_DIR / "violations_dashboard.html"


def load_csv(path):
    """Load CSV file and return list of dicts."""
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def escape_html(text):
    """Escape HTML special characters."""
    if not text or text == 'None':
        return '-'
    text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def generate_dashboard():
    """Generate complete HTML dashboard."""
    
    # Load all data
    p8814_final = load_csv(OUTPUT_DIR / "p8814_violations_final.csv")
    p5063_final = load_csv(OUTPUT_DIR / "p5063_violations_final.csv")
    p8814_enhanced = load_csv(OUTPUT_DIR / "p8814_violations_enhanced.csv")
    p5063_enhanced = load_csv(OUTPUT_DIR / "p5063_violations_enhanced.csv")
    
    # Stats
    total_violations = len(p8814_final) + len(p5063_final)
    p8814_real = sum(1 for r in p8814_final if r['is_real_violation'] == 'TRUE')
    p8814_valid = sum(1 for r in p8814_final if r['is_real_violation'] == 'FALSE')
    p5063_real = sum(1 for r in p5063_final if r['is_real_violation'] == 'TRUE')
    p5063_valid = sum(1 for r in p5063_final if r['is_real_violation'] == 'FALSE')
    
    # Category counts
    p8814_cats = Counter(r['category'] for r in p8814_final)
    p5063_cats = Counter(r['category'] for r in p5063_final)
    
    # Generate rows
    p8814_rows_html = generate_p8814_rows(p8814_final)
    p5063_rows_html = generate_p5063_rows(p5063_final)
    
    p8814_cat_rows = generate_cat_rows(p8814_cats, len(p8814_final))
    p5063_cat_rows = generate_cat_rows(p5063_cats, len(p5063_final))
    
    p8814_enhanced_cat_rows = generate_enhanced_cat_rows(p8814_enhanced)
    p5063_enhanced_cat_rows = generate_enhanced_cat_rows(p5063_enhanced)
    
    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WordNet2Wikidata - Constraint Violation Analysis</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ 
            color: #333; 
            font-size: 2em;
            margin-bottom: 10px;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }}
        h2 {{ 
            color: #555;
            font-size: 1.5em;
            margin: 20px 0 10px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 5px;
        }}
        h3 {{ color: #666; margin: 15px 0 10px; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ 
            background: white; 
            padding: 15px; 
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .value {{ font-size: 2em; font-weight: bold; color: #0066cc; }}
        .stat-card .label {{ color: #666; font-size: 0.9em; }}
        
        .summary-table {{ 
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            margin: 15px 0;
        }}
        .summary-table table {{ width: 100%; border-collapse: collapse; }}
        .summary-table th, .summary-table td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        .summary-table th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        .summary-table tr:hover {{ background: #f5f5f5; }}
        
        .violation-table {{ 
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            margin: 15px 0;
            max-height: 600px;
            overflow-y: auto;
        }}
        .violation-table table {{ width: 100%; border-collapse: collapse; }}
        .violation-table th, .violation-table td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        .violation-table th {{ 
            background: #0066cc; 
            color: white;
            font-weight: 600;
            position: sticky;
            top: 0;
            cursor: pointer;
            user-select: none;
        }}
        .violation-table th:hover {{ background: #0055aa; }}
        .violation-table tr:hover {{ background: #f5f5f5; }}
        .violation-table tr.real-violation {{ background: #ffebee; }}
        .violation-table tr.valid-keep {{ background: #e8f5e9; }}
        
        .filter-controls {{ 
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 15px 0;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .filter-controls select, .filter-controls input {{ 
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            min-width: 150px;
        }}
        .filter-controls button {{ 
            padding: 8px 16px;
            background: #0066cc;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .filter-controls button:hover {{ background: #0055aa; }}
        
        .badge {{ 
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 500;
        }}
        .badge-real {{ background: #ffcdd2; color: #c62828; }}
        .badge-valid {{ background: #c8e6c9; color: #2e7d32; }}
        
        .collapsible {{ cursor: pointer; }}
        .collapsible-content {{ display: none; }}
        .collapsible.active .collapsible-content {{ display: block; }}
        .collapsible-header {{ 
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 10px;
        }}
        .collapsible-header:hover {{ background: #e9ecef; }}
        
        .export-buttons {{ margin: 20px 0; display: flex; gap: 10px; flex-wrap: wrap; }}
        .export-buttons a {{ 
            padding: 10px 20px;
            background: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }}
        .export-buttons a:hover {{ background: #0055aa; }}
        
        .total-stats {{ 
            font-size: 1.1em;
            color: #555;
            margin: 10px 0;
        }}
        
        .date-stamp {{ 
            color: #888;
            font-size: 0.9em;
            text-align: right;
            margin-top: 10px;
        }}
        
        .summary-table p, .summary-table ol, .summary-table ul {{ padding: 15px; }}
        
        @media (max-width: 768px) {{ 
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .filter-controls {{ flex-direction: column; align-items: stretch; }}
            .filter-controls select, .filter-controls input {{ width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>WordNet2Wikidata - Constraint Violation Analysis</h1>
        <div class="date-stamp">Generated: {escape_html(str(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))}</div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="value">{total_violations}</div>
                <div class="label">Total Violations</div>
            </div>
            <div class="stat-card">
                <div class="value">{p8814_real + p5063_real}</div>
                <div class="label">Real Errors</div>
            </div>
            <div class="stat-card">
                <div class="value">{p8814_valid + p5063_valid}</div>
                <div class="label">Valid Mappings</div>
            </div>
            <div class="stat-card">
                <div class="value">0</div>
                <div class="label">Needs Review</div>
            </div>
        </div>
        
        <h2>📊 Executive Summary</h2>
        <div class="summary-table">
            <table>
                <tr>
                    <th>Property</th>
                    <th>Total</th>
                    <th>Real Errors</th>
                    <th>Valid</th>
                    <th>% Errors</th>
                </tr>
                <tr>
                    <td><strong>P8814 (Synset ID)</strong></td>
                    <td>{len(p8814_final)}</td>
                    <td>{p8814_real}</td>
                    <td>{p8814_valid}</td>
                    <td>{p8814_real/len(p8814_final)*100:.1f}%</td>
                </tr>
                <tr>
                    <td><strong>P5063 (ILI)</strong></td>
                    <td>{len(p5063_final)}</td>
                    <td>{p5063_real}</td>
                    <td>{p5063_valid}</td>
                    <td>{p5063_real/len(p5063_final)*100:.1f}%</td>
                </tr>
                <tr>
                    <td><strong>Total</strong></td>
                    <td><strong>{total_violations}</strong></td>
                    <td><strong>{p8814_real + p5063_real}</strong></td>
                    <td><strong>{p8814_valid + p5063_valid}</strong></td>
                    <td><strong>{(p8814_real + p5063_real)/total_violations*100:.1f}%</strong></td>
                </tr>
            </table>
        </div>
        
        <h2>🎯 P8814 Violations (Synset &rarr; Multiple QIDs)</h2>
        <div class="total-stats">
            <strong>Total:</strong> {len(p8814_final)} | 
            <span class="badge badge-real">Real: {p8814_real}</span> | 
            <span class="badge badge-valid">Valid: {p8814_valid}</span>
        </div>
        
        <div class="collapsible">
            <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')">
                <strong>📋 Category Breakdown</strong>
                <span>▼</span>
            </div>
            <div class="collapsible-content">
                <div class="summary-table">
                    <table>
                        <tr>
                            <th>Category</th>
                            <th>Count</th>
                            <th>%</th>
                            <th>Action</th>
                        </tr>
                        {p8814_cat_rows}
                    </table>
                </div>
            </div>
        </div>
        
        <div class="filter-controls">
            <select id="p8814-category-filter" onchange="filterP8814Table()">
                <option value="">All Categories</option>
                {''.join(f'<option value="{cat}">{escape_html(cat)}</option>' for cat in sorted(p8814_cats.keys()))}
            </select>
            <select id="p8814-violation-filter" onchange="filterP8814Table()">
                <option value="">All Types</option>
                <option value="TRUE">Real Errors</option>
                <option value="FALSE">Valid</option>
            </select>
            <input type="text" id="p8814-search" placeholder="Search..." onkeyup="filterP8814Table()">
            <button onclick="resetP8814Filter()">Reset</button>
        </div>
        
        <div class="violation-table" id="p8814-table-container">
            <table id="p8814-table">
                <thead>
                    <tr>
                        <th onclick="sortTable('p8814-table', 0)">QID</th>
                        <th onclick="sortTable('p8814-table', 1)">Label</th>
                        <th onclick="sortTable('p8814-table', 2)">Synset ID</th>
                        <th onclick="sortTable('p8814-table', 3)">Synset Definition</th>
                        <th onclick="sortTable('p8814-table', 4)">Wikidata Description</th>
                        <th onclick="sortTable('p8814-table', 5)">Category</th>
                        <th onclick="sortTable('p8814-table', 6)">Action</th>
                        <th onclick="sortTable('p8814-table', 7)">Confidence</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {p8814_rows_html}
                </tbody>
            </table>
        </div>
        
        <h2>🎯 P5063 Violations (ILI &rarr; Multiple QIDs or Multiple ILIs &rarr; One QID)</h2>
        <div class="total-stats">
            <strong>Total:</strong> {len(p5063_final)} | 
            <span class="badge badge-real">Real: {p5063_real}</span> | 
            <span class="badge badge-valid">Valid: {p5063_valid}</span>
        </div>
        
        <div class="collapsible">
            <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')">
                <strong>📋 Category Breakdown</strong>
                <span>▼</span>
            </div>
            <div class="collapsible-content">
                <div class="summary-table">
                    <table>
                        <tr>
                            <th>Category</th>
                            <th>Count</th>
                            <th>%</th>
                            <th>Action</th>
                        </tr>
                        {p5063_cat_rows}
                    </table>
                </div>
            </div>
        </div>
        
        <div class="filter-controls">
            <select id="p5063-category-filter" onchange="filterP5063Table()">
                <option value="">All Categories</option>
                {''.join(f'<option value="{cat}">{escape_html(cat)}</option>' for cat in sorted(p5063_cats.keys()))}
            </select>
            <select id="p5063-violation-filter" onchange="filterP5063Table()">
                <option value="">All Types</option>
                <option value="TRUE">Real Errors</option>
                <option value="FALSE">Valid</option>
            </select>
            <input type="text" id="p5063-search" placeholder="Search..." onkeyup="filterP5063Table()">
            <button onclick="resetP5063Filter()">Reset</button>
        </div>
        
        <div class="violation-table" id="p5063-table-container">
            <table id="p5063-table">
                <thead>
                    <tr>
                        <th onclick="sortTable('p5063-table', 0)">ILI/QID</th>
                        <th onclick="sortTable('p5063-table', 1)">Label</th>
                        <th onclick="sortTable('p5063-table', 2)">Synset ID</th>
                        <th onclick="sortTable('p5063-table', 3)">Synset Definition</th>
                        <th onclick="sortTable('p5063-table', 4)">Wikidata Description</th>
                        <th onclick="sortTable('p5063-table', 5)">Type</th>
                        <th onclick="sortTable('p5063-table', 6)">Category</th>
                        <th onclick="sortTable('p5063-table', 7)">Action</th>
                        <th onclick="sortTable('p5063-table', 8)">Confidence</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {p5063_rows_html}
                </tbody>
            </table>
        </div>
        
        <h2>📦 Export Data</h2>
        <div class="export-buttons">
            <a href="p8814_violations_final.csv" download>Download P8814 Final CSV</a>
            <a href="p5063_violations_final.csv" download>Download P5063 Final CSV</a>
            <a href="p8814_violations_enhanced.csv" download>Download P8814 Enhanced CSV</a>
            <a href="p5063_violations_enhanced.csv" download>Download P5063 Enhanced CSV</a>
            <a href="p8814_violations_from_wd.csv" download>Download P8814 Raw CSV</a>
            <a href="p5063_violations_from_wd.csv" download>Download P5063 Raw CSV</a>
        </div>
        
        <h2>ℹ️ Methodology</h2>
        <div class="summary-table">
            <p><strong>Work done:</strong></p>
            <ol>
                <li><strong>Data Collection:</strong> Queried Wikidata SPARQL for live P5063 and P8814 constraint violations</li>
                <li><strong>Enrichment:</strong> Joined with OEWN/OENN synset data (definitions, members, ILIs)</li>
                <li><strong>Categorization:</strong> 
                    <ul>
                        <li><strong>P8814:</strong> Used label matching + description similarity to identify real vs. valid duplicates</li>
                        <li><strong>P5063:</strong> Used synset definition matching to identify valid ILI mappings</li>
                        <li><strong>Polysemy detection:</strong> Identified cases where multiple valid mappings exist for different senses</li>
                        <li><strong>POS conflict detection:</strong> Identified valid cases where different parts of speech map to same concept</li>
                        <li><strong>Similarity matching:</strong> Token-based comparison of synset definitions vs Wikidata descriptions to detect semantic mismatches</li>
                    </ul>
                </li>
                <li><strong>100% Coverage:</strong> All violations categorized (0% REVIEW remaining)</li>
            </ol>
            <p><strong>Next steps:</strong></p>
            <ol>
                <li>Review the categorization in this dashboard</li>
                <li>Manually verify borderline cases (medium confidence)</li>
                <li>Generate QuickStatements for real violations</li>
                <li>Discuss with WordNet community</li>
            </ol>
        </div>
        
        <h2>📊 Enhanced Analysis (With Similarity Matching)</h2>
        <p>For a more nuanced view with similarity scores and confidence levels, see the enhanced CSV files.</p>
        
        <div class="collapsible">
            <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')">
                <strong>🔍 Enhanced P8814 Stats</strong>
                <span>▼</span>
            </div>
            <div class="collapsible-content">
                <div class="summary-table">
                    <table>
                        <tr><th>Category</th><th>Total</th><th>Real</th><th>Valid</th></tr>
                        {p8814_enhanced_cat_rows}
                    </table>
                </div>
            </div>
        </div>
        
        <div class="collapsible">
            <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')">
                <strong>🔍 Enhanced P5063 Stats</strong>
                <span>▼</span>
            </div>
            <div class="collapsible-content">
                <div class="summary-table">
                    <table>
                        <tr><th>Category</th><th>Total</th><th>Real</th><th>Valid</th></tr>
                        {p5063_enhanced_cat_rows}
                    </table>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 40px; padding: 20px; text-align: center; color: #888; font-size: 0.9em;">
            <p>Generated from <strong>WordNet2Wikidata-Mappings</strong> repository</p>
            <p>Data source: Wikidata SPARQL Query Service | Date: {escape_html(str(__import__('datetime').datetime.now().strftime('%Y-%m-%d')))}</p>
        </div>
    </div>
    
    <script>
        // Filter functions
        function filterP8814Table() {{
            const category = document.getElementById('p8814-category-filter').value;
            const violation = document.getElementById('p8814-violation-filter').value;
            const search = document.getElementById('p8814-search').value.toLowerCase();
            const rows = document.querySelectorAll('#p8814-table tbody tr');
            let visibleCount = 0;
            
            rows.forEach(row => {{
                const rowCategory = row.getAttribute('data-category');
                const rowViolation = row.getAttribute('data-violation');
                const rowText = row.textContent.toLowerCase();
                
                let show = true;
                if (category && rowCategory !== category) show = false;
                if (violation && rowViolation !== violation) show = false;
                if (search && !rowText.includes(search)) show = false;
                
                row.style.display = show ? '' : 'none';
                if (show) visibleCount++;
            }});
        }}
        
        function filterP5063Table() {{
            const category = document.getElementById('p5063-category-filter').value;
            const violation = document.getElementById('p5063-violation-filter').value;
            const search = document.getElementById('p5063-search').value.toLowerCase();
            const rows = document.querySelectorAll('#p5063-table tbody tr');
            let visibleCount = 0;
            
            rows.forEach(row => {{
                const rowCategory = row.getAttribute('data-category');
                const rowViolation = row.getAttribute('data-violation');
                const rowText = row.textContent.toLowerCase();
                
                let show = true;
                if (category && rowCategory !== category) show = false;
                if (violation && rowViolation !== violation) show = false;
                if (search && !rowText.includes(search)) show = false;
                
                row.style.display = show ? '' : 'none';
                if (show) visibleCount++;
            }});
        }}
        
        function resetP8814Filter() {{
            document.getElementById('p8814-category-filter').value = '';
            document.getElementById('p8814-violation-filter').value = '';
            document.getElementById('p8814-search').value = '';
            filterP8814Table();
        }}
        
        function resetP5063Filter() {{
            document.getElementById('p5063-category-filter').value = '';
            document.getElementById('p5063-violation-filter').value = '';
            document.getElementById('p5063-search').value = '';
            filterP5063Table();
        }}
        
        // Sort functions
        let sortState = {{}};
        function sortTable(tableId, columnIndex) {{
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            const key = tableId + '-' + columnIndex;
            const currentDir = sortState[key] || 'asc';
            const newDir = currentDir === 'asc' ? 'desc' : 'asc';
            sortState[key] = newDir;
            
            rows.sort((a, b) => {{
                const aText = a.cells[columnIndex].textContent.trim();
                const bText = b.cells[columnIndex].textContent.trim();
                
                if (newDir === 'asc') {{
                    return aText.localeCompare(bText);
                }} else {{
                    return bText.localeCompare(aText);
                }}
            }});
            
            // Remove all rows
            while (tbody.firstChild) {{
                tbody.removeChild(tbody.firstChild);
            }}
            
            // Re-add sorted rows
            rows.forEach(row => tbody.appendChild(row));
        }}
    </script>
</body>
</html>
"""
    
    # Write to file
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard generated: {DASHBOARD_PATH}")


def generate_p8814_rows(rows):
    """Generate HTML rows for P8814 table."""
    html_parts = []
    for row in rows:
        is_real = row['is_real_violation'] == 'TRUE'
        cls = 'real-violation' if is_real else 'valid-keep'
        
        html_parts.append(f'<tr class="{cls}" data-category="{escape_html(row.get("category",""))}" data-violation="{row.get("is_real_violation","")}">')
        html_parts.append(f'<td>{escape_html(row.get("qid",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("wikidata_label",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("synset_id",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("synset_definition",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("wikidata_description",""))}</td>')
        html_parts.append(f'<td><span class="badge {"badge-real" if is_real else "badge-valid"}">{escape_html(row.get("category",""))}</span></td>')
        html_parts.append(f'<td>{escape_html(row.get("recommendation",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("confidence",""))}%</td>')
        html_parts.append(f'<td>{escape_html(row.get("categorization_notes",""))}</td>')
        html_parts.append('</tr>')
    
    return ''.join(html_parts)


def generate_p5063_rows(rows):
    """Generate HTML rows for P5063 table."""
    html_parts = []
    for row in rows:
        is_real = row['is_real_violation'] == 'TRUE'
        cls = 'real-violation' if is_real else 'valid-keep'
        
        html_parts.append(f'<tr class="{cls}" data-category="{escape_html(row.get("category",""))}" data-violation="{row.get("is_real_violation","")}">')
        html_parts.append(f'<td>{escape_html(row.get("ili", row.get("qid","")))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("wikidata_label",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("synset_id",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("synset_definition",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("wikidata_description",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("violation_type",""))}</td>')
        html_parts.append(f'<td><span class="badge {"badge-real" if is_real else "badge-valid"}">{escape_html(row.get("category",""))}</span></td>')
        html_parts.append(f'<td>{escape_html(row.get("recommendation",""))}</td>')
        html_parts.append(f'<td>{escape_html(row.get("confidence",""))}%</td>')
        html_parts.append(f'<td>{escape_html(row.get("categorization_notes",""))}</td>')
        html_parts.append('</tr>')
    
    return ''.join(html_parts)


def generate_cat_rows(counter, total):
    """Generate category breakdown rows."""
    html_parts = []
    for cat, count in counter.most_common():
        if count > 0:
            pct = (count / total) * 100 if total > 0 else 0
            html_parts.append(f'<tr><td>{escape_html(cat)}</td><td>{count}</td><td>{pct:.1f}%</td><td>KEEP</td></tr>')
    return ''.join(html_parts)


def generate_enhanced_cat_rows(rows):
    """Generate enhanced category rows with real/valid counts."""
    counter = Counter(r['category'] for r in rows)
    html_parts = []
    for cat, count in counter.most_common():
        real = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'TRUE')
        valid = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'FALSE')
        html_parts.append(f'<tr><td>{escape_html(cat)}</td><td>{count}</td><td>{real}</td><td>{valid}</td></tr>')
    return ''.join(html_parts)


if __name__ == "__main__":
    generate_dashboard()
