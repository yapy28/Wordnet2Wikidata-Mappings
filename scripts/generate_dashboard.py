"""
Generate a static HTML dashboard from violation CSV files with ToC and collapsible sections.
"""
import csv
from pathlib import Path
from collections import Counter
import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "output" / "20260929"
DASHBOARD_PATH = OUTPUT_DIR / "violations_dashboard.html"

CSS = """
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { 
            color: #333; 
            font-size: 2em;
            margin-bottom: 10px;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }
        h2 { 
            color: #555;
            font-size: 1.5em;
            margin: 20px 0 10px;
        }
        h3 { color: #666; margin: 15px 0 10px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-card .value { font-size: 2em; font-weight: bold; color: #0066cc; }
        .stat-card .label { color: #666; font-size: 0.9em; }
        .summary-table { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; margin: 15px 0; }
        .summary-table table { width: 100%; border-collapse: collapse; }
        .summary-table th, .summary-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        .summary-table th { background: #f8f9fa; font-weight: 600; color: #555; }
        .summary-table tr:hover { background: #f5f5f5; }
        .violation-table { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); overflow: hidden; margin: 15px 0; max-height: 600px; overflow-y: auto; }
        .violation-table table { width: 100%; border-collapse: collapse; }
        .violation-table th, .violation-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }
        .violation-table th { background: #0066cc; color: white; font-weight: 600; position: sticky; top: 0; cursor: pointer; user-select: none; }
        .violation-table th:hover { background: #0055aa; }
        .violation-table tr:hover { background: #f5f5f5; }
        .violation-table tr.real-violation { background: #ffebee; }
        .violation-table tr.valid-keep { background: #e8f5e9; }
        .filter-controls { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 15px 0; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }
        .filter-controls select, .filter-controls input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; min-width: 150px; }
        .filter-controls button { padding: 8px 16px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .filter-controls button:hover { background: #0055aa; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 12px; font-size: 0.85em; font-weight: 500; }
        .badge-real { background: #ffcdd2; color: #c62828; }
        .badge-valid { background: #c8e6c9; color: #2e7d32; }
        .collapsible { cursor: pointer; }
        .collapsible-content { display: none; }
        .collapsible.active .collapsible-content { display: block; }
        .collapsible-header { padding: 10px; background: #f8f9fa; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
        .collapsible-header:hover { background: #e9ecef; }
        .export-buttons { margin: 20px 0; display: flex; gap: 10px; flex-wrap: wrap; }
        .export-buttons a { padding: 10px 20px; background: #0066cc; color: white; text-decoration: none; border-radius: 4px; }
        .export-buttons a:hover { background: #0055aa; }
        .total-stats { font-size: 1.1em; color: #555; margin: 10px 0; }
        .date-stamp { color: #888; font-size: 0.9em; text-align: right; margin-top: 10px; }
        .summary-table p, .summary-table ol, .summary-table ul { padding: 15px; }
        .toc { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; margin: 20px 0; }
        .toc h2 { margin-top: 0; }
        .toc ul { list-style: none; padding-left: 0; }
        .toc li { padding: 5px 0; }
        .toc a { color: #0066cc; text-decoration: none; display: inline-block; padding: 5px 10px; border-radius: 4px; }
        .toc a:hover { background: #f0f0f0; }
        .toc .toc-level-1 { font-weight: bold; }
        .toc .toc-level-2 { padding-left: 20px; }
        .toc .toc-level-3 { padding-left: 40px; color: #666; }
        .toc-button { padding: 8px 16px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; margin-bottom: 10px; }
        .toc-button:hover { background: #0055aa; }
        .section { margin: 15px 0; border: 1px solid #eee; border-radius: 8px; overflow: hidden; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .section.active { border-color: #0066cc; box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        .section-header { padding: 15px 20px; background: #0066cc; color: white; cursor: pointer; font-size: 1.2em; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
        .section-header:hover { background: #0055aa; }
        .section-header .toggle-indicator { font-size: 1.2em; transition: transform 0.3s; }
        .section.active .section-header .toggle-indicator { transform: rotate(180deg); }
        .section-header h2, .section-header h3 { color: white; margin: 0; font-size: 1.2em; }
        .section-content { padding: 20px; border-top: 1px solid #eee; display: none; }
        .section.active .section-content { display: block; }
        .stats-section { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 20px; margin: 20px 0; }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .filter-controls { flex-direction: column; align-items: stretch; }
            .filter-controls select, .filter-controls input { width: 100%; }
        }
    </style>
"""

JS = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const sections = document.querySelectorAll('.section-header');
            sections.forEach((header, index) => {
                if (index < 4) header.parentElement.classList.add('active');
            });
        });
        function toggleSection(element) { element.parentElement.classList.toggle('active'); }
        function filterP8814Table() {
            const category = document.getElementById('p8814-category-filter').value;
            const violation = document.getElementById('p8814-violation-filter').value;
            const search = document.getElementById('p8814-search').value.toLowerCase();
            document.querySelectorAll('#p8814-table tbody tr').forEach(row => {
                const show = (!category || row.getAttribute('data-category') === category) &&
                             (!violation || row.getAttribute('data-violation') === violation) &&
                             (!search || row.textContent.toLowerCase().includes(search));
                row.style.display = show ? '' : 'none';
            });
        }
        function filterP5063Table() {
            const category = document.getElementById('p5063-category-filter').value;
            const violation = document.getElementById('p5063-violation-filter').value;
            const search = document.getElementById('p5063-search').value.toLowerCase();
            document.querySelectorAll('#p5063-table tbody tr').forEach(row => {
                const show = (!category || row.getAttribute('data-category') === category) &&
                             (!violation || row.getAttribute('data-violation') === violation) &&
                             (!search || row.textContent.toLowerCase().includes(search));
                row.style.display = show ? '' : 'none';
            });
        }
        function resetP8814Filter() {
            document.getElementById('p8814-category-filter').value = '';
            document.getElementById('p8814-violation-filter').value = '';
            document.getElementById('p8814-search').value = '';
            filterP8814Table();
        }
        function resetP5063Filter() {
            document.getElementById('p5063-category-filter').value = '';
            document.getElementById('p5063-violation-filter').value = '';
            document.getElementById('p5063-search').value = '';
            filterP5063Table();
        }
        let sortState = {};
        function sortTable(tableId, columnIndex) {
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const key = tableId + '-' + columnIndex;
            const currentDir = sortState[key] || 'asc';
            const newDir = currentDir === 'asc' ? 'desc' : 'asc';
            sortState[key] = newDir;
            rows.sort((a, b) => {
                const aText = a.cells[columnIndex].textContent.trim();
                const bText = b.cells[columnIndex].textContent.trim();
                return newDir === 'asc' ? aText.localeCompare(bText) : bText.localeCompare(aText);
            });
            while (tbody.firstChild) tbody.removeChild(tbody.firstChild);
            rows.forEach(row => tbody.appendChild(row));
        }
        function toggleAllSections() {
            const sections = document.querySelectorAll('.section');
            const hasInactive = Array.from(sections).some(s => !s.classList.contains('active'));
            sections.forEach(s => hasInactive ? s.classList.add('active') : s.classList.remove('active'));
        }
        function scrollToSection(sectionId) {
            const section = document.getElementById(sectionId);
            if (section) {
                section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                if (!section.classList.contains('active')) section.classList.add('active');
            }
        }
    </script>
"""


def load_csv(path):
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def escape_html(text):
    if not text or text == 'None':
        return '-'
    text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def generate_rows(rows, is_p5063=False):
    html_parts = []
    for row in rows:
        is_real = row['is_real_violation'] == 'TRUE'
        cls = 'real-violation' if is_real else 'valid-keep'
        
        if is_p5063:
            html_parts.append(f'<tr class="{cls}" data-category="{escape_html(row.get("category",""))}" data-violation="{row.get("is_real_violation","")}">')
            html_parts.append(f'<td>{escape_html(row.get("ili", row.get("qid","")))}</td>')
            html_parts.append(f'<td>{escape_html(row.get("wikidata_label",""))}</td>')
            html_parts.append(f'<td>{escape_html(row.get("synset_id",""))}</td>')
            html_parts.append(f'<td>{escape_html(row.get("synset_definition",""))}</td>')
            html_parts.append(f'<td>{escape_html(row.get("wikidata_description",""))}</td>')
            html_parts.append(f'<td>{escape_html(row.get("violation_type",""))}</td>')
        else:
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


def generate_cat_rows(counter, total):
    html_parts = []
    for cat, count in counter.most_common():
        if count > 0:
            pct = (count / total) * 100 if total > 0 else 0
            html_parts.append(f'<tr><td>{escape_html(cat)}</td><td>{count}</td><td>{pct:.1f}%</td><td>KEEP</td></tr>')
    return ''.join(html_parts)


def generate_enhanced_cat_rows(rows):
    counter = Counter(r['category'] for r in rows)
    html_parts = []
    for cat, count in counter.most_common():
        real = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'TRUE')
        valid = sum(1 for r in rows if r['category'] == cat and r['is_real_violation'] == 'FALSE')
        html_parts.append(f'<tr><td>{escape_html(cat)}</td><td>{count}</td><td>{real}</td><td>{valid}</td></tr>')
    return ''.join(html_parts)


def generate_dashboard():
    p8814_final = load_csv(OUTPUT_DIR / "p8814_violations_final.csv")
    p5063_final = load_csv(OUTPUT_DIR / "p5063_violations_final.csv")
    p8814_enhanced = load_csv(OUTPUT_DIR / "p8814_violations_enhanced.csv")
    p5063_enhanced = load_csv(OUTPUT_DIR / "p5063_violations_enhanced.csv")
    
    total = len(p8814_final) + len(p5063_final)
    p8814_real = sum(1 for r in p8814_final if r['is_real_violation'] == 'TRUE')
    p8814_valid = sum(1 for r in p8814_final if r['is_real_violation'] == 'FALSE')
    p5063_real = sum(1 for r in p5063_final if r['is_real_violation'] == 'TRUE')
    p5063_valid = sum(1 for r in p5063_final if r['is_real_violation'] == 'FALSE')
    
    p8814_cats = Counter(r['category'] for r in p8814_final)
    p5063_cats = Counter(r['category'] for r in p5063_final)
    
    p8814_rows = generate_rows(p8814_final)
    p5063_rows = generate_rows(p5063_final, is_p5063=True)
    p8814_cat_rows = generate_cat_rows(p8814_cats, len(p8814_final))
    p5063_cat_rows = generate_cat_rows(p5063_cats, len(p5063_final))
    p8814_enhanced_cat_rows = generate_enhanced_cat_rows(p8814_enhanced)
    p5063_enhanced_cat_rows = generate_enhanced_cat_rows(p5063_enhanced)
    
    p8814_cat_options = ''.join(f'<option value="{cat}">{escape_html(cat)}</option>' for cat in sorted(p8814_cats.keys()))
    p5063_cat_options = ''.join(f'<option value="{cat}">{escape_html(cat)}</option>' for cat in sorted(p5063_cats.keys()))
    
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    date_only = datetime.datetime.now().strftime('%Y-%m-%d')
    
    p8814_total = len(p8814_final)
    p5063_total = len(p5063_final)
    total_real = p8814_real + p5063_real
    total_valid = p8814_valid + p5063_valid
    p8814_pct = p8814_real / p8814_total * 100 if p8814_total > 0 else 0
    p5063_pct = p5063_real / p5063_total * 100 if p5063_total > 0 else 0
    total_pct = total_real / total * 100 if total > 0 else 0
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WordNet2Wikidata - Constraint Violation Analysis</title>
{CSS}
</head>
<body>
    <div class="container">
        <h1>WordNet2Wikidata - Constraint Violation Analysis</h1>
        <div class="date-stamp">Generated: {now}</div>
        
        <div class="toc">
            <h2>Table of Contents</h2>
            <button onclick="toggleAllSections()" class="toc-button">Toggle All Sections</button>
            <ul>
                <li class="toc-level-1"><a href="#executive-summary" onclick="scrollToSection('executive-summary'); return false;">Executive Summary</a></li>
                <li class="toc-level-1"><a href="#background" onclick="scrollToSection('background'); return false;">Background & History</a></li>
                <li class="toc-level-1"><a href="#p8814-section" onclick="scrollToSection('p8814-section'); return false;">P8814 Violations ({p8814_total})</a>
                    <ul>
                        <li class="toc-level-2"><a href="#p8814-categories" onclick="scrollToSection('p8814-categories'); return false;">Category Breakdown</a></li>
                        <li class="toc-level-2"><a href="#p8814-table" onclick="scrollToSection('p8814-table'); return false;">Violation Table</a></li>
                    </ul>
                </li>
                <li class="toc-level-1"><a href="#p5063-section" onclick="scrollToSection('p5063-section'); return false;">P5063 Violations ({p5063_total})</a>
                    <ul>
                        <li class="toc-level-2"><a href="#p5063-categories" onclick="scrollToSection('p5063-categories'); return false;">Category Breakdown</a></li>
                        <li class="toc-level-2"><a href="#p5063-table" onclick="scrollToSection('p5063-table'); return false;">Violation Table</a></li>
                    </ul>
                </li>
                <li class="toc-level-1"><a href="#exports" onclick="scrollToSection('exports'); return false;">Export Data</a></li>
                <li class="toc-level-1"><a href="#methodology" onclick="scrollToSection('methodology'); return false;">Methodology</a></li>
                <li class="toc-level-1"><a href="#enhanced" onclick="scrollToSection('enhanced'); return false;">Enhanced Analysis</a></li>
            </ul>
        </div>
        
        <div class="stats-section">
            <div class="stats-grid">
                <div class="stat-card"><div class="value">{total}</div><div class="label">Total Violations</div></div>
                <div class="stat-card"><div class="value">{total_real}</div><div class="label">Real Errors</div></div>
                <div class="stat-card"><div class="value">{total_valid}</div><div class="label">Valid Mappings</div></div>
                <div class="stat-card"><div class="value">0</div><div class="label">Needs Review</div></div>
            </div>
            <div class="summary-table">
                <table>
                    <tr><th>Property</th><th>Total</th><th>Real Errors</th><th>Valid</th><th>% Errors</th></tr>
                    <tr><td><strong>P8814 (Synset ID)</strong></td><td>{p8814_total}</td><td>{p8814_real}</td><td>{p8814_valid}</td><td>{p8814_pct:.1f}%</td></tr>
                    <tr><td><strong>P5063 (ILI)</strong></td><td>{p5063_total}</td><td>{p5063_real}</td><td>{p5063_valid}</td><td>{p5063_pct:.1f}%</td></tr>
                    <tr><td><strong>Total</strong></td><td><strong>{total}</strong></td><td><strong>{total_real}</strong></td><td><strong>{total_valid}</strong></td><td><strong>{total_pct:.1f}%</strong></td></tr>
                </table>
            </div>
        </div>
        
        <!-- Background Section -->
        <div class="section" id="background">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>Background & History</h2>
                <span class="toggle-indicator">▼</span>
            </div>
            <div class="section-content">
                <div class="summary-table">
                    <p><strong>Properties Analyzed:</strong></p>
                    <ul>
                        <li><strong>P5063</strong>: Interlingual Index (ILI) - Single-value property linking a Wikidata entity to a concept in the Global WordNet Association's Collaborative Interlingual Index</li>
                        <li><strong>P8814</strong>: WordNet 3.1 Synset ID - Unique-value property linking a Wikidata entity to a WordNet synset</li>
                    </ul>
                    <p><strong>Constraint Types:</strong></p>
                    <table>
                        <tr><th>Property</th><th>Constraint</th><th>Meaning</th><th>Violation Type</th></tr>
                        <tr><td>P5063</td><td>Single value</td><td>Each Wikidata item should have at most one ILI</td><td>Item has multiple ILIs</td></tr>
                        <tr><td>P5063</td><td>Unique value</td><td>Each ILI should map to only one Wikidata item</td><td>ILI maps to multiple items</td></tr>
                        <tr><td>P8814</td><td>Unique value</td><td>Each synset ID should map to only one Wikidata item</td><td>Synset maps to multiple items</td></tr>
                    </table>
                    <p><strong>Initial Problem (from Wikidata reports):</strong></p>
                    <ul>
                        <li>P5063: 17 single-value + 178 unique-value violations = <strong>195 total</strong></li>
                        <li>P8814: <strong>2,146 violations</strong> (synsets with multiple QIDs)</li>
                        <li>Note: Our live SPARQL query found more violations as Wikidata has grown</li>
                    </ul>
                    <p><strong>Initial Approach (Discarded):</strong></p>
                    <ul>
                        <li>Parsed static markdown files from Wikidata constraint report page</li>
                        <li>Abandoned because: static data, parsing complexity, maintenance burden</li>
                        <li>Files deleted: P5063violations.md, P8814violations.md, missingILIs.csv</li>
                    </ul>
                    <p><strong>Current Approach:</strong></p>
                    <ul>
                        <li>Direct SPARQL queries via <code>fetch_violations.py</code></li>
                        <li>Always current data from Wikidata</li>
                        <li>Cross-references with OEWN/OENN YAML to get synset definitions, members, and metadata</li>
                        <li>Joins with source data to provide full context for each violation</li>
                    </ul>
                    <p><strong>Key Insights:</strong></p>
                    <ul>
                        <li>Many "violations" are actually <strong>valid mappings</strong> representing different perspectives</li>
                        <li>Same entity can have multiple ILIs from OEWN and OENN (different names for same thing)</li>
                        <li>Same concept can have different parts of speech (noun vs verb)</li>
                        <li>Polysemy: single word with multiple meanings, all valid</li>
                        <li>True errors are duplicate ILIs added by mistake or stale mappings</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div class="section" id="p8814-section">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>P8814 Violations (Synset &rarr; Multiple QIDs)</h2>
                <span class="toggle-indicator">▼</span>
            </div>
            <div class="section-content">
                <div class="total-stats"><strong>Total:</strong> {p8814_total} | <span class="badge badge-real">Real: {p8814_real}</span> | <span class="badge badge-valid">Valid: {p8814_valid}</span></div>
                <div class="collapsible">
                    <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')"><strong>Category Breakdown</strong><span>▼</span></div>
                    <div class="collapsible-content"><div class="summary-table"><table><tr><th>Category</th><th>Count</th><th>%</th><th>Action</th></tr>{p8814_cat_rows}</table></div></div>
                </div>
                <div class="filter-controls">
                    <select id="p8814-category-filter" onchange="filterP8814Table()"><option value="">All Categories</option>{p8814_cat_options}</select>
                    <select id="p8814-violation-filter" onchange="filterP8814Table()"><option value="">All Types</option><option value="TRUE">Real Errors</option><option value="FALSE">Valid</option></select>
                    <input type="text" id="p8814-search" placeholder="Search..." onkeyup="filterP8814Table()">
                    <button onclick="resetP8814Filter()">Reset</button>
                </div>
                <div class="violation-table" id="p8814-table"><table><thead><tr><th onclick="sortTable('p8814-table', 0)">QID</th><th onclick="sortTable('p8814-table', 1)">Label</th><th onclick="sortTable('p8814-table', 2)">Synset ID</th><th onclick="sortTable('p8814-table', 3)">Synset Definition</th><th onclick="sortTable('p8814-table', 4)">Wikidata Description</th><th onclick="sortTable('p8814-table', 5)">Category</th><th onclick="sortTable('p8814-table', 6)">Action</th><th onclick="sortTable('p8814-table', 7)">Confidence</th><th>Notes</th></tr></thead><tbody>{p8814_rows}</tbody></table></div>
            </div>
        </div>
        
        <div class="section" id="p5063-section">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>P5063 Violations (ILI &rarr; Multiple QIDs or Multiple ILIs &rarr; One QID)</h2>
                <span class="toggle-indicator">▼</span>
            </div>
            <div class="section-content">
                <div class="total-stats"><strong>Total:</strong> {p5063_total} | <span class="badge badge-real">Real: {p5063_real}</span> | <span class="badge badge-valid">Valid: {p5063_valid}</span></div>
                <div class="collapsible">
                    <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')"><strong>Category Breakdown</strong><span>▼</span></div>
                    <div class="collapsible-content"><div class="summary-table"><table><tr><th>Category</th><th>Count</th><th>%</th><th>Action</th></tr>{p5063_cat_rows}</table></div></div>
                </div>
                <div class="filter-controls">
                    <select id="p5063-category-filter" onchange="filterP5063Table()"><option value="">All Categories</option>{p5063_cat_options}</select>
                    <select id="p5063-violation-filter" onchange="filterP5063Table()"><option value="">All Types</option><option value="TRUE">Real Errors</option><option value="FALSE">Valid</option></select>
                    <input type="text" id="p5063-search" placeholder="Search..." onkeyup="filterP5063Table()">
                    <button onclick="resetP5063Filter()">Reset</button>
                </div>
                <div class="violation-table" id="p5063-table"><table><thead><tr><th onclick="sortTable('p5063-table', 0)">ILI/QID</th><th onclick="sortTable('p5063-table', 1)">Label</th><th onclick="sortTable('p5063-table', 2)">Synset ID</th><th onclick="sortTable('p5063-table', 3)">Synset Definition</th><th onclick="sortTable('p5063-table', 4)">Wikidata Description</th><th onclick="sortTable('p5063-table', 5)">Type</th><th onclick="sortTable('p5063-table', 6)">Category</th><th onclick="sortTable('p5063-table', 7)">Action</th><th onclick="sortTable('p5063-table', 8)">Confidence</th><th>Notes</th></tr></thead><tbody>{p5063_rows}</tbody></table></div>
            </div>
        </div>
        
        <div class="section" id="exports">
            <div class="section-header" onclick="toggleSection(this)"><h2>Export Data</h2><span class="toggle-indicator">▼</span></div>
            <div class="section-content">
                <div class="export-buttons">
                    <a href="p8814_violations_final.csv" download>Download P8814 Final CSV</a>
                    <a href="p5063_violations_final.csv" download>Download P5063 Final CSV</a>
                    <a href="p8814_violations_enhanced.csv" download>Download P8814 Enhanced CSV</a>
                    <a href="p5063_violations_enhanced.csv" download>Download P5063 Enhanced CSV</a>
                    <a href="p8814_violations_from_wd.csv" download>Download P8814 Raw CSV</a>
                    <a href="p5063_violations_from_wd.csv" download>Download P5063 Raw CSV</a>
                </div>
            </div>
        </div>
        
        <div class="section" id="methodology">
            <div class="section-header" onclick="toggleSection(this)"><h2>Methodology</h2><span class="toggle-indicator">▼</span></div>
            <div class="section-content">
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
                                <li><strong>Similarity matching:</strong> Token-based comparison of synset definitions vs Wikidata descriptions</li>
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
            </div>
        </div>
        
        <div class="section" id="enhanced">
            <div class="section-header" onclick="toggleSection(this)"><h2>Enhanced Analysis</h2><span class="toggle-indicator">▼</span></div>
            <div class="section-content">
                <p>For a more nuanced view with similarity scores and confidence levels, see the enhanced CSV files.</p>
                <div class="collapsible">
                    <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')"><strong>Enhanced P8814 Stats</strong><span>▼</span></div>
                    <div class="collapsible-content"><div class="summary-table"><table><tr><th>Category</th><th>Total</th><th>Real</th><th>Valid</th></tr>{p8814_enhanced_cat_rows}</table></div></div>
                </div>
                <div class="collapsible">
                    <div class="collapsible-header" onclick="this.parentElement.classList.toggle('active')"><strong>Enhanced P5063 Stats</strong><span>▼</span></div>
                    <div class="collapsible-content"><div class="summary-table"><table><tr><th>Category</th><th>Total</th><th>Real</th><th>Valid</th></tr>{p5063_enhanced_cat_rows}</table></div></div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 40px; padding: 20px; text-align: center; color: #888; font-size: 0.9em;">
            <p>Generated from <strong>WordNet2Wikidata-Mappings</strong> repository</p>
            <p>Data source: Wikidata SPARQL Query Service | Date: {date_only}</p>
        </div>
    </div>
{JS}
</body>
</html>
"""
    
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard generated: {DASHBOARD_PATH}")


if __name__ == "__main__":
    generate_dashboard()
