"""
Comprehensive Report Tool: Multi-stage pipeline for generating detailed business reports.
"""
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from app.services.logging_service import logging_service
from app.services.profile_service import profile_service
from app.services.summary_service import summary_service
from app.services.mcp_service import mcp_service
from app.utils.config import settings
from fpdf import FPDF
import os
import logging
from datetime import datetime, timedelta
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


def parse_date_range(start_input: str, end_input: str = None) -> tuple:
    """
    Parse flexible date inputs into datetime objects.
    
    Handles:
    - "yesterday" -> yesterday's date
    - "last week" -> 7 days ago to today
    - "2024-12-01" -> specific date
    - "December 1st" -> specific date
    """
    today = datetime.now().date()
    
    # Parse start date
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
    
    # Parse end date (defaults to today)
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
    """
    Generate a comprehensive business report for the specified period.
    
    This is a multi-stage pipeline:
    1. Data Gathering (messages, orders, profiles)
    2. Per-Customer Analysis (sentiment, retention)
    3. Pattern Aggregation (top products, stockouts)
    4. LLM Synthesis (insights, recommendations)
    
    Args:
        start_date: Start of period ("yesterday", "last week", "2024-12-01")
        end_date: End of period (defaults to today)
    
    Returns:
        Formatted Markdown report
    """
    try:
        # Parse dates
        start, end = parse_date_range(start_date, end_date)
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())
        
        logger.info(f"Generating report for {start} to {end}")
        
        # ========== STAGE 1: DATA GATHERING ==========
        
        # 1a. Get message statistics
        unique_users = await logging_service.get_unique_users_for_period(start_dt, end_dt)
        messages = await logging_service.get_messages_for_period(start_dt, end_dt)
        
        total_messages = len(messages)
        user_messages = [m for m in messages if m.get("role") == "user"]
        avg_sentiment = sum(m.get("sentiment_score", 0) for m in user_messages) / max(len(user_messages), 1)
        
        # 1b. Get aggregated summaries (if available)
        aggregated = await summary_service.get_aggregated_summary(start, end)
        
        # 1c. Get orders from PHPPOS via MCP
        total_orders = aggregated.get("total_orders", 0)
        total_revenue = aggregated.get("total_revenue", 0.0)
        
        # Try to get top products from MCP
        top_products = []
        try:
            pos_data = await mcp_service.call_tool("pos", "search_products", {"query": ""})
            # This is a fallback - in production, you'd query order history
        except:
            pass
        
        # ========== STAGE 2: PER-CUSTOMER ANALYSIS ==========
        
        customer_data = []
        for user_id in unique_users[:20]:  # Limit to top 20 for performance
            profile = await profile_service.get_or_create_profile(user_id)
            retention = await profile_service.calculate_retention_score(user_id)
            
            customer_data.append({
                "user_id": user_id[-6:] + "...",  # Anonymize
                "purchases": profile.get("total_purchases", 0),
                "sentiment": round(profile.get("avg_sentiment", 0), 2),
                "retention": round(retention, 2)
            })
        
        # Sort by purchases (highest first)
        customer_data.sort(key=lambda x: x["purchases"], reverse=True)
        
        # ========== STAGE 3: PATTERN AGGREGATION ==========
        
        # Count intents
        intent_counts = {}
        for msg in user_messages:
            intent = msg.get("intent", "other")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # ========== STAGE 4: LLM SYNTHESIS ==========
        
        synthesis_prompt = f"""You are a business analyst for Ashandy Cosmetics.

Based on the following data, generate:
1. A 2-3 sentence Executive Summary
2. 3 Key Sales Insights
3. 3 Recommended Next Steps

DATA:
- Period: {start} to {end}
- Total Messages: {total_messages}
- Unique Customers: {len(unique_users)}
- Average Sentiment: {avg_sentiment:.2f} (-1 to 1 scale)
- Intent Distribution: {intent_counts}
- Orders: {total_orders}
- Revenue: N{total_revenue:,.0f}

Customer Activity (Top 5):
{customer_data[:5]}

Be concise and professional. Do not use markdown formatting or special characters.
"""
        
        # Use Llama 4 Scout for synthesis
        llm = ChatGroq(
            temperature=0.3,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-scout-17b-16e-instruct"
        )
        
        synthesis_response = await llm.ainvoke([SystemMessage(content=synthesis_prompt)])
        synthesis_text = synthesis_response.content
        
        # ========== GENERATE PDF REPORT ==========
        
        # Create reports directory
        os.makedirs("reports", exist_ok=True)
        
        # Generate PDF
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "ASHANDY COSMETICS - BUSINESS REPORT", ln=True, align="C")
        pdf.ln(5)
        
        # Period and Generation Date
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"Period: {start} to {end}", ln=True)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(5)
        
        # Horizontal line
        pdf.set_draw_color(0, 0, 0)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Executive Summary Section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "EXECUTIVE SUMMARY & INSIGHTS", ln=True)
        pdf.set_font("Arial", "", 10)
        
        # Clean synthesis text and add to PDF
        clean_text = synthesis_text.replace("#", "").replace("*", "").replace("_", "")
        for line in clean_text.split("\n"):
            line = line.strip()
            if line:
                pdf.multi_cell(0, 5, line)
        pdf.ln(5)
        
        # Metrics Section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "KEY METRICS", ln=True)
        pdf.set_font("Arial", "", 10)
        
        metrics = [
            ("Total Messages", str(total_messages)),
            ("Unique Customers", str(len(unique_users))),
            ("Average Sentiment", f"{avg_sentiment:.2f}"),
            ("Total Orders", str(total_orders)),
            ("Total Revenue", f"N{total_revenue:,.0f}")
        ]
        
        for metric, value in metrics:
            pdf.cell(80, 6, metric + ":", border=0)
            pdf.cell(0, 6, value, ln=True, border=0)
        pdf.ln(5)
        
        # Customer Activity Section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "CUSTOMER ACTIVITY (TOP 10)", ln=True)
        
        # Table header
        pdf.set_font("Arial", "B", 9)
        pdf.cell(40, 7, "Customer ID", border=1)
        pdf.cell(40, 7, "Purchases (N)", border=1)
        pdf.cell(35, 7, "Sentiment", border=1)
        pdf.cell(40, 7, "Retention Score", border=1, ln=True)
        
        # Table rows
        pdf.set_font("Arial", "", 9)
        for c in customer_data[:10]:
            pdf.cell(40, 6, c["user_id"], border=1)
            pdf.cell(40, 6, f"{c['purchases']:,.0f}", border=1)
            pdf.cell(35, 6, str(c["sentiment"]), border=1)
            pdf.cell(40, 6, str(c["retention"]), border=1, ln=True)
        pdf.ln(5)
        
        # Intent Distribution Section
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, "INTENT DISTRIBUTION", ln=True)
        
        pdf.set_font("Arial", "B", 9)
        pdf.cell(60, 7, "Intent", border=1)
        pdf.cell(40, 7, "Count", border=1, ln=True)
        
        pdf.set_font("Arial", "", 9)
        for intent, count in sorted(intent_counts.items(), key=lambda x: x[1], reverse=True):
            pdf.cell(60, 6, intent, border=1)
            pdf.cell(40, 6, str(count), border=1, ln=True)
        
        # Save PDF
        filename = f"reports/report_{start}_{end}.pdf"
        pdf.output(filename)
        
        abs_path = os.path.abspath(filename)
        logger.info(f"PDF report generated: {abs_path}")
        
        return f"✅ Report generated successfully!\n\nFile: {abs_path}\n\nSummary:\n- Period: {start} to {end}\n- Customers: {len(unique_users)}\n- Messages: {total_messages}\n- Revenue: N{total_revenue:,.0f}"
        
    except Exception as e:
        logger.error(f"Report generation error: {e}", exc_info=True)
        return f"❌ Failed to generate report: {str(e)}"


# Keep legacy function for backwards compatibility
@tool
async def generate_weekly_report(week_start: str) -> str:
    """
    Generate a weekly report (legacy wrapper).
    Calls generate_comprehensive_report with a 7-day range.
    """
    return await generate_comprehensive_report.ainvoke({
        "start_date": week_start,
        "end_date": None
    })

