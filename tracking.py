def show_tracking(conn, cur):
    import streamlit as st

    st.title("🏭 Production Tracker")

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()

    if not projects:
        st.warning("No data available")
        return

    project_dict = {p[1]: p[0] for p in projects}
    selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    # ================= UNIT =================
    cur.execute("""
        SELECT unit_id, unit_name 
        FROM units 
        WHERE project_id=%s 
        ORDER BY unit_name
    """, (project_id,))
    units = cur.fetchall()

    if not units:
        st.warning("No units")
        return

    unit_dict = {u[1]: u[0] for u in units}
    selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
    unit_id = unit_dict[selected_unit]

    # ================= HOUSE =================
    cur.execute("""
        SELECT house_id, house_no 
        FROM houses 
        WHERE unit_id=%s 
        ORDER BY house_no
    """, (unit_id,))
    houses = cur.fetchall()

    if not houses:
        st.warning("No houses")
        return

    house_dict = {h[1]: h[0] for h in houses}
    selected_house = st.selectbox("Select House", list(house_dict.keys()))
    house_id = house_dict[selected_house]

    # ================= PRODUCT (WITH ORIENTATION) =================
    cur.execute("""
        SELECT pm.product_id, pm.product_code, p.orientation
        FROM products p
        JOIN products_master pm ON p.product_id = pm.product_id
        WHERE p.house_id = %s
        ORDER BY pm.product_code, p.orientation
    """, (house_id,))
    products = cur.fetchall()

    if not products:
        st.warning("No products")
        return

    product_display = [
        f"{p[1]} ({p[2] if p[2] else '-'})" for p in products
    ]

    product_map = {
        f"{p[1]} ({p[2] if p[2] else '-'})": (p[0], p[2])
        for p in products
    }

    selected_product = st.selectbox("Select Product", product_display)
    product_id, orientation = product_map[selected_product]

    # ================= CURRENT STAGE =================
    cur.execute("""
        SELECT COALESCE(MAX(s.sequence), 0)
        FROM tracking_log t
        JOIN stages s ON t.stage_id = s.stage_id
        WHERE t.house_id = %s 
        AND t.product_id = %s
        AND COALESCE(t.orientation,'') = COALESCE(%s,'')
    """, (house_id, product_id, orientation))

    current_seq = cur.fetchone()[0]
    st.info(f"Completed Stage: {current_seq}")

    # ================= STAGE =================
    cur.execute("SELECT stage_id, stage_name, sequence FROM stages ORDER BY sequence")
    stages = cur.fetchall()

    stage_map = {s[1]: (s[0], s[2]) for s in stages}
    selected_stage_name = st.selectbox("Select Stage", list(stage_map.keys()))
    stage_id, selected_seq = stage_map[selected_stage_name]

    # ================= VALIDATION =================
    cur.execute("""
        SELECT MAX(s.sequence)
        FROM tracking_log t
        JOIN stages s ON t.stage_id = s.stage_id
        WHERE t.house_id = %s 
        AND t.product_id = %s
        AND COALESCE(t.orientation,'') = COALESCE(%s,'')
        AND t.status = 'Completed'
    """, (house_id, product_id, orientation))

    last_completed = cur.fetchone()[0]
    allowed_seq = (last_completed or 0) + 1

    if selected_seq > allowed_seq:
        st.error("❌ Complete previous stage first")
        return

    # ================= STATUS =================
    status = st.selectbox("Status", ["Started", "In Progress", "Completed"])

    # ================= SAVE =================
    if st.button("Submit"):
        try:
            cur.execute("""
                INSERT INTO tracking_log 
                (house_id, product_id, stage_id, status, orientation, timestamp)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (house_id, product_id, stage_id, status, orientation))

            conn.commit()
            st.success("✅ Saved successfully")

        except Exception as e:
            st.error(f"Error: {e}")
