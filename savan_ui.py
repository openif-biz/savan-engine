# 【通番18】savan_ui.py 最終決定版 改3（GitHubプレビュー追加）
import streamlit as st
import sys
import os
import subprocess
import time
import yaml
from contextlib import contextmanager
from llama_cpp import Llama
import tempfile

# --- 設定 ---
def get_model_path():
    # スクリプトの場所に基づいて、ワークスペースのルートを堅牢に特定
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(workspace_root, "models", "deepseek-coder-6.7b-instruct.Q4_K_M.gguf")

MODEL_PATH = get_model_path()

# --- バックエンド処理 1: AIによる分析フェーズ ---
def analyze_document_and_propose_spec(document_content):
    """ドキュメントを分析し、app_spec.ymlの内容とプロジェクト名を提案する"""
    st.info("[SAVAN] AIアーキテクトが入力ドキュメントを分析・蒸留しています...")
    spec_content = ""
    try:
        # 'with'構文を使うことで、リソース管理を自動化
        with load_llm() as llm:
            if llm is None:
                raise Exception("AIエンジンの起動に失敗しました。")
            prompt = f"""### Instruction ###
You are a senior system architect. Analyze the user's document and distill its essence into a structured YAML format with `app_name`, `concept`, and `basic_functions`. Strictly output only the YAML content inside a ```yaml code block.
### User's Document ###
{document_content}
### Output YAML ###
```yaml
"""
            output = llm(prompt, max_tokens=1024, stop=["```"], echo=False, temperature=0.2)
            spec_content = output['choices'][0]['text'].strip()
            if spec_content.startswith("yaml"):
                spec_content = spec_content[4:].strip()
            
            spec_data = yaml.safe_load(spec_content)
            project_name = spec_data.get('app_name', 'Unnamed_Project')
            st.success(f"[SAVAN] 骨格の生成に成功。プロジェクト名 '{project_name}' を提案します。")
            
            return project_name, spec_content, True

    except Exception as e:
        st.error(f"ERROR: AIによるapp_spec.ymlの骨格生成に失敗しました。\nエラー詳細: {e}")
        st.code(f"AIの出力:\n---\n{spec_content}\n---", language='yaml')
        return None, None, False

# --- バックエンド処理 2: プロジェクト創出の実行フェーズ ---
def execute_project_creation(project_name, spec_content):
    """提案に基づき、実際にファイルとリポジトリを作成する"""
    st.info(f"[SAVAN] プロジェクト '{project_name}' の創出を開始します。")
    project_path, success = create_project_scaffolding(project_name, spec_content)
    if not success:
        st.error("!!!!! プロジェクト創出ワークフローが中断されました !!!!!")
        return False
    
    success = initialize_git_and_create_repo(project_path)
    if not success:
        st.error("!!!!! プロジェクト創出ワークフローが中断されました !!!!!")
        return False
        
    st.balloons()
    st.success(f"===== SAVAN 構想具体化ワークフロー正常完了 =====")
    return True

# --- ヘルパー関数群 (変更なし) ---
@contextmanager
def load_llm():
    if not os.path.exists(MODEL_PATH):
        st.error(f"ERROR: AIモデルファイルが見つかりません: {MODEL_PATH}")
        yield None; return
    with st.spinner("[SAVAN] AIエンジンを起動しています..."):
        llm = Llama(model_path=MODEL_PATH, n_ctx=4096, n_gpu_layers=-1, verbose=False)
    st.success("[SAVAN] AIエンジン起動完了。")
    yield llm
    st.info("[SAVAN] AIエンジンを停止します。")

def get_workspace_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def create_project_scaffolding(project_name, generated_spec_content):
    workspace_root = get_workspace_root()
    project_path = os.path.join(workspace_root, 'projects', project_name)
    st.info(f"[SAVAN] プロジェクトフォルダを作成しています: {project_path}")
    if os.path.exists(project_path):
        st.error(f"ERROR: プロジェクトフォルダ '{project_name}' は既に存在します。")
        return None, False
    src_dir = os.path.join(project_path, 'src')
    os.makedirs(src_dir)
    st.write(f" - フォルダを作成しました: {src_dir}")
    gitignore_content = "# Python\n__pycache__/\n*.pyc\n.env\n.venv\n"
    with open(os.path.join(project_path, '.gitignore'), 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    st.write(" - .gitignore を作成しました。")
    with open(os.path.join(project_path, 'app_spec.yml'), 'w', encoding='utf-8') as f:
        f.write(generated_spec_content)
    st.write(" - app_spec.yml を配置しました。")
    with open(os.path.join(project_path, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(f"# {project_name}\n\nこのプロジェクトはSAVANによって自動生成されました。")
    st.write(" - README.md を作成しました。")
    return project_path, True

def initialize_git_and_create_repo(project_path):
    project_name = os.path.basename(project_path)
    original_cwd = os.getcwd()
    try:
        os.chdir(project_path)
        st.info("[SAVAN] Gitリポジトリを初期化しています...")
        subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
        st.info(f"[SAVAN] GitHubに新しいリポジトリ openif-biz/{project_name} を作成または接続します...")
        command = ["gh", "repo", "create", f"openif-biz/{project_name}", "--private", "--source=."]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            if "Name already exists" in result.stderr:
                st.warning("INFO: GitHubリポジトリは既に存在します。既存のリポジトリに接続します。")
                remote_check = subprocess.run(["git", "remote"], capture_output=True, text=True)
                if "origin" not in remote_check.stdout:
                    subprocess.run(["git", "remote", "add", "origin", f"git@github.com:openif-biz/{project_name}.git"], check=True)
            else:
                raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
        st.info("[SAVAN] 変更をコミットしています...")
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit by SAVAN"], check=True, capture_output=True)
        st.info("[SAVAN] GitHubへ初回pushを実行しています...")
        subprocess.run(["git", "push", "-u", "origin", "main"], check=True, capture_output=True)
        st.success(f"[SAVAN] GitHubリポジトリの準備が完了しました。")
        st.info(f"URL: [https://github.com/openif-biz/](https://github.com/openif-biz/){project_name}")
        return True
    except FileNotFoundError:
        st.error("ERROR: 'gh' コマンドが見つかりません。GitHub CLIがインストールされているか確認してください。")
        return False
    except subprocess.CalledProcessError as e:
        st.error(f"ERROR: GitまたはGitHubリポジトリの操作に失敗しました。\n{e.stderr}")
        return False
    finally:
        os.chdir(original_cwd)

# --- フロントエンド UI ---
if "step" not in st.session_state:
    st.session_state.step = "upload_document" 

st.set_page_config(layout="wide")
st.title("SAVAN - Universal Project Creator")
st.markdown("---")

if st.session_state.step == "upload_document":
    st.header("Step 1: ドキュメントのアップロード")
    uploaded_file = st.file_uploader("構想を記したドキュメントをアップロードしてください。", type=['txt', 'md'])
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.step = "confirm_analysis"
        st.rerun()

elif st.session_state.step == "confirm_analysis":
    st.header("Step 2: ドキュメント分析の開始")
    st.info(f"ファイル '{st.session_state.uploaded_file.name}' を受信しました。")
    if st.button("🚀 AIによる分析を開始する", type="primary"):
        st.session_state.step = "analyzing"
        st.rerun()

elif st.session_state.step == "analyzing":
    st.header("Step 2: ドキュメント分析中...")
    document_content = st.session_state.uploaded_file.getvalue().decode("utf-8")
    project_name, spec_content, success = analyze_document_and_propose_spec(document_content)
    if success:
        st.session_state.project_name = project_name
        st.session_state.spec_content = spec_content
        st.session_state.step = "preview_and_confirm"
        st.rerun()
    else:
        st.session_state.step = "upload_document" # エラー時は最初に戻る
        st.error("分析に失敗しました。最初からやり直してください。")
        # エラー表示のためにrerunはボタン押下時にする
        
elif st.session_state.step == "preview_and_confirm":
    st.header("Step 3: 実行内容の確認と承認")
    st.info("AIによる分析が完了しました。以下の内容でプロジェクトを創出してよろしいですか？")
    
    project_name = st.session_state.project_name
    workspace_root = get_workspace_root()
    project_path = os.path.join(workspace_root, 'projects', project_name)

    st.subheader("提案プロジェクト名")
    st.code(project_name, language="text")

    st.subheader("生成されるローカルフォルダ構成（プレビュー）")
    st.code(f"""
{project_path}
├── src/
├── .gitignore
├── app_spec.yml
└── README.md
    """, language="bash")
    
    # --- ▼▼▼【機能追加】GitHubリポジトリのプレビュー ▼▼▼ ---
    st.subheader("作成されるGitHubリポジトリ（プレビュー）")
    st.info("以下のプライベートリポジトリがGitHub上に作成（または接続）され、ローカルのファイルがpushされます。")
    st.code(f"[https://github.com/openif-biz/](https://github.com/openif-biz/){project_name}", language="text")
    # --- ▲▲▲【機能追加】▲▲▲ ---

    st.subheader("生成される app_spec.yml の内容")
    st.code(st.session_state.spec_content, language="yaml")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 承認して環境構築を開始する", type="primary"):
            st.session_state.step = "creating_project"
            st.rerun()
    with col2:
        if st.button("❌ キャンセルしてやり直す"):
            # セッション状態をクリアして最初のステップに戻る
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

elif st.session_state.step == "creating_project":
    st.header("Step 4: プロジェクト創出を実行中...")
    execute_project_creation(st.session_state.project_name, st.session_state.spec_content)
    st.session_state.step = "finished"
    st.rerun()

elif st.session_state.step == "finished":
    st.header("完了")
    st.success("プロジェクトの創出が完了しました。")
    if st.button("新しいプロジェクトを開始する"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

