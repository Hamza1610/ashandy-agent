"""
Report Tool: Multi-stage pipeline for generating comprehensive business reports with PDF output.
"""
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage
from app.services.logging_service import logging_service
from app.services.profile_service import profile_service
from app.services.summary_service import summary_service
from app.services.mcp_service import mcp_service
from app.services.llm_service import invoke_with_fallback
from fpdf import FPDF
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import os
import logging

logger = logging.getLogger(__name__)


def parse_date_range(start_input: str, end_input: str = None) -> tuple:
    """Parse flexible date inputs ('yesterday', 'last week', '2024-12-01') to date objects."""
    today = datetime.now().date()
    start_lower = start_input.lower().strip()
    
    if start_lower == "yesterday":
        start_date = today - timedelta(days=1)
    elif start_lower in ["last week", "past week", "this week"]:
        start_date = today - timedelta(days=7)
    elif start_lower in ["last month", "past month"]:
        start_date = today - timedelta(days=30)
    else:
        try:
            start_date = date_parser.parse(start_input).date()
        except:
            start_date = today - timedelta(days=7)
    
    if end_input:
        end_lower = end_input.lower().strip()
        if end_lower in ["today", "now"]:
            end_date = today
        else:
            try:
                end_date = date_parser.parse(end_input).date()
            except:
                end_date = today
    else:
        end_date = today
    
    return start_date, end_date


@tool
async def generate_comprehensive_report(start_date: str, end_date: str = None) -> str:
    """Generate a comprehensive business report for the specified period."""
    try:
        start, end = parse_date_range(start_date, end_date)
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())
        logger.info(f"Generating report for {start} to {end}")
        
        # Stage 1: Data Gathering
        unique_users = await logging_service.get_unique_users_for_period(start_dt, end_dt)
        messages = await logging_service.get_messages_for_period(start_dt, end_dt)
        user_messages = [m for m in messages if m.get("role") == "user"]
        avg_sentiment = sum(m.get("sentiment_score", 0) for m in user_messages) / max(len(user_messages), 1)
        aggregated = await summary_service.get_aggregated_summary(start, end)
        total_orders = aggregated.get("total_orders", 0)
        total_revenue = aggregated.get("total_revenue", 0.0)
        
        # Stage 2: Customer Analysis
        customer_data = []
        for user_id in unique_users[:20]:
            profile = await profile_service.get_or_create_profile(user_id)
            retention = await profile_service.calculate_retention_score(user_id)
            customer_data.append({
                "user_id": user_id[-6:] + "...",
                "purchases": profile.get("total_purchases", 0),
                "sentiment": round(profile.get("avg_sentiment", 0), 2),
                "retention": round(retention, 2)
            })
        customer_data.sort(key=lambda x: x["purchases"], reverse=True)
        
        # Stage 3: Pattern Aggregation
        intent_counts = {}
        for msg in user_messages:
            intent = msg.get("intent", "other")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Stage 4: LLM Synthesis with Fallback
        synthesis_prompt = f"""You are a business analyst for Ashandy Cosmetics.
Generate: 1) 2-3 sentence Executive Summary, 2) 3 Key Insights, 3) 3 Recommendations

DATA: Period: {start} to {end}, Messages: {len(messages)}, Customers: {len(unique_users)},
Sentiment: {avg_sentiment:.2f}, Intents: {intent_counts}, Orders: {total_orders}, Revenue: N{total_revenue:,.0f}
Top Customers: {customer_data[:5]}

Be concise. No markdown."""
        
        synthesis_text = await invoke_with_fallback(
            messages=[("system", synthesis_prompt)],
            model_type="fast",
            temperature=0.3
        )
        
        # Generate PDF
        os.makedirs("reports", exist_ok=True)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "ASHANDY COSMETICS - BUSINESS REPORT", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"Period: {start} to {end}", ln=True)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "EXECUTIVE SUMMARY & INSIGHTS", ln=True)
        pdf.set_font("Arial", "", 10)
        for line in synthesis_text.replace("#", "").replace("*", "").split("\n"):
            if line.strip():
                pdf.multi_cell(0, 5, line.strip())
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "KEY METRICS", ln=True)
        pdf.set_font("Arial", "", 10)
        for label, val in [("Messages", len(messages)), ("Customers", len(unique_users)), ("Sentiment", f"{avg_sentiment:.2f}"), ("Orders", total_orders), ("Revenue", f"N{total_revenue:,.0f}")]:
            pdf.cell(80, 6, f"{label}:", 0)
            pdf.cell(0, 6, str(val), ln=True)
        
        filename = f"reports/report_{start}_{end}.pdf"
        pdf.output(filename)
        abs_path = os.path.abspath(filename)
        logger.info(f"PDF report: {abs_path}")
        
        return f"✅ Report generated!\n\nFile: {abs_path}\n\nPeriod: {start} to {end}\nCustomers: {len(unique_users)}\nMessages: {len(messages)}\nRevenue: N{total_revenue:,.0f}"
        
    except Exception as e:
        logger.error(f"Report error: {e}", exc_info=True)
        return f"❌ Report failed: {str(e)}"


@tool
async def generate_weekly_report(week_start: str) -> str:
    """Generate weekly report (legacy wrapper)."""
    return await generate_comprehensive_report.ainvoke({"start_date": week_start, "end_date": None})
