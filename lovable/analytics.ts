import { ANALYTICS_CONFIG } from "./analytics-config";

type EventParams = Record<string, string | number | boolean | undefined>;

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    dataLayer?: unknown[];
    clarity?: (...args: unknown[]) => void;
  }
}

function isProd(): boolean {
  return ANALYTICS_CONFIG.prodDomains.includes(window.location.hostname);
}

function initAnalytics(): void {
  if (!isProd()) {
    console.log("[Analytics] Dev/preview — tracking disabled");
    window.gtag = () => {};
    return;
  }

  const { ga4Id, clarityId } = ANALYTICS_CONFIG;
  if (!ga4Id) {
    console.warn("[Analytics] Missing GA4 measurement ID");
    window.gtag = () => {};
    return;
  }

  window.dataLayer = window.dataLayer || [];
  function gtag(...args: unknown[]) {
    window.dataLayer!.push(args);
  }
  window.gtag = gtag;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(ga4Id)}`;
  document.head.appendChild(script);

  gtag("js", new Date());
  gtag("config", ga4Id, {
    send_page_view: false,
    anonymize_ip: true,
  });

  if (clarityId) {
    (function (c, l, a, r, i) {
      c[a] =
        c[a] ||
        function (...args: unknown[]) {
          (c[a].q = c[a].q || []).push(args);
        };
      const t = l.createElement(r) as HTMLScriptElement;
      t.async = true;
      t.src = `https://www.clarity.ms/tag/${i}`;
      const y = l.getElementsByTagName(r)[0];
      y.parentNode?.insertBefore(t, y);
    })(window, document, "clarity", "script", clarityId);
  }
}

export function trackPageView(path: string, title?: string): void {
  if (!window.gtag) return;
  window.gtag("event", "page_view", {
    page_path: path,
    page_title: title || document.title,
    site: ANALYTICS_CONFIG.site,
  });
}

export function trackEvent(name: string, params?: EventParams): void {
  if (!window.gtag) return;
  window.gtag("event", name, { site: ANALYTICS_CONFIG.site, ...params });
}

initAnalytics();
