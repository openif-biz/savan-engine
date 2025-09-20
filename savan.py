import sys
import os
import subprocess
import time
import requests
from contextlib import contextmanager
import knowledge_manager # <<<【追加】記憶マネージャーをインポート

# --- 以前からあった関数定義（内容はそのまま維持） ---

@contextmanager
def run_streamlit_server(file_path, port=8501):
    """Streamlitアプリをバックグラウンドで起動し、終了時に確実に停止する"""
    command = ["streamlit", "run", file_path, "--server.port", str(port), "--server.headless", "true"]
    server_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"[SAVAN] テストサーバー起動中... (PID: {server_process.pid})")
    time.sleep(10)
    yield f"http://localhost:{port}"
    print(f"[SAVAN] テストサーバー停止中... (PID: {server_process.pid})")
    server_process.terminate()
    server_process.wait()
    print("[SAVAN] サーバー停止完了")

def generate_apps(timestamp):
    """
    (この関数の中身は、以前ユキさんが持っていた実装のままにしてください)
    """
    print("[SAVAN] アプリの自動生成を実行します...")
    # (仮の実装)
    apps_dir = "generated_apps"
    os.makedirs(apps_dir, exist_ok=True)
    app_file = os.path.join(apps_dir, f"savan_app_{timestamp}.py")
    with open(app_file, "w", encoding="utf-8") as f:
        f.write("import streamlit as st\nst.title('Generated App')")
    return app_file

def test_app(file_path):
    """
    (この関数の中身は、以前ユキさんが持っていた実装のままにしてください)
    """
    print(f"[SAVAN] アプリのテストを実行します: {file_path}")
    # (仮の実装)
    try:
        with run_streamlit_server(file_path) as url:
            response = requests.get(url, timeout=10)
            return response.status_code == 200
    except Exception:
        return False

def push_to_github(timestamp, target): # target を受け取る
    """
    (この関数の中身は、以前ユキさんが持っていた実装のままにしてください)
    """
    print("[SAVAN] GitHubへのpushを実行します...")
    # (仮の実装)
    try:
        commit_message = f"SAVAN: Auto-generate app at {timestamp} [to-{target}]" # メッセージに荷札を追加
        subprocess.run(["git", "add", "generated_apps/"], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def deploy_on_linode():
    """
    (この関数の中身は、以前ユキさんが持っていた実装のままにしてください)
    """
    print("[SAVAN] Linodeへのデプロイを実行します...")
    # (仮の実装)
    # 実際にはSSH経由で 'git pull' と 'docker-compose up' を実行する
    return True

# --- メインのワークフロー（exceptブロックに学習機能を追加）---

def main_workflow(target): # target を受け取る
    """
    メインのワークフロー。エラーが発生した場合、ナレッジベースを検索する。
    """
    print(f"===== SAVAN 自動化ワークフロー開始 (ターゲット: {target.upper()}) =====")
    try:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        generated_file = generate_apps(timestamp)
        
        if not test_app(generated_file):
            raise Exception("アプリのテストに失敗しました。")

        if not push_to_github(timestamp, target): # target を渡す
            raise Exception("GitHubへのpushに失敗しました。")

        # この関数は現在、直接的なデプロイは行わないが、ロジックの骨格として残す
        if target == "linode":
            if not deploy_on_linode():
                raise Exception("Linodeへのデプロイに失敗しました。")
        
        print(f"[SAVAN] GitHub Actionsを通じて [{target.upper()}] へのデプロイを起動しました。")
        print(f"===== SAVAN 自動化ワークフロー正常完了 (ターゲット: {target.upper()}) =====")

    except Exception as e:
        print(f"\n!!!!! ワークフロー実行中にエラーが発生しました !!!!!")
        print(f"エラー内容: {e}")
        
        # ---【ここからが学習機能】---
        print("\n>>> SAVANの記憶（ナレッジベース）を検索しています...")
        solution = knowledge_manager.find_solution_in_kb(e)
        
        if not solution:
            print(">>> 類似した解決策は見つかりませんでした。")
        # ---【学習機能ここまで】---

if __name__ == "__main__":
    # 実行時の引数を解析して、ターゲットを決定する
    target = None
    for arg in sys.argv:
        if arg.startswith("--target="):
            target = arg.split("=")[1]

    if target in ["linode", "gcp"]:
        main_workflow(target)
    else:
        # 以前の --start も動くように互換性を維持
        if "--start" in sys.argv:
             print("警告: --start は非推奨です。--target=linode を使用してください。")
             main_workflow("linode")
        else:
             print("実行方法: python savan.py --target=linode または python savan.py --target=gcp")
