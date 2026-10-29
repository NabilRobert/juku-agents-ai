// Real-user timings (FE8): LCP, INP and CLS, sent to the app's own endpoint with the
// page's name and the value only. No learner ID, no content, no third party.
import { type Metric, onCLS, onINP, onLCP } from "web-vitals";

const page = document.body.dataset.page ?? "unknown";

function report(metric: Metric): void {
  void fetch("/web-vitals", {
    method: "POST",
    keepalive: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ page, metric: metric.name, value: metric.value }),
  });
}

onLCP(report);
onINP(report);
onCLS(report);
