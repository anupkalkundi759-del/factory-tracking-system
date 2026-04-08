# =========================================================
# ================= DELETE DATA PAGE =======================
# =========================================================
def show_delete(conn, cur):
    import streamlit as st

    if st.session_state.role != "admin":
        st.error("Access denied")
        st.stop()

    st.title("🗑 Delete Data")

    # ================= DELETE TYPE =================
    delete_type = st.radio(
        "Select what to delete",
        ["Project", "Unit", "House", "Product"]
    )

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()

    if not projects:
        st.warning("No projects found")
        return

    project_dict = {p[1]: p[0] for p in projects}
    selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    unit_id = None
    house_id = None
    product_id = None

    # ================= UNIT =================
    if delete_type in ["Unit", "House", "Product"]:
        cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s", (project_id,))
        units = cur.fetchall()

        if units:
            unit_dict = {u[1]: u[0] for u in units}
            selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
            unit_id = unit_dict[selected_unit]
        else:
            st.warning("No units found")

    # ================= HOUSE =================
    if delete_type in ["House", "Product"] and unit_id:
        cur.execute("SELECT house_id, house_name FROM houses WHERE unit_id=%s", (unit_id,))
        houses = cur.fetchall()

        if houses:
            house_dict = {h[1]: h[0] for h in houses}
            selected_house = st.selectbox("Select House", list(house_dict.keys()))
            house_id = house_dict[selected_house]
        else:
            st.warning("No houses found")

    # ================= PRODUCT =================
    if delete_type == "Product" and house_id:
        cur.execute("""
            SELECT pm.product_id, pm.product_name
            FROM products p
            JOIN products_master pm ON p.product_id = pm.product_id
            WHERE p.house_id = %s
        """, (house_id,))
        products = cur.fetchall()

        if products:
            product_dict = {p[1]: p[0] for p in products}
            selected_product = st.selectbox("Select Product", list(product_dict.keys()))
            product_id = product_dict[selected_product]
        else:
            st.warning("No products found")

    # ================= PREVIEW =================
    st.markdown("---")
    st.subheader("⚠ Delete Preview")

    if delete_type == "Project":
        st.info("This will delete entire project (units, houses, products)")
    elif delete_type == "Unit":
        st.info("This will delete unit and all its houses & products")
    elif delete_type == "House":
        st.info("This will delete house and its products")
    elif delete_type == "Product":
        st.info("This will delete only selected product")

    # ================= CONFIRM =================
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if st.button("Proceed to Delete"):
        st.session_state.confirm_delete = True

    if st.session_state.confirm_delete:

        confirm_text = st.text_input("Type DELETE to confirm")

        if confirm_text == "DELETE":

            try:

                # ================= PRODUCT =================
                if delete_type == "Product" and house_id and product_id:
                    cur.execute("""
                        DELETE FROM products
                        WHERE house_id=%s AND product_id=%s
                    """, (house_id, product_id))

                # ================= HOUSE =================
                elif delete_type == "House" and house_id:
                    cur.execute("DELETE FROM products WHERE house_id=%s", (house_id,))
                    cur.execute("DELETE FROM houses WHERE house_id=%s", (house_id,))

                # ================= UNIT =================
                elif delete_type == "Unit" and unit_id:

                    # 🔴 FIX: delete unit_products first
                    cur.execute("""
                        DELETE FROM unit_products
                        WHERE unit_id = %s
                    """, (unit_id,))

                    cur.execute("""
                        DELETE FROM products
                        WHERE house_id IN (
                            SELECT house_id FROM houses WHERE unit_id=%s
                        )
                    """, (unit_id,))

                    cur.execute("DELETE FROM houses WHERE unit_id=%s", (unit_id,))
                    cur.execute("DELETE FROM units WHERE unit_id=%s", (unit_id,))

                # ================= PROJECT =================
                elif delete_type == "Project":

                    # 🔴 FIX: delete unit_products first
                    cur.execute("""
                        DELETE FROM unit_products
                        WHERE unit_id IN (
                            SELECT unit_id FROM units WHERE project_id=%s
                        )
                    """, (project_id,))

                    cur.execute("""
                        DELETE FROM products
                        WHERE house_id IN (
                            SELECT h.house_id
                            FROM houses h
                            JOIN units u ON h.unit_id = u.unit_id
                            WHERE u.project_id = %s
                        )
                    """, (project_id,))

                    cur.execute("""
                        DELETE FROM houses
                        WHERE unit_id IN (
                            SELECT unit_id FROM units WHERE project_id = %s
                        )
                    """, (project_id,))

                    cur.execute("DELETE FROM units WHERE project_id=%s", (project_id,))
                    cur.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))

                conn.commit()
                st.success("Deleted successfully")

                st.session_state.confirm_delete = False
                st.rerun()

            except Exception as e:
                conn.rollback()
                st.error(f"Error: {e}")
