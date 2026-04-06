import streamlit as st
import psycopg2
import pandas as pd
from io import StringIO

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
    page = st.sidebar.radio("Navigation", ["Tracking", "Dashboard"])
else:
    page = "Tracking"

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

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

    # ================= STAGE + STATUS =================
    if selected_product:
        product_id = product_dict[selected_product]

        # Current stage
        cur.execute("""
            SELECT COALESCE(MAX(s.sequence), 0)
            FROM tracking_log t
            JOIN stages s ON t.stage_id = s.stage_id
            WHERE t.house_id = %s AND t.product_id = %s
        """, (house_id, product_id))

        current_seq = cur.fetchone()[0]
        st.info(f"Current Progress Stage: {current_seq}")

        # Stage dropdown
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

        if last_completed:
            allowed_sequence = last_completed[0] + 1
        else:
            allowed_sequence = 1

        if selected_sequence > allowed_sequence:
            st.error("❌ Complete previous stage first")
        else:
            # Status logic
            if selected_sequence == 1:
                status_options = ["Pending", "Started", "Completed"]
            else:
                cur.execute("""
                    SELECT status FROM tracking_log t
                    JOIN stages s ON t.stage_id = s.stage_id
                    WHERE t.house_id = %s 
                    AND t.product_id = %s 
                    AND s.sequence = %s
                    ORDER BY t.timestamp DESC LIMIT 1
                """, (house_id, product_id, selected_sequence - 1))

                prev = cur.fetchone()

                if prev and prev[0] == "Completed":
                    status_options = ["Pending", "Started", "Completed"]
                else:
                    status_options = ["Pending"]

            status = st.selectbox("Status", status_options)

            if st.button("Submit"):
                cur.execute("""
                    INSERT INTO tracking_log (house_id, product_id, stage_id, status, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (house_id, product_id, stage_id, status))

                conn.commit()
                st.success("Saved successfully!")

    # ================= UPLOAD SECTION =================
    st.subheader("Upload Project Setup Excel")

    uploaded_file = st.file_uploader("Upload Excel", type=["xlsx"])

    if uploaded_file:

    start_time = time.time()

    status = st.empty()
    status.info("⏳ Uploading and processing... please wait")

    # ================= READ FILE =================
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # ================= CLEAN DATA =================
    df["project_name"] = df["project_name"].astype(str).str.strip()
    df["unit_name"] = df["unit_name"].astype(str).str.strip()
    df["house_no"] = df["house_no"].astype(str).str.strip()
    df["product_code"] = df["product_code"].astype(str).str.strip()

    df = df.drop_duplicates()
    total_rows = len(df)

    # ================= BEFORE COUNTS =================
    cur.execute("SELECT COUNT(*) FROM projects")
    before_projects = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM units")
    before_units = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM houses")
    before_houses = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products_master")
    before_products = cur.fetchone()[0]

    # ================= PROJECTS =================
    for p in df["project_name"].dropna().unique():
        cur.execute("""
            INSERT INTO projects (project_name)
            VALUES (%s)
            ON CONFLICT (project_name) DO NOTHING
        """, (p,))
    conn.commit()

    cur.execute("SELECT project_id, project_name FROM projects")
    project_map = {str(name).strip(): pid for pid, name in cur.fetchall()}

    # ================= UNITS =================
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO units (project_id, unit_name)
            VALUES (%s, %s)
            ON CONFLICT (project_id, unit_name) DO NOTHING
        """, (project_map[row["project_name"]], row["unit_name"]))
    conn.commit()

    cur.execute("SELECT unit_id, unit_name, project_id FROM units")
    unit_map = {(str(u[1]).strip(), u[2]): u[0] for u in cur.fetchall()}

    # ================= HOUSES =================
    for _, row in df.iterrows():
        uid = unit_map.get((row["unit_name"], project_map[row["project_name"]]))

        if uid is None:
            continue

        cur.execute("""
            INSERT INTO houses (unit_id, house_no)
            VALUES (%s, %s)
            ON CONFLICT (unit_id, house_no) DO NOTHING
        """, (uid, row["house_no"]))
    conn.commit()

    cur.execute("SELECT house_id, house_no, unit_id FROM houses")
    house_map = {(str(h[1]).strip(), h[2]): h[0] for h in cur.fetchall()}

    # ================= PRODUCTS MASTER =================
    for p in df["product_code"].dropna().unique():
        cur.execute("""
            INSERT INTO products_master (product_code)
            VALUES (%s)
            ON CONFLICT (product_code) DO NOTHING
        """, (p,))
    conn.commit()

    cur.execute("SELECT product_id, product_code FROM products_master")
    product_map = {str(p[1]).strip(): p[0] for p in cur.fetchall()}

    # ================= FINAL PRODUCTS =================
    error_count = 0

    for _, row in df.iterrows():

        uid = unit_map.get((row["unit_name"], project_map[row["project_name"]]))

        if uid is None:
            error_count += 1
            continue

        hid = house_map.get((row["house_no"], uid))

        if hid is None:
            error_count += 1
            continue

        pid = product_map.get(row["product_code"])

        if pid is None:
            error_count += 1
            continue

        cur.execute("""
            INSERT INTO products (house_id, product_id)
            VALUES (%s, %s)
            ON CONFLICT (house_id, product_id) DO NOTHING
        """, (hid, pid))

    conn.commit()

    # ================= AFTER COUNTS =================
    cur.execute("SELECT COUNT(*) FROM projects")
    after_projects = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM units")
    after_units = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM houses")
    after_houses = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM products_master")
    after_products = cur.fetchone()[0]

    # ================= CALCULATE ADDED =================
    added_projects = after_projects - before_projects
    added_units = after_units - before_units
    added_houses = after_houses - before_houses
    added_products = after_products - before_products

    # ================= TIME =================
    end_time = time.time()
    total_time = round(end_time - start_time, 2)

    status.empty()

    # ================= FINAL OUTPUT =================
    st.success(f"""
🚀 Upload Completed!

⏱ Time Taken: {total_time} sec  
📄 Rows Processed: {total_rows}  
⚠️ Errors Skipped: {error_count}

📊 Added:
- Projects: {added_projects}
- Units: {added_units}
- Houses: {added_houses}
- Products: {added_products}
""")

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
# 🔹 PRODUCT TRACKING (LATEST + QUANTITY)
# =========================================================
st.subheader("🔍 Product Tracking")

# ================= PROJECT =================
cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
projects = cur.fetchall()
project_dict = {p[1]: p[0] for p in projects}

selected_project = st.selectbox(
    "Select Project",
    list(project_dict.keys()),
    key="dashboard_project"   # ✅ IMPORTANT
)
project_id = project_dict[selected_project]

# ================= UNIT =================
cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s", (project_id,))
units = cur.fetchall()

if not units:
    st.warning("No units for this project")
    st.stop()

unit_dict = {u[1]: u[0] for u in units}

selected_unit = st.selectbox(
    "Select Unit",
    list(unit_dict.keys()),
    key="dashboard_unit"   # ✅ IMPORTANT
)
unit_id = unit_dict[selected_unit]

# ================= HOUSE =================
cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id=%s", (unit_id,))
houses = cur.fetchall()

if not houses:
    st.warning("No houses for this unit")
    st.stop()

house_dict = {h[1]: h[0] for h in houses}

selected_house = st.selectbox(
    "Select House",
    list(house_dict.keys()),
    key="dashboard_house"   # ✅ IMPORTANT
)
house_id = house_dict[selected_house]

# ================= DATA QUERY =================
cur.execute("""
SELECT 
    pm.product_code,
    pm.type,
    p.quantity,
    COALESCE(s.stage_name, 'Not Started') AS current_stage,
    COALESCE(t.status, 'Not Started') AS status,
    t.timestamp
FROM products p
JOIN products_master pm ON p.product_id = pm.product_id

LEFT JOIN LATERAL (
    SELECT t.stage_id, t.status, t.timestamp
    FROM tracking_log t
    WHERE t.house_id = p.house_id
    AND t.product_id = p.product_id
    ORDER BY t.timestamp DESC
    LIMIT 1
) t ON TRUE

LEFT JOIN stages s ON t.stage_id = s.stage_id

WHERE p.house_id = %s
ORDER BY pm.product_code;
""", (house_id,))

df_prod = pd.DataFrame(cur.fetchall(), columns=[
    "Product", "Type", "Quantity", "Current Stage", "Status", "Last Updated"
])
df_prod["Last Updated"] = df_prod["Last Updated"] + pd.Timedelta(hours=5, minutes=30)

st.dataframe(df_prod, use_container_width=True)
