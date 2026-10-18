"""OpenTelemetry traces to Application Insights (agent, workflow and tool spans from Agent
Framework), enabled when APPLICATIONINSIGHTS_CONNECTION_STRING is set."""

import logging
import os

log = logging.getLogger(__name__)


def setup() -> bool:
    cs = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not cs:
        return False
    from agent_framework.observability import configure_otel_providers
    from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

    configure_otel_providers(
        service_name="regista",
        exporters=[AzureMonitorTraceExporter(connection_string=cs)],
    )
    log.info("tracing to Application Insights")
    return True
