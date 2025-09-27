import streamlit as st

st.set_page_config(page_title='HelloWorldApp')

st.title("My First SAVAN-Generated App")
if st.button("Click Me!"):
    st.success("Hello from SAVAN!")