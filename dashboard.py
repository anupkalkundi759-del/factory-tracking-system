# =========================================================
# ===================== DASHBOARD ==========================
# =========================================================
def show_dashboard(conn, cur):
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    import plotly.express as px
    import plotly.graph_objects as go

    st.title("📊 Dashboard")

    # =========================================================
    # 🔹 PROJECT OVERVIEW (LATEST STATUS BASED)
    # =========================================================
    st.subheader("🏢 Project Overview")

    cur.execute("""
    WITH latest_tracking AS (
        SELECT DISTINCT ON (house_id, product_id)
            house_id,
            product_id,
            stage_id,
            status
        FROM tracking_log
        ORDER BY house_id, product_id, timestamp DESC
    ),

    product_progress AS (
        SELECT 
            p.house_id,
            p.product_id,
            COALESCE(s.sequence, 0) AS stage_reached
        FROM products p
        LEFT JOIN latest_tracking lt
            ON p.house_id = lt.house_id
            AND p.product_id = lt.product_id
        LEFT JOIN stages s
            ON lt.stage_id = s.stage_id
    )

    SELECT 
        pr.project_name,
        COUNT(DISTINCT p.house_id) AS total_houses,
        COUNT(*) AS total_products,
        COUNT(CASE WHEN stage_reached = 7 THEN 1 END) AS completed_products,
        COUNT(*) - COUNT(CASE WHEN stage_reached = 7 THEN 1 END) AS pending_products,
        ROUND(AVG(stage_reached * 100.0 / 7), 2) AS avg_progress
    FROM product_progress p
    JOIN houses h ON p.house_id = h.house_id
    JOIN units u ON h.unit_id = u.unit_id
    JOIN projects pr ON u.project_id = pr.project_id
    GROUP BY pr.project_name
    ORDER BY pr.project_name;
    """)

    df_proj = pd.DataFrame(cur.fetchall(), columns=[
        "Project", "Total Houses", "Total Products",
        "Completed", "Pending", "Avg Progress"
    ])

    st.dataframe(df_proj, use_container_width=True)

    st.divider()
