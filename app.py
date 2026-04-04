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
# 🔹 NAVIGATION
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
# ===================== TRACKING ===========================
# =========================================================
if page == "Tracking":

    # ================= PROJECT =================
    cur.execute("SELECT project_id, project_name FROM projects ORDER BY project_name")
    projects = cur.fetchall()

    if not projects:
        st.warning("⚠️ No data found. Upload Excel first.")
        st.stop()

    project_dict = {p[1]: p[0] for p in projects}
    selected_project = st.selectbox("Select Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    # ================= UNIT =================
    cur.execute("SELECT unit_id, unit_name FROM units WHERE project_id=%s", (project_id,))
    units = cur.fetchall()

    if not units:
        st.warning("No units for this project")
        st.stop()

    unit_dict = {u[1]: u[0] for u in units}
    selected_unit = st.selectbox("Select Unit", list(unit_dict.keys()))
    unit_id = unit_dict[selected_unit]

    # ================= HOUSE =================
    cur.execute("SELECT house_id, house_no FROM houses WHERE unit_id=%s", (unit_id,))
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

    # ================= CURRENT STAGE =================
    cur.execute("""
        SELECT COALESCE(MAX(s.sequence), 0)
        FROM tracking_log t
        JOIN stages s ON t.stage_id = s.stage_id
        WHERE t.house_id = %s AND t.product_id = %s
    """, (house_id, product_id))

    current_seq = cur.fetchone()[0]
    st.info(f"Current Stage: {current_seq}")

    # ================= STAGE =================
    cur.execute("SELECT stage_id, stage_name, sequence FROM stages ORDER BY sequence")
    stages = cur.fetchall()

    stage_map = {s[1]: (s[0], s[2]) for s in stages}
    selected_stage = st.selectbox("Select Stage", list(stage_map.keys()))
    stage_id, seq = stage_map[selected_stage]

    # ================= SAVE =================
    if st.button("Submit"):
        cur.execute("""
            INSERT INTO tracking_log (house_id, product_id, stage_id, status, timestamp)
            VALUES (%s, %s, %s, %s, NOW())
        """, (house_id, product_id, stage_id, "Completed"))
        conn.commit()
        st.success("Saved!")

# =========================================================
# 📥 EXCEL UPLOAD
# =========================================================
if page == "Tracking" and st.session_state.role == "admin":

    st.subheader("📥 Upload Excel")

    file = st.file_uploader("Upload", type=["xlsx"])

    if file:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

        required = [
            "project_name","unit_name","house_no",
            "product_code","quantity",
            "product_category","manufacturing_code"
        ]

        missing = [c for c in required if c not in df.columns]
        if missing:
            st.error(f"Missing columns: {missing}")
            st.stop()

        for row in df.itertuples(index=False):

            project = row.project_name
            unit = row.unit_name
            house = row.house_no
            product = row.product_code
            qty = int(row.quantity)
            ptype = row.product_category
            mcode = row.manufacturing_code

            # PROJECT
            cur.execute("INSERT INTO projects (project_name) VALUES (%s) ON CONFLICT DO NOTHING", (project,))
            cur.execute("SELECT project_id FROM projects WHERE project_name=%s", (project,))
            pid = cur.fetchone()[0]

            # UNIT
            cur.execute("INSERT INTO units (project_id, unit_name) VALUES (%s,%s) ON CONFLICT DO NOTHING", (pid, unit))
            cur.execute("SELECT unit_id FROM units WHERE project_id=%s AND unit_name=%s", (pid, unit))
            uid = cur.fetchone()[0]

            # HOUSE
            cur.execute("INSERT INTO houses (unit_id, house_no) VALUES (%s,%s) ON CONFLICT DO NOTHING", (uid, house))
            cur.execute("SELECT house_id FROM houses WHERE unit_id=%s AND house_no=%s", (uid, house))
            hid = cur.fetchone()[0]

            # PRODUCT MASTER
            cur.execute("""
                INSERT INTO products_master (product_code, type, manufacturing_code)
                VALUES (%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (product, ptype, mcode))

            cur.execute("SELECT product_id FROM products_master WHERE product_code=%s", (product,))
            prid = cur.fetchone()[0]

            # PRODUCT
            cur.execute("""
                INSERT INTO products (house_id, product_id, quantity)
                VALUES (%s,%s,%s)
                ON CONFLICT (house_id, product_id)
                DO UPDATE SET quantity=EXCLUDED.quantity
            """, (hid, prid, qty))

        conn.commit()
        st.success("Upload complete")

# =========================================================
# ================= DASHBOARD ==============================
# =========================================================
if page == "Dashboard":

    cur.execute("SELECT project_id, project_name FROM projects")
    projects = cur.fetchall()

    if not projects:
        st.warning("No data available")
        st.stop()

    project_dict = {p[1]: p[0] for p in projects}
    selected_project = st.selectbox("Project", list(project_dict.keys()))
    project_id = project_dict[selected_project]

    st.success("Dashboard ready (data exists)")
