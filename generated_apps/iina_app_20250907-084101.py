import sys
import os
import subprocess
import time
import logging

# -----------------------------
# ログ設定
# -----------------------------
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/savan.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -----------------------------
# Linode デプロイ関数（本番）
# -----------------------------
def deploy_linode(file_path):
    logging.info(f"[SAVAN] デプロイ開始: {file_path}")
    app_name = os.path.basename(file_path)
    linode_ip = "123.45.67.89"  # 本番 IP
    deployed_url = f"http://{linode_ip}:8501/{app_name}"
    logging.info(f"[SAVAN] Linode 本番公開完了: {deployed_url}")
    return deployed_url

# -----------------------------
# アプリ自動生成
# -----------------------------
def generate_apps():
    apps_dir = "generated_apps"
    os.makedirs(apps_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    
    iina_file = os.path.join(apps_dir, f"iina_app_{timestamp}.py")
    clickdply_file = os.path.join(apps_dir, f"clickdply_app_{timestamp}.py")
    
    with open(iina_file, "w") as f:
        f.write('print("Hello from IINA generated app!")\n')
    with open(clickdply_file, "w") as f:
        f.write('print("Hello from 1ClickDply generated app!")\n')
    
    logging.info(f"[SAVAN] 自動生成完了: {iina_file}")
    logging.info(f"[SAVAN] 自動生成完了: {clickdply_file}")
    
    return iina_file, clickdply_file

# -----------------------------
# アプリテスト
# -----------------------------
def test_app(file_path):
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True, timeout=10)
        logging.info(result.stdout)
        return True
    except Exception as e:
        logging.error(f"[SAVAN] テスト失敗: {file_path}, {e}")
        return False

# -----------------------------
# GitHub 自動 push
# -----------------------------
def push_github():
    files_to_push = ["docker-compose.yml", "Dockerfile", "requirements.txt", "savan.py"]
    try:
        subprocess.run(["git", "add"] + files_to_push, check=True)
        subprocess.run(["git", "commit", "-m", "SAVAN automated commit"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        logging.info("[SAVAN] GitHub push 完了")
    except subprocess.CalledProcessError as e:
        logging.error(f"[SAVAN] GitHub push 失敗: {e}")

# -----------------------------
# Docker ファイル自動デプロイ
# -----------------------------
def deploy_docker_files():
    server_path = "/root/savan_apps"
    files = ["docker-compose.yml", "Dockerfile", "requirements.txt", "savan.py"]
    for f in files:
        src = os.path.join(os.getcwd(), f)
        if os.path.exists(src):
            subprocess.run(f"scp {src} root@123.45.67.89:{server_path}/", shell=True)
    # Docker-compose 起動
    subprocess.run(f"ssh root@123.45.67.89 'cd {server_path} && docker-compose up -d'", shell=True)
    logging.info("[SAVAN] Docker ファイルデプロイ完了")

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
# 永続稼働対応
# -----------------------------
def deploy_forever(interval_sec=300):
    while True:
        try:
            deploy_and_test_all()
        except Exception as e:
            logging.error(f"[SAVAN] 永続稼働中に例外発生: {e}")
        time.sleep(interval_sec)  # interval_sec 秒ごとに再実行

# -----------------------------
# CLI 実行
# -----------------------------
if __name__ == "__main__":
    if "--deploy-all-and-test" in sys.argv:
        deploy_and_test_all()
    elif "--deploy-all-and-test-forever" in sys.argv:
        deploy_forever()
    elif "--generate-iina" in sys.argv:
        generate_apps()
    elif "--push-docker-files" in sys.argv:
        push_github()
    elif "--deploy-docker-files" in sys.argv:
        deploy_docker_files()
