#!/usr/bin/env python3
# FILE: savan.py (統合版)

import sys
import json
from pathlib import Path
import subprocess
import streamlit as st

# --- utils ---
def run_command(command: str):
    """シェルコマンドをSAVANから実行"""
    try:
        print(f"[SAVAN] 実行中: {command}")
        subprocess.run(command, shell=True, check=True)
        print("[SAVAN] 実行完了")
    except subprocess.CalledProcessError as e:
        print(f"[SAVAN] 実行エラー: {e}")

# --- IINA PoC生成 ---
def generate_iina(spec_path=None):
    """
    spec_path があれば JSON 仕様に基づき PoCを生成
    生成済みの場合はファイルパスを返す
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path("generated_apps")
    output_dir.mkdir(exist_ok=True)
    filename = output_dir / f"iina_poc_{timestamp}.py"

    # --- テンプレート適用 ---
    template_file = Path("templates/iina_template.py")
    if not template_file.exists():
        raise FileNotFoundError("テンプレート iina_template.py が見つかりません")
    tpl = template_file.read_text(encoding="utf-8")

    spec_json = {}
    if spec_path:
        spec_json = json.loads(Path(spec_path).read_text(encoding="utf-8"))

    content = tpl.replace("__SPEC_PLACEHOLDER__", json.dumps(spec_json, ensure_ascii=False, indent=2))
    filename.write_text(content, encoding="utf-8")
    print(f"[SAVAN] Generated IINA app: {filename}")
    return filename

# --- IINA改良ループ ---
def improve_iina_with_savan(spec_path=None):
    """生成したPoCをLLMに渡して自動改良"""
    new_poc = generate_iina(spec_path)
    print(f"[SAVAN] 生成したPoC: {new_poc}")

    # LLM呼び出しの仮想コード（ここを StarCoder2/ChatGPT API などに置換）
    try:
        from iina_model import llm  # 実際は IINAモデルロード済み
    except ImportError:
        print("[SAVAN] LLMモデル未ロード、改良はスキップ")
        return new_poc

    code_text = new_poc.read_text(encoding="utf-8")
    prompt = f"""
以下の IINA PoC コードを、最新仕様・効率化・改善可能な部分を含めてブラッシュアップしてください。
コード構造は維持しつつ、可読性・エラー処理・ユーザー体験を向上させてください。

{code_text}
"""
    output = llm(prompt, max_tokens=4096, stop=None, echo=False)
    improved_code = output['choices'][0]['text']

    improved_file = new_poc.parent / f"{new_poc.stem}_improved.py"
    improved_file.write_text(improved_code, encoding="utf-8")
    print(f"[SAVAN] 改良済PoCを保存: {improved_file}")

    # --- テンプレート更新 ---
    template_file = Path("templates/iina_template.py")
    template_content = improved_code.replace(json.dumps(load_spec(spec_path), ensure_ascii=False, indent=2),
                                             "__SPEC_PLACEHOLDER__")
    template_file.write_text(template_content, encoding="utf-8")
    print(f"[SAVAN] テンプレートを更新: {template_file}")

    return improved_file

def load_spec(spec_path):
    if spec_path and Path(spec_path).exists():
        return json.loads(Path(spec_path).read_text(encoding="utf-8"))
    return {}

# --- Chatモード ---
def chat_mode():
    print("[SAVAN] Chatモード開始。'exit' と入力で終了します")
    spec = None
    while True:
        try:
            cmd = input("あなた> ").strip()
        except EOFError:
            break
        if not cmd:
            continue
        if cmd.lower() in ("exit", "quit"):
            print("[SAVAN] Chatモード終了")
            break

        print(f"[SAVAN] 受け取った指示: {cmd}")

        # --- IINA生成 ---
        if "generate-iina" in cmd or "PoC生成" in cmd:
            try:
                generated_file = generate_iina(spec)
                print(f"[SAVAN] IINA生成完了: {generated_file}")
            except Exception as e:
                print(f"[SAVAN] 生成中エラー: {e}")

        # --- IINA自動改良 ---
        elif "改良" in cmd or "ブラッシュアップ" in cmd:
            try:
                improved_file = improve_iina_with_savan(spec)
                print(f"[SAVAN] 自動改良完了: {improved_file}")
                run_command(f"streamlit run {improved_file}")
            except Exception as e:
                print(f"[SAVAN] 改良中にエラー: {e}")

        # --- Streamlit で開く ---
        elif "開く" in cmd or "ブラウザ" in cmd:
            try:
                if 'generated_file' in locals():
                    run_command(f"streamlit run {generated_file}")
                else:
                    print("[SAVAN] 先に PoCを生成してください")
            except Exception as e:
                print(f"[SAVAN] ブラウザ起動エラー: {e}")

        else:
            print("[SAVAN] コマンド理解済（実行未実装）")

# --- CLI Entrypoint ---
def main():
    args = sys.argv[1:]
    if "--chat" in args:
        chat_mode()
        return

    if "--generate-iina" in args:
        spec_index = None
        if "--spec" in args:
            try:
                spec_index = args.index("--spec") + 1
                spec_path = args[spec_index]
            except Exception:
                spec_path = None
        else:
            spec_path = None

        try:
            p = generate_iina(spec_path)
            print("[SAVAN] 生成完了:", p)
        except Exception as e:
            print("[SAVAN] 生成中エラー:", e)
        return

    print("Usage: python savan.py [--chat] [--generate-iina --spec path.json]")

if __name__ == "__main__":
    main()
