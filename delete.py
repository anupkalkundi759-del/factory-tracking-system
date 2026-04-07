# =========================================================
# ================= DELETE DATA PAGE =======================
# =========================================================
def show_delete(conn, cur):
    import streamlit as st

    # 🔐 ADMIN ONLY
    if st.session_state.role != "admin":
        st.error("Access denied")
        st.stop()

    st.title("🗑 Delete Data")

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    project_dict = {p[1]: p[0] for p in projects}

    selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    # ================= UNIT =================
    cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s", (project_id,))
    units = cur.fetchall()

    if units:
        unit_dict = {u[1]: u[0] for u in units}
        selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
        unit_id = unit_dict[selected_unit]
    else:
        st.warning("No units")
        st.stop()

    # ================= HOUSE =================
    cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id=%s", (unit_id,))
    houses = cur.fetchall()

    if houses:
        house_dict = {h[1]: h[0] for h in houses}
        selected_house = st.selectbox("Select House", list(house_dict.keys()))
        house_id = house_dict[selected_house]
    else:
        st.warning("No houses")
        st.stop()

    st.markdown("---")
    st.subheader("⚠ Delete Preview")

    # ================= PREVIEW =================
    cur.execute("SELECT COUNT(*) FROM products WHERE house_id=%s", (house_id,))
    product_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tracking_log WHERE house_id=%s", (house_id,))
    tracking_count = cur.fetchone()[0]

    st.info(f"""
    If you delete this house:
    - Products deleted: {product_count}
    - Tracking logs deleted: {tracking_count}
    """)

    # ================= DELETE TYPE =================
    delete_type = st.radio(
        "Select what to delete",
        ["Product", "House", "Unit", "Project"]
    )

    # ================= PRODUCT LIST =================
    if delete_type == "Product":
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
            st.warning("No products found")

    # ================= CONFIRMATION POPUP =================
    if st.button("Proceed to Delete"):

        st.warning("⚠ FINAL CONFIRMATION")

        confirm_text = st.text_input("Type DELETE to confirm")

        if confirm_text == "DELETE":

            try:

                # ================= DELETE PRODUCT =================
                if delete_type == "Product":
                    product_id = product_dict[selected_product]

                    cur.execute("DELETE FROM tracking_log WHERE house_id=%s AND product_id=%s",
                                (house_id, product_id))
                    cur.execute("DELETE FROM products WHERE house_id=%s AND product_id=%s",
                                (house_id, product_id))

                    st.success("Product deleted")

                # ================= DELETE HOUSE =================
                elif delete_type == "House":
                    cur.execute("DELETE FROM tracking_log WHERE house_id=%s", (house_id,))
                    cur.execute("DELETE FROM products WHERE house_id=%s", (house_id,))
                    cur.execute("DELETE FROM houses WHERE house_id=%s", (house_id,))

                    st.success("House deleted")

                # ================= DELETE UNIT =================
                elif delete_type == "Unit":
                    cur.execute("SELECT house_id FROM houses WHERE unit_id=%s", (unit_id,))
                    house_ids = [h[0] for h in cur.fetchall()]

                    for hid in house_ids:
                        cur.execute("DELETE FROM tracking_log WHERE house_id=%s", (hid,))
                        cur.execute("DELETE FROM products WHERE house_id=%s", (hid,))

                    cur.execute("DELETE FROM houses WHERE unit_id=%s", (unit_id,))
                    cur.execute("DELETE FROM units WHERE unit_id=%s", (unit_id,))

                    st.success("Unit deleted")

                # ================= DELETE PROJECT =================
                elif delete_type == "Project":
                    cur.execute("SELECT unit_id FROM units WHERE project_id=%s", (project_id,))
                    unit_ids = [u[0] for u in cur.fetchall()]

                    for uid in unit_ids:
                        cur.execute("SELECT house_id FROM houses WHERE unit_id=%s", (uid,))
                        house_ids = [h[0] for h in cur.fetchall()]

                        for hid in house_ids:
                            cur.execute("DELETE FROM tracking_log WHERE house_id=%s", (hid,))
                            cur.execute("DELETE FROM products WHERE house_id=%s", (hid,))

                        cur.execute("DELETE FROM houses WHERE unit_id=%s", (uid,))
                        cur.execute("DELETE FROM units WHERE unit_id=%s", (uid,))

                    cur.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))

                    st.success("Project deleted")

                conn.commit()
                st.rerun()
