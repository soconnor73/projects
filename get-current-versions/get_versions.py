import urllib.request
import json
import ssl
import re
import argparse
import sys
import os
import base64
import html as html_lib
from datetime import datetime

# Disable SSL verification issues if any
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

__version__ = "1.0.1"

API_HOST = "https://docs-cybersec-be.thalesgroup.com"
PORTAL_HOST = "https://docs-cybersec.thalesgroup.com"

def get_json(url: str) -> dict:
    """Helper to fetch JSON data from a URL."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        return json.loads(response.read().decode('utf-8', errors='ignore'))

def extract_bundle_names_from_categories() -> list[str]:
    """
    Part 1 & 2: Fetches the categories tree from the Zoomin backend API,
    locates the CDSP node, and extracts all unique bundle names.
    """
    categories_url = f"{API_HOST}/api/categories"
    try:
        categories = get_json(categories_url)
    except Exception as e:
        print(f"Error fetching categories from {categories_url}: {e}", file=sys.stderr)
        return []

    # Find the CDSP node in the category tree
    def find_node(node):
        if isinstance(node, dict):
            if node.get("id") == "CDSP":
                return node
            for child in node.get("children", []):
                found = find_node(child)
                if found:
                    return found
        elif isinstance(node, list):
            for item in node:
                found = find_node(item)
                if found:
                    return found
        return None

    cdsp_node = find_node(categories)
    if not cdsp_node:
        print("CDSP Category node not found in the documentation tree.", file=sys.stderr)
        return []

    # Recursively traverse CDSP node to find all routes/links
    bundle_names: set[str] = set()
    
    def traverse_links(node):
        if isinstance(node, dict):
            for link in node.get("subLinks", []):
                route = link.get("route") or ""
                # Extract bundle name from route e.g., /bundle/latest-cdsp-cte/page/...
                match = re.search(r'/bundle/([^/]+)/page/', route)
                if match:
                    bundle_names.add(match.group(1))
            for child in node.get("children", []):
                traverse_links(child)
        elif isinstance(node, list):
            for item in node:
                traverse_links(item)

    traverse_links(cdsp_node)
    return sorted(list(bundle_names))

def fetch_product_details(bundle_name: str) -> dict[str, str]:
    """
    Part 3: Fetches details for a specific bundle, extracts its title,
    landing page path, and the current release version marked '(latest)'.
    """
    bundle_url = f"{API_HOST}/api/bundle/{bundle_name}"
    try:
        data = get_json(bundle_url)
        bundle = data.get("bundle") or {}
        title = bundle.get("title") or bundle_name
        landing_page = bundle.get("landing_page") or "index.html"
        
        # Build home page link
        homepage = f"{PORTAL_HOST}/bundle/{bundle_name}/page/{landing_page}"
        
        # Find latest version in labels metadata
        version = "N/A (SaaS/Cloud)" if bundle_name == "cdsp-cdspaas" else "Unknown"
        labels = bundle.get("labels", [])
        for label in labels:
            if label.get("subjectHeadId") == "productversionid":
                version = label.get("navtitle", "Unknown")
                break
                
        return {
            "title": title,
            "version": version,
            "homepage": homepage
        }
    except Exception as e:
        return {
            "title": bundle_name,
            "version": f"Error: {e}",
            "homepage": f"{PORTAL_HOST}/bundle/{bundle_name}"
        }

def fetch_cte_components() -> list[dict[str, str]]:
    """
    Fetches and parses the CipherTrust Transparent Encryption (CTE) component
    and agent versions from their respective OS and platform release notes pages.
    """
    cte_specs = [
        {
            "title": "CTE for Windows",
            "bundle": "latest-cdsp-cte",
            "page": "release-notes/windows-rn/index.html",
        },
        {
            "title": "CTE for Linux",
            "bundle": "latest-cdsp-cte",
            "page": "release-notes/linux-rn/index.html",
        },
        {
            "title": "CTE for AIX",
            "bundle": "latest-cdsp-cte",
            "page": "release-notes/aix-rn/index.html",
        },
        {
            "title": "CTE UserSpace",
            "bundle": "latest-cdsp-cteu",
            "page": "release-notes/index.html",
        },
        {
            "title": "CTE for Kubernetes",
            "bundle": "latest-cdsp-cte-k8s",
            "page": "release-notes/index.html",
        }
    ]

    components = []

    def extract_version_and_date(html: str) -> tuple[str, str]:
        # Strategy 1: Look for <h[1-6]> tags containing version numbers (e.g., 7.9.0.127, 10.6.0.53)
        heading_pattern = re.compile(r'<h([1-6])[^>]*>\s*(?:v\.?|CTE\s+)?(\d+(?:\.\d+){2,3})\s*</h\1>', re.IGNORECASE)
        match = heading_pattern.search(html)
        if match:
            version = match.group(2).strip()
            after_text = html[match.end():match.end() + 600]
            date_match = re.search(r'Release Date:\s*([A-Za-z0-9,\s-]+?)(?:<|\n|$)', after_text, re.IGNORECASE)
            date = date_match.group(1).strip() if date_match else ""
            return version, date

        # Strategy 2: Look for table rows with Product/Version (e.g., CTE for Kubernetes table)
        table_row_pattern = re.compile(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
        for row_m in table_row_pattern.finditer(html):
            col2 = re.sub(r'<[^>]+>', '', row_m.group(2)).strip()
            if re.match(r'^\d+(?:\.\d+){2,3}$', col2):
                version = col2
                before_text = html[:row_m.start()]
                date_match = re.findall(r'Release Date:\s*([A-Za-z0-9,\s-]+?)(?:<|\n|$)', before_text, re.IGNORECASE)
                date = date_match[-1].strip() if date_match else ""
                return version, date

        # Strategy 3: Fallback regex search
        date_match = re.search(r'Release Date:\s*([A-Za-z0-9,\s-]+?)(?:<|\n|$)', html, re.IGNORECASE)
        date = date_match.group(1).strip() if date_match else ""
        ver_match = re.search(r'\b(\d+(?:\.\d+){2,3})\b', html)
        version = ver_match.group(1).strip() if ver_match else "Unknown"
        return version, date

    for spec in cte_specs:
        b = spec["bundle"]
        p = spec["page"]
        title = spec["title"]
        url = f"{API_HOST}/api/bundle/{b}/page/{p}"
        homepage = f"{PORTAL_HOST}/bundle/{b}/page/{p}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                html = data.get("topic_html", "")
                version, date = extract_version_and_date(html)
                components.append({
                    "title": title,
                    "version": version,
                    "date": date,
                    "homepage": homepage
                })
        except Exception as e:
            print(f"Error fetching {title}: {e}", file=sys.stderr)
            components.append({
                "title": title,
                "version": f"Error: {e}",
                "date": "",
                "homepage": homepage
            })

    return components

def fetch_luna_hsm_components() -> list[dict[str, str]]:
    """
    Fetches and parses the Luna Network HSM component versions table
    from the Luna 7 documentation page.
    """
    url = "https://www.thalesdocs.com/gphsm/luna/7/docs/network/Content/Home_Luna.htm"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        pattern = re.compile(
            r'<td class="TableStyle-Page-Body[EB]-Column1-Body1">'
            r'<a href="([^"]+)"[^>]*>([^<]+)</a>'
            r'(?:\s*\(([^)]+)\))?\s*</td>\s*'
            r'<td class="TableStyle-Page-Body[DA]-Column1-Body1">([^<]+)</td>',
            re.DOTALL
        )
        matches = pattern.findall(html)
        components = []
        for href, title, note, date in matches:
            title_text = title.strip()
            note_text = note.strip() if note else ""
            date_text = date.strip()
            
            # Extract version from anchor text
            v_match = re.search(r'(.*?)\s+v?(\d+(?:\.\d+)+)$', title_text)
            if v_match:
                prod_title = v_match.group(1).strip()
                version = v_match.group(2).strip()
            else:
                prod_title = title_text
                version = "Unknown"
                
            if note_text:
                prod_title += f" ({note_text})"
                
            link = f"https://www.thalesdocs.com/gphsm/luna/7/docs/network/Content/{href.strip()}"
            
            components.append({
                "title": prod_title,
                "version": version,
                "date": date_text,
                "homepage": link
            })
        return components
    except Exception as e:
        print(f"Error fetching Luna HSM components: {e}", file=sys.stderr)
        return []

def fetch_dsf_components() -> list[dict[str, str]]:
    """
    Fetches and parses the Data Security Fabric (DSF) component versions table
    from the DSF Integration Guide page.
    """
    url = "https://docs-cybersec-be.thalesgroup.com/api/bundle/v1-data-security-overview-and-integration-guide/page/78571.htm"
    try:
        data = get_json(url)
        html = data.get("topic_html") or ""
        
        row_pattern = re.compile(
            r'<tr[^>]*>\s*'
            r'<td[^>]*>\s*<p class="tableheading">([^<]+)</p>\s*</td>\s*'
            r'<td[^>]*>\s*<p class="(?:bodytext|tablebodytext)">([^<]+)</p>\s*</td>\s*'
            r'</tr>',
            re.DOTALL
        )
        matches = row_pattern.findall(html)
        components = []
        for prod, ver in matches:
            components.append({
                "title": prod.strip(),
                "version": ver.strip(),
                "homepage": "https://docs-cybersec.thalesgroup.com/bundle/v1-data-security-overview-and-integration-guide/page/78571.htm"
            })
        return components
    except Exception as e:
        print(f"Error fetching DSF components: {e}", file=sys.stderr)
        return []

def detect_changes(
    last_items: list[dict[str, str]],
    curr_items: list[dict[str, str]],
    category_name: str,
    has_date: bool = False
) -> list[str]:
    """Compare current items against past ones to detect additions, removals, and changes."""
    changes = []
    last_map = {item["title"]: item for item in last_items}
    curr_map = {item["title"]: item for item in curr_items}
    
    for title, curr_val in curr_map.items():
        if title not in last_map:
            if has_date:
                changes.append(f"  [New {category_name}] '{title}' added (Version: {curr_val['version']}, Date: {curr_val['date']})")
            else:
                changes.append(f"  [New {category_name}] '{title}' added (Version: {curr_val['version']})")
        else:
            last_val = last_map[title]
            if has_date:
                version_changed = curr_val["version"] != last_val["version"]
                date_changed = curr_val["date"] != last_val["date"]
                if version_changed or date_changed:
                    v_change = f"{last_val['version']} -> {curr_val['version']}" if version_changed else curr_val["version"]
                    d_change = f"{last_val['date']} -> {curr_val['date']}" if date_changed else curr_val["date"]
                    changes.append(f"  [{category_name} Change] '{title}': Version [{v_change}], Date [{d_change}]")
            else:
                if curr_val["version"] != last_val["version"]:
                    changes.append(f"  [{category_name} Version Change] '{title}': {last_val['version']} -> {curr_val['version']}")
                    
    for title, last_val in last_map.items():
        if title not in curr_map:
            if category_name == "CDSP Product":
                changes.append(f"  [Removed CDSP Product] '{title}' (Last Version: {last_val['version']})")
            else:
                changes.append(f"  [Removed {category_name}] '{title}'")
                
    return changes

def print_table(
    section_title: str,
    items: list[dict[str, str]],
    keys: list[str],
    headers: list[str],
    show_urls: bool,
    empty_message: str
) -> None:
    """Prints a formatted console table for a list of items."""
    print(f"\n=== {section_title} ===")
    if not items:
        print(empty_message)
        return

    active_keys = list(keys)
    active_headers = list(headers)
    if show_urls:
        active_keys.append("homepage")
        active_headers.append("URL")

    widths = []
    for i, key in enumerate(active_keys):
        max_len = max(len(item.get(key, "")) for item in items)
        max_len = max(max_len, len(active_headers[i]))
        widths.append(max_len + 2)

    # Use standard width format with trailing column unpadded for cleaner console output
    row_fmt = " ".join(f"{{:<{widths[i]}}}" for i in range(len(widths) - 1)) + " {}"

    print(row_fmt.format(*active_headers))
    total_width = sum(widths[:-1]) + (80 if show_urls else widths[-1])
    print("-" * total_width)

    for item in items:
        row_vals = [item.get(key, "") for key in active_keys]
        print(row_fmt.format(*row_vals))

HTML_STYLE = """
:root {
    --navy: #071b3a;
    --blue: #003da5;
    --azure: #0076ff;
    --steel: #4f6e9e;
    --cool-gray: #d8dee9;
    --light: #f5f7fa;
    --charcoal: #1a1f2b;
    --success: #00a870;
    --warning: #f5a623;
    --danger: #d62d20;
    --radius: 8px;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--light);
    color: var(--charcoal);
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
}
a { color: var(--blue); }
.topbar {
    background: var(--navy);
    color: white;
    padding: 0.7rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.topbar .mark { height: 1.6rem; width: auto; flex-shrink: 0; }
.topbar .brand { font-weight: 700; font-size: 1.05rem; }
.topbar .tagline { color: var(--cool-gray); font-size: 0.85rem; }
.wrap { max-width: 960px; margin: 2rem auto 4rem; padding: 0 1.5rem; }
h1 { margin: 0 0 0.5rem; color: var(--navy); }
.meta {
    color: var(--steel);
    font-size: 0.88rem;
    margin: 0 0 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--cool-gray);
}
.section-title { color: var(--navy); margin: 1.75rem 0 0.6rem; }
.table-wrap { overflow-x: auto; margin: 0 0 1rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; background: white; }
th {
    background: var(--navy);
    color: white;
    text-align: left;
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--navy);
}
td {
    padding: 0.5rem 0.7rem;
    border: 1px solid var(--cool-gray);
    vertical-align: top;
}
tbody tr:nth-child(even) { background: var(--light); }
.empty { color: var(--steel); font-style: italic; }
.changes { list-style: none; padding: 0; margin: 0; }
.changes li {
    padding: 0.4rem 0.7rem;
    border-left: 3px solid var(--steel);
    background: white;
    margin-bottom: 0.35rem;
    font-size: 0.88rem;
}
.changes li.added { border-left-color: var(--success); }
.changes li.removed { border-left-color: var(--danger); }
.changes li.changed { border-left-color: var(--warning); }
.no-changes { color: var(--success); font-weight: 600; }
"""


def _esc(value: str) -> str:
    return html_lib.escape(str(value or ""))


def _logo_img() -> str:
    """Return an <img> tag with the Thales logo inlined as a data URI, or '' if missing."""
    svg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "Thales_A_white.svg")
    try:
        with open(svg_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f'<img class="mark" alt="Thales" src="data:image/svg+xml;base64,{encoded}">'
    except OSError:
        return ""


def _html_table(
    items: list[dict[str, str]],
    columns: list[tuple[str, str]],
    empty_message: str,
) -> str:
    """Render one section table. `columns` is a list of (key, header) pairs."""
    if not items:
        return f'<p class="empty">{_esc(empty_message)}</p>'

    head = "".join(f"<th>{_esc(header)}</th>" for _, header in columns)
    rows = []
    for item in items:
        cells = []
        for key, _ in columns:
            if key == "homepage":
                url = item.get("homepage", "")
                cells.append(
                    f'<td><a href="{_esc(url)}" target="_blank" rel="noopener">Docs</a></td>'
                    if url else "<td></td>"
                )
            else:
                cells.append(f"<td>{_esc(item.get(key, ''))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


def render_html(data: dict, changes: list[str], has_last: bool) -> str:
    """Build a full standalone HTML report for the scraped version data."""
    ts = data.get("timestamp", "")
    try:
        ts_display = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    except ValueError:
        ts_display = ts

    sections = [
        (
            "CipherTrust Data Security Platform (CDSP)",
            data.get("ciphertrust_products", []),
            [("title", "Name"), ("version", "Version"), ("homepage", "Docs")],
            "No CipherTrust products found.",
        ),
        (
            "CipherTrust Transparent Encryption (CTE)",
            data.get("cte_components", []),
            [("title", "Name"), ("version", "Version"), ("date", "Release Date"), ("homepage", "Docs")],
            "No CTE components found.",
        ),
        (
            "Luna Network HSM Components",
            data.get("luna_hsm_components", []),
            [("title", "Name"), ("version", "Version"), ("date", "Release Date"), ("homepage", "Docs")],
            "No Luna HSM components found.",
        ),
        (
            "Data Security Fabric (DSF)",
            data.get("dsf_components", []),
            [("title", "Name"), ("version", "Version"), ("homepage", "Docs")],
            "No DSF components found.",
        ),
    ]

    body_parts = []
    for title, items, columns, empty_message in sections:
        body_parts.append(f'<h2 class="section-title">{_esc(title)}</h2>')
        body_parts.append(_html_table(items, columns, empty_message))

    if has_last:
        body_parts.append('<h2 class="section-title">Detected Changes</h2>')
        if changes:
            change_items = []
            for change in changes:
                lowered = change.lower()
                if "added" in lowered or "[new" in lowered:
                    cls = "added"
                elif "removed" in lowered:
                    cls = "removed"
                else:
                    cls = "changed"
                change_items.append(f'<li class="{cls}">{_esc(change.strip())}</li>')
            body_parts.append(f'<ul class="changes">{"".join(change_items)}</ul>')
        else:
            body_parts.append('<p class="no-changes">No changes detected since the previous run.</p>')

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Thales Product Versions</title>\n"
        f"<style>{HTML_STYLE}</style>\n"
        "</head>\n<body>\n"
        f'<header class="topbar">{_logo_img()}'
        '<span class="brand">Thales Product Versions</span>'
        '<span class="tagline">CDSP &middot; CTE &middot; Luna HSM &middot; DSF</span></header>\n'
        '<main class="wrap">\n'
        "<h1>Current Product Versions</h1>\n"
        f'<p class="meta">Generated {_esc(ts_display)}</p>\n'
        + "\n".join(body_parts)
        + "\n</main>\n</body>\n</html>\n"
    )


def main():
    parser = argparse.ArgumentParser(description="Get current product version numbers for Thales CipherTrust (CDSP), CipherTrust Transparent Encryption (CTE), Luna HSM, and DSF products.")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}",
                        help="Show program's version number and exit")
    parser.add_argument("-f", "--format", choices=["table", "markdown"], default="table",
                        help="CLI output format (default: table)")
    parser.add_argument("--show-urls", action="store_true",
                        help="Display product homepage URLs in CLI output (off by default)")
    parser.add_argument("--html", nargs="?", const="versions.html", metavar="FILE",
                        help="Also write an HTML report with formatted tables (default file: versions.html)")
    args = parser.parse_args()

    # 1. Scraping CipherTrust (CDSP) Versions
    print("Discovering CipherTrust products from Thales Documentation tree...", file=sys.stderr)
    bundle_names = extract_bundle_names_from_categories()
    cdsp_products = []
    if bundle_names:
        filtered_bundles = [b for b in bundle_names if b.startswith("latest-cdsp-") or b == "cdsp-cdspaas"]
        print(f"Fetching details for {len(filtered_bundles)} CipherTrust products...", file=sys.stderr)
        for name in filtered_bundles:
            details = fetch_product_details(name)
            cdsp_products.append(details)
        # Sort alphabetically by product title
        cdsp_products.sort(key=lambda x: x.get("title", "").lower())
    else:
        print("Warning: No CipherTrust products found.", file=sys.stderr)

    # 2. Scraping CipherTrust Transparent Encryption (CTE) Component Versions
    print("Fetching CipherTrust Transparent Encryption (CTE) component versions...", file=sys.stderr)
    cte_components = fetch_cte_components()
    # Sort alphabetically by component title
    cte_components.sort(key=lambda x: x.get("title", "").lower())

    # 3. Scraping Luna HSM Component Versions
    print("Fetching Luna HSM components table...", file=sys.stderr)
    luna_components = fetch_luna_hsm_components()
    # Sort alphabetically by component title
    luna_components.sort(key=lambda x: x.get("title", "").lower())

    # 4. Scraping Data Security Fabric (DSF) Component Versions
    print("Fetching Data Security Fabric (DSF) components table...", file=sys.stderr)
    dsf_components = fetch_dsf_components()
    # Sort alphabetically by component title
    dsf_components.sort(key=lambda x: x.get("title", "").lower())

    # 5. Save JSON and Manage History
    current_file = "current.json"
    last_file = "last.json"

    if os.path.exists(current_file):
        try:
            os.replace(current_file, last_file)
        except Exception as e:
            print(f"Warning: Could not archive current.json to last.json: {e}", file=sys.stderr)

    timestamp = datetime.now().astimezone().isoformat()
    new_data = {
        "timestamp": timestamp,
        "ciphertrust_products": cdsp_products,
        "cte_components": cte_components,
        "luna_hsm_components": luna_components,
        "dsf_components": dsf_components
    }

    try:
        with open(current_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2)
        print(f"Saved latest versions to {current_file}", file=sys.stderr)
    except Exception as e:
        print(f"Error saving to {current_file}: {e}", file=sys.stderr)

    # 6. Compare current.json and last.json for changes
    changes = []
    if os.path.exists(last_file):
        try:
            with open(last_file, "r", encoding="utf-8") as f:
                last_data = json.load(f)
            
            changes.extend(detect_changes(last_data.get("ciphertrust_products", []), cdsp_products, "CDSP Product"))
            changes.extend(detect_changes(last_data.get("cte_components", []), cte_components, "CTE Component", has_date=True))
            changes.extend(detect_changes(last_data.get("luna_hsm_components", []), luna_components, "Luna HSM Component", has_date=True))
            changes.extend(detect_changes(last_data.get("dsf_components", []), dsf_components, "DSF Component"))
        except Exception as e:
            print(f"Error comparing current and last versions: {e}", file=sys.stderr)

    # 7. Display Formatted CLI Output
    if args.format == "markdown":
        print("# Thales CipherTrust, CTE, Luna HSM, & DSF Product Versions\n")
        
        print("## CipherTrust Data Security Platform (CDSP)")
        if args.show_urls:
            print("| Name | Version | URL |")
            print("|---|---|---|")
            for p in cdsp_products:
                print(f"| {p['title']} | {p['version']} | [Documentation Home]({p['homepage']}) |")
        else:
            print("| Name | Version |")
            print("|---|---|")
            for p in cdsp_products:
                print(f"| {p['title']} | {p['version']} |")

        print("\n## CipherTrust Transparent Encryption (CTE)")
        if args.show_urls:
            print("| Name | Version | Release Date | URL |")
            print("|---|---|---|---|")
            for c in cte_components:
                print(f"| {c['title']} | {c['version']} | {c['date']} | [Release Notes]({c['homepage']}) |")
        else:
            print("| Name | Version | Release Date |")
            print("|---|---|---|")
            for c in cte_components:
                print(f"| {c['title']} | {c['version']} | {c['date']} |")
            
        print("\n## Luna Network HSM Components")
        if args.show_urls:
            print("| Name | Version | Release Date | URL |")
            print("|---|---|---|---|")
            for c in luna_components:
                print(f"| {c['title']} | {c['version']} | {c['date']} | [Release Notes]({c['homepage']}) |")
        else:
            print("| Name | Version | Release Date |")
            print("|---|---|---|")
            for c in luna_components:
                print(f"| {c['title']} | {c['version']} | {c['date']} |")

        print("\n## Data Security Fabric (DSF)")
        if args.show_urls:
            print("| Name | Version | URL |")
            print("|---|---|---|")
            for d in dsf_components:
                print(f"| {d['title']} | {d['version']} | [Documentation Home]({d['homepage']}) |")
        else:
            print("| Name | Version |")
            print("|---|---|")
            for d in dsf_components:
                print(f"| {d['title']} | {d['version']} |")
            
    else:
        # Table output
        print_table(
            "CIPHERTRUST DATA SECURITY PLATFORM (CDSP)",
            cdsp_products,
            ["title", "version"],
            ["Name", "Version"],
            args.show_urls,
            "No CipherTrust products found."
        )

        print_table(
            "CIPHERTRUST TRANSPARENT ENCRYPTION (CTE)",
            cte_components,
            ["title", "version", "date"],
            ["Name", "Version", "Release Date"],
            args.show_urls,
            "No CTE components found."
        )

        print_table(
            "LUNA NETWORK HSM COMPONENTS",
            luna_components,
            ["title", "version", "date"],
            ["Name", "Version", "Release Date"],
            args.show_urls,
            "No Luna HSM components found."
        )

        print_table(
            "DATA SECURITY FABRIC (DSF)",
            dsf_components,
            ["title", "version"],
            ["Name", "Version"],
            args.show_urls,
            "No DSF components found."
        )

    # 8. Display Change Detection Results
    if os.path.exists(last_file):
        if changes:
            print("\n=== DETECTED CHANGES ===")
            for change in changes:
                print(change)
        else:
            print("\n=== NO CHANGES DETECTED ===")

    # 9. Optional HTML Report
    if args.html:
        try:
            html_out = render_html(new_data, changes, os.path.exists(last_file))
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(html_out)
            print(f"Wrote HTML report to {args.html}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing HTML report to {args.html}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
