import sys
import os
import subprocess
import time
import yaml
from contextlib import contextmanager
import knowledge_manager

# --- 関数定義 ---

def get_project_path(project_name):
    """プロジェクト名からプロジェクトの絶対パスを取得する"""
    # このスクリプト(savan.py)の親ディレクトリを基準とする
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(base_dir, '..', 'projects', project_name)
    return os.path.abspath(project_path)

def push_to_github(project_path, timestamp, target):
    """
    指定されたプロジェクトのディレクトリに移動し、GitHubへ変更をpushする
    """
    print(f"[SAVAN] プロジェクト {os.path.basename(project_path)} のGitHubへのpushを実行します...")
    
    # --- 重要：Git操作の前に、必ずプロジェクトのディレクトリに移動する ---
    original_cwd = os.getcwd()
    try:
        os.chdir(project_path)
        print(f"[SAVAN] 作業ディレクトリを {project_path} に変更しました。")

        commit_message = f"SAVAN Central Engine: Deploy trigger for {os.path.basename(project_path)} at {timestamp} [to-{target}]"
        
        subprocess.run(["git", "add", "."], check=True)
        # 変更がない場合もコミットするため --allow-empty を使用
        subprocess.run(["git", "commit", "--allow-empty", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print(f"[SAVAN] プロジェクト {os.path.basename(project_path)} のpushに成功しました。")
        return True
    except FileNotFoundError:
        print(f"ERROR: Gitリポジトリが見つかりません。パスを確認してください: {project_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Git操作中にエラーが発生しました: {e}")
        return False
    finally:
        # --- 重要：元のディレクトリに戻る ---
        os.chdir(original_cwd)
        print(f"[SAVAN] 作業ディレクトリを {original_cwd} に戻しました。")


# --- メインのワークフロー ---
def main_workflow(target, project_name):
    """
    指定されたプロジェクトのデプロイを起動するメインワークフロー
    """
    print(f"===== SAVAN 中央エンジン 自動化ワークフロー開始 =====")
    print(f"ターゲットプラットフォーム: {target.upper()}")
    print(f"対象プロジェクト: {project_name}")
    
    project_path = get_project_path(project_name)

    if not os.path.isdir(project_path):
        print(f"\n!!!!! プロジェクトフォルダが見つかりません !!!!!")
        print(f"エラー: 指定されたプロジェクト '{project_name}' は存在しません。")
        print(f"確認したパス: {project_path}")
        return

    try:
        # このワークフローはデプロイの起動のみを担当
        # アプリの生成やテストは別のコマンド体系で行う想定
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if not push_to_github(project_path, timestamp, target):
            raise Exception("GitHubへのpushに失敗しました。")

        print(f"\n[SAVAN] GitHub Actionsを通じて [{target.upper()}] へのデプロイを起動しました。")
        print(f"===== SAVAN 自動化ワークフロー正常完了 =====")

    except Exception as e:
        print(f"\n!!!!! ワークフロー実行中にエラーが発生しました !!!!!")
        print(f"エラー内容: {e}")
        
        print("\n>>> SAVANの記憶（ナレッジベース）を検索しています...")
        solution = knowledge_manager.find_solution_in_kb(e)
        
        if not solution:
            print(">>> 類似した解決策は見つかりませんでした。")

if __name__ == "__main__":
    target = None
    project_name = None

    # コマンドライン引数を解析
    for arg in sys.argv[1:]:
        if arg.startswith("--target="):
            target = arg.split("=")[1]
        elif arg.startswith("--project="):
            project_name = arg.split("=")[1]

    if target in ["linode", "gcp"] and project_name:
        main_workflow(target, project_name)
    else:
        print("\n実行方法:")
        print("python savan.py --target=<ターゲット> --project=<プロジェクト名>")
        print("\n例:")
        print("python savan.py --target=linode --project=gantt_line")
        print("\n説明:")
        print("  --target: デプロイ先プラットフォーム (linode または gcp)")
        print("  --project: 'projects'フォルダ内にある、対象のプロジェクト名")

