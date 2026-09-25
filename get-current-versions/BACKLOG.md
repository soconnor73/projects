# ~~Repeating entries~~ (Completed in 1.0.3)

- Luna Backup HSM 7 Firmware is listed twice
- Done: the Luna home page itself repeats the row, so the Luna scraper now drops rows that are exact copies of an earlier one

# ~~Enhancement - show minimum supported CipherTrust version~~ (Completed in 1.0.4)

- Done: new "CipherTrust Manager Release Support" section showing the LTS releases (scheduled patches until / support until) and the end-of-support version list, with change detection

- Show LTS release support timeframe
- Source: https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cm/page/admin/cm_admin/cm_release_model/index.html
- Example text from page:
```text
Our current LTS releases are:
2.23.x-LTS release. This is the most current and preferred LTS version. It receives scheduled patches until Q2 2028 and support until Q2 2030.
2.11.x-LTS release. This is the first LTS release. It receives scheduled patches until Q4 2026 and support until Q3 2027.
```
- Show End of support versions
- Source: https://docs-cybersec.thalesgroup.com/bundle/latest-cdsp-cm/page/admin/cm_admin/cm_release_model/index.html
- Example text from page:
```text
Versions 2.10.x and older, 2.12.x, 2.13.x, and 2.14.x have reached end of support.
```

# ~~Enhancement - link to CTE Compatibility Matrix~~ (Completed in 1.0.2)

- There are too many OS kernel and CTE agent permutations to recreate. They are already listed in the Compatibility Matrix
- ~~https://thalesdocs.com/ctp/cte/cte-cm/?OsMajor=ALMA%208&OsMinor=all&Kernel=all~~
- Done: the CTE section of every output format now links to:
  - CTE Compatibility Matrix, filtered to RHEL 10: https://docs-cybersec.thalesgroup.com/cte-con/?OsMajor=RHEL%2010&OsMinor=all&Kernel=all&selectedOsMajor=RHEL%2010
  - CipherTrust Manager Compatible CTE Versions: https://docs-cybersec.thalesgroup.com/cte-con/?sideBarIndex=6&radioOption=0&firstOption=All&secondOption=All
