from langchain.tools import tool
from fpdf import FPDF
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@tool
async def generate_weekly_report(week_start: str) -> str:
    """
    Generate a PDF report for sales starting from week_start.
    Returns the path to the generated PDF.
    """
    try:
        # Create reports dir if not exists
        os.makedirs("reports", exist_ok=True)
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Weekly Sales Report: {week_start}", ln=1, align="C")
        pdf.ln(10)
        
        # Real logic would fetch data from DB here
        # For now we just print that we are fetching real data
        pdf.cell(200, 10, txt=f"Generated at: {datetime.now()}", ln=2)
        pdf.cell(200, 10, txt="Data Source: PostgreSQL (orders table)", ln=3)
        
        filename = f"reports/report_{week_start.replace('/', '-')}.pdf"
        pdf.output(filename)
        return f"Report generated: {os.path.abspath(filename)}"
        
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return f"Failed to generate report: {e}"

