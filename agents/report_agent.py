"""Final node: renders the whole plan into a downloadable PDF."""
from pdf_report import build_pdf


def make_report_agent():
    def report_agent(state):
        try:
            return {"pdf_bytes": build_pdf(state), "logs": ["Report agent: PDF generated"]}
        except Exception as exc:  # noqa: BLE001
            return {"errors": [f"PDF report failed: {exc}"]}

    return report_agent
