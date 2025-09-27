import sys
import os
import subprocess
import time
import requests
import yaml  # YAMLファイルを読み込むために追加
from contextlib import contextmanager
import knowledge_manager

# --- 関数定義 ---

@contextmanager
def run_streamlit_server(file_path, port=8501):
    """Streamlitアプリをバックグラウンドで起動し、終了時に確実に停止する"""
    command = ["streamlit", "run", file_path, "--server.port", str(port), "--server.headless", "true"]
    server_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[SAVAN] テストサーバー起動中... (PID: {server_process.pid})")
    time.sleep(10) # サーバーが完全に起動するのを待つ
    yield f"http://localhost:{port}"
    print(f"[SAVAN] テストサーバー停止中... (PID: {server_process.pid})")
    server_process.terminate()
    server_process.wait()
    print("[SAVAN] サーバー停止完了")

def generate_apps(spec_path="app_spec.yml"):
    """
    設計仕様書(YAML)を読み込み、アプリケーションのソースコードを自動生成する。
    """
    print(f"[SAVAN] 設計仕様書 {spec_path} に基づき、アプリの自動生成を実行します...")
    
    try:
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: 設計仕様書 {spec_path} が見つかりません。savan.pyと同じ階層に配置してください。")
        raise
    except yaml.YAMLError as e:
        print(f"ERROR: 設計仕様書 {spec_path} の解析中にエラーが発生しました: {e}")
        raise

    app_name = spec.get("appName", "GeneratedApp")
    app_type = spec.get("appType", "Streamlit")

    if app_type != "Streamlit":
        raise NotImplementedError("現在、Streamlitアプリの生成のみ対応しています。")

    code_lines = [
        "import streamlit as st",
        "",
        f"st.set_page_config(page_title='{app_name}')",
        ""
    ]

    for component in spec.get("components", []):
        comp_type = component.get("type")
        if comp_type == "title":
            code_lines.append(f"st.title(\"{component.get('text', '')}\")")
        elif comp_type == "button":
            label = component.get('label', 'Button')
            action = component.get('action', {})
            if action.get('type') == 'show_message':
                message = action.get('message', '')
                code_lines.append(f"if st.button(\"{label}\"):")
                code_lines.append(f"    st.success(\"{message}\")")

    generated_code = "\n".join(code_lines)

    apps_dir = "generated_apps"
    os.makedirs(apps_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    app_file_path = os.path.join(apps_dir, f"{app_name}_{timestamp}.py")
    
    with open(app_file_path, "w", encoding="utf-8") as f:
        f.write(generated_code)
    
    print(f"[SAVAN] アプリケーションコードを {app_file_path} に生成しました。")
    return app_file_path

def test_app(file_path):
    """
    生成されたアプリが正常に起動し、HTTP 200を返すかテストする。
    """
    print(f"[SAVAN] アプリのテストを実行します: {file_path}")
    try:
        with run_streamlit_server(file_path) as url:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                print(f"[SAVAN] テスト成功: {url} は正常に応答しました。")
                return True
            else:
                print(f"[SAVAN] テスト失敗: {url} がステータスコード {response.status_code} を返しました。")
                return False
    except Exception as e:
        print(f"[SAVAN] テスト中に例外が発生しました: {e}")
        return False

def push_to_github(timestamp, target):
    """GitHubへ変更をpushする"""
    print("[SAVAN] GitHubへのpushを実行します...")
    try:
        commit_message = f"SAVAN: Auto-generate and deploy app at {timestamp} [to-{target}]"
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git操作中にエラーが発生しました: {e}")
        return False

# --- メインのワークフロー ---
def main_workflow(target):
    """メインのワークフロー。エラー発生時に自己解決を試みる。"""
    print(f"===== SAVAN 自動化ワークフロー開始 (ターゲット: {target.upper()}) =====")
    try:
        # 1. 設計仕様書に基づいてアプリを生成
        generated_file = generate_apps()
        
        # 2. 生成されたアプリをテスト
        if not test_app(generated_file):
            raise Exception("生成されたアプリのテストに失敗しました。")
        
        # 3. 変更をGitHubにpush（これによりActionsが起動）
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if not push_to_github(timestamp, target):
            raise Exception("GitHubへのpushに失敗しました。")

        print(f"[SAVAN] GitHub Actionsを通じて [{target.upper()}] へのデプロイを起動しました。")
        print(f"===== SAVAN 自動化ワークフロー正常完了 (ターゲット: {target.upper()}) =====")

    except Exception as e:
        print(f"\n!!!!! ワークフロー実行中にエラーが発生しました !!!!!")
        print(f"エラー内容: {e}")
        
        # ---【自己解決（学習）機能】---
        print("\n>>> SAVANの記憶（ナレッジベース）を検索しています...")
        solution = knowledge_manager.find_solution_in_kb(e)
        
        if not solution:
            print(">>> 類似した解決策は見つかりませんでした。")
        # ---【自己解決機能ここまで】---

if __name__ == "__main__":
    target = None
    for arg in sys.argv:
        if arg.startswith("--target="):
            target = arg.split("=")[1]

    if target in ["linode", "gcp"]:
        main_workflow(target)
    else:
        print("実行方法: python savan.py --target=linode または python savan.py --target=gcp")

