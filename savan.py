# 【通番29改2】savan_ui.py (文字コードエラー修正版)
import streamlit as st
import sys
import os
import subprocess
import yaml
from contextlib import contextmanager
from llama_cpp import Llama
import tempfile
import json

# --- 定数とヘルパー関数 ---
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROJECTS_DIR = os.path.join(WORKSPACE_ROOT, "projects")
SAVAN_PY_PATH = os.path.join(os.path.dirname(__file__), "savan.py")

def get_project_list():
    if not os.path.isdir(PROJECTS_DIR): return []
    return [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]

def get_template_list():
    return ["linode-docker-deploy"] 

# (既存のバックエンド関数群はここにそのまま配置)
# ...

# --- UI ---
st.set_page_config(layout="wide")
st.title("SAVAN - Universal Console")
st.markdown("---")

workflow_options = ["プロジェクトを新規創出する", "既存プロジェクトにテンプレートを適用する"]
selected_workflow_label = st.selectbox(
    "実行したいワークフローを選択してください:",
    workflow_options
)

if selected_workflow_label == "プロジェクトを新規創出する":
    # (既存のプロジェクト創出UIロジック)
    pass
elif selected_workflow_label == "既存プロジェクトにテンプレートを適用する":
    st.header("ワークフロー2: 既存プロジェクトにテンプレートを適用")
    st.write("SAVANが学習済みの設計図（テンプレート）を、選択したプロジェクトに適用し、必要なファイルを自動生成します。")
    projects = get_project_list()
    templates = get_template_list()

    if not projects:
        st.error(f"`{PROJECTS_DIR}`にプロジェクトが見つかりません。")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_project = st.selectbox("対象プロジェクトを選択:", projects)
        with col2:
            selected_template = st.selectbox("適用するテンプレートを選択:", templates)
        
        if st.button(f"🚀 '{selected_project}'に'{selected_template}'を適用する", type="primary"):
            st.info(f"SAVANが '{selected_project}' にテンプレート '{selected_template}' を適用しています...")
            command = ["python", SAVAN_PY_PATH, "--apply-template", selected_template, "--project", selected_project]
            
            with st.spinner("SAVANが実行中..."):
                # --- ▼▼▼【ここが修正箇所です】▼▼▼ ---
                result = subprocess.run(command, capture_output=True, text=True, encoding='cp932', errors='ignore')
                # --- ▲▲▲【ここまで】▲▲▲ ---

            st.subheader("実行結果")
            if result.returncode == 0:
                st.success("テンプレートの適用が正常に完了しました。")
                st.code(result.stdout, language="log")
            else:
                st.error("テンプレートの適用中にエラーが発生しました。")
                st.code(result.stdout, language="log")
                st.code(result.stderr, language="log")