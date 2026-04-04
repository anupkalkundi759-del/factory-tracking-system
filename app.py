import streamlit as st
import psycopg2
import pandas as pd

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
            "admin": {"password": "admin123", "role": "admin"}
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
try:
    conn = psycopg2.connect(
        host="aws-1-ap-south-1.pooler.supabase.com",
        port="6543",
        database="postgres",
        user="postgres.veiqtpgsiarxboikevgk",
        password="0rJWQiDcmlEn3KLf"
    )
    cur = conn.cursor()
except Exception as e:
    st.error(f"DB connection failed: {e}")
    st.stop()

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

    project_dict = {p[1]: p[0] for p in projects}

    selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    # ================= UNIT =================
    cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s ORDER BY unit_name", (project_id,))
    units = cur.fetchall()

    if not units:
        st.warning("No units for this project")
        st.stop()

    unit_dict = {u[1]: u[0] for u in units}

    selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
    unit_id = unit_dict[selected_unit]

    # ================= HOUSE =================
    cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id=%s ORDER BY house_no", (unit_id,))
    houses = cur.fetchall()

    if not houses:
        st.warning("No houses for this unit")
        st.stop()

    house_dict = {h[1]: h[0] for h in houses}

    selected_house = st.selectbox("Select House", list(house_dict.keys()))
    house_id = house_dict[selected_house]

    # ================= PRODUCT =================
    cur.execute("""
        SELECT pm.product_id, pm.product_code
        FROM products p
        JOIN products_master pm ON p.product_id = pm.product_id
        WHERE p.house_id = %s
    """, (house_id,))
    products = cur.fetchall()

    if not products:
        st.warning("No products for this house")
        st.stop()

    product_dict = {p[1]: p[0] for p in products}

    selected_product = st.selectbox("Select Product", list(product_dict.keys()))
    product_id = product_dict[selected_product]

    # ================= CURRENT STAGE INFO =================
    cur.execute("""
        SELECT COALESCE(MAX(s.sequence), 0)
        FROM tracking_log t
        JOIN stages s ON t.stage_id = s.stage_id
        WHERE t.house_id = %s AND t.product_id = %s
    """, (house_id, product_id))

    current_seq = cur.fetchone()[0]

    st.info(f"Current Progress Stage: {current_seq}")

    # ================= STAGE =================
    cur.execute("SELECT stage_id, stage_name, sequence FROM stages ORDER BY sequence")
    all_stages = cur.fetchall()

    stage_names = [s[1] for s in all_stages]
    stage_map = {s[1]: (s[0], s[2]) for s in all_stages}

    selected_stage_name = st.selectbox("Select Stage", stage_names)
    stage_id, selected_sequence = stage_map[selected_stage_name]

    # ================= VALIDATION =================
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
        st.stop()

    # ================= STATUS =================
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

    # ================= SAVE =================
    if st.button("Submit"):
        cur.execute("""
            INSERT INTO tracking_log (house_id, product_id, stage_id, status, timestamp)
            VALUES (%s, %s, %s, %s, NOW())
        """, (house_id, product_id, stage_id, status))

        conn.commit()
        st.success("Saved successfully!")

   # =========================================================
# 📥 EXCEL UPLOAD (FINAL CLEAN VERSION)
# =========================================================
if page == "Tracking" and st.session_state.role == "admin":

    st.subheader("📥 Upload Project Setup Excel")

    uploaded_file = st.file_uploader(
        "Upload Excel File",
        type=["xlsx"],
        key="upload_tracking_unique"
    )

    if uploaded_file is not None:

        with st.spinner("⚡ Fast upload..."):

            df = pd.read_excel(uploaded_file)

            # CLEAN
            df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

            required_cols = [
                "project_name", "unit_name", "house_no",
                "product_code", "quantity"
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                st.error(f"Missing columns: {missing}")
                st.stop()

            # keep only needed
            keep_cols = required_cols + ["manufacturing_code"] if "manufacturing_code" in df.columns else required_cols
            df = df[keep_cols]

            # clean data
            df = df.dropna(subset=required_cols)
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)

            # 🔥 REMOVE DUPLICATES (your logic)
            df = df.drop_duplicates(subset=[
                "project_name", "unit_name", "house_no", "product_code"
            ])

            # ================= TEMP TABLE =================
            cur.execute("""
                CREATE TEMP TABLE temp_upload (
                    project_name TEXT,
                    unit_name TEXT,
                    house_no TEXT,
                    product_code TEXT,
                    quantity INT,
                    manufacturing_code TEXT
                )
            """)

            # ================= COPY =================
            buffer = StringIO()
            df.to_csv(buffer, index=False, header=False)
            buffer.seek(0)

            cur.copy_expert("""
                COPY temp_upload (
                    project_name, unit_name, house_no,
                    product_code, quantity, manufacturing_code
                )
                FROM STDIN WITH CSV
            """, buffer)

            # ================= PROJECT =================
            cur.execute("""
                INSERT INTO projects (project_name)
                SELECT DISTINCT project_name FROM temp_upload
                ON CONFLICT DO NOTHING
            """)

            # ================= UNIT =================
            cur.execute("""
                INSERT INTO units (project_id, unit_name)
                SELECT DISTINCT p.project_id, t.unit_name
                FROM temp_upload t
                JOIN projects p ON p.project_name = t.project_name
                ON CONFLICT DO NOTHING
            """)

            # ================= HOUSE =================
            cur.execute("""
                INSERT INTO houses (unit_id, house_no)
                SELECT DISTINCT u.unit_id, t.house_no
                FROM temp_upload t
                JOIN projects p ON p.project_name = t.project_name
                JOIN units u ON u.project_id = p.project_id AND u.unit_name = t.unit_name
                ON CONFLICT DO NOTHING
            """)

            # ================= PRODUCT MASTER =================
            cur.execute("""
                INSERT INTO products_master (product_code, manufacturing_code)
                SELECT DISTINCT product_code, manufacturing_code
                FROM temp_upload
                ON CONFLICT (product_code)
                DO UPDATE SET manufacturing_code = EXCLUDED.manufacturing_code
            """)

            # ================= FINAL PRODUCTS =================
            cur.execute("""
                INSERT INTO products (house_id, product_id, quantity)
                SELECT DISTINCT
                    h.house_id,
                    pm.product_id,
                    t.quantity
                FROM temp_upload t
                JOIN projects p ON p.project_name = t.project_name
                JOIN units u ON u.project_id = p.project_id AND u.unit_name = t.unit_name
                JOIN houses h ON h.unit_id = u.unit_id AND h.house_no = t.house_no
                JOIN products_master pm ON pm.product_code = t.product_code
                ON CONFLICT (house_id, product_id)
                DO UPDATE SET quantity = EXCLUDED.quantity
            """)

            conn.commit()

        st.success(f"🚀 Upload complete! {len(df)} rows processed.")

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

st.dataframe(df_prod, use_container_width=True)
