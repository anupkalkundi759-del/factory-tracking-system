def show_dashboard(conn, cur):
    import streamlit as st
    import pandas as pd

    st.title("📊 Dashboard")
    st.subheader("🏢 Project Overview")

    cur.execute("""
    WITH latest_tracking AS (
        SELECT DISTINCT ON (house_id, product_id)
            house_id,
            product_id,
            stage_id,
            timestamp
        FROM tracking_log
        ORDER BY house_id, product_id, timestamp DESC
    ),

    product_data AS (
        SELECT 
            p.house_id,
            p.product_id,
            p.quantity,
            COALESCE(s.sequence, 0) AS stage_reached,
            lt.timestamp
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

        COALESCE(SUM(p.quantity), 0) AS total_products,

        -- COMPLETED (S6 and S7)
        COALESCE(SUM(CASE WHEN stage_reached >= 6 THEN p.quantity ELSE 0 END), 0) AS completed,

        -- DISPATCHED (S7 only)
        COALESCE(SUM(CASE WHEN stage_reached = 7 THEN p.quantity ELSE 0 END), 0) AS dispatched,

        -- PENDING (not dispatched)
        COALESCE(SUM(p.quantity), 0) - 
        COALESCE(SUM(CASE WHEN stage_reached = 7 THEN p.quantity ELSE 0 END), 0) AS pending,

        -- LAST DISPATCH TIME
        MAX(CASE WHEN stage_reached = 7 THEN timestamp END) AS last_dispatch_time

    FROM product_data p
    JOIN houses h ON p.house_id = h.house_id
    JOIN units u ON h.unit_id = u.unit_id
    JOIN projects pr ON u.project_id = pr.project_id

    GROUP BY pr.project_name
    ORDER BY pr.project_name;
    """)

    df_proj = pd.DataFrame(cur.fetchall(), columns=[
        "Project",
        "Total Houses",
        "Total Products",
        "Completed",
        "Dispatched",
        "Pending",
        "Last Dispatch Time"
    ])

    st.dataframe(df_proj, use_container_width=True)

    st.divider()
