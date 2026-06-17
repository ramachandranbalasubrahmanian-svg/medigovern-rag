# Add GA4 to MediGovern RAG (Lovable)

**Measurement ID:** `G-FE6TRT5KLL`  
**Stream:** medigovern-insight — `https://medigovern-insight.lovable.app`

Paste this into **Lovable chat** for the MediGovern project, then **Publish**.

---

```
Add Google Analytics 4 to this MediGovern RAG dashboard.

Measurement ID: G-FE6TRT5KLL
Production hostname only: medigovern-insight.lovable.app

1. In index.html <head> (right after charset), add GA4 gtag bootstrap for G-FE6TRT5KLL — only on hostname medigovern-insight.lovable.app.

2. Create src/lib/analytics-config.ts:
   ga4Id: import.meta.env.VITE_GA4_MEASUREMENT_ID || "G-FE6TRT5KLL"
   site: medigovern-rag
   prodDomains: ["medigovern-insight.lovable.app"]

3. Create src/lib/analytics.ts and src/hooks/usePageAnalytics.ts (copy from medigovern-rag/lovable/ on GitHub).

4. In App.tsx, call usePageAnalytics() for SPA route tracking.

5. Wire trackEvent:
   - ask_query_submitted — Ask/Q&A submit
   - ask_answer_received — answer loaded (param: confidence_band)
   - policy_catalog_filter — catalog filters changed
   - quarantine_viewed — Quarantine page opened
   - audit_download — audit packet download
   - api_docs_click — Railway API docs links

6. Lovable env: VITE_GA4_MEASUREMENT_ID=G-FE6TRT5KLL

7. Publish. Do not break API or CORS.
```

## Verify

Visit [medigovern-insight.lovable.app](https://medigovern-insight.lovable.app) → GA4 stream **medigovern-insight** → **Realtime**.
