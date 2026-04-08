import os
import sys
import argparse
import json
import yaml
from datetime import datetime
import subprocess
import traceback

ROOT_DIR = r'C:\Users\Owner\local_savan'
ENGINE_DIR = os.path.join(ROOT_DIR, 'savan-engine')
REPORT_DIR = os.path.join(ENGINE_DIR, 'reports')
KNOWLEDGE_BASE_PATH = os.path.join(ENGINE_DIR, 'savan_knowledge_base.json')

# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def run_cmd(cmd, cwd=None, timeout=60):
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        res = []
        if out:
            res.append(out)
        if err:
            res.append(f"[stderr]\n{err}")
        if res:
            return "\n".join(res)
        return "(no output)"
    except subprocess.TimeoutExpired:
        return f"[Timeout: {timeout}s exceeded for '{cmd}']"
    except Exception as e:
        return f"[Error running '{cmd}': {e}]"

def safe_read(filepath, tail_chars=None):
    for enc in ('utf-8', 'cp932'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                content = f.read()
            if tail_chars and len(content) > tail_chars:
                return "...(末尾のみ)\n" + content[-tail_chars:]
            return content
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"[Error reading file: {e}]"
    return "[Error: 読み込み失敗（UTF-8/CP932ともに失敗）]"

def append_report(report_path, text):
    with open(report_path, 'a', encoding='utf-8') as f:
        f.write(text)

def get_directory_tree(path, indent=0, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = {'.git', 'node_modules', '__pycache__', '.venv', '.cache', 'qdrant_db'}
    output = ""
    try:
        if not os.path.exists(path):
            return f"{'    ' * indent}[Path not found]\n"
        for item in sorted(os.listdir(path)):
            if item in exclude_dirs:
                continue
            full_path = os.path.join(path, item)
            output += f"{'    ' * indent}./{item}\n"
            if os.path.isdir(full_path) and indent < 3:
                output += get_directory_tree(full_path, indent + 1, exclude_dirs)
    except Exception as e:
        output += f"{'    ' * indent}[Error accessing {path}: {e}]\n"
    return output

# ──────────────────────────────────────────────
# スキャン：全域
# ──────────────────────────────────────────────

def scan_all_environments():
    print("[*] 全域スキャンを開始します...")

    report_path = os.path.join(REPORT_DIR, 'savan_report.txt')
    os.makedirs(REPORT_DIR, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("### SAVAN 2.0 Global Environment Report ###\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    print("[1/5] 開発環境全体マップ スキャン中...")
    sec = "[1] 開発環境全体マップ\n"
    try:
        for proj in sorted(os.listdir(ROOT_DIR)):
            proj_path = os.path.join(ROOT_DIR, proj)
            if not os.path.isdir(proj_path):
                continue
            sec += f"\n--- Project: {proj} ---\n"
            sec += get_directory_tree(proj_path, indent=1)

            python_exe = os.path.join(proj_path, '.venv', 'Scripts', 'python.exe')
            if os.path.exists(python_exe):
                sec += f"  Python Version: {run_cmd(f'{python_exe} --version')}\n"

            req_path = os.path.join(proj_path, 'requirements.txt')
            if os.path.exists(req_path):
                sec += f"  requirements.txt:\n{safe_read(req_path)}\n"
    except Exception as e:
        sec += f"[Error in Section 1: {e}]\n"
    append_report(report_path, sec + "\n")

    print("[2/5] Ollama / Qdrant 稼働確認中...")
    sec = "[2] プロジェクト固有の環境情報 (AI & Vector DB)\n"
    try:
        sec += f"Ollama稼働状態・ロード済みモデル一覧:\n{run_cmd('ollama list')}\n"
        sec += f"Qdrant Vector DB コレクション存在確認:\n{run_cmd('curl.exe -s http://localhost:6333/collections')}\n"

        for proj in sorted(os.listdir(ROOT_DIR)):
            proj_path = os.path.join(ROOT_DIR, proj)
            env_path = os.path.join(proj_path, '.env')
            if os.path.exists(env_path):
                sec += f"\n{proj} .env variables (keys only):\n"
                for line in safe_read(env_path).splitlines():
                    if '=' in line and not line.strip().startswith('#'):
                        sec += f"  {line.split('=')[0]}\n"
    except Exception as e:
        sec += f"[Error in Section 2: {e}]\n"
    append_report(report_path, sec + "\n")

    print("[3/5] pip freeze & インフラ状態 確認中 (時間がかかる場合があります)...")
    sec = "[3] 横断的な依存関係 & インフラ状態\n"
    try:
        sec += f"Docker Containers:\n{run_cmd('docker ps -a')}\n"
        sec += f"Ports (8501, 8502):\n{run_cmd('netstat -ano | findstr 850')}\n"

        for proj in sorted(os.listdir(ROOT_DIR)):
            proj_path = os.path.join(ROOT_DIR, proj)
            python_exe = os.path.join(proj_path, '.venv', 'Scripts', 'python.exe')
            if os.path.exists(python_exe):
                print(f"pip freeze: {proj} ...")
                pip_freeze = run_cmd(f'{python_exe} -m pip freeze', timeout=90)
                sec += f"\n--- {proj} pip freeze ---\n{pip_freeze}\n"
                lc = [l for l in pip_freeze.splitlines() if 'langchain' in l.lower()]
                if lc:
                    sec += f"LangChain Packages in {proj}:\n" + "\n".join(lc) + "\n"
    except Exception as e:
        sec += f"[Error in Section 3: {e}]\n"
    append_report(report_path, sec + "\n")

    print("[4/5] Git差分 & エラーログ 収集中...")
    sec = "[4] エラー履歴（直近） & Git未コミット差分\n"
    try:
        for proj in sorted(os.listdir(ROOT_DIR)):
            proj_path = os.path.join(ROOT_DIR, proj)
            if not os.path.isdir(proj_path):
                continue
            git_status = run_cmd('git status -s', cwd=proj_path)
            if git_status and 'not a git' not in git_status.lower():
                sec += f"\nGit Status ({proj}):\n{git_status}\n"

            for file in os.listdir(proj_path):
                if file.endswith('.log'):
                    log_path = os.path.join(proj_path, file)
                    sec += f"\nError Log ({proj}/{file}):\n"
                    sec += safe_read(log_path, tail_chars=1000) + "\n"
    except Exception as e:
        sec += f"[Error in Section 4: {e}]\n"
    append_report(report_path, sec + "\n")

    print("[5/5] Knowledge Base 確認中...")
    sec = "[5] Knowledge Base Summary\n"
    try:
        if os.path.exists(KNOWLEDGE_BASE_PATH):
            kb = json.loads(safe_read(KNOWLEDGE_BASE_PATH))
            sec += f"Loaded {len(kb)} knowledge nodes.\n"
            for node in kb[:5]:
                sec += f"  - {node.get('title', node.get('model_name', 'Unknown'))}\n"
        else:
            sec += f"(Knowledge Base not found: {KNOWLEDGE_BASE_PATH})\n"
    except Exception as e:
        sec += f"[Error in Section 5: {e}]\n"
    append_report(report_path, sec + "\n")

    print(f"[+] 全域スキャン完了 → {report_path}")

# ──────────────────────────────────────────────
# スキャン：プロジェクト単体
# ──────────────────────────────────────────────

def scan_project(project_name):
    print(f"[*] プロジェクトスキャンを開始します: {project_name}")
    proj_path = os.path.join(ROOT_DIR, project_name)

    if not os.path.exists(proj_path):
        print(f"[!] Project not found: {proj_path}")
        return

    report_path = os.path.join(REPORT_DIR, f'savan_report_{project_name}.txt')
    os.makedirs(REPORT_DIR, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"### SAVAN 2.0 Project Report: {project_name} ###\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    sec = "[1] 開発環境全体マップ\n"
    sec += get_directory_tree(proj_path, indent=1)
    append_report(report_path, sec + "\n")

    sec = "[2] プロジェクト固有の環境情報 (AI & Vector DB)\n"
    sec += f"Ollama稼働状態・ロード済みモデル一覧:\n{run_cmd('ollama list')}\n"
    sec += f"Qdrant Vector DB コレクション存在確認:\n{run_cmd('curl.exe -s http://localhost:6333/collections')}\n"
    append_report(report_path, sec + "\n")

    sec = "[3] 横断的な依存関係 & インフラ状態\n"
    python_exe = os.path.join(proj_path, '.venv', 'Scripts', 'python.exe')
    if os.path.exists(python_exe):
        sec += f"Python Version: {run_cmd(f'{python_exe} --version')}\n"
        pip_freeze = run_cmd(f'{python_exe} -m pip freeze', timeout=90)
        sec += f"\n--- {project_name} pip freeze ---\n{pip_freeze}\n"

    env_path = os.path.join(proj_path, '.env')
    if os.path.exists(env_path):
        sec += "\n.env variables (keys only):\n"
        for line in safe_read(env_path).splitlines():
            if '=' in line and not line.strip().startswith('#'):
                sec += f"  {line.split('=')[0]}\n"

    sec += f"\nGit Status (Uncommitted changes):\n{run_cmd('git status -s', cwd=proj_path)}\n"
    append_report(report_path, sec + "\n")

    print(f"[+] プロジェクトスキャン完了 → {report_path}")

# ──────────────────────────────────────────────
# 指示書実行
# ──────────────────────────────────────────────

def execute_instruction(yaml_path):
    print(f"[*] 指示書を実行します: {yaml_path}")
    if not os.path.exists(yaml_path):
        print(f"[!] 指示書が見つかりません: {yaml_path}")
        return

    try:
        instruction = yaml.safe_load(safe_read(yaml_path))
    except Exception as e:
        print(f"[!] YAMLパースエラー: {e}")
        return

    for task in instruction.get('tasks', []):
        t_type = task.get('type', '')
        desc = task.get('description', '(説明なし)')
        print(f"\n--- Task: {desc} ({t_type}) ---")

        if t_type in ('file_create', 'file_update'):
            target = task.get('target')
            file_content = task.get('content', '')
            if not target:
                print("[!] target が指定されていません。スキップします。")
                continue
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(file_content)
            print(f"[+] Created/Updated: {target}")

        elif t_type in ('execute_command', 'command'):
            cmd = task.get('command') or task.get('execute')
            if not cmd:
                print("[!] command が指定されていません。スキップします。")
                continue
            require_approval = task.get('require_approval', True)
            if require_approval:
                ans = input(f"[?] 以下のコマンドを実行しますか？ (Y/n)\n    {cmd}\n> ")
                if ans.strip().lower() not in ('y', 'yes', ''):
                    print("[-] スキップしました。")
                    continue
            print(f"[*] 実行中: {cmd}")
            os.system(cmd)

        else:
            print(f"[!] 未対応のタスクタイプ: {t_type} → スキップします。")

# ──────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAVAN 2.0 Core")
    parser.add_argument("--scan-all", action="store_true", help="全域環境スキャン")
    parser.add_argument("--scan-project", metavar="PROJECT_NAME", help="特定プロジェクトのスキャン")
    parser.add_argument("--execute", dest="exec_yaml", metavar="YAML_PATH", help="YAML指示書の実行")
    args = parser.parse_args()

    try:
        if args.scan_all:
            scan_all_environments()
        elif args.scan_project:
            scan_project(args.scan_project)
        elif args.exec_yaml:
            execute_instruction(args.exec_yaml)
        else:
            parser.print_help()
    except Exception as e:
        print(f"\n[!] 致命的なエラー: {e}")
        traceback.print_exc()
