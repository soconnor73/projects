import urllib.request
import json
import ssl
import re
import argparse
import sys
import os
from datetime import datetime

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
            os.replace(current_file, last_file)
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
            
            changes.extend(detect_changes(last_data.get("ciphertrust_products", []), cdsp_products, "CDSP Product"))
            changes.extend(detect_changes(last_data.get("luna_hsm_components", []), luna_components, "Luna HSM Component", has_date=True))
            changes.extend(detect_changes(last_data.get("dsf_components", []), dsf_components, "DSF Component"))
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
        print_table(
            "CIPHERTRUST DATA SECURITY PLATFORM (CDSP)",
            cdsp_products,
            ["title", "version"],
            ["Name", "Version"],
            args.show_urls,
            "No CipherTrust products found."
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
