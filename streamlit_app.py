"""Entry point for Streamlit Cloud deployment."""
import streamlit as st

st.set_page_config(page_title="Báo cáo CSKH MB", layout="wide")

pg = st.navigation(
    {
        "Dữ liệu": [
            st.Page("pages/1_tai_du_lieu.py", title="Tải dữ liệu", icon="📤"),
        ],
        "Báo cáo": [
            st.Page("pages/2_tao_bao_cao.py", title="Tạo báo cáo", icon="📊"),
        ],
    }
)
pg.run()
