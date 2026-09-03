# CipherTrust API Explorer Design Document

This document outlines the architecture, user interface design, core functionality, and codebase details of the CipherTrust API Explorer single-page HTML application. It serves as a technical reference for future maintenance, updates, and feature extensions.

---

## 1. Architectural Overview

The application is structured as a client-side Single-Page Application (SPA) contained entirely within a single `index.html` file. It relies on vanilla HTML5, CSS3, and modern standard JavaScript (ES6+), requiring no build steps, external bundlers, or framework dependencies.

### Key Components of the SPA
1. **Sidebar Panel**: Handles the application logo, the search and filter controls (search bar, HTTP method filter buttons, and tag selector dropdown), and the collapsible tag-grouped navigation pane (collapsing by default and expanding dynamically).
2. **Main Details Panel**: Divided into two main sections:
   - **Details Header**: Displays the active endpoint HTTP method, copyable resource path, full summary, description, and list of tags.
   - **Details Body**: Houses a tabbed navigation system for four tabs: Parameters, Request Body (Schema and simulated payload), Responses, and the **KSCTL CLI** reference context.
3. **Resizer Splitter**: A custom vertical split-bar allowing users to adjust the height ratio between the Details Header and the Details Body.
4. **Overlays**: 
   - **Loading Overlay**: Shown during JSON schema processing.
   - **Drag-and-Drop Overlay**: Displayed if auto-fetching the local schema file fails (e.g., due to browser security policies on `file://` URLs).
5. **Toast Alerts**: A non-intrusive notification layer at the bottom-right corner for action feedbacks (e.g., copying clipboard data).

---

## 2. Visual and Styling Design

The visual layout implements a modern dark theme with specific accent colors corresponding to HTTP methods.

### Design Tokens (CSS Variables)
- **Backgrounds**:
  - Primary canvas: `--bg-primary` (`#090d16`) with subtle radial gradients (`rgba(99, 102, 241, 0.05)` and `rgba(6, 182, 212, 0.05)`).
  - Sidebar/Cards: `--bg-secondary` (`#111827`)
  - Elevated elements: `--bg-tertiary` (`#1f2937`)
  - Glass effect: `--bg-glass` (`rgba(17, 24, 39, 0.7)`) with border `--border-glass` (`rgba(255, 255, 255, 0.06)`).
- **Typography**:
  - Sans-serif: `--font-sans` (`Outfit` font from Google Fonts, falling back to system sans-serif).
  - Monospace: `--font-mono` (`Fira Code` font from Google Fonts, falling back to standard monospace).
- **HTTP Method Visual Codes**:
  - `GET`: Cyan (`#0ea5e9`), background (`rgba(14, 165, 233, 0.15)`)
  - `POST`: Emerald Green (`#10b981`), background (`rgba(16, 185, 129, 0.15)`)
  - `PUT`: Violet (`#8b5cf6`), background (`rgba(139, 92, 246, 0.15)`)
  - `PATCH`: Amber/Orange (`#f59e0b`), background (`rgba(245, 158, 11, 0.15)`)
  - `DELETE`: Red (`#ef4444`), background (`rgba(239, 68, 68, 0.15)`)

### Layout & Responsiveness
- The app utilizes a full viewport flex container (`.app-container` with `100vh` and `100vw`) and disables body scroll (`overflow: hidden`). Scrollable areas are handled locally in components.
- The sidebar width is fixed at `380px`.
- Split-pane resizing is achieved programmatically via standard pointer/mouse tracking events.

---

## 3. Data Definition & State Management

### Global State Object
State is maintained inside a global variable named `App`:
```javascript
const App = {
  data: null,            // Raw Swagger 2.0 JSON payload
  endpoints: [],         // Normalized array of parsed endpoint objects
  tags: [],              // Sorted unique list of tag names
  definitions: {},       // Reference schemas map from '#/definitions'
  ksctlCommands: {},     // Grouped CLI commands parsed from ksctl_for_embedding.jsonl
  searchQuery: '',       // Active search keyword input
  selectedMethods: new Set(), // Set of HTTP method filters (GET, POST, etc.)
  selectedTag: '',       // Currently selected tag filter
  selectedEndpoint: null // Pointer to the active endpoint model
};
```

### Normalization Pipeline (`initApplication`)

The application concurrently loads two major datasets during bootstrap: the OpenAPI `ciphertrust-api-2_22.json` and the CLI reference `ksctl_for_embedding.jsonl`. When parsed:

1. **CLI Commands Grouping**: Reads `ksctl_for_embedding.jsonl` line by line. Each line represents a JSON record detailing a CLI path (`p`), a partial help string type (`h`), and description/synopsis context (`c`). Records are grouped dynamically into array buckets under `App.ksctlCommands` using their combined command string (e.g. `'ksctl users list'`) as the lookup key.
2. **API Path Traversing**: Traversing all relative `paths` and nested HTTP methods (`get`, `post`, `put`, `delete`, `patch`) from the Swagger specification.
3. **Endpoint Object Creation**: Each route is normalized into an `endpoint` object containing:
   - `path`: The relative URL path string.
   - `method`: Upper-cased HTTP verb.
   - `summary`: Short summary string.
   - `description`: Extended endpoint documentation.
   - `tags`: Array of category tags.
   - `parameters`: Declared URL, query, header, or body arguments.
   - `responses`: HTTP status code maps with descriptions and schema objects.
   - `operationId`: Generated unique identifier for element selection.
4. **Definitions Caching**: Schema definitions are extracted from the top-level `definitions` key and cached in `App.definitions` for deferred dereferencing.

---

## 4. Key Programmatic Features

### A. Dynamic Schema Reference Resolver (`resolveSchema`)
To render nested request and response payloads, references (`$ref`) must be dereferenced dynamically.
- **Recursive Dereferencing**: The function traverses schemas and swaps `$ref` pointers with target definitions inside `App.definitions`.
- **Circular Reference Protection**: Tracks visited schemas using a local `Set`. If a definition references an ancestor (e.g. key-groups containing key-groups), the recursion stops and outputs a `{ type: 'object', isCircular: true, name: refName }` node to prevent infinite call stack execution.
- **AllOf Merging**: When schemas utilize the Swagger `allOf` operator, properties and required fields are aggregated into a single merged object context.

### B. Fuzzy Multi-Token Search Engine (`searchEndpoints`)
The sidebar search filters all 1,747 endpoints instantaneously with the following details:
- **Tokenization**: Splits the search query by white space into multiple search tokens.
- **Scoring**: Each endpoint is assigned a score if *all* tokens match at least one of these criteria:
  - Path contains token: `+10` (Starts with token: additional `+5`)
  - Summary contains token: `+5`
  - Tags contain token: `+4`
  - Description contains token: `+3`
- **Relevance Sort**: Matches are ordered descending by accumulated score.
- **Match Highlighting**: Replaces search terms inside the path string with wrapping `<span class="search-highlight">` tags, sorting tokens by length to ensure nested substring highlights do not break HTML tags.
- **Dynamic Grouping Integration**: Results are dynamically sorted alphabetically and grouped by tag under collapsible categories, removing the need for flat virtualization capping.

### C. Interactive Tree Schema Builder (`buildInteractiveTree`)
For POST, PUT, and PATCH operations requiring a structured body, the application renders a visual tree view:
- **Sorted Rows**: Generates tree rows dynamically, sorting required parameters to the top, and ordering optional parameters alphabetically.
- **Tree Toggles**: Incorporates expansion markers (`▶` / `▼`) next to object and array nodes.
- **Path-Based Branch Control**: Collapse and expand behaviors are managed by matching data-path attributes (e.g., `root.user_metadata` or `root.operations[]`) of elements. Descendants are hidden or displayed by toggling their layout display attributes.

### D. Mock Payload Generator & Highlighting
- **Mock Generation (`generateMockPayload`)**: Recursively navigates the parameter's body schema to generate a mock JSON representation. Resolves defaults (`schema.default`), example values (`schema.example`), string formats (e.g. `date-time`, `uuid`), integers, numbers, booleans, and arrays.
- **Syntax Highlighting (`syntaxHighlightJSON`)**: Performs high-speed regular expression matching on JSON strings, wrapping keys (`json-key`), strings (`json-string`), numbers (`json-number`), booleans (`json-boolean`), and null values (`json-null`) with corresponding classes for custom coloring.

### E. API to KSCTL CLI Mapping Engine (`findBestCliCommand`)
To provide the user with the correct corresponding `ksctl` CLI command for each selected API endpoint:
1. **Explicit Overrides Lookup**: First, checks the `KSCTL_EXPLICIT_MAP` lookup dictionary. If an explicit mapping exists for the method and path (e.g., `GET /v1/auth/self/user` -> `ksctl users get`), the engine retrieves all matching sub-commands from the parsed database and uses standard score matching.
2. **Direct Synopsis Scan**: Scans all synopses for explicit HTTP verb + route statements (e.g., `POST to /v1/vault/keys2`) using standard regular expressions.
3. **Advanced Token Overlap Scoring (`calculateMatchScore`)**: Compares normalized path segments. Segments are parsed, translated via domain prefixes (e.g., `cte` -> `transparent-encryption`, `nodes` -> `cluster`), and stripped of plurals (`keys` -> `key`, `users` -> `user`).
   - Penalty deductions are applied for unmatched CLI tokens to prevent spurious mapping mismatches.
   - Verb matching adds a scoring bonus.
   - **Collection vs Single-Resource GET Heuristics**: Applies strict path structural rules. Parameterized single-resource GETs (ending in `{id}`) favor `get` / `show` CLI commands, while unparameterized collection GETs favor `list` commands.

### F. Collapsible Sidebar Groups by Tag
- **Categorization & Sorting**: Organizes endpoints under collapsible category containers using `ep.tags[0] || 'Uncategorized'`. Categories and endpoint paths are sorted alphabetically using standard locale comparison.
- **Smart Expand State Tracking**: Toggles the `.collapsed` classes dynamically. Categories are collapsed by default in an empty search state, but automatically expand in active search states, filter selections, or if the category contains the currently active selection.
- **Layout Rendering Resiliency**: Styled utilizing `display: block;` (rather than flexbox columns) and without `overflow: hidden;` constraints to prevent nesting layout recalculation issues inside the scrollable container.

---

## 5. Engineering Reference Mappings

### DOM Cache Mapping (`el`)
A static namespace caches DOM lookups at bootstrap to prevent layout thrashing and redundant query selection:
```javascript
const el = {
  loadingOverlay, loadingText, dropOverlay, dropzone, fileInput, browseBtn,
  searchInput, tagSelect, resultsCount, resultsList, methodBtns,
  welcomePane, detailsPane, detailsMethod, detailsPath, detailsSummary,
  detailsDesc, detailsTags, tabItems, tabPanes, badgeCountParams,
  badgeCountBody, badgeCountResponses, paramsTable, paramsTableBody,
  emptyParamsState, bodyTabLayout, schemaRowsBody, mockPayloadCode,
  emptyBodyState, responsesListContainer, copyPathBtn, copyMockBtn, toastContainer,
  
  // KSCTL CLI additions
  badgeCountKsctl, ksctlTabLayout, ksctlCmdName, ksctlCmdSynopsis, 
  ksctlCmdOptions, ksctlCmdExamples, emptyKsctlState, copyKsctlBtn
};
```

### Key Event Bindings
- **Initial Load**: Concurrently auto-fetches both `ciphertrust-api-2_22.json` and `ksctl_for_embedding.jsonl` using a startup `Promise.all` construct. If either file fails to load, displays `dropOverlay`.
- **Drag-and-Drop / Browse**: Registers listeners for file drop and manual file browse, reading local schemas via `FileReader`. Tracks uploads individually and initializes only when both datasets are present.
- **Resizer Mouse Tracking**: Tracks mouse movements `mousemove` on `document.documentElement` during dragging state to alter the `height` styles of `detailsHeader` inside a bounded range (`120px` to `parentHeight - 150px`).
- **Clipboard Interaction**: Hooks into `navigator.clipboard` to write raw endpoint path strings, stringified simulated JSON payloads, and formatted CLI examples.

---

## 6. Guidelines for Future Modification

When adding features, observe the following conventions:
- **Styles**: Keep styling inside the `<style>` tag of `index.html` categorized by section using standard CSS variables under `:root`.
- **Vanilla DOM**: Avoid importing external utility libraries like jQuery, Lodash, or custom tree-renderers. Stick to vanilla web API procedures.
- **Memory Safety**: Clean up dynamic listeners if elements are destroyed, and prevent recursive functions from creating deep reference copies of the massive Swagger schema structure (8.6 MB). Ensure recursion is controlled via the visited tracking checks.
