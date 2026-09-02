# Thales Product Version Scraper

**Version**: `1.0.1`

A lightweight Python scraping utility that automatically fetches, tracks, and logs the current latest release versions for:
1.  **Thales CipherTrust Data Security Platform (CDSP)** products.
2.  **CipherTrust Transparent Encryption (CTE)** components and OS agents.
3.  **Luna Network HSM 7** components.
4.  **Data Security Fabric (DSF)** components.

---

## Features

-   **Dynamic CDSP Discovery**: Queries the Zoomin categories tree API to dynamically locate all current CDSP products on `docs-cybersec.thalesgroup.com`.
-   **Granular CTE Version Scraping**: Fetches OS-specific patch release versions and release dates directly from dedicated release notes pages for:
    -   CTE for Windows
    -   CTE for Linux
    -   CTE for AIX
    -   CTE UserSpace (CTE-U)
    -   CTE for Kubernetes (CTE-K8s)
-   **Luna HSM Table Scraping**: Scrapes the component version grid directly from the MadCap Flare static homepage on `thalesdocs.com`.
-   **DSF Component Scraping**: Fetches the dynamic JSON topic data for the DSF integration page from the backend API to scrape its product versions table.
-   **Change Detection**: Compares the scraped versions from the current run against the previous execution's state, detailing additions, removals, and version number/release date changes.
-   **State History**: Automatically archives the previous run to `last.json` and saves the current state to `current.json` with an ISO 8601 creation timestamp.
-   **HTML Report**: Optionally emits a standalone, nicely formatted HTML page (`--html`) with one table per product group and a highlighted change list.
-   **Zero Dependencies**: Written purely in Python using built-in standard libraries (`urllib`, `re`, `json`, `argparse`, `os`, `html`, `datetime`).

---

## Prerequisites

-   Python 3.6 or higher.
-   An active internet connection to query the Thales documentation portals.

---

## Installation

No external packages or installation steps are required. Simply download or clone this repository to your system:

```bash
git clone https://github.com/soconnor73/projects.git
cd projects/get-current-versions
```

---

## Running the Script

Execute the script from your terminal using Python:

### 1. Default Run (Recommended)
Displays a clean, sorted text table of all CipherTrust, CTE, Luna, and DSF products. Automatically saves the full JSON data to `current.json` (archiving any existing state to `last.json`) and prints detected version changes.
```bash
python get_versions.py
```

### 2. Include Documentation Homepage URLs
Add the `--show-urls` flag to append the homepage URL column to the terminal output:
```bash
python get_versions.py --show-urls
```

### 3. Markdown Formatting
Outputs the results formatted as a Markdown table (handy for generating reports or documentation):
```bash
python get_versions.py -f markdown
```

### 4. HTML Report
Add the `--html` flag to also write a standalone, styled HTML page with formatted tables for every product group (plus a detected-changes list). The console/Markdown output is still printed as usual.
```bash
# Write to the default file (versions.html in the working directory)
python get_versions.py --html

# Write to a specific path
python get_versions.py --html ./dist/versions.html
```
The generated file is self-contained (inline CSS, no external assets) and safe to open directly in a browser or share.

### 5. Display Script Version
```bash
python get_versions.py --version
```

---

## Docker

The repo ships a container that runs the scan once on start-up, re-runs it **every day at local midnight**, and serves the generated `versions.html` over HTTP on container port 80. It uses only the Python standard library (no web framework).

Three compose files are provided; all read the image tag from `VERSION` in `.env`:

| File | Use | Exposure |
|------|-----|----------|
| `docker-compose-local.yml` | local runs / QA | publishes host port **3210** → container 80 |
| `docker-compose-staging.yml` | staging (`cargo.apoapsis.xyz`), behind Traefik | no published port; `Host(\`ver.apoapsis.xyz\`)` on the external `proxy_network` |
| `docker-compose-prod.yml` | production, behind Traefik | no published port; `Host(\`ver.thalescryptolabs.com\`)` on the external `proxy_network` |

### Build & run (local)
```bash
cd get-current-versions

# with docker compose (recommended)
docker compose -f docker-compose-local.yml up -d --build

# or plain docker
docker build -t thales-version-scraper .
docker run -d --name thales-version-scraper \
    -p 3210:80 \
    -e TZ=America/New_York \
    thales-version-scraper
```

Then open `http://localhost:3210/` — `/` and `/index.html` both serve `versions.html`. While the first scan is running a lightweight placeholder page is served and auto-refreshes.

Everything runs inside the container: nothing is mounted from the host. State
files (`current.json` / `last.json`) and the report are ephemeral and rebuilt
from scratch each time the container starts — the boot scan means the page is
current within a minute of every restart.

### Configuration

| Variable   | Default  | Purpose                                                        |
|------------|----------|---------------------------------------------------------------|
| `TZ`       | `UTC`    | Time zone that defines when "midnight" is (needs a valid tz name, e.g. `Europe/Dublin`). |
| `PORT`     | `80`     | Port the HTTP server listens on inside the container.          |
| `DATA_DIR` | `/data`  | In-container directory for `current.json`, `last.json`, and `versions.html`. |

A `HEALTHCHECK` polls the HTTP server every 30s.

### How the schedule works

`serve.py` supervises everything in one process:
- on start it writes a placeholder, kicks off a background scan, and starts the HTTP server immediately;
- a scheduler thread sleeps until the next local midnight, runs `get_versions.py --html /data/versions.html`, and repeats.

---

## File Lifecycle

When the script runs, it manages database state in the current working directory:

-   `current.json`: Holds the output of the most recent scrape.
-   `last.json`: Holds the output of the previous scrape (created by moving `current.json` before writing the new one).

### JSON State Format Example
```json
{
  "timestamp": "2026-08-31T11:56:38.123456-05:00",
  "ciphertrust_products": [
    {
      "title": "CipherTrust Manager",
      "version": "v2.24 (latest)",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cm/page/get_started/index.html"
    }
  ],
  "cte_components": [
    {
      "title": "CTE for Windows",
      "version": "7.9.0.127",
      "date": "2026-08-21",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cte/page/release-notes/windows-rn/index.html"
    },
    {
      "title": "CTE for Linux",
      "version": "7.9.0.127",
      "date": "2026-08-21",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cte/page/release-notes/linux-rn/index.html"
    },
    {
      "title": "CTE for AIX",
      "version": "7.9.0.22",
      "date": "2026-02-10",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cte/page/release-notes/aix-rn/index.html"
    },
    {
      "title": "CTE UserSpace",
      "version": "10.6.0.53",
      "date": "2026-08-11",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cteu/page/release-notes/index.html"
    },
    {
      "title": "CTE for Kubernetes",
      "version": "1.7.0.34",
      "date": "2026-01-07",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cte-k8s/page/release-notes/index.html"
    }
  ],
  "luna_hsm_components": [
    {
      "title": "Luna Appliance Software",
      "version": "7.9.1",
      "date": "February 2026",
      "homepage": "https://www.thalesdocs.com/gphsm/luna/7/docs/network/Content/CRN/Luna/appliance/7-9-1.htm"
    }
  ],
  "dsf_components": [
    {
      "title": "DAM",
      "version": "v15.4",
      "homepage": "https://docs-cybersec.thalesgroup.com/bundle/v1-data-security-overview-and-integration-guide/page/78571.htm"
    }
  ]
}
```
