---
name: mnemosyne-report
description: Produce the engagement deliverables from Mnemosyne — export the verifiable bundle and/or drive the Confluence+Jira publish. Use at engagement close or for a status package.
---

# Producing deliverables

1. Confirm findings are reviewed: `query_findings(engagement_id, status="confirmed")`. Only confirmed findings are exported/published — nudge the human to confirm any that are still `draft`/`open`.
2. Export the bundle: `export_engagement(engagement_id, out_path="engagement.zip")`. This zip has `findings.json` (Deliverables format), evidence, obfuscated secrets, all screenshots, and an integrity manifest. Hand it to Rovo or archive it.
3. For Confluence/Jira, the deterministic publish is driven from the UI wizard (Engagement → Publish to Confluence & Jira). Do not free-form pages/tickets yourself — the wizard is idempotent and traceable. You may draft the executive-summary narrative from the bundle.

Never alter finding content when summarizing — cite it verbatim; the export carries integrity hashes.
