import streamlit as st
import psycopg2
import pandas as pd
from io import StringIO
import time

from tracking import show_tracking
from dashboard import show_dashboard
from product_tracking import show_product_tracking

# ==============================
# 🔐 LOGIN SYSTEM
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

def login():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        users = {
            "worker": {"password": "123", "role": "worker"},
            "admin": {"password": "admin@123", "role": "admin"}
        }

        if username in users and users[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = users[username]["role"]
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state.logged_in:
    login()
    st.stop()

# ==============================
# 🔹 DB CONNECTION
# ==============================
conn = psycopg2.connect(
    host="aws-1-ap-south-1.pooler.supabase.com",
    port="6543",
    database="postgres",
    user="postgres.veiqtpgsiarxboikevgk",
    password="0rJWQiDcmlEn3KLf"
)
cur = conn.cursor()

# ==============================
# 🔹 SIDEBAR NAVIGATION
# ==============================
if st.session_state.role == "admin":
    page = st.sidebar.radio(
        "Navigation",
        ["Tracking", "Dashboard", "Product Tracking", "Upload Excel", "Delete Data"]
    )
else:
    page = st.sidebar.radio(
        "Navigation",
        ["Tracking", "Product Tracking"]
    )
st.title("Factory Tracking System")

# =========================================================
# ================= UPLOAD PAGE ============================
# =========================================================
if page == "Upload Excel":

    if st.session_state.role != "admin":
        st.error("Access denied")
        st.stop()

    st.subheader("Upload Project Setup Excel")

    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded_file:

        start_time = time.time()

        status = st.empty()
        status.info("⏳ Uploading...")

        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        df = df.drop_duplicates()
        total_rows = len(df)

        # BEFORE
        cur.execute("SELECT COUNT(*) FROM projects")
        before_projects = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM units")
        before_units = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM houses")
        before_houses = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products_master")
        before_products = cur.fetchone()[0]

        # PROJECTS
        for p in df["project_name"].dropna().unique():
            cur.execute("INSERT INTO projects (project_name) VALUES (%s) ON CONFLICT DO NOTHING", (p,))
        conn.commit()

        cur.execute("SELECT project_id, project_name FROM projects")
        project_map = {name: pid for pid, name in cur.fetchall()}

        error_count = 0

        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO units (project_id, unit_name)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (project_map[row["project_name"]], row["unit_name"]))
            except:
                error_count += 1

        conn.commit()

        # AFTER
        cur.execute("SELECT COUNT(*) FROM projects")
        after_projects = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM units")
        after_units = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM houses")
        after_houses = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products_master")
        after_products = cur.fetchone()[0]

        added_projects = after_projects - before_projects
        added_units = after_units - before_units
        added_houses = after_houses - before_houses
        added_products = after_products - before_products

        total_time = round(time.time() - start_time, 2)

        status.empty()

        st.success(f"""
🚀 Upload Completed!

⏱ Time: {total_time}s  
📄 Rows: {total_rows}  
⚠️ Errors: {error_count}

📊 Added:
Projects: {added_projects}
Units: {added_units}
Houses: {added_houses}
Products: {added_products}
""")

# =========================================================
# ================= DELETE DATA PAGE =======================
# =========================================================
if page == "Delete Data":

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

            except Exception as e:
                conn.rollback()
                st.error(f"Error: {e}")
