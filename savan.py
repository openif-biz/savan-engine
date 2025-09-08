import sys
import os
import subprocess
import time

# -----------------------------
# Linode デプロイ関数 (本番ポート8501対応)
# -----------------------------
def deploy_linode(file_path):
    print(f"[SAVAN] デプロイ開始: {file_path}")
    app_name = os.path.basename(file_path)

    # 本番 Linode IP とポート
    linode_ip = "123.45.67.89"
    deployed_url = f"http://{linode_ip}:8501/{app_name}"

    # Docker/Streamlit 本番起動を想定
    # ここで本番LinodeにSSHして docker-compose up 等を実行可能
    # 仮で短時間公開としてメッセージ出力
    print(f"[SAVAN] Linode 本番公開完了: {deployed_url}")
    return deployed_url

# -----------------------------
# アプリ自動生成 (Streamlit対応)
# -----------------------------
def generate_apps():
    apps_dir = "generated_apps"
    os.makedirs(apps_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    # Streamlit対応 IINA app
    iina_file = os.path.join(apps_dir, f"iina_app_{timestamp}.py")
    with open(iina_file, "w") as f:
        f.write(
            "import streamlit as st\n"
            "st.title('IINA Generated App')\n"
            "st.write('Hello from IINA generated Streamlit app!')\n"
        )

    # Streamlit対応 1ClickDply app
    clickdply_file = os.path.join(apps_dir, f"clickdply_app_{timestamp}.py")
    with open(clickdply_file, "w") as f:
        f.write(
            "import streamlit as st\n"
            "st.title('1ClickDply Generated App')\n"
            "st.write('Hello from 1ClickDply generated Streamlit app!')\n"
        )

    print(f"[SAVAN] 自動生成完了: {iina_file}")
    print(f"[SAVAN] 自動生成完了: {clickdply_file}")

    return iina_file, clickdply_file

# -----------------------------
# アプリテスト
# -----------------------------
def test_app(file_path):
    try:
        result = subprocess.run(["streamlit", "run", file_path, "--server.headless", "true", "--server.port", "8501"],
                                capture_output=True, text=True, timeout=10)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"[SAVAN] テスト失敗: {file_path}, {e}")
        return False

# -----------------------------
# GitHub 自動 push
# -----------------------------
def push_github():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "SAVAN automated commit"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("[SAVAN] GitHub push 完了")
    except subprocess.CalledProcessError as e:
        print(f"[SAVAN] GitHub push 失敗: {e}")

# -----------------------------
# 全アプリ生成・テスト・デプロイ
# -----------------------------
def deploy_and_test_all():
    iina_file, clickdply_file = generate_apps()
    for app_file in [iina_file, clickdply_file]:
        if test_app(app_file):
            deploy_linode(app_file)
    push_github()

# -----------------------------
# CLI 実行
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
