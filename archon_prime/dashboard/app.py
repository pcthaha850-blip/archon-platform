# ARCHON_FEAT: dashboard-003
"""
ARCHON PRIME - Streamlit Dashboard
==================================

Real-time monitoring dashboard for the trading platform.

Run with:
    streamlit run archon_prime/dashboard/app.py

Author: ARCHON Development Team
Version: 1.0.0
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone
import time

# Page configuration
st.set_page_config(
    page_title="ARCHON PRIME Dashboard",
    page_icon="assets/logos/archon_prime_logo_1.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import data provider
from archon_prime.dashboard.data_provider import DashboardDataProvider

# Initialize data provider
@st.cache_resource
def get_data_provider():
    return DashboardDataProvider()

provider = get_data_provider()


# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 0.5rem;
    }

    .sub-header {
        font-size: 1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }

    /* Status indicators */
    .status-running { color: #4CAF50; font-weight: bold; }
    .status-stopped { color: #f44336; font-weight: bold; }
    .status-warning { color: #FF9800; font-weight: bold; }

    /* Kill switch button */
    .kill-switch {
        background-color: #f44336 !important;
        color: white !important;
        font-weight: bold !important;
    }

    /* Risk status colors */
    .risk-normal { color: #4CAF50; }
    .risk-caution { color: #FF9800; }
    .risk-warning { color: #f44336; }
    .risk-critical { color: #9C27B0; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.image("assets/logos/archon_prime_logo_1.png", width=200)
    st.markdown("---")

    # System Status
    st.subheader("System Status")
    health = provider.get_system_health()

    status_color = "green" if health["status"] == "OPERATIONAL" else "red"
    st.markdown(f"**Status:** :{status_color}[{health['status']}]")
    st.metric("Uptime", f"{health['uptime_hours']:.1f} hrs")
    st.metric("Events Processed", f"{health['events_processed']:,}")
    st.metric("Latency", f"{health['latency_ms']:.1f} ms")

    st.markdown("---")

    # Auto-refresh
    st.subheader("Settings")
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.slider("Refresh interval (sec)", 5, 60, 10)

    st.markdown("---")

    # Kill Switch
    st.subheader("Emergency Controls")
    if st.button("KILL SWITCH", type="primary", use_container_width=True):
        if provider.trigger_kill_switch():
            st.error("KILL SWITCH ACTIVATED - All trading halted!")
        else:
            st.error("Failed to activate kill switch!")

    st.caption("Immediately halts all trading activity")


# =============================================================================
# MAIN CONTENT
# =============================================================================

# Header
st.markdown('<p class="main-header">ARCHON PRIME</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Plugin-based Real-time Intelligence for Market Execution</p>', unsafe_allow_html=True)

# Account Summary Row
st.markdown("### Account Overview")
account = provider.get_account_summary()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Balance",
        f"${account['balance']:,.2f}",
        delta=f"${account['daily_pnl']:,.2f}",
    )

with col2:
    st.metric(
        "Equity",
        f"${account['equity']:,.2f}",
    )

with col3:
    st.metric(
        "Unrealized P&L",
        f"${account['unrealized_pnl']:,.2f}",
        delta_color="normal" if account['unrealized_pnl'] >= 0 else "inverse",
    )

with col4:
    st.metric(
        "Free Margin",
        f"${account['free_margin']:,.2f}",
    )

with col5:
    st.metric(
        "Margin Level",
        f"{account['margin_level_pct']:,.0f}%",
    )

st.markdown("---")

# Main Charts Row
col_chart, col_risk = st.columns([2, 1])

with col_chart:
    st.markdown("### Equity Curve")

    # Time range selector
    time_range = st.selectbox(
        "Time Range",
        ["24 Hours", "7 Days", "30 Days"],
        index=0,
        label_visibility="collapsed",
    )

    hours_map = {"24 Hours": 24, "7 Days": 168, "30 Days": 720}
    equity_data = provider.get_equity_curve(hours=hours_map[time_range])

    if equity_data:
        df = pd.DataFrame(equity_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Create dual-axis chart
        fig = go.Figure()

        # Equity line
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['equity'],
            name='Equity',
            line=dict(color='#1E88E5', width=2),
            fill='tozeroy',
            fillcolor='rgba(30, 136, 229, 0.1)',
        ))

        # Balance line
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['balance'],
            name='Balance',
            line=dict(color='#4CAF50', width=1, dash='dash'),
        ))

        fig.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            xaxis_title="",
            yaxis_title="USD",
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No equity data available")

with col_risk:
    st.markdown("### Risk Status")

    risk = provider.get_risk_metrics()

    # Risk status indicator
    status_class = f"risk-{risk['risk_status'].lower()}"
    st.markdown(f"**Status:** <span class='{status_class}'>{risk['risk_status']}</span>", unsafe_allow_html=True)

    # Drawdown gauge
    fig_dd = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk['current_drawdown_pct'],
        title={'text': "Current Drawdown"},
        number={'suffix': "%"},
        gauge={
            'axis': {'range': [0, 15], 'tickwidth': 1},
            'bar': {'color': "#1E88E5"},
            'steps': [
                {'range': [0, 5], 'color': "#E8F5E9"},
                {'range': [5, 8], 'color': "#FFF3E0"},
                {'range': [8, 10], 'color': "#FFEBEE"},
                {'range': [10, 15], 'color': "#F3E5F5"},
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 10,
            },
        },
    ))

    fig_dd.update_layout(height=200, margin=dict(l=20, r=20, t=40, b=0))
    st.plotly_chart(fig_dd, use_container_width=True)

    # Risk metrics
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.metric("Max DD", f"{risk['max_drawdown_pct']:.1f}%")
        st.metric("Daily VaR", f"${risk['daily_var']:.0f}")
    with col_r2:
        st.metric("Exposure", f"{risk['exposure_pct']:.1f}%")
        st.metric("Corr Risk", f"{risk['correlation_risk']:.2f}")

st.markdown("---")

# Strategy Performance Row
st.markdown("### Strategy Performance")

strategies = provider.get_strategy_stats()

cols = st.columns(len(strategies))

for i, strategy in enumerate(strategies):
    with cols[i]:
        status_icon = "" if strategy['status'] == "RUNNING" else ""
        st.markdown(f"**{strategy['name']}** {status_icon}")

        if strategy['enabled']:
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.metric("Trades", strategy['trades'])
                st.metric("Win Rate", f"{strategy['win_rate']:.1f}%")
            with col_s2:
                st.metric("P&L", f"${strategy['pnl']:,.2f}")
                st.metric("Sharpe", f"{strategy['sharpe']:.2f}")
        else:
            st.info("Strategy disabled")

        # Toggle button
        if st.button(
            "Disable" if strategy['enabled'] else "Enable",
            key=f"toggle_{i}",
            use_container_width=True,
        ):
            provider.toggle_plugin(strategy['name'], not strategy['enabled'])
            st.rerun()

st.markdown("---")

# Positions and Trades Row
col_pos, col_trades = st.columns(2)

with col_pos:
    st.markdown("### Open Positions")

    positions = provider.get_open_positions()

    if positions:
        df_pos = pd.DataFrame(positions)
        df_pos['direction'] = df_pos['direction'].apply(
            lambda x: f" {x}" if x == "BUY" else f" {x}"
        )
        df_pos['unrealized_pnl'] = df_pos['unrealized_pnl'].apply(
            lambda x: f"${x:+,.2f}"
        )

        st.dataframe(
            df_pos[['ticket', 'symbol', 'direction', 'volume', 'entry_price', 'current_price', 'unrealized_pnl']],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No open positions")

with col_trades:
    st.markdown("### Recent Trades")

    trades = provider.get_recent_trades(limit=10)

    if trades:
        df_trades = pd.DataFrame(trades)
        df_trades['direction'] = df_trades['direction'].apply(
            lambda x: f" {x}" if x == "BUY" else f" {x}"
        )
        df_trades['pnl'] = df_trades['pnl'].apply(
            lambda x: f"${x:+,.2f}"
        )

        st.dataframe(
            df_trades[['ticket', 'symbol', 'direction', 'volume', 'pnl']],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No recent trades")

st.markdown("---")

# Plugin Status Row
st.markdown("### Plugin Status")

plugins = provider.get_plugin_status()

# Group by category
categories = {}
for plugin in plugins:
    cat = plugin['category']
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(plugin)

cols = st.columns(len(categories))

for i, (category, cat_plugins) in enumerate(categories.items()):
    with cols[i]:
        st.markdown(f"**{category}**")
        for plugin in cat_plugins:
            health_icon = "" if plugin['health'] == "HEALTHY" else ""
            status_color = "green" if plugin['status'] in ["RUNNING", "CONNECTED"] else "gray"
            st.markdown(f"{health_icon} :{status_color}[{plugin['name']}]")

# Footer
st.markdown("---")
st.markdown(
    f"<center><small>ARCHON PRIME v1.0.0 | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</small></center>",
    unsafe_allow_html=True,
)

# Auto-refresh logic
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
