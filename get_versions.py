import urllib.request
import json
import ssl
import re
import argparse
import sys
import os
from datetime import datetime
from typing import List, Dict, Set

# Disable SSL verification issues if any
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

API_HOST = "https://docs-cybersec-be.thalesgroup.com"
PORTAL_HOST = "https://docs-cybersec.thalesgroup.com"

def get_json(url: str) -> dict:
    """Helper to fetch JSON data from a URL."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
        return json.loads(response.read().decode('utf-8', errors='ignore'))

def extract_bundle_names_from_categories() -> List[str]:
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
    cdsp_node = None
    
    def find_node(node):
        nonlocal cdsp_node
        if isinstance(node, dict):
            if node.get("id") == "CDSP":
                cdsp_node = node
                return
            for child in node.get("children", []):
                find_node(child)
        elif isinstance(node, list):
            for item in node:
                find_node(item)

    find_node(categories)
    if not cdsp_node:
        print("CDSP Category node not found in the documentation tree.", file=sys.stderr)
        return []

    # Recursively traverse CDSP node to find all routes/links
    bundle_names: Set[str] = set()
    
    def traverse_links(node):
        if isinstance(node, dict):
            for link in node.get("subLinks", []):
                route = link.get("route", "")
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

def fetch_product_details(bundle_name: str) -> Dict[str, str]:
    """
    Part 3: Fetches details for a specific bundle, extracts its title,
    landing page path, and the current release version marked '(latest)'.
    """
    bundle_url = f"{API_HOST}/api/bundle/{bundle_name}"
    try:
        data = get_json(bundle_url)
        bundle = data.get("bundle", {})
        title = bundle.get("title", bundle_name)
        landing_page = bundle.get("landing_page", "index.html")
        
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

def fetch_luna_hsm_components() -> List[Dict[str, str]]:
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
            v_match = re.search(r'(.*?)\s+v?(\d+\.\d+(?:\.\d+)?)$', title_text)
            if v_match:
                prod_title = v_match.group(1).strip()
                version = v_match.group(2).strip()
                if note_text:
                    prod_title += f" ({note_text})"
            else:
                prod_title = title_text
                if note_text:
                    prod_title += f" ({note_text})"
                version = "Unknown"
                
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

def fetch_dsf_components() -> List[Dict[str, str]]:
    """
    Fetches and parses the Data Security Fabric (DSF) component versions table
    from the DSF Integration Guide page.
    """
    url = "https://docs-cybersec-be.thalesgroup.com/api/bundle/v1-data-security-overview-and-integration-guide/page/78571.htm"
    try:
        data = get_json(url)
        html = data.get("topic_html", "")
        
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

def main():
    parser = argparse.ArgumentParser(description="Get current product version numbers for Thales CipherTrust, Luna HSM, and DSF products.")
    parser.add_argument("-f", "--format", choices=["table", "markdown"], default="table",
                        help="CLI output format (default: table)")
    parser.add_argument("--show-urls", action="store_true",
                        help="Display product homepage URLs in CLI output (off by default)")
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

    # 2. Scraping Luna HSM Component Versions
    print("Fetching Luna HSM components table...", file=sys.stderr)
    luna_components = fetch_luna_hsm_components()
    # Sort alphabetically by component title
    luna_components.sort(key=lambda x: x.get("title", "").lower())

    # 3. Scraping Data Security Fabric (DSF) Component Versions
    print("Fetching Data Security Fabric (DSF) components table...", file=sys.stderr)
    dsf_components = fetch_dsf_components()
    # Sort alphabetically by component title
    dsf_components.sort(key=lambda x: x.get("title", "").lower())

    # 4. Save JSON and Manage History
    current_file = "current.json"
    last_file = "last.json"

    if os.path.exists(current_file):
        try:
            if os.path.exists(last_file):
                os.remove(last_file)
            os.rename(current_file, last_file)
        except Exception as e:
            print(f"Warning: Could not archive current.json to last.json: {e}", file=sys.stderr)

    timestamp = datetime.now().astimezone().isoformat()
    new_data = {
        "timestamp": timestamp,
        "ciphertrust_products": cdsp_products,
        "luna_hsm_components": luna_components,
        "dsf_components": dsf_components
    }

    try:
        with open(current_file, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2)
        print(f"Saved latest versions to {current_file}", file=sys.stderr)
    except Exception as e:
        print(f"Error saving to {current_file}: {e}", file=sys.stderr)

    # 5. Compare current.json and last.json for changes
    changes = []
    if os.path.exists(last_file):
        try:
            with open(last_file, "r", encoding="utf-8") as f:
                last_data = json.load(f)
            
            # Compare CipherTrust Products
            last_cdsp = {p["title"]: p for p in last_data.get("ciphertrust_products", [])}
            curr_cdsp = {p["title"]: p for p in cdsp_products}
            
            for title, p_curr in curr_cdsp.items():
                if title not in last_cdsp:
                    changes.append(f"  [New CDSP Product] '{title}' added (Version: {p_curr['version']})")
                else:
                    p_last = last_cdsp[title]
                    if p_curr["version"] != p_last["version"]:
                        changes.append(f"  [CDSP Product Version Change] '{title}': {p_last['version']} -> {p_curr['version']}")
            for title in last_cdsp:
                if title not in curr_cdsp:
                    changes.append(f"  [Removed CDSP Product] '{title}' (Last Version: {last_cdsp[title]['version']})")
            
            # Compare Luna HSM Components
            last_luna = {c["title"]: c for c in last_data.get("luna_hsm_components", [])}
            curr_luna = {c["title"]: c for c in luna_components}
            
            for title, c_curr in curr_luna.items():
                if title not in last_luna:
                    changes.append(f"  [New Luna HSM Component] '{title}' added (Version: {c_curr['version']}, Date: {c_curr['date']})")
                else:
                    c_last = last_luna[title]
                    if c_curr["version"] != c_last["version"] or c_curr["date"] != c_last["date"]:
                        v_change = f"{c_last['version']} -> {c_curr['version']}" if c_curr["version"] != c_last["version"] else c_curr["version"]
                        d_change = f"{c_last['date']} -> {c_curr['date']}" if c_curr["date"] != c_last["date"] else c_curr["date"]
                        changes.append(f"  [Luna HSM Component Change] '{title}': Version [{v_change}], Date [{d_change}]")
            for title in last_luna:
                if title not in curr_luna:
                    changes.append(f"  [Removed Luna HSM Component] '{title}'")

            # Compare DSF Components
            last_dsf = {d["title"]: d for d in last_data.get("dsf_components", [])}
            curr_dsf = {d["title"]: d for d in dsf_components}
            
            for title, d_curr in curr_dsf.items():
                if title not in last_dsf:
                    changes.append(f"  [New DSF Component] '{title}' added (Version: {d_curr['version']})")
                else:
                    d_last = last_dsf[title]
                    if d_curr["version"] != d_last["version"]:
                        changes.append(f"  [DSF Component Version Change] '{title}': {d_last['version']} -> {d_curr['version']}")
            for title in last_dsf:
                if title not in curr_dsf:
                    changes.append(f"  [Removed DSF Component] '{title}'")
        except Exception as e:
            print(f"Error comparing current and last versions: {e}", file=sys.stderr)

    # 6. Display Formatted CLI Output
    if args.format == "markdown":
        print("# Thales CipherTrust, Luna HSM, & DSF Product Versions\n")
        
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
        print("\n=== CIPHERTRUST DATA SECURITY PLATFORM (CDSP) ===")
        if cdsp_products:
            title_w = max(max(len(p['title']) for p in cdsp_products), 4) + 2
            ver_w = max(max(len(p['version']) for p in cdsp_products), 7) + 2
            if args.show_urls:
                row_fmt = f"{{:<{title_w}}} {{:<{ver_w}}} {{}}"
                print(row_fmt.format("Name", "Version", "URL"))
                print("-" * (title_w + ver_w + 80))
                for p in cdsp_products:
                    print(row_fmt.format(p['title'], p['version'], p['homepage']))
            else:
                row_fmt = f"{{:<{title_w}}} {{}}"
                print(row_fmt.format("Name", "Version"))
                print("-" * (title_w + ver_w))
                for p in cdsp_products:
                    print(row_fmt.format(p['title'], p['version']))
        else:
            print("No CipherTrust products found.")

        print("\n=== LUNA NETWORK HSM COMPONENTS ===")
        if luna_components:
            title_w = max(max(len(c['title']) for c in luna_components), 4) + 2
            ver_w = max(max(len(c['version']) for c in luna_components), 7) + 2
            date_w = max(max(len(c['date']) for c in luna_components), 12) + 2
            if args.show_urls:
                row_fmt = f"{{:<{title_w}}} {{:<{ver_w}}} {{:<{date_w}}} {{}}"
                print(row_fmt.format("Name", "Version", "Release Date", "URL"))
                print("-" * (title_w + ver_w + date_w + 80))
                for c in luna_components:
                    print(row_fmt.format(c['title'], c['version'], c['date'], c['homepage']))
            else:
                row_fmt = f"{{:<{title_w}}} {{:<{ver_w}}} {{}}"
                print(row_fmt.format("Name", "Version", "Release Date"))
                print("-" * (title_w + ver_w + date_w))
                for c in luna_components:
                    print(row_fmt.format(c['title'], c['version'], c['date']))
        else:
            print("No Luna HSM components found.")

        print("\n=== DATA SECURITY FABRIC (DSF) ===")
        if dsf_components:
            title_w = max(max(len(d['title']) for d in dsf_components), 4) + 2
            ver_w = max(max(len(d['version']) for d in dsf_components), 7) + 2
            if args.show_urls:
                row_fmt = f"{{:<{title_w}}} {{:<{ver_w}}} {{}}"
                print(row_fmt.format("Name", "Version", "URL"))
                print("-" * (title_w + ver_w + 80))
                for d in dsf_components:
                    print(row_fmt.format(d['title'], d['version'], d['homepage']))
            else:
                row_fmt = f"{{:<{title_w}}} {{}}"
                print(row_fmt.format("Name", "Version"))
                print("-" * (title_w + ver_w))
                for d in dsf_components:
                    print(row_fmt.format(d['title'], d['version']))
        else:
            print("No DSF components found.")

    # 7. Display Change Detection Results
    if os.path.exists(last_file):
        if changes:
            print("\n=== DETECTED CHANGES ===")
            for change in changes:
                print(change)
        else:
            print("\n=== NO CHANGES DETECTED ===")

if __name__ == "__main__":
    main()
