# Или используйте в своём коде:
from NATType import DiagnosticServiceFactory, ReportFormatter

service = DiagnosticServiceFactory.create_service()
report = service.run_diagnostics()
print(ReportFormatter.format_report(report))
