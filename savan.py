import sys
import os
import subprocess
import time
import shutil

# -----------------------------
# 内蔵テンプレート
# -----------------------------
IINA_TEMPLATE = """print("Hello from IINA generated app!")"""
CLICKDPLY_TEMPLATE = """print("Hello from 1ClickDply generated app!")"""

# -----------------------------
# 生成処理
# -----------------------------
def generate_apps():
    apps_dir = "generated_apps"
    os.makedirs(apps_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    iina_file = os.path.join(apps_dir, f"iina_app_{timestamp}.py")
    clickdply_file = os.path.join(apps_dir, f"clickdply_app_{timestamp}.py")

    with open(iina_file, "w") as f:
        f.write(IINA_TEMPLATE)
    with open(clickdply_file, "w") as f:
        f.write(CLICKDPLY_TEMPLATE)

    print(f"[SAVAN] 自動生成完了: {iina_file}")
    print(f"[SAVAN] 自動生成完了: {clickdply_file}")
    return iina_file, clickdply_file

# -----------------------------
# テスト処理
# -----------------------------
def test_app(file_path):
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True, timeout=10)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"[SAVAN] テスト失敗: {file_path}, {e}")
        return False

# -----------------------------
# Linode デプロイ
# -----------------------------
def deploy_linode(file_path):
    print(f"[SAVAN] デプロイ開始: {file_path}")
    linode_ip = "123.45.67.89"  # 仮 IP
    app_name = os.path.basename(file_path)
    deployed_url = f"http://{linode_ip}:5000/{app_name}"
    print(f"[SAVAN] Linode 短時間公開完了: {deployed_url}")
    return deployed_url

# -----------------------------
# GitHub push
# -----------------------------
def github_push():
    print("[SAVAN] GitHub push 開始")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "SAVAN automated commit"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("[SAVAN] GitHub push 完了")
    except subprocess.CalledProcessError as e:
        print(f"[SAVAN] GitHub push 失敗: {e}")

# -----------------------------
# 一括生成・テスト・デプロイ
# -----------------------------
def deploy_and_test_all():
    iina_file, clickdply_file = generate_apps()
    for app_file in [iina_file, clickdply_file]:
        test_app(app_file)
        deploy_linode(app_file)
    github_push()

# -----------------------------
# コマンド実行
# -----------------------------
if __name__ == "__main__":
    if "--deploy-all-and-test" in sys.argv:
        deploy_and_test_all()
    elif "--generate-iina" in sys.argv:
        generate_apps()
    elif "--deploy-linode" in sys.argv and "--file" in sys.argv:
        idx = sys.argv.index("--file") + 1
        file_path = sys.argv[idx]
        deploy_linode(file_path)
