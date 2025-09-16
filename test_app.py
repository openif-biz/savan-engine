import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("SAVAN 自動デプロイテスト")
st.header("このページがサーバー上で見えれば成功です！")

st.info("これは、GitHub Actionsを通じて自動的にデプロイされたテスト用アプリケーションです。")

st.balloons()

st.success(f"デプロイ時刻: {pd.Timestamp.now(tz='Asia/Tokyo').strftime('%Y年%m月%d日 %H:%M:%S')}")