---
name: mnemosyne-finding
description: Create and evidence a finding in Mnemosyne, anchored to the service it affects, following the Five9 finding format. Use when you have validated a vulnerability.
---

# Recording a finding

Findings are always anchored to a **service**. Use the Deliverables finding format.

1. Find the service id (`list_hosts` → `list_services`, or you already have it from recon).
2. `create_finding(engagement_id, service_id, title, severity, description, business_impact, reproduction_steps, remediation, cve, cvss_vector, status="draft")`.
   - severity: info/low/medium/high/critical.
   - Write `business_impact` in terms of what an attacker achieves (data exposure, lateral movement, compliance breach).
   - `reproduction_steps` as numbered, copy-pasteable steps.
   - Start at `status="draft"`; the human moves it to `confirmed` after review. Only `confirmed` findings are exported.
3. Attach proof: `add_evidence(title, content, finding_id=<id>)` for tool output, and `attach_screenshot_file("finding", finding_id, "/path/to/poc.png")` for screenshots (pass the PATH — never paste base64, it can exceed the output-token limit).
4. If you recovered a secret while proving impact: `add_credential(...)` then `cred_works_on(credential_id, service_id, "works")`. Check reuse with `where_cred_works`.

Keep findings one-instance-per-detection (e.g. SMBv1 on 5 hosts = 5 findings, one per service).
