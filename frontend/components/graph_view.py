"""
PyVis Interactive Network Graph Component.
Renders nodes, relationships, and contagion paths into an interactive physics-enabled canvas.
"""

from typing import Dict, Any
from pyvis.network import Network


COLOR_PALETTE = {
    "Business": "#F59E0B",      # Amber
    "Customer": "#3B82F6",      # Royal Blue
    "Supplier": "#8B5CF6",      # Purple
    "BankAccount": "#10B981",   # Emerald Green
    "Invoice": "#EF4444",       # Crimson Red
    "Obligation": "#DC2626",    # Dark Red
    "Advance": "#F97316",       # Orange
    "Delivery": "#14B8A6",      # Teal
    "Payment": "#06B6D4",       # Cyan
    "Unknown": "#9CA3AF"        # Neutral Gray
}


def generate_network_html(graph_data: Dict[str, Any], height: str = "600px", width: str = "100%") -> str:
    """Generates standalone HTML string for embedding PyVis graph in Streamlit iframe."""
    net = Network(height=height, width=width, bgcolor="#0e1117", font_color="#ffffff", directed=True)
    net.force_atlas_2based(gravity=-50, central_gravity=0.01, spring_length=100, spring_strength=0.08, damping=0.4)

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type", "Unknown")
        label = node.get("label", node_id)
        props = node.get("properties", {})

        color = COLOR_PALETTE.get(node_type, "#9CA3AF")
        size = 28 if node_type == "Business" else (22 if node_type in ("Customer", "Supplier", "BankAccount") else 16)

        # Build tooltip
        tooltip_lines = [f"<b>{node_type}</b>: {label}"]
        for k, v in props.items():
            tooltip_lines.append(f"{k}: {v}")
        title = "<br>".join(tooltip_lines)

        net.add_node(
            node_id,
            label=label,
            title=title,
            color=color,
            size=size,
            shape="dot"
        )

    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        relation = edge.get("relation", "")
        amt = edge.get("amount")
        label = f"{relation}" + (f"\n(₹{amt:,.0f})" if amt else "")

        net.add_edge(
            source,
            target,
            title=f"{relation}: {amt}" if amt else relation,
            label=label if amt else relation,
            color="#4B5563",
            arrows="to"
        )

    # Disable options menu in production UI for clean appearance
    net.set_options("""
    var options = {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.01,
          "springLength": 95,
          "springConstant": 0.08
        },
        "maxVelocity": 40,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      }
    }
    """)

    return net.generate_html()
