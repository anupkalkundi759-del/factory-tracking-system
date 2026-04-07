# =========================================================
# ===================== TRACKING PAGE ======================
# =========================================================
def show_tracking(conn, cur):
    import streamlit as st

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()

    if projects:
        project_dict = {p[1]: p[0] for p in projects}
        selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    else:
        st.warning("No data available. Please upload Excel below.")
        selected_project = None

    # ================= UNIT =================
    if selected_project:
        project_id = project_dict[selected_project]

        cur.execute(
            "SELECT unit_id, unit_name FROM units WHERE project_id=%s ORDER BY unit_name",
            (project_id,)
        )
        units = cur.fetchall()

        if units:
            unit_dict = {u[1]: u[0] for u in units}
            selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
        else:
            st.warning("No units for this project")
            selected_unit = None
    else:
        selected_unit = None

    # ================= HOUSE =================
    if selected_unit:
        unit_id = unit_dict[selected_unit]

        cur.execute(
            "SELECT house_id, house_no FROM houses WHERE unit_id=%s ORDER BY house_no",
            (unit_id,)
        )
        houses = cur.fetchall()

        if houses:
            house_dict = {h[1]: h[0] for h in houses}
            selected_house = st.selectbox("Select House", list(house_dict.keys()))
        else:
            st.warning("No houses for this unit")
            selected_house = None
    else:
        selected_house = None

    # ================= PRODUCT =================
    if selected_house:
        house_id = house_dict[selected_house]

        cur.execute("""
            SELECT pm.product_id, pm.product_code
            FROM products p
            JOIN products_master pm ON p.product_id = pm.product_id
            WHERE p.house_id = %s
        """, (house_id,))
        products = cur.fetchall()

        if products:
            product_dict = {p[1]: p[0] for p in products}
            selected_product = st.selectbox("Select Product", list(product_dict.keys()))
        else:
            st.warning("No products for this house")
            selected_product = None
    else:
        selected_product = None

    # ================= STAGE =================
    if selected_product:
        product_id = product_dict[selected_product]

        cur.execute("""
            SELECT COALESCE(MAX(s.sequence), 0)
            FROM tracking_log t
            JOIN stages s ON t.stage_id = s.stage_id
            WHERE t.house_id = %s AND t.product_id = %s
        """, (house_id, product_id))

        current_seq = cur.fetchone()[0]
        st.info(f"Current Progress Stage: {current_seq}")

        cur.execute("SELECT stage_id, stage_name, sequence FROM stages ORDER BY sequence")
        all_stages = cur.fetchall()

        stage_names = [s[1] for s in all_stages]
        stage_map = {s[1]: (s[0], s[2]) for s in all_stages}

        selected_stage_name = st.selectbox("Select Stage", stage_names)
        stage_id, selected_sequence = stage_map[selected_stage_name]

        # Validation
        cur.execute("""
            SELECT s.sequence
            FROM tracking_log t
            JOIN stages s ON t.stage_id = s.stage_id
            WHERE t.house_id = %s 
            AND t.product_id = %s 
            AND t.status = 'Completed'
            ORDER BY s.sequence DESC
            LIMIT 1
        """, (house_id, product_id))

        last_completed = cur.fetchone()
        allowed_sequence = last_completed[0] + 1 if last_completed else 1

        if selected_sequence > allowed_sequence:
            st.error("❌ Complete previous stage first")
        else:
            status = st.selectbox("Status", ["Pending", "Started", "Completed"])

            if st.button("Submit"):
                cur.execute("""
                    INSERT INTO tracking_log (house_id, product_id, stage_id, status, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (house_id, product_id, stage_id, status))

                conn.commit()
                st.success("Saved successfully!")
