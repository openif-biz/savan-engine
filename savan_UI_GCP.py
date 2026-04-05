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

# --- GASロボット用テンプレート (User Authority First版) ---
GAS_MANIFEST_TEMPLATE = """{
  "timeZone": "Asia/Tokyo",
  "dependencies": {
  },
  "exceptionLogging": "STACKDRIVER",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}"""

GAS_CODE_TEMPLATE = """// ----------------------------------------------------
// 【重要】設定項目 (SAVANにより自動生成)
// ----------------------------------------------------

/**
 * PDFを格納するルートフォルダの ID
 * ターゲット: {target_folder_name}
 */
const ROOT_DRIVE_FOLDER_ID = '{drive_folder_id}';

/**
 * 検索対象とするファイル名に含まれるキーワードリスト。
 */
const TARGET_KEYWORDS = {keywords_list}; 

// ----------------------------------------------------

/**
 * メイン関数：参加している全Chatスペースを自動検出し、全ての添付ファイルをダウンロードする。
 */
function processAllChatSpaces() {
  Logger.log('処理を開始します...');

  // 1. 全スペースを自動取得
  const spaces = fetchAllSpaces();
  Logger.log(`検出されたChatスペース数: ${spaces.length}件`);

  if (spaces.length === 0) {
    Logger.log('処理対象のスペースが見つかりませんでした。終了します。');
    return;
  }

  let totalFilesSaved = 0;

  // 2. 各スペースを巡回
  for (const space of spaces) {
    const spaceId = space.name.split('/')[1]; 
    const displayName = space.displayName || `名無しスペース_${spaceId}`;
    
    Logger.log(`\\n======================================================`);
    Logger.log(`== [開始] スペース: ${displayName}`);
    
    try {
      // フォルダ準備
      const targetFolder = getOrCreateDriveFolder(ROOT_DRIVE_FOLDER_ID, displayName);
      
      // メッセージ取得＆保存
      const filesSaved = downloadMessages(spaceId, targetFolder);
      totalFilesSaved += filesSaved;
      
      Logger.log(`== [完了] スペース: ${displayName} 保存数: ${filesSaved}`);
    } catch (e) {
      Logger.log(`❌ スペース処理エラー (${displayName}): ${e.toString()}`);
    }
  }
  
  Logger.log(`\\n--- 全処理終了 ---`);
  Logger.log(`Driveに保存したPDFファイル総数: ${totalFilesSaved}`);
}

/**
 * 参加しているChatスペースの一覧を取得する関数
 */
function fetchAllSpaces() {
  const spaces = [];
  let pageToken = null;
  const baseUrl = 'https://chat.googleapis.com/v1/spaces';
  
  const options = {
    'method': 'get',
    'headers': { 'Authorization': `Bearer ${ScriptApp.getOAuthToken()}` },
    'muteHttpExceptions': true
  };

  do {
    let url = `${baseUrl}?pageSize=100`;
    if (pageToken) url += `&pageToken=${pageToken}`;
    
    const response = UrlFetchApp.fetch(url, options);
    
    if (response.getResponseCode() !== 200) {
      Logger.log(`⚠️ スペース一覧取得エラー: Code ${response.getResponseCode()}`);
      break;
    }
    
    const data = JSON.parse(response.getContentText());
    if (data.spaces && data.spaces.length > 0) {
      spaces.push(...data.spaces);
    }
    pageToken = data.nextPageToken;
    
  } while (pageToken);
  
  return spaces;
}

/**
 * 指定スペースのメッセージからファイルをダウンロード
 */
function downloadMessages(spaceId, targetFolder) {
  let filesSaved = 0;
  let pageToken = null;
  const chatUrl = `https://chat.googleapis.com/v1/spaces/${spaceId}/messages`;
  
  const options = {
    'method': 'get',
    'headers': { 'Authorization': `Bearer ${ScriptApp.getOAuthToken()}` },
    'muteHttpExceptions': true
  };

  // 最新100件を取得
  do {
    let apiUrl = chatUrl + '?pageSize=100'; 
    if (pageToken) apiUrl += `&pageToken=${pageToken}`;

    const response = UrlFetchApp.fetch(apiUrl, options);
    
    if (response.getResponseCode() !== 200) {
      Logger.log(`❌ APIエラー (メッセージ取得): Code ${response.getResponseCode()}`);
      break; 
    }

    const data = JSON.parse(response.getContentText());
    const messages = data.messages || [];

    for (const message of messages) {
      filesSaved += processMessageAttachments(message, targetFolder, options);
    }

    pageToken = data.nextPageToken;

  } while (pageToken); 

  return filesSaved;
}

/**
 * 添付ファイルの判定と保存（Media API直撃版）
 */
function processMessageAttachments(message, targetFolder, options) {
  let savedCount = 0;
  if (!message.attachment || message.attachment.length === 0) return 0;

  for (const attachment of message.attachment) {
    
    if (attachment.attachmentDataRef) {
      const resourceName = attachment.attachmentDataRef.resourceName;
      Logger.log(`🔍 発見: ${attachment.name}`);

      try {
        const downloadUrl = `https://chat.googleapis.com/v1/media/${resourceName}?alt=media`;
        const fileResponse = UrlFetchApp.fetch(downloadUrl, options);
        
        if (fileResponse.getResponseCode() === 200) {
             const fileName = attachment.name;
             const fileBlob = fileResponse.getBlob().setName(fileName);
             
             if (!targetFolder.getFilesByName(fileName).hasNext()) {
                targetFolder.createFile(fileBlob);
                savedCount++;
                Logger.log(`✅ 成功: ${fileName}`);
             } else {
                Logger.log(`ℹ️ スキップ (保存済): ${fileName}`);
             }
        } else {
             Logger.log(`❌ ダウンロード失敗: Code ${fileResponse.getResponseCode()}`);
             Logger.log(fileResponse.getContentText());
        }
      } catch (e) {
        Logger.log(`❌ 保存時例外: ${e.toString()}`);
      }
    }
  }
  return savedCount;
}

/**
 * フォルダ取得・作成
 */
function getOrCreateDriveFolder(parentFolderId, folderName) {
  const parentFolder = DriveApp.getFolderById(parentFolderId);
  const folders = parentFolder.getFoldersByName(folderName);
  return folders.hasNext() ? folders.next() : parentFolder.createFolder(folderName);
}
"""

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
    "既存アプリの自動デプロイ設定 (Auto-Deploy Config)",
    "Google Workspace連携ロボットを生成する (GAS Bot)" # 【追加】
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
            st.info("SAVAN CLIを呼び出し中...")
            st.success("テンプレート適用プロセスを開始しました。")

# ==========================================
# ワークフロー3: 既存アプリの自動デプロイ設定 (Strong Mode w/ Zombie & Docker Killer)
# ==========================================
elif "自動デプロイ設定" in selected_workflow:
    st.header("🚀 Auto-Deploy Configuration (Strong Mode)")
    st.markdown("任意のプロジェクトに対して、Linodeサーバーへの自動デプロイ(CI/CD)機能を付与します。")
    st.caption("✅ Includes: Docker Killer, Process Zombie Killer (fuser), Firewall Auto-Unlock (ufw)")
    
    projects = get_project_list()
    if not projects:
        st.error(f"プロジェクトが見つかりません。\n参照先: {PROJECTS_DIR} および {ROOT_DIR}")
        st.stop()
        
    target_project = st.selectbox("対象プロジェクトを選択してください:", projects)
    
    # パス設定
    if target_project == "savan-engine":
        repo_dir = ENGINE_DIR
    elif (PROJECTS_DIR / target_project).exists():
        repo_dir = PROJECTS_DIR / target_project
    else:
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
            linode_host = st.text_input("Server IP (LINODE_HOST_IP)", value="172.237.4.248")
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
        default_port = 8801 if target_project == 'savan-engine' else 8501
        app_port = st.number_input("Deploy Port (Default: 8501)", min_value=1024, max_value=65535, value=default_port)
        
        # パイプライン定義 (SCP & SSH & Zombie Killer & Docker Killer)
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
            echo "🚀 SAVAN Strong-Deploy Initiated for {target_project} on port {app_port}..."
            
            # 0. 準備: fuserコマンドが使えるようにする (Zombie Killer用)
            export DEBIAN_FRONTEND=noninteractive

            TARGET_DIR="/var/www/{target_project}"
            
            # ディレクトリが存在しない場合は作成 (初回デプロイ対応)
            if [ ! -d "$TARGET_DIR" ]; then
                echo "📂 Creating target directory: $TARGET_DIR"
                mkdir -p $TARGET_DIR
            fi
            
            cd $TARGET_DIR
            
            echo "📂 Current Directory: $(pwd)"
            
            if [ -f requirements.txt ]; then 
                echo "📦 Installing dependencies..."
                pip install -r requirements.txt
            fi
            
            # --- App File Detection Logic (Smart) ---
            APP_FILE=""
            if [ "{target_project}" == "savan-engine" ]; then
                APP_FILE="savan_ui.py"
            else
                APP_FILE="src/{target_project}.py"
                if [ ! -f "$APP_FILE" ]; then
                    if [ -f "{target_project}.py" ]; then APP_FILE="{target_project}.py";
                    elif [ -f "MatchupAppCOST.py" ]; then APP_FILE="MatchupAppCOST.py";
                    elif [ -f "MatchupApp_PDF_Extractor.py" ]; then APP_FILE="MatchupApp_PDF_Extractor.py";
                    elif [ -f "gantt_line.py" ]; then APP_FILE="gantt_line.py";
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
            
            # --- DOCKER KILLER (Added in v12.3) ---
            # Dockerコンテナがポートを占有している場合に備えて強制排除する
            if command -v docker > /dev/null; then
                echo "🐳 Checking for Docker ghosts..."
                # 全てのコンテナを停止・削除 (Strong Mode Policy)
                # エラーが出ても止まらないように || true をつける
                docker rm -f $(docker ps -aq) || true
                echo "🐳 Docker ghosts eradicated."
            fi

            # --- Process Kill (Strong Mode: Zombie Killer) ---
            echo "💀 Killing process on port {app_port}..."
            
            # Method A: Kill by PORT (Most reliable)
            if command -v fuser > /dev/null; then
                fuser -k {app_port}/tcp || true
            else
                # Method B: Fallback to pkill
                echo "⚠️ 'fuser' not found, using pkill..."
                pkill -f "streamlit run $APP_FILE" || true
            fi
            
            # Wait a moment for port to free up
            sleep 2
            
            # --- Restart App ---
            echo "🌟 Starting new process..."
            nohup streamlit run $APP_FILE --server.port {app_port} --server.address 0.0.0.0 > app.log 2>&1 &
            
            echo "✅ SAVAN Deployment Completed on port {app_port}."
            echo "🌍 App URL: http://${{{{ secrets.LINODE_HOST_IP }}}}:{app_port}"
"""
        st.code(pipeline_template, language="yaml")

        if st.button("⚙️ Deploy (Generate & Push Automatically)"):
            try:
                # GitHub Actions ワークフローファイル生成
                workflow_dir.mkdir(parents=True, exist_ok=True)
                with open(workflow_file, "w", encoding="utf-8") as f:
                    f.write(pipeline_template)
                
                st.success(f"パイプライン生成完了: `{workflow_file}`")
                
                st.markdown("### 🚀 Git自動操作: GitHubへプッシュ中...")
                
                repo_dir_str = str(repo_dir.resolve())
                
                with st.spinner(f"Git操作を実行中... ({repo_dir_str})"):
                    # git add
                    cmd_add = ["git", "add", "."]
                    subprocess.run(cmd_add, cwd=repo_dir_str, check=True)

                    # git commit
                    commit_msg = f"feat(savan): strong-deploy config for {target_project} on port {app_port}"
                    subprocess.run(["git", "commit", "-m", commit_msg], cwd=repo_dir_str, stderr=subprocess.DEVNULL)

                    # git push
                    cmd_push = ["git", "push", "origin", "main"]
                    result_push = subprocess.run(cmd_push, cwd=repo_dir_str, capture_output=True, text=True, encoding='utf-8')
                    
                    if result_push.returncode != 0:
                        st.error(f"git push に失敗しました:\n{result_push.stderr}")
                        st.stop()
                    
                    st.text(result_push.stderr)

                st.success("✅ デプロイがトリガーされました！ GitHub Actionsで実行状況を確認してください。")
                st.balloons()

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# ==========================================
# ワークフロー4: Google Workspace連携ロボット生成 (User Authority First)
# ==========================================
elif "Google Workspace連携ロボット" in selected_workflow:
    st.header("🤖 Google Workspace Bot Generator (User Authority First)")
    st.write("ユーザー自身の権限を活用して、ChatやDriveと連携する自動化ロボット(GAS)を生成・設定します。")
    st.info("💡 サービスアカウントは使用しません。あなた自身のGoogleアカウント権限で安全に動作します。")
    
    with st.form("gas_bot_form"):
        col1, col2 = st.columns(2)
        with col1:
            bot_name = st.text_input("ロボット名 (プロジェクト名)", value="ChatPDFDownloader", help="半角英数字推奨")
            drive_folder_id = st.text_input("保存先DriveフォルダID", help="ブラウザURLの末尾のIDを入力 (例: 1j68k4k...)")
        with col2:
            target_keywords = st.text_input("検索キーワード (カンマ区切り)", value="完了報告書, 調査報告書, 完成図書")
            gcp_project_id = st.text_input("GCPプロジェクトID (新規作成用)", value="iina-chat-bot-00X", help="一意なIDを指定 (例: my-company-bot-001)")

        submitted = st.form_submit_button("🚀 ロボット資材を生成＆手順を表示")

    if submitted:
        if not bot_name or not drive_folder_id or not gcp_project_id:
            st.error("全ての項目を入力してください。")
        else:
            # 1. ディレクトリ作成
            target_dir = PROJECTS_DIR / bot_name
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 2. appsscript.json 生成
            manifest_path = target_dir / "appsscript.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(GAS_MANIFEST_TEMPLATE)
            
            # 3. code.gs 生成
            # JS形式の配列文字列に変換 (例: ['A', 'B'])
            keywords_list_str = str([k.strip() for k in target_keywords.split(",")]).replace("'", '"')
            code_content = GAS_CODE_TEMPLATE.replace("{drive_folder_id}", drive_folder_id)\
                                            .replace("{keywords_list}", keywords_list_str)\
                                            .replace("{target_folder_name}", "指定フォルダ")
            
            code_path = target_dir / "コード.gs"
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code_content)
                
            st.success(f"✅ ロボット資材を `{target_dir}` に生成しました！")
            
            # 4. セットアップ手順の表示 (User Authority First Protocol)
            st.markdown("---")
            st.subheader("🛠️ セットアップ手順 (User Authority First Protocol)")
            st.info("以下の手順に従って、ターミナルとブラウザで設定を行ってください。")

            st.markdown("#### 手順 1: GCPプロジェクトの構築 (ターミナル)")
            st.code(f"""
# 1. ログイン (管理者権限)
gcloud auth login

# 2. プロジェクト作成
gcloud projects create {gcp_project_id} --name="{bot_name}"

# 3. ターゲット切り替え
gcloud config set project {gcp_project_id}

# 4. API有効化
gcloud services enable chat.googleapis.com
gcloud services enable drive.googleapis.com

# 5. プロジェクト番号の取得 (この番号をコピーしてください)
gcloud projects describe {gcp_project_id} --format="value(projectNumber)"
""", language="bash")

            st.markdown(f"#### 手順 2: GASプロジェクトとの紐付け (ブラウザ)")
            st.markdown(f"1. [GASエディタ](https://script.google.com/)を開き、生成された `{bot_name}` プロジェクトを開く。")
            st.markdown("2. 左メニュー「プロジェクトの設定」 > 「GCPプロジェクトを変更」をクリック。")
            st.markdown("3. **手順1で取得したプロジェクト番号**を入力して保存。")
            st.markdown(f"   * ※エラーが出る場合は、[OAuth同意画面設定](https://console.cloud.google.com/apis/credentials/consent?project={gcp_project_id}) から「内部」で作成し、必須項目のみ入力して保存してください。")

            st.markdown("#### 手順 3: アプリ構成の設定 (ブラウザ)")
            st.markdown(f"1. [Chat API設定画面](https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat?project={gcp_project_id}) を開く。")
            st.markdown("2. 以下の通り入力して保存する。")
            st.markdown("""
            * **アプリ名**: `ChatBot`
            * **アバターURL**: `https://fonts.gstatic.com/s/i/productlogos/googleg_48dp/v6/192px.svg`
            * **説明**: `Bot`
            * **インタラクティブ機能**: **OFF** (重要！)
            """)
            
            st.markdown("#### 手順 4: コードの反映と実行")
            st.markdown("1. 生成された `appsscript.json` と `コード.gs` の中身を、GASエディタにコピペする。")
            st.markdown("2. `processAllChatSpaces` を実行し、権限を承認する。")

st.markdown("---")
st.caption(f"SAVAN Engine v12.3 (Strongest) | Universal Console | Path: {CURRENT_FILE_PATH}")