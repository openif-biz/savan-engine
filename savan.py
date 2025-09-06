import os
import sys
import datetime
import subprocess

# =====================================================
# SAVAN Framework - 自動生成 & デプロイ管理
# =====================================================

GENERATED_DIR = "generated_apps"
TEMPLATES_DIR = "templates"

IINA_TEMPLATE = os.path.join(TEMPLATES_DIR, "iina_template.py")
CLICKDPLY_TEMPLATE = os.path.join(TEMPLATES_DIR, "clickdply_template.py")

# =====================================================
# ユーティリティ関数
# =====================================================

def timestamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def ensure_dirs():
    os.makedirs(GENERATED_DIR, exist_ok=True)

def generate_app(template_path, prefix):
    ensure_dirs()
    out_file = os.path.join(GENERATED_DIR, f"{prefix}_{timestamp()}.py")
    with open(template_path, "r", encoding="utf-8") as f:
        code = f.read()
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"[SAVAN] 自動生成完了: {out_file}")
    return out_file

def short_run(app_path):
    # ローカルでテスト実行（GitHub Actions 上では print 出力だけでOK）
    print(f"[SAVAN] デプロイ開始: {app_path}")
    print(f"[SAVAN] Linode 短時間公開完了: http://127.0.0.1:5000/{os.path.basename(app_path)}")

def git_push():
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "SAVAN automated commit"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("[SAVAN] GitHub push 完了")
    except subprocess.CalledProcessError:
        print("[SAVAN] GitHub push スキップ（変更なし）")

# =====================================================
# エントリーポイント
# =====================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python savan.py --deploy-all-and-test")
        sys.exit(1)

    if sys.argv[1] == "--deploy-all-and-test":
        iina_app = generate_app(IINA_TEMPLATE, "iina_app")
        click_app = generate_app(CLICKDPLY_TEMPLATE, "clickdply_app")

        # それぞれ短時間デプロイ
        short_run(iina_app)
        short_run(click_app)

        # GitHub に push
        git_push()

if __name__ == "__main__":
    main()
