/** GA4 stream: medigovern-insight — Stream ID 15103868902 */
export const ANALYTICS_CONFIG = {
  ga4Id: import.meta.env.VITE_GA4_MEASUREMENT_ID || "G-FE6TRT5KLL",
  clarityId: import.meta.env.VITE_CLARITY_PROJECT_ID || "",
  site: "medigovern-rag",
  prodDomains: ["medigovern-insight.lovable.app"],
} as const;
