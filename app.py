import streamlit as st

from yt.components import draw_browse_page, draw_modify_page

# Explicitly set the page title so Streamlit doesn't try to guess it from the filename
# Make the page full-width to accommodate the horizontal carousels
st.set_page_config(page_title="YouTube subscription manager", layout="wide")

pg = st.navigation(
    # The favicon will be read from the currently selected `st.Page`
    pages=[
        st.Page(
            title="Browse",
            url_path="browse",
            page=draw_browse_page,
            icon=":material/video_library:",
        ),
        st.Page(
            title="Modify",
            url_path="modify",
            page=draw_modify_page,
            icon=":material/edit:",
        ),
    ],
    position="top",
)


pg.run()
