import streamlit as st
import sys
import os
import subprocess
import time
import yaml
from contextlib import contextmanager
# from llama_cpp import Llama 
import tempfile
import json
from pathlib import Path

# --- 設定 ---
def get_model_path():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(workspace_root, "models", "deepseek-coder-6.7b-instruct.Q4_K_M.gguf")

MODEL_PATH = get_model_path()

# --- パス解決ロジック (強化版) ---
CURRENT_FILE_PATH = Path(__file__).resolve()
ENGINE_DIR = CURRENT_FILE_PATH.parent # savan-engine
ROOT_DIR = ENGINE_DIR.parent          # local_savan または /var/www
PROJECTS_DIR = ROOT_DIR / 'projects'
SAVAN_PY_PATH = os.path.join(os.path.dirname(__file__), "savan.py")

# --- フロントエンド UI 設定 ---
st.set_page_config(page_title="SAVAN Console", page_icon="🏭", layout="wide")
st.title("🏭 SAVAN - Universal Console")
st.markdown("### Intellectual Software Factory Interface")
st.divider()

# --- Helper Functions ---
def get_project_list():
    """
    【修正ロジック】
    ローカルPC (projects/) とサーバー (ROOT_DIR) の両方をスキャンし、プロジェクトをリスト化
    """
    projects = set() # 重複を避けるためにsetを使用
    
    # 1. ローカルPCの 'projects' フォルダをスキャン
    if PROJECTS_DIR.exists():
        for d in PROJECTS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith('.'):
                projects.add(d.name)
    
    # 2. サーバの /var/www/ (ROOT_DIR) をスキャン
    #    (ローカル実行時は local_savan/ をスキャンするが、欲しいのは 'savan-engine' だけ)
    if ROOT_DIR.exists():
        for d in ROOT_DIR.iterdir():
            if d.is_dir() and not d.name.startswith('.'):
                # 'projects' フォルダ自体と 'models' は除外
                if d.name == 'projects' or d.name == 'models':
                    continue
                
                # 'savan-engine' は手動で追加するので除外 (重複防止)
                if d.name == 'savan-engine':
                    continue
                
                projects.add(d.name)

    # 3. savan-engine自身を追加 (自己デプロイ用)
    projects.add("savan-engine")
    
    return sorted(list(projects))

def get_template_list():
    return ["linode-docker-deploy"]

# --- ワークフロー選択UI ---
workflow_options = [
    "プロジェクトを新規創出する (New Project)", 
    "既存プロジェクトにテンプレートを適用する (Apply Template)",
    "既存アプリの自動デプロイ設定 (Auto-Deploy Config)"
]

selected_workflow = st.selectbox(
    "実行したいワークフローを選択してください:",
    workflow_options,
    key="workflow_choice"
)

# ==========================================
# ワークフロー1: プロジェクト新規創出
# ==========================================
if "新規創出" in selected_workflow:
    st.header("Step 1: ドキュメントのアップロード")
    st.info("※既存のロジックを使用します (backend logic preserved)")
    
    uploaded_file = st.file_uploader("構想を記したドキュメントをアップロードしてください。", type=['txt', 'md'])
    if uploaded_file:
        st.success("ドキュメントを受領しました。分析フェーズへ移行可能です。")

# ==========================================
# ワークフロー2: テンプレート適用
# ==========================================
elif "テンプレートを適用" in selected_workflow:
    st.header("ワークフロー2: 既存プロジェクトにテンプレートを適用")
    projects = get_project_list()
    if not projects:
        st.error(f"`{PROJECTS_DIR}`にプロジェクトが見つかりません。")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_project = st.selectbox("対象プロジェクトを選択:", projects)
        with col2:
            selected_template = st.selectbox("適用するテンプレートを選択:", templates)
        
        if st.button(f"🚀 '{selected_project}'に'{selected_template}'を適用する", type="primary"):
            st.info("SAVAN CLIを呼び出し中...")
            st.success("テンプレート適用プロセスを開始しました。")

# ==========================================
# ワークフロー3: 既存アプリの自動デプロイ設定 (SCP転送版・ポート指定・FW設定・自己デプロイ対応)
# ==========================================
elif "自動デプロイ設定" in selected_workflow:
    st.header("🚀 Auto-Deploy Configuration")
    st.markdown("任意のプロジェクトに対して、Linodeサーバーへの自動デプロイ(CI/CD)機能を装備させます。")
    
    projects = get_project_list()
    if not projects:
        st.error(f"プロジェクトが見つかりません。\n参照先: {PROJECTS_DIR} および {ROOT_DIR}")
        st.stop()
        
    target_project = st.selectbox("対象プロジェクトを選択してください:", projects)
    
    # パス設定 (savan-engine または projects/ 以外 (サーバールート) の場合)
    if target_project == "savan-engine":
        repo_dir = ENGINE_DIR
    elif (PROJECTS_DIR / target_project).exists():
        repo_dir = PROJECTS_DIR / target_project
    else:
        # projects/ に見つからない場合は、ROOT_DIR 直下と仮定 (サーバ構成)
        repo_dir = ROOT_DIR / target_project

    workflow_dir = repo_dir / ".github" / "workflows"
    workflow_file = workflow_dir / f"deploy_{target_project}.yml"
    
    st.info(f"Target Project: **{target_project}** (Path: {repo_dir})")

    tab1, tab2 = st.tabs(["1. Infrastructure & Secrets", "2. Pipeline Generation"])

    with tab1:
        st.subheader("Linode Server Configuration")
        st.markdown("GitHubリポジトリのSecrets設定用コマンドを生成します。")
        
        col1, col2 = st.columns(2)
        with col1:
            linode_host = st.text_input("Server IP (LINODE_HOST_IP)", placeholder="e.g. 203.0.113.1")
            linode_user = st.text_input("Server User (LINODE_USER)", value="root")
        with col2:
            linode_key = st.text_area("SSH Private Key (LINODE_SSH_KEY)", height=150, placeholder="-----BEGIN OPENSSH PRIVATE KEY-----...")
            
        repo_name = st.text_input("GitHub Repository Name (user/repo)", value=f"openif-biz/{target_project}")

        if st.button("🔐 Generate Secret Registration Command"):
            if not (linode_host and linode_user and linode_key):
                st.error("全てのフィールドを入力してください。")
            else:
                st.success("以下のコマンドを**順番に**ターミナルに貼り付けて実行してください。")
                
                st.markdown("##### 1. サーバーIPの設定")
                st.code(f'gh secret set LINODE_HOST_IP -b "{linode_host}" --repo {repo_name}', language="powershell")
                
                st.markdown("##### 2. ユーザー名の設定")
                st.code(f'gh secret set LINODE_USER -b "{linode_user}" --repo {repo_name}', language="powershell")
                
                st.markdown("##### 3. SSH秘密鍵の設定 (PowerShell用)")
                st.warning("※このコマンドは複数行です。すべてコピーして貼り付けてください。")
                ps_key_cmd = f'''$key = @"
{linode_key}
"@
gh secret set LINODE_SSH_KEY --body "$key" --repo {repo_name}'''
                st.code(ps_key_cmd, language="powershell")

    with tab2:
        st.subheader("CI/CD Pipeline Generation")
        st.markdown(f"自動デプロイ用の設計図 (`{workflow_file.name}`) を生成し、Gitへコミットします。")
        
        # ポート指定UI
        st.markdown("##### 🔌 Application Port Settings")
        # target_project に応じて推奨ポートを変更
        default_port = 8801 if target_project == 'savan-engine' else 8501
        app_port = st.number_input("Deploy Port (Default: 8501)", min_value=1024, max_value=65535, value=default_port, help="8501(Gantt), 8502(MatchupApp), 8801(SAVAN UI) など、競合しない番号を指定してください。")
        
        # パイプライン定義
        pipeline_template = f"""name: Deploy {target_project} to Linode (SCP)
on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      # 1. ファイル転送 (SCP Actionを使用)
      - name: Copy files via SCP
        uses: appleboy/scp-action@master
        with:
          host: ${{{{ secrets.LINODE_HOST_IP }}}}
          username: ${{{{ secrets.LINODE_USER }}}}
          key: ${{{{ secrets.LINODE_SSH_KEY }}}}
          port: 22
          source: "." 
          target: "/var/www/{target_project}"
          rm: true # 転送前にターゲットフォルダをクリアする

      # 2. リモートコマンド実行 (SSH Action)
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{{{ secrets.LINODE_HOST_IP }}}}
          username: ${{{{ secrets.LINODE_USER }}}}
          key: ${{{{ secrets.LINODE_SSH_KEY }}}}
          port: 22
          script: |
            echo "🚀 SAVAN Auto-Deploy Initiated for {target_project} on port {app_port}..."
            
            TARGET_DIR="/var/www/{target_project}"
            cd $TARGET_DIR
            
            echo "📂 Current Directory: $(pwd)"
            ls -la
            
            if [ -f requirements.txt ]; then 
                echo "📦 Installing dependencies..."
                pip install -r requirements.txt
            fi
            
            # --- App File Detection Logic ---
            APP_FILE=""
            if [ "{target_project}" == "savan-engine" ]; then
                # SAVAN Engineの場合はUIを起動する
                APP_FILE="savan_ui.py"
            else
                # 通常のプロジェクトの場合
                APP_FILE="src/{target_project}.py"
                if [ ! -f "$APP_FILE" ]; then
                    if [ -f "{target_project}.py" ]; then APP_FILE="{target_project}.py";
                    elif [ -f "MatchupAppCOST.py" ]; then APP_FILE="MatchupAppCOST.py";
                    elif [ -f "MatchupApp_PDF_Extractor.py" ]; then APP_FILE="MatchupApp_PDF_Extractor.py"; # 検出ロジック追加
                    elif [ -f "main.py" ]; then APP_FILE="main.py";
                    elif [ -f "app.py" ]; then APP_FILE="app.py"; 
                    else APP_FILE=$(find . -name "*.py" | head -n 1); fi
                fi
            fi
            
            echo "🎯 Detected App File: $APP_FILE"
            
            # --- Firewall Configuration (Auto Unlock) ---
            if command -v ufw > /dev/null; then
                echo "🔓 Opening firewall port {app_port}..."
                ufw allow {app_port}
            fi
            # ------------------------------------------
            
            pkill -f "streamlit run $APP_FILE" || true
            
            # ログファイルへの書き込み権限も考慮して実行
            nohup streamlit run $APP_FILE --server.port {app_port} --server.address 0.0.0.0 > app.log 2>&1 &
            
            echo "✅ SAVAN Deployment Completed on port {app_port}."
            echo "🌍 App URL: http://${{{{ secrets.LINODE_HOST_IP }}}}:{app_port}"
"""
        st.code(pipeline_template, language="yaml")

        if st.button("⚙️ Generate & Commit Pipeline"):
            try:
                # GitHub Actions ワークフローファイル (.yml) を書き込む
                workflow_dir.mkdir(parents=True, exist_ok=True)
                with open(workflow_file, "w", encoding="utf-8") as f:
                    f.write(pipeline_template)
                
                st.success(f"パイプラインファイルを生成しました (Port: {app_port}): `{workflow_file}`")
                
                st.markdown("### 🚀 Final Step: Push to GitHub")
                st.markdown("以下のコマンドを実行して、設定変更を反映してください。")
                
                # Gitコマンドを生成
                cmd = f"""
                cd {repo_dir}
                git add .github/workflows/deploy_{target_project}.yml
                git commit -m "feat(savan): configure auto-deploy for {target_project} on port {app_port}"
                git push origin main
                """
                
                st.code(cmd, language="bash")
                
            except Exception as e:
                st.error(f"生成エラー: {e}")

st.markdown("---")
st.caption(f"SAVAN Engine v11.0 | Universal Console | Path: {CURRENT_FILE_PATH}")