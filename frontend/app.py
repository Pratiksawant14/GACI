"""
Streamlit Web Application for Wholesale MSME Cash-Flow Intelligence.
Provides executive KPI dashboards, cash blockage diagnostics, interactive PyVis graph,
forward cash-flow deficit projections, and grounded AI agent conversational explainability.
"""

import sys
import os
import io
from datetime import date, datetime
from typing import Dict, Any, List
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is in sys.path for direct module resolution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from frontend.api_client import ApiClient
    from frontend.components.graph_view import generate_network_html, COLOR_PALETTE
except ModuleNotFoundError:
    from api_client import ApiClient
    from components.graph_view import generate_network_html, COLOR_PALETTE

# Page Configuration
st.set_page_config(
    page_title="Cash-Flow Intelligence System | MSME Decision Support",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark-Mode Modern Design)
st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #3b82f6;
        margin-bottom: 15px;
    }
    .metric-card-danger {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #ef4444;
        margin-bottom: 15px;
    }
    .metric-card-warning {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #f59e0b;
        margin-bottom: 15px;
    }
    .metric-card-success {
        background: #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 4px solid #10b981;
        margin-bottom: 15px;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.75rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-danger { background: #7f1d1d; color: #fecaca; }
    .badge-warning { background: #78350f; color: #fef3c7; }
    .badge-success { background: #064e3b; color: #a7f3d0; }
    .badge-info { background: #1e3a8a; color: #bfdbfe; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


api = get_client()

# Sidebar: System Controls & Connectivity Status
with st.sidebar:
    st.title("💹 MSME Cash Intelligence")
    st.markdown("Decision-support platform for wholesale working capital & contagion risk.")
    st.divider()

    # Health Check
    ready_data = api.check_ready()
    db_ok = ready_data.get("database_connected", False)
    neo_ok = ready_data.get("neo4j_connected", False)

    st.subheader("System Infrastructure")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown(f"**Ledger DB:** {'🟢 Active' if db_ok else '🔴 Offline'}")
    with col_s2:
        st.markdown(f"**Neo4j Graph:** {'🟢 Online' if neo_ok else '🟡 Fallback'}")

    st.divider()

    # Reference Date Filter
    as_of_date = st.date_input("Analysis Reference Date", value=date(2026, 10, 23))

    st.divider()
    st.subheader("Quick Actions")

    if st.button("🔄 Sync Business Graph", use_container_width=True):
        try:
            with st.spinner("Synchronizing PostgreSQL ledger to Graph..."):
                sync_res = api.sync_graph()
                st.success(f"Graph synced! {sync_res.get('synced_nodes', 0)} nodes updated.")
        except Exception as exc:
            st.error(f"Sync failed: {exc}")

    if st.button("📥 Load Wholesale Sample Data", use_container_width=True):
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "data", "samples")
        files_to_load = [
            ("customers.csv", "customers"),
            ("suppliers.csv", "suppliers"),
            ("bank_accounts.csv", "bank_accounts"),
            ("invoices.csv", "invoices"),
            ("payments.csv", "payments"),
            ("advances.csv", "advances"),
            ("deliveries.csv", "deliveries"),
            ("obligations.csv", "obligations"),
        ]
        loaded_count = 0
        with st.spinner("Ingesting comprehensive wholesale sample dataset..."):
            for fname, ttype in files_to_load:
                fpath = os.path.abspath(os.path.join(sample_dir, fname))
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        api.upload_file(fname, f.read(), table_type=ttype)
                        loaded_count += 1
            st.success(f"Successfully ingested {loaded_count} ledger files & projected graph!")

# Main Tabs
tab_exec, tab_block, tab_graph, tab_fore, tab_agent, tab_ingest = st.tabs([
    "📊 Executive KPIs",
    "🚫 Cash Blockages",
    "🕸️ Business Graph",
    "📈 Forward Trajectory",
    "🤖 AI Financial Advisor",
    "📂 Data Ingestion"
])

# TAB 1: EXECUTIVE KPIS
with tab_exec:
    st.header("Executive Working Capital & Liquidity Overview")

    try:
        summary = api.get_cash_summary(as_of=as_of_date)
        liquid = float(summary.get("liquid_cash") or 0.0)
        overdue = float(summary.get("total_overdue_receivables") or 0.0)
        stranded = float(summary.get("total_stranded_advances") or 0.0)
        bounced = float(summary.get("bounced_cheque_exposure") or 0.0)
        ob_15d = float(summary.get("upcoming_obligations_15d") or 0.0)
        net_15d = float(summary.get("projected_net_position_15d") or 0.0)
        net_30d = float(summary.get("projected_net_position_30d") or 0.0)

        # Deficit Warning Banner
        if net_15d < 0 or net_30d < 0:
            st.error(f"⚠️ **LIQUIDITY DEFICIT ALERT:** Projected 15-day balance is ₹{net_15d:,.2f} (30-day: ₹{net_30d:,.2f}). Immediate collection required to cover scheduled obligations.")

        # Metric Cards Row
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""
            <div class="metric-card-success">
                <div class="metric-label">Verified Liquid Cash</div>
                <div class="metric-value">₹{liquid:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card-danger">
                <div class="metric-label">Overdue Receivables</div>
                <div class="metric-value">₹{overdue:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card-warning">
                <div class="metric-label">Stranded Advances</div>
                <div class="metric-value">₹{stranded:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with c4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">15-Day Obligations</div>
                <div class="metric-value">₹{ob_15d:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        st.subheader("Accounts Receivable Aging Distribution")
        aging_data = api.get_aging_buckets(as_of=as_of_date)
        if aging_data:
            df_aging = pd.DataFrame(aging_data)
            df_aging["total_amount"] = pd.to_numeric(df_aging["total_amount"], errors="coerce").fillna(0.0)
            st.bar_chart(df_aging.set_index("bucket")["total_amount"])
        else:
            st.info("No overdue accounts receivable records found.")

    except Exception as exc:
        st.warning(f"Could not load executive summary from API: {exc}. Please verify backend server is running.")

# TAB 2: CASH BLOCKAGES
with tab_block:
    st.header("Cash Blockage Diagnostic & Severity Rankings")
    st.markdown("Prioritized table of uncollected capital, stranded supplier disbursements, and bounced cheques.")

    try:
        blockages = api.get_blockages(as_of=as_of_date)
        if blockages:
            df_blk = pd.DataFrame(blockages)
            df_blk["amount"] = pd.to_numeric(df_blk["amount"], errors="coerce").fillna(0.0)
            df_blk["severity_score"] = pd.to_numeric(df_blk["severity_score"], errors="coerce").fillna(0.0)
            df_blk["days_overdue"] = pd.to_numeric(df_blk["days_overdue"], errors="coerce").fillna(0)

            filter_cat = st.selectbox("Filter Blockage Category", ["ALL"] + sorted(list(df_blk["category"].unique())))
            if filter_cat != "ALL":
                df_blk = df_blk[df_blk["category"] == filter_cat]

            # Display Table
            display_cols = ["blockage_id", "category", "entity_name", "amount", "days_overdue", "severity_score", "status"]
            st.dataframe(
                df_blk[display_cols].sort_values(by="severity_score", ascending=False),
                use_container_width=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount (INR)", format="₹%.2f"),
                    "severity_score": st.column_config.NumberColumn("Severity Score", format="%.1f"),
                }
            )

            # Expandable Details
            st.subheader("Detailed Evidence & Actionable Recovery Plans")
            for _, b in df_blk.iterrows():
                with st.expander(f"📌 {b['blockage_id']} — {b['entity_name']} (₹{float(b['amount']):,.2f})"):
                    st.markdown(f"**Evidence:** {b.get('evidence_summary', 'N/A')}")
                    st.markdown(f"**Suggested Recovery Action:** `{b.get('suggested_action', 'Contact counterparty')}`")
        else:
            st.info("No cash blockages currently identified.")
    except Exception as exc:
        st.warning(f"Failed to fetch blockages: {exc}")

# TAB 3: BUSINESS GRAPH & CONTAGION
with tab_graph:
    st.header("Temporal Business Graph & Liquidity Contagion Paths")
    st.markdown("Visual topology linking overdue customer receivables directly to scheduled loan, tax, and supplier liabilities.")

    col_g1, col_g2 = st.columns([3, 2])

    with col_g1:
        st.subheader("Interactive Business Network Canvas")
        try:
            subgraph = api.get_subgraph()
            if subgraph and subgraph.get("nodes"):
                html_canvas = generate_network_html(subgraph, height="550px")
                components.html(html_canvas, height=570, scrolling=False)
            else:
                st.info("No graph nodes available. Ingest ledger data and trigger graph sync.")
        except Exception as exc:
            st.error(f"Error rendering network visualization: {exc}")

    with col_g2:
        st.subheader("Liquidity Contagion Chains")
        try:
            paths = api.get_contagion_paths(as_of=as_of_date, horizon_days=15)
            if paths:
                for idx, p in enumerate(paths, 1):
                    st.markdown(f"""
                    <div style="background:#1e293b; border-left:3px solid #ef4444; padding:12px; border-radius:6px; margin-bottom:10px;">
                        <span class="badge badge-danger">CONTAGION PATH #{idx}</span><br>
                        <b>{p.get('customer_name')}</b> overdue invoice of ₹{float(p.get('invoice_unpaid', 0)):,.2f}<br>
                        ↳ Direct deficit risk for <b>{p.get('obligation_name')}</b> (₹{float(p.get('obligation_amount', 0)):,.2f} due on {p.get('obligation_due_date')})
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("No active contagion paths threatening near-term obligations.")
        except Exception as exc:
            st.warning(f"Could not load contagion paths: {exc}")

        st.subheader("Top Counterparty Concentration Exposure")
        try:
            concentrations = api.get_concentrations()
            if concentrations:
                df_conc = pd.DataFrame(concentrations)
                for num_col in ["blocked_amount", "concentration_percentage"]:
                    if num_col in df_conc.columns:
                        df_conc[num_col] = pd.to_numeric(df_conc[num_col], errors="coerce").fillna(0.0)
                st.dataframe(
                    df_conc,
                    use_container_width=True,
                    column_config={
                        "blocked_amount": st.column_config.NumberColumn("Blocked (INR)", format="₹%.2f"),
                        "concentration_percentage": st.column_config.NumberColumn("Share (%)", format="%.1f%%")
                    }
                )
        except Exception as exc:
            st.warning(f"Could not load concentration metrics: {exc}")

# TAB 4: FORWARD TRAJECTORY
with tab_fore:
    st.header("Forward Daily Cash-Flow Trajectory (30-Day Horizon)")

    try:
        projection = api.get_cash_projection(as_of=as_of_date, horizon_days=30)
        daily = projection.get("daily_forecasts", [])
        first_deficit = projection.get("first_deficit_date")
        max_deficit = float(projection.get("max_deficit_amount") or 0.0)

        if first_deficit:
            st.error(f"🚨 **First Liquidity Deficit Date:** {first_deficit} | Maximum Capital Shortfall: ₹{max_deficit:,.2f}")
        else:
            st.success("✅ Projected closing cash balances remain positive across the entire 30-day forecast horizon.")

        if daily:
            df_daily = pd.DataFrame(daily)
            for d_col in ["opening", "inflows", "outflows", "closing"]:
                if d_col in df_daily.columns:
                    df_daily[d_col] = pd.to_numeric(df_daily[d_col], errors="coerce").fillna(0.0)

            st.line_chart(df_daily.set_index("date")["closing"])

            with st.expander("View Daily Cash Trajectory Ledger"):
                st.dataframe(
                    df_daily[["date", "opening", "inflows", "outflows", "closing", "has_deficit"]],
                    use_container_width=True,
                    column_config={
                        "opening": st.column_config.NumberColumn("Opening", format="₹%.2f"),
                        "inflows": st.column_config.NumberColumn("Inflows", format="₹%.2f"),
                        "outflows": st.column_config.NumberColumn("Outflows", format="₹%.2f"),
                        "closing": st.column_config.NumberColumn("Closing", format="₹%.2f"),
                    }
                )
    except Exception as exc:
        st.warning(f"Could not calculate forward cash projection: {exc}")

# TAB 5: AI AGENT CONSOLE
with tab_agent:
    st.header("AI Financial Advisor & Explainability Console")
    st.markdown("Ask natural language questions regarding where working capital is stuck and how obligations will be affected.")

    # Preset Sample Queries
    col_p1, col_p2, col_p3 = st.columns(3)
    preset_query = None
    with col_p1:
        if st.button("❓ Where is our cash stuck right now?", use_container_width=True):
            preset_query = "Where is our cash stuck right now?"
    with col_p2:
        if st.button("❓ Can we pay our upcoming loan EMI & GST?", use_container_width=True):
            preset_query = "Can we pay our upcoming loan EMI and GST?"
    with col_p3:
        if st.button("❓ Which customers have highest concentration risk?", use_container_width=True):
            preset_query = "Which customers have the highest concentration risk?"

    user_query = st.text_input("Enter your question for the financial agent:", value=preset_query or "")

    if st.button("🚀 Analyze & Explain", type="primary") or preset_query:
        if user_query.strip():
            with st.spinner("Agent running 4-stage LangGraph diagnostic workflow..."):
                try:
                    res = api.query_agent(query=user_query, as_of=as_of_date)
                    st.markdown(f"**Intent Classified:** `{res.get('intent', 'general').upper()}` | **Engine Provider:** `{res.get('provider_used', 'LLM')}` | **Latency:** `{res.get('latency_ms', 0):.0f}ms`")
                    st.markdown(res.get("answer", "No response generated."))

                    citations = res.get("citations", [])
                    if citations:
                        with st.expander(f"🔍 Canonical Database Records Cited ({len(citations)} references)"):
                            st.dataframe(pd.DataFrame(citations), use_container_width=True)
                except Exception as exc:
                    st.error(f"Agent execution encountered an error: {exc}")
        else:
            st.warning("Please enter a question.")

    # Live Provider Diagnostics Expander
    with st.expander("🔬 Live Multi-Provider LLM Engine Health & Network Ping", expanded=False):
        st.markdown("Test the live external APIs (OpenRouter, Google Gemini, Hugging Face) directly with real HTTP requests and inspect raw round-trip latency.")
        if st.button("⚡ Test All Provider APIs Now"):
            with st.spinner("Pinging external LLM providers with real test payloads..."):
                try:
                    h_res = api.get_llm_health()
                    cols = st.columns(4)
                    for i, (prov, pdata) in enumerate(h_res.items()):
                        with cols[i % 4]:
                            status_val = pdata.get("status", "UNKNOWN")
                            badge = "🟢" if "ONLINE" in status_val else "⚠️"
                            st.markdown(f"**{badge} {prov.upper()}**")
                            st.markdown(f"Status: `{status_val}`")
                            st.markdown(f"Model: `{pdata.get('model', 'N/A')}`")
                            st.markdown(f"Latency: `{pdata.get('latency_ms', 0)}ms`")
                            if "response" in pdata:
                                st.caption(f"Raw Output: {pdata['response']}")
                            elif "error" in pdata:
                                st.caption(f"Error: {pdata['error'][:100]}...")
                except Exception as exc:
                    st.error(f"Health check failed: {exc}")

# TAB 6: DATA INGESTION
with tab_ingest:
    st.header("Wholesale Ledger Ingestion & Audit Pipeline")
    st.markdown("Upload bank statements, sales invoices, advance disbursements, delivery receipts, and obligations.")

    uploaded_files = st.file_uploader(
        "Upload CSV or Excel Files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True
    )

    col_i1, col_i2 = st.columns([2, 1])
    with col_i1:
        manual_type = st.selectbox(
            "Explicit Table Type (Leave as AUTO if uploading standard filenames)",
            ["AUTO", "customers", "suppliers", "bank_accounts", "invoices", "payments", "advances", "deliveries", "obligations"]
        )
    with col_i2:
        st.write("")
        st.write("")
        upload_btn = st.button("📤 Process & Ingest Files", type="primary", use_container_width=True)

    if upload_btn and uploaded_files:
        with st.spinner("Validating chronological consistency and persisting to PostgreSQL..."):
            for ufile in uploaded_files:
                ttype = None if manual_type == "AUTO" else manual_type
                try:
                    res = api.upload_file(ufile.name, ufile.read(), table_type=ttype)
                    st.success(f"File `{ufile.name}` successfully ingested!")
                    reports = res.get("reports", [])
                    for rep in reports:
                        st.markdown(f"* **Table:** `{rep.get('table_name')}` | Valid: **{rep.get('valid_rows')}** rows | Errors: **{rep.get('error_rows')}** rows")
                        if rep.get("errors"):
                            st.warning(f"Validation warnings: {rep['errors']}")
                except Exception as exc:
                    st.error(f"Failed to ingest `{ufile.name}`: {exc}")

    st.markdown("---")
    st.subheader("🧹 Clean Slate & Reset (Zero Records Testing)")
    st.markdown("Wipe all transactional ledgers to start from a **100% clean, blank slate (0 records)** so you can test your own custom real data.")

    col_rst1, col_rst2 = st.columns([3, 1])
    with col_rst1:
        st.caption("This will purge all customers, suppliers, bank accounts, invoices, payments, advances, and obligations for the active business.")
    with col_rst2:
        if st.button("⚠️ Wipe All Data (0 Records)", type="secondary", use_container_width=True):
            try:
                rst_res = api.reset_database()
                st.success(rst_res.get("message", "Database successfully wiped!"))
                st.rerun()
            except Exception as exc:
                st.error(f"Database reset failed: {exc}")
