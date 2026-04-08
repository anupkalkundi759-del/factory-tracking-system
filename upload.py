# =========================================================
# ================= UPLOAD PAGE ============================
# =========================================================
def show_upload(conn, cur):
    import streamlit as st
    import pandas as pd
    import time

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
