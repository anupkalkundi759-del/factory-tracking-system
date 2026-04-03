import streamlit as st
import psycopg2
import pandas as pd

# ==============================
# LOGIN SYSTEM
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
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state.logged_in:
    login()
    st.stop()

# ==============================
# DB CONNECTION
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
# NAVIGATION
# ==============================
if st.session_state.role == "admin":
    page = st.sidebar.radio("Navigation", ["Upload", "Tracking", "Dashboard"])
else:
    page = "Tracking"

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.rerun()

st.title("Factory Tracking System")

# =========================================================
# ===================== UPLOAD =============================
# =========================================================
if page == "Upload":

    st.subheader("📥 Upload Project Setup Excel")

    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        required_cols = ["project_name","unit_name","house_no","product_code","quantity"]

        if not all(col in df.columns for col in required_cols):
            st.error("Missing required columns")
            st.stop()

        for _, row in df.iterrows():

            project = str(row["project_name"]).strip()
            unit = str(row["unit_name"]).strip()
            house = str(row["house_no"]).strip()
            product = str(row["product_code"]).strip()
            quantity = int(row.get("quantity", 1))

            if not project or not unit or not house or not product:
                continue

            # PROJECT
            cur.execute("INSERT INTO projects (project_name) VALUES (%s) ON CONFLICT DO NOTHING",(project,))
            cur.execute("SELECT project_id FROM projects WHERE project_name=%s",(project,))
            project_id = cur.fetchone()[0]

            # UNIT
            cur.execute("INSERT INTO units (project_id, unit_name) VALUES (%s,%s) ON CONFLICT DO NOTHING",(project_id,unit))
            cur.execute("SELECT unit_id FROM units WHERE project_id=%s AND unit_name=%s",(project_id,unit))
            unit_id = cur.fetchone()[0]

            # HOUSE
            cur.execute("INSERT INTO houses (unit_id, house_no) VALUES (%s,%s) ON CONFLICT DO NOTHING",(unit_id,house))
            cur.execute("SELECT house_id FROM houses WHERE unit_id=%s AND house_no=%s",(unit_id,house))
            house_id = cur.fetchone()[0]

            # PRODUCT MASTER
            cur.execute("INSERT INTO products_master (product_code) VALUES (%s) ON CONFLICT DO NOTHING",(product,))
            cur.execute("SELECT product_id FROM products_master WHERE product_code=%s",(product,))
            product_id = cur.fetchone()[0]

            # PRODUCTS
            cur.execute("INSERT INTO products (house_id, product_id, quantity) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                        (house_id, product_id, quantity))

        conn.commit()
        st.success("Upload completed successfully")

# =========================================================
# ===================== TRACKING ===========================
# =========================================================
if page == "Tracking":

    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()

    if not projects:
        st.warning("⚠️ Upload Excel first")
        st.stop()

    project_dict = {p[1]: p[0] for p in projects}
    selected_project = st.selectbox("Project", list(project_dict.keys()))
    project_id = project_dict.get(selected_project)

    if not project_id:
        st.stop()

    # UNIT
    cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s",(project_id,))
    units = cur.fetchall()

    if not units:
        st.warning("No units")
        st.stop()

    unit_dict = {u[1]: u[0] for u in units}
    selected_unit = st.selectbox("Unit", list(unit_dict.keys()))
    unit_id = unit_dict.get(selected_unit)

    # HOUSE
    cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id=%s",(unit_id,))
    houses = cur.fetchall()

    if not houses:
        st.warning("No houses")
        st.stop()

    house_dict = {h[1]: h[0] for h in houses}
    selected_house = st.selectbox("House", list(house_dict.keys()))
    house_id = house_dict.get(selected_house)

    # PRODUCT
    cur.execute("""
        SELECT pm.product_id, pm.product_code
        FROM products p
        JOIN products_master pm ON p.product_id = pm.product_id
        WHERE p.house_id = %s
    """, (house_id,))
    products = cur.fetchall()

    if not products:
        st.warning("No products")
        st.stop()

    product_dict = {p[1]: p[0] for p in products}
    selected_product = st.selectbox("Product", list(product_dict.keys()))
    product_id = product_dict.get(selected_product)

    # STAGES
    cur.execute("SELECT stage_id, stage_name FROM stages ORDER BY sequence")
    stages = cur.fetchall()

    stage_dict = {s[1]: s[0] for s in stages}
    selected_stage = st.selectbox("Stage", list(stage_dict.keys()))
    stage_id = stage_dict[selected_stage]

    status = st.selectbox("Status", ["Pending", "Started", "Completed"])

    if st.button("Submit"):
        cur.execute("""
            INSERT INTO tracking_log (house_id, product_id, stage_id, status, timestamp)
            VALUES (%s, %s, %s, %s, NOW())
        """, (house_id, product_id, stage_id, status))
        conn.commit()
        st.success("Saved successfully")

# =========================================================
# ===================== DASHBOARD ==========================
# =========================================================
if page == "Dashboard":

    import plotly.express as px

    st.title("📊 Dashboard")

    # PROJECT OVERVIEW
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
        COUNT(DISTINCT p.house_id),
        COUNT(*),
        COUNT(CASE WHEN stage_reached = 7 THEN 1 END),
        COUNT(*) - COUNT(CASE WHEN stage_reached = 7 THEN 1 END),
        ROUND(AVG(stage_reached * 100.0 / 7), 2)
    FROM product_progress p
    JOIN houses h ON p.house_id = h.house_id
    JOIN units u ON h.unit_id = u.unit_id
    JOIN projects pr ON u.project_id = pr.project_id
    GROUP BY pr.project_name;
    """)

    data = cur.fetchall()

    if not data:
        st.warning("Upload Excel first")
        st.stop()

    df = pd.DataFrame(data, columns=["Project","Houses","Products","Completed","Pending","Progress"])
    st.dataframe(df)

    fig = px.bar(df, x="Project", y="Progress")
    st.plotly_chart(fig)
