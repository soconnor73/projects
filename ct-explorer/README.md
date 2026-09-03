# CipherTrust API Explorer

CipherTrust API Explorer is a client-side Single-Page Application (SPA) designed to browse, search, and analyze the CipherTrust OpenAPI specification. The explorer maps API endpoints directly to their corresponding `ksctl` Command Line Interface (CLI) equivalents and displays interactive parameter trees and mock payloads.

It is built using vanilla HTML5, CSS3, and standard modern JavaScript (ES6+). It requires no build steps, compilers, or external package dependencies.

---

## Required Data Files

The application requires two main source files to initialize and function:

1. **`ciphertrust-api-2_22.json`**  
   * **Format:** OpenAPI / Swagger 2.0 JSON specification.
   * **Purpose:** Provides metadata, parameters, schemas, and descriptions for the 1,747 API endpoints.
   
2. **`ksctl_for_embedding.jsonl`**  
   * **Format:** JSON Lines (.jsonl).
   * **Purpose:** Represents the CLI reference database containing `ksctl` commands, options, synopsis descriptions, and usage examples.

---

## Loading Data Files

The explorer supports two methods for importing the required data files:

### 1. Auto-Fetch Mode (Recommended)
When hosted on a local or remote web server, the application automatically attempts to fetch both `ciphertrust-api-2_22.json` and `ksctl_for_embedding.jsonl` from the application's root directory.
* **To run via a local server:**
  * Using Node.js: `npx http-server`
  * Using Python: `python -m http.server 8000`
* **Result:** The application automatically reads the specification and initializes the interface.

### 2. Manual Drag-and-Drop / File Picker
If the auto-fetch routine fails (for example, when opening `index.html` directly from a local drive via the `file://` protocol where browser CORS security policies restrict local fetch requests), the interface displays a dedicated load overlay.
* **To load files manually:**
  * Drag and drop both `ciphertrust-api-2_22.json` and `ksctl_for_embedding.jsonl` simultaneously onto the drag-and-drop zone.
  * Alternatively, click **"Browse files"** to select and upload the two files from your operating system's file browser.
* **Dynamic Import Feedback:** If only one file is loaded, a toast notification prompts the user to supply the remaining file.

---

## User Interface & Features

### 1. Sidebar Navigation & Filtering
The left sidebar contains search and filtering capabilities to isolate endpoints:

* **Fuzzy Multi-Token Search:**
  * Splits search input into separate words (tokens).
  * Evaluates and scores endpoints based on matching all input tokens against:
    * Relative Path (Weight: `+10` points, with an additional `+5` points if it starts with the query token).
    * Summary (Weight: `+5` points).
    * Tags (Weight: `+4` points).
    * Extended Description (Weight: `+3` points).
  * Sorts search results descending by relevance score.
  * Highlights matching terms inside the sidebar path text using cyan markers (bold and underlined).

* **HTTP Method Filters:**
  * Quick-filter buttons are available for `GET`, `POST`, `PUT`, `DELETE`, and `PATCH`.
  * Supports multi-select filtering to display any combination of methods.

* **Tag Categorization Dropdown:**
  * An alphabetical selector allowing users to filter endpoints by their primary category tag.

* **Collapsible Tag Groups:**
  * Displays endpoints grouped under collapsible headers based on their primary tags.
  * Endpoints within groups are sorted alphabetically by path.
  * Tag groups collapse by default during idle states but expand automatically when a search is active, a filter is applied, or if the group contains the currently selected endpoint.

---

### 2. Main Details Pane
Selecting an endpoint from the sidebar populates the details area, divided into a header and tabbed body:

* **Adjustable Splitter Pane:**
  * A horizontal divider allowing height adjustments between the Details Header and the Tabbed Body.

* **Header Block:**
  * Shows the selected HTTP method badge, copyable relative resource path, full summary, description, and list of tags.

---

### 3. Detail Body Tab Panels

#### Parameters Tab
* Displays non-body parameters (Path, Query, and Header variables).
* Tabulates parameter names, location, data type / format, requirement status (Required/Optional), and structural description.

#### Request Body Tab
* Enabled for operations requiring payloads (`POST`, `PUT`, `PATCH`).
* **Interactive Schema Tree:** Displays the payload structure recursively. Sorts required attributes to the top and optional fields alphabetically. Users can expand or collapse object nodes to navigate nested structures.
* **Mock Payload Generator:** Dynamically creates a simulated JSON payload based on the schema defaults, examples, and formats. Includes real-time syntax highlighting for keys, strings, numbers, booleans, and nulls, along with a one-click clipboard copy button.

#### Responses Tab
* Displays documented HTTP response codes.
* Sorts codes numerically and presents them in collapsible cards containing status details and simulated response JSON schema payloads.

#### KSCTL CLI Tab
* **Cli Command Mapping Engine:** Dynamically calculates the corresponding `ksctl` command for each endpoint.
  * Resolves overrides for non-CLI managed endpoints (e.g., resources restricted to Web UI or those requiring the `pdbctl` utility).
  * Scores candidate commands by parsing relative segments, translating domain abbreviations (e.g., `cte` -> `transparent-encryption`), and evaluating token overlaps.
  * Applies heuristics to resolve collection list commands versus single-resource get/show actions.
* Shows the matched command name, a synopsis description, command options, and examples, along with a clipboard copy utility.

---

## Technical Architecture

* **Framework-Free Execution:** Written entirely in vanilla JavaScript (ES6) with direct DOM manipulation.
* **Recursive Dereferencing (`resolveSchema`):** Traverses the Swagger definitions cache to resolve reference parameters. Employs visited-node tracking to intercept circular references and handle consolidated properties within `allOf` schemas.
* **Performance Optimizations:** Features a DOM caching namespace (`el`) to minimize browser layout recalculations during dynamic updates and search operations.
