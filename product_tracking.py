def show_product_tracking(conn, cur):
    import streamlit as st
    import pandas as pd

    st.title("🔍 Product Tracking")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    project_dict = {p[1]: p[0] for p in projects}

    selected_project = col1.selectbox("Project", ["All"] + list(project_dict.keys()))

    # ================= UNIT =================
    if selected_project == "All":
        cur.execute("SELECT unit_id, unit_name FROM units ORDER BY unit_name")
    else:
        cur.execute("""
            SELECT unit_id, unit_name
            FROM units
            WHERE project_id = %s
        """, (project_dict[selected_project],))

    units = cur.fetchall()
    unit_dict = {u[1]: u[0] for u in units}
    selected_unit = col2.selectbox("Unit", ["All"] + list(unit_dict.keys()))

    # ================= HOUSE =================
    if selected_unit == "All":
        if selected_project == "All":
            cur.execute("SELECT house_id, house_no FROM houses")
        else:
            cur.execute("""
                SELECT h.house_id, h.house_no
                FROM houses h
                JOIN units u ON h.unit_id = u.unit_id
                WHERE u.project_id = %s
            """, (project_dict[selected_project],))
    else:
        cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id = %s",
                    (unit_dict[selected_unit],))

    houses = cur.fetchall()
    house_dict = {h[1]: h[0] for h in houses}
    selected_house = col3.selectbox("House", ["All"] + list(house_dict.keys()))

    # ================= STATUS =================
    selected_status = col4.selectbox("Status", ["All", "Not Started", "Started", "Completed"])

    # ================= STAGE =================
    cur.execute("SELECT stage_name FROM stages ORDER BY sequence")
    stages = [s[0] for s in cur.fetchall()]
    selected_stage = col5.selectbox("Stage", ["All"] + stages)

    # ================= SEARCH =================
    search = col6.text_input("Search")

    # ================= QUERY =================
    query = """
    SELECT 
        pm.product_code,
        pm.type,
        COALESCE(p.orientation, '-') AS orientation,
        p.quantity,
        pr.project_name,
        u.unit_name,
        h.house_no,
        COALESCE(s.stage_name, 'Not Started') AS stage,
        COALESCE(t.status, 'Not Started') AS status,
        COALESCE(s.sequence, 0) AS stage_seq,
        t.timestamp

    FROM products p
    JOIN products_master pm ON p.product_id = pm.product_id
    JOIN houses h ON p.house_id = h.house_id
    JOIN units u ON h.unit_id = u.unit_id
    JOIN projects pr ON u.project_id = pr.project_id

    LEFT JOIN LATERAL (
        SELECT t.stage_id, t.status, t.timestamp, t.orientation
        FROM tracking_log t
        WHERE t.house_id = p.house_id
        AND t.product_id = p.product_id
        AND COALESCE(t.orientation, '') = COALESCE(p.orientation, '')
        ORDER BY t.timestamp DESC
        LIMIT 1
    ) t ON TRUE

    LEFT JOIN stages s ON t.stage_id = s.stage_id
    WHERE 1=1
    """

    params = []

    if selected_project != "All":
        query += " AND pr.project_name = %s"
        params.append(selected_project)

    if selected_unit != "All":
        query += " AND u.unit_name = %s"
        params.append(selected_unit)

    if selected_house != "All":
        query += " AND h.house_no = %s"
        params.append(selected_house)

    if selected_status != "All":
        query += " AND COALESCE(t.status, 'Not Started') = %s"
        params.append(selected_status)

    if selected_stage != "All":
        query += " AND COALESCE(s.stage_name, 'Not Started') = %s"
        params.append(selected_stage)

    if search:
        query += " AND pm.product_code ILIKE %s"
        params.append(f"%{search}%")

    query += " ORDER BY pm.product_code, p.orientation"

    cur.execute(query, tuple(params))
    data = cur.fetchall()

    df = pd.DataFrame(data, columns=[
        "Product", "Type", "Orientation", "Qty",
        "Project", "Unit", "House",
        "Stage", "Status", "Stage Seq", "Last Update"
    ])

    # ================= DATE + TIME COMBINED =================
    df["Last Update"] = pd.to_datetime(df["Last Update"], errors="coerce")
    df["Date & Time"] = df["Last Update"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # ================= PROGRESS =================
    df["Progress"] = (df["Stage Seq"] / 7 * 100).astype(int).astype(str) + "%"

    df_display = df.drop(columns=["Stage Seq", "Last Update"])

    st.dataframe(df_display, use_container_width=True)
