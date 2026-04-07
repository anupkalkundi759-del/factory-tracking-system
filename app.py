import streamlit as st
import psycopg2
import pandas as pd
from io import StringIO
import time

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
# ===================== TRACKING PAGE ======================
# =========================================================
if page == "Tracking":

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

# =========================================================
# ===================== DASHBOARD ==========================
# =========================================================
if page == "Dashboard":

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

# =========================================================
# ================= PRODUCT TRACKING PAGE ==================
# =========================================================
if page == "Product Tracking":

    st.title("🔍 Product Tracking")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()
    project_dict = {p[1]: p[0] for p in projects}

    project_options = ["All"] + list(project_dict.keys())
    selected_project = col1.selectbox("Project", project_options, key="proj")

    # ================= UNIT (DEPENDENT) =================
    if selected_project == "All":
        cur.execute("SELECT unit_id, unit_name FROM units ORDER BY unit_name")
    else:
        cur.execute("""
            SELECT unit_id, unit_name
            FROM units
            WHERE project_id = %s
            ORDER BY unit_name
        """, (project_dict[selected_project],))

    units = cur.fetchall()
    unit_dict = {u[1]: u[0] for u in units}

    unit_options = ["All"] + list(unit_dict.keys())
    selected_unit = col2.selectbox("Unit", unit_options, key="unit")

    # ================= HOUSE (DEPENDENT) =================
    if selected_unit == "All":
        if selected_project == "All":
            cur.execute("SELECT house_id, house_no FROM houses ORDER BY house_no")
        else:
            cur.execute("""
                SELECT h.house_id, h.house_no
                FROM houses h
                JOIN units u ON h.unit_id = u.unit_id
                WHERE u.project_id = %s
            """, (project_dict[selected_project],))
    else:
        cur.execute("""
            SELECT house_id, house_no
            FROM houses
            WHERE unit_id = %s
        """, (unit_dict[selected_unit],))

    houses = cur.fetchall()
    house_dict = {h[1]: h[0] for h in houses}

    house_options = ["All"] + list(house_dict.keys())
    selected_house = col3.selectbox("House", house_options, key="house")

    # ================= STATUS =================
    status_options = ["All", "Not Started", "Started", "Completed"]
    selected_status = col4.selectbox("Status", status_options)

    # ================= STAGE =================
    cur.execute("SELECT stage_name FROM stages ORDER BY sequence")
    stages = cur.fetchall()
    stage_options = ["All"] + [s[0] for s in stages]

    selected_stage = col5.selectbox("Stage", stage_options)

    # ================= SEARCH =================
    search = col6.text_input("Search")

    # ================= QUERY =================
    query = """
    SELECT 
        pm.product_code,
        pm.type,
        p.quantity,
        pr.project_name,
        u.unit_name,
        h.house_no,
        COALESCE(s.stage_name, 'Not Started') AS stage,
        COALESCE(t.status, 'Not Started') AS status,
        COALESCE(s.sequence, 0) AS stage_seq
    FROM products p
    JOIN products_master pm ON p.product_id = pm.product_id
    JOIN houses h ON p.house_id = h.house_id
    JOIN units u ON h.unit_id = u.unit_id
    JOIN projects pr ON u.project_id = pr.project_id

    LEFT JOIN LATERAL (
        SELECT t.stage_id, t.status, t.timestamp
        FROM tracking_log t
        WHERE t.house_id = p.house_id
        AND t.product_id = p.product_id
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

    query += " ORDER BY pm.product_code"

    cur.execute(query, tuple(params))
    data = cur.fetchall()

    df = pd.DataFrame(data, columns=[
        "Product", "Type", "Qty", "Project", "Unit", "House",
        "Stage", "Status", "Stage Seq"
    ])

    # ================= PROGRESS =================
    total_stages = 7
    df["Progress %"] = (df["Stage Seq"] / total_stages) * 100
    df["Progress"] = df["Progress %"].astype(int).astype(str) + "%"

    df_display = df.drop(columns=["Stage Seq", "Progress %"])

    # ================= FINAL DISPLAY (FIXED) =================
    st.dataframe(df_display, use_container_width=True)

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
