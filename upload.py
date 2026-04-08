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

        # ================= VALIDATION =================
        required_cols = ["project_name", "unit_name", "house_name", "product_code", "product_category"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"Missing column: {col}")
                st.stop()

        # ================= CLEAN =================
        df["project_name"] = df["project_name"].astype(str).str.strip()
        df["unit_name"] = df["unit_name"].astype(str).str.strip()
        df["house_name"] = df["house_name"].astype(str).str.strip()
        df["product_code"] = df["product_code"].astype(str).str.strip()
        df["product_category"] = df["product_category"].astype(str).str.strip()

        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
        else:
            df["quantity"] = 0

        df = df.drop_duplicates()
        total_rows = len(df)

        error_count = 0

        # ================= PROJECT =================
        for p in df["project_name"].dropna().unique():
            cur.execute("""
                INSERT INTO projects (project_name)
                VALUES (%s)
                ON CONFLICT (project_name) DO NOTHING
            """, (p,))
        conn.commit()

        cur.execute("SELECT project_id, project_name FROM projects")
        project_map = {name: pid for pid, name in cur.fetchall()}

        # ================= UNIT =================
        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO units (project_id, unit_name)
                    VALUES (%s, %s)
                    ON CONFLICT (project_id, unit_name) DO NOTHING
                """, (project_map[row["project_name"]], row["unit_name"]))
            except:
                error_count += 1
        conn.commit()

        cur.execute("SELECT unit_id, unit_name, project_id FROM units")
        unit_map = {(u, p): uid for uid, u, p in cur.fetchall()}

        # ================= HOUSE =================
        for _, row in df.iterrows():
            try:
                project_id = project_map[row["project_name"]]
                unit_id = unit_map[(row["unit_name"], project_id)]

                cur.execute("""
                    INSERT INTO houses (unit_id, house_name)
                    VALUES (%s, %s)
                    ON CONFLICT (unit_id, house_name) DO NOTHING
                """, (unit_id, row["house_name"]))
            except:
                error_count += 1
        conn.commit()

        cur.execute("SELECT house_id, house_name, unit_id FROM houses")
        house_map = {(h, u): hid for hid, h, u in cur.fetchall()}

        # ================= PRODUCT MASTER (WITH CATEGORY) =================
        for _, row in df.iterrows():
            try:
                cur.execute("""
                    INSERT INTO products_master (product_name, product_category)
                    VALUES (%s, %s)
                    ON CONFLICT (product_name)
                    DO UPDATE SET product_category = EXCLUDED.product_category
                """, (row["product_code"], row["product_category"]))
            except:
                error_count += 1
        conn.commit()

        cur.execute("SELECT product_id, product_name FROM products_master")
        product_map = {name: pid for pid, name in cur.fetchall()}

        # ================= HOUSE PRODUCTS =================
        for _, row in df.iterrows():
            try:
                project_id = project_map[row["project_name"]]
                unit_id = unit_map[(row["unit_name"], project_id)]
                house_id = house_map[(row["house_name"], unit_id)]
                product_id = product_map[row["product_code"]]
                quantity = int(row["quantity"])

                cur.execute("""
                    INSERT INTO house_products (house_id, product_id, quantity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (house_id, product_id)
                    DO UPDATE SET quantity = EXCLUDED.quantity
                """, (house_id, product_id, quantity))

            except:
                error_count += 1

        conn.commit()

        total_time = round(time.time() - start_time, 2)
        status.empty()

        st.success(f"""
🚀 Upload Completed!

⏱ Time: {total_time}s  
📄 Rows: {total_rows}  
⚠️ Errors: {error_count}

✅ Category + Quantity + Structure all working
""")
