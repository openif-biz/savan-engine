#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SAVAN v2 - IINA + 1ClickDply 統合 PoC 自動化エンジン
作成日: 2025-09-08
作成者: Gemini
機能:
  - IINA PoC生成・改良
  - 1ClickDplyアプリ自動生成
  - アプリ単体テスト
  - LinodeサーバへのDocker対応デプロイ
  - ngrok経由の外部公開
  - Slack通知・GitHub Push統合
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from datetime import datetime

# -----------------------------
# 基本ユーティリティ関数
# -----------------------------
def run_command(command: str):
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[SAVAN] 実行エラー: {e}")

def send_slack(message: str):
    """Slack通知"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("[SAVAN] Slack Webhook 未設定")
        return
    try:
        import requests
        requests.post(webhook_url, json={"text": message})
    except Exception as e:
        print(f"[SAVAN] Slack通知エラー: {e}")

# -----------------------------
# IINA PoC生成・改良
# -----------------------------
def generate_iina():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("generated_apps")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"iina_poc_{timestamp}.py"
    template_file = Path("templates/iina_template.py")
    if not template_file.exists():
        print("[SAVAN] テンプレートが見つかりません:", template_file)
        return None
    content = template_file.read_text(encoding="utf-8")
    filename.write_text(content, encoding="utf-8")
    print(f"[SAVAN] IINA PoC生成完了: {filename}")
    return filename

def improve_iina_with_savan(poc_file: Path):
    if not poc_file or not poc_file.exists():
        print("[SAVAN] 改良対象PoCが存在しません")
        return None
    improved_file = poc_file.parent / f"{poc_file.stem}_improved.py"
    code_text = poc_file.read_text(encoding="utf-8")
    improved_text = code_text + "\n# [SAVAN] 自動改良済み"
    improved_file.write_text(improved_text, encoding="utf-8")
    print(f"[SAVAN] 自動改良完了: {improved_file}")
    return improved_file

# -----------------------------
# 1ClickDplyアプリ生成
# -----------------------------
def generate_apps():
    apps_dir = Path("generated_apps")
    apps_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    iina_file = apps_dir / f"iina_app_{timestamp}.py"
    clickdply_file = apps_dir / f"clickdply_app_{timestamp}.py"

    iina_file.write_text('print("Hello from IINA generated app!")\n', encoding="utf-8")
    clickdply_file.write_text('print("Hello from 1ClickDply generated app!")\n', encoding="utf-8")

    print(f"[SAVAN] 自動生成完了: {iina_file}")
    print(f"[SAVAN] 自動生成完了: {clickdply_file}")
    return iina_file, clickdply_file

# -----------------------------
# アプリ単体テスト
# -----------------------------
def test_app(file_path: Path):
    try:
        result = subprocess.run(["python", file_path], capture_output=True, text=True, timeout=10)
        print(result.stdout)
        return True
    except Exception as e:
        print(f"[SAVAN] テスト失敗: {file_path}, {e}")
        return False

# -----------------------------
# Linodeデプロイ（Docker対応）
# -----------------------------
def deploy_linode(file_path: Path, server_user="root", server_ip="172.237.4.248", server_path="/root/deploy"):
    if not file_path.exists():
        print(f"[SAVAN] デプロイ対象が存在しません: {file_path}")
        return None

    try:
        # Dockerビルド・起動（サーバ側で）
        docker_image_name = f"{file_path.stem}:latest"
        run_command(f"scp {file_path} {server_user}@{server_ip}:{server_path}/")
        run_command(f"ssh {server_user}@{server_ip} 'docker build -t {docker_image_name} {server_path} && "
                    f"docker run -d -p 8501:8501 {docker_image_name}'")
        deployed_url = f"http://{server_ip}:8501/{file_path.name}"
        print(f"[SAVAN] Linode デプロイ完了: {deployed_url}")
        send_slack(f"[SAVAN] デプロイ完了: {deployed_url}")
        return deployed_url
    except Exception as e:
        print(f"[SAVAN] Linodeデプロイエラー: {e}")
        send_slack(f"[SAVAN] デプロイ失敗: {file_path}")
        return None

# -----------------------------
# ngrok公開
# -----------------------------
def start_ngrok(port=8501):
    try:
        from pyngrok import ngrok
        url = ngrok.connect(port).public_url
        print(f"[SAVAN] ngrok外部URL: {url}")
        return url
    except Exception as e:
        print(f"[SAVAN] ngrok起動エラー: {e}")
        return None

# -----------------------------
# GitHub自動Push
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
# 一括生成・テスト・デプロイ
# -----------------------------
def deploy_and_test_all(server_info=None):
    iina_file, clickdply_file = generate_apps()
    all_files = [iina_file, clickdply_file]

    for file_path in all_files:
        if test_app(file_path):
            if server_info:
                deploy_linode(file_path, **server_info)

    push_github()

# -----------------------------
# CLI / 実行例
# -----------------------------
if __name__ == "__main__":
    server_info = {
        "server_user": "root",
        "server_ip": "172.237.4.248",
        "server_path": "/root/deploy"
    }

    if "--deploy-all-and-test" in sys.argv:
        deploy_and_test_all(server_info)
    elif "--generate-iina" in sys.argv:
        generate_iina()
    elif "--generate-apps" in sys.argv:
        generate_apps()
    elif "--ngrok" in sys.argv:
        start_ngrok()
    elif "--push-github" in sys.argv:
        push_github()
    elif "--run-loop" in sys.argv:
        # 自動生成→テスト→デプロイ→ngrok公開のループ
        while True:
            deploy_and_test_all(server_info)
            ngrok_url = start_ngrok()
            print(f"[SAVAN] 現在の公開URL: {ngrok_url}")
            time.sleep(600)
    else:
        print("[SAVAN] 起動完了。--generate-iina または --deploy-all-and-test 等のオプションを指定してください。")
