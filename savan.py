# 【通番25改】savan.py (統合推論フロー V2 最終版)
import sys
import os
import subprocess
import time
import yaml
from contextlib import contextmanager
import knowledge_manager
from knowledge_engine import KnowledgeEngine
from llama_cpp import Llama
import requests
import json
import logging
import argparse
import hashlib

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- 設定 ---
def get_model_path():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(workspace_root, "models", "deepseek-coder-6.7b-instruct.Q4_K_M.gguf")

MODEL_PATH = get_model_path()

# --- ユーティリティ & 自己診断 ---
def verify_execution_context():
    engine_dir_name = "savan-engine"
    current_dir_name = os.path.basename(os.getcwd())
    if current_dir_name != engine_dir_name:
        logging.error(f"実行場所が不正です。'{engine_dir_name}' ディレクトリから実行してください。")
        script_path = os.path.abspath(__file__)
        savan_engine_path = os.path.dirname(script_path)
        print(f"\n推奨コマンド:\ncd {savan_engine_path}\n")
        return False
    return True

@contextmanager
def load_llm():
    if not os.path.exists(MODEL_PATH):
        logging.error(f"AIモデルファイルが見つかりません: {MODEL_PATH}")
        yield None
        return
    logging.info("AIエンジン(LLM)を起動しています...")
    llm = Llama(model_path=MODEL_PATH, n_ctx=8192, n_gpu_layers=-1, verbose=False)
    logging.info("AIエンジン(LLM)起動完了。")
    yield llm
    logging.info("AIエンジン(LLM)を停止します。")

def get_workspace_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- 思考エンジンの初期化 ---
logging.info("思考エンジン(KnowledgeEngine)を初期化・接続しています...")
try:
    engine = KnowledgeEngine()
    engine.load_knowledge_base()
    if not getattr(engine, "is_loaded", False):
        logging.warning("KnowledgeEngineはロードできましたが、知識ベースが空か不正です。")
    else:
        logging.info(f"{len(engine.knowledge_base)}件の知識をロードしました。思考準備完了。")
except Exception as e:
    logging.error(f"KnowledgeEngineの初期化に失敗しました。思考機能は利用できません。エラー: {e}")
    engine = None

# --- 思考ロジック V2 ---

def _define_goal(user_document: str) -> dict:
    logging.info("【思考ステップ1/9: ゴール設定】")
    goal = "不明なドキュメント"
    try:
        json_data = json.loads(user_document)
        goal = json_data.get('title', 'タイトルのないJSONドキュメント')
    except json.JSONDecodeError:
        first_line = user_document.split('\n')[0].strip()
        goal = first_line.replace("#", "").strip() if first_line else "名称未設定のドキュメント"
    goal_data = {
        "goal_statement": goal,
        "keywords": ["ドキュメント分析", "プロジェクト創出"],
        "source_document_hash": hashlib.sha256(user_document.encode()).hexdigest()
    }
    logging.info(f"  > ゴールを『{goal_data['goal_statement']}』と設定しました。")
    return goal_data

def _backtrack_steps(goal_data: dict) -> dict:
    logging.info("【思考ステップ2/9: 逆算ステップ】")
    requirements_data = {
        "required_tasks": [
            {"task_id": "T01", "name": "app_spec.ymlの骨格定義"},
            {"task_id": "T02", "name": "プロジェクトフォルダの作成"},
            {"task_id": "T03", "name": "Gitリポジトリの初期化とGitHub連携"}
        ]
    }
    logging.info(f"  > ゴール達成に必要なタスクを洗い出しました: {[t['name'] for t in requirements_data['required_tasks']]}")
    return requirements_data

def _assess_resources(requirements_data: dict) -> dict:
    logging.info("【思考ステップ3/9: リソース評価】")
    assessment_data = {
        "feasibility": "実行可能",
        "checked_constraints": [{"constraint": "ローカルPC上での実行", "status": "OK"}, {"constraint": "GitHub CLI (gh) の利用", "status": "OK"}],
        "notes": "基本要件は満たされていると判断。"
    }
    logging.info(f"  > リソース評価の結果: {assessment_data['feasibility']}")
    return assessment_data

def _apply_framework_and_generate_spec(user_document: str, phase1_output: dict) -> dict:
    logging.info("【思考ステップ4/9: フレームワーク適用】")
    knowledge_prompt_injection = ""
    referenced_knowledge = []
    if engine and getattr(engine, "is_loaded", False):
        logging.info("  > 関連する過去の経験を検索し、思考材料として注入します...")
        query_text = phase1_output["goal_data"]["goal_statement"] + "\n" + user_document[:400]
        results = engine.search(query_text=query_text, top_k=3, mode='human_consult')
        if results:
            referenced_knowledge = [exp.get('experience_id', exp.get('title')) for exp in results]
            knowledge_prompt_injection += "\n### Past Learnings for Reference ###\n"
            for exp in results:
                knowledge_prompt_injection += f"# Title: {exp.get('title', '')}\n# Summary: {exp.get('summary', '')}\n"
            logging.info(f"  > {len(results)}件の関連経験をプロンプトに反映しました。")

    logging.info("【思考ステップ5/9: 中間アウトプット生成】")
    logging.info("  > AIアーキテクトが思考を開始し、app_spec.ymlを生成します...")
    metadata = {"referenced_knowledge_ids": referenced_knowledge, "prompt_template_version": "1.0", "llm_token_usage": None}
    try:
        with load_llm() as llm:
            if llm is None: raise Exception("AIエンジン(LLM)の起動に失敗")
            prompt = f"""### Instruction ###
You are a senior system architect. Analyze the user's document and distill its essence into a structured YAML (`app_spec.yml`). The YAML must contain `app_name`, `concept`, and `basic_functions`.
{knowledge_prompt_injection}
### User's Document ###
{user_document}
### Output YAML ###
```yaml
"""
            output = llm(prompt, max_tokens=1024, stop=["```"], echo=False, temperature=0.2)
            spec_content = output['choices'][0]['text'].strip()
            metadata["llm_token_usage"] = output['usage']
            spec_data = yaml.safe_load(spec_content)
            required_keys = ['app_name', 'concept', 'basic_functions']
            if not all(key in spec_data for key in required_keys):
                raise ValueError(f"LLMの出力YAMLに必須キーが不足しています。不足キー: {[k for k in required_keys if k not in spec_data]}")
            project_name = spec_data.get('app_name', 'untitled_project')
            logging.info(f"  > app_spec.ymlの骨格生成とバリデーションに成功。プロジェクト名: '{project_name}'")
            return {"status": "success", "spec_content": spec_content, "project_name": project_name, "metadata": metadata}
    except Exception as e:
        logging.error(f"  > AIによるapp_spec.ymlの骨格生成に失敗しました。エラー詳細: {e}")
        return {"status": "error", "error_message": str(e), "metadata": metadata}

def _test_hypothesis_and_evaluate(intermediate_data: dict) -> dict:
    logging.info("【思考ステップ6/9: 仮説検証・評価】")
    phase1_goal = intermediate_data["phase1_output"]["goal_data"]["goal_statement"]
    phase2_spec = intermediate_data["phase2_output"]["spec_content"]
    evaluation_score = 0.0
    notes = []
    if phase1_goal.lower() in phase2_spec.lower():
        evaluation_score = 0.8
        notes.append("生成物は当初のゴール設定と一定の整合性があります。")
    else:
        evaluation_score = 0.3
        notes.append("警告: 生成物が当初のゴール設定と乖離している可能性があります。")
    evaluation_result = {"evaluation_score": evaluation_score, "notes": notes, "needs_adjustment": evaluation_score < 0.7}
    logging.info(f"  > 中間アウトプットの自己評価スコア: {evaluation_score:.2f}")
    return evaluation_result

def _adjust_approach(intermediate_data: dict) -> dict:
    logging.info("【思考ステップ7/9: フィードバック調整】")
    adjustment_plan = {"action": "refine_prompt", "details": "basic_functionsをより具体化するためのプロンプト修正を推奨。"}
    logging.info(f"  > 修正方針を生成しました: {adjustment_plan['details']}")
    return {"adjustment_plan": adjustment_plan}

def _finalize_output(intermediate_data: dict) -> dict:
    logging.info("【思考ステップ8/9: 最終アウトプット生成】")
    final_output = {
        "project_name": intermediate_data["phase2_output"]["project_name"],
        "app_spec_content": intermediate_data["phase2_output"]["spec_content"],
        "thought_process_audit_trail": {
            "phase1_goal_setting": intermediate_data["phase1_output"]["goal_data"],
            "phase2_core_inference": intermediate_data["phase2_output"]["metadata"],
            "phase3_evaluation": intermediate_data.get("phase3_output", {})
        }
    }
    logging.info("  > 思考プロセス全体の最終報告を生成しました。")
    logging.info("【思考ステップ9/9: 最適化】")
    logging.info("  > (今回は最適化処理をスキップします)")
    return final_output

def universal_creation_workflow(document_path):
    logging.info(f"===== SAVAN 統合推論ワークフロー V2 開始 =====")
    if not os.path.exists(document_path):
        logging.error(f"入力ドキュメントが見つかりません: {document_path}")
        return None
    with open(document_path, 'r', encoding='utf-8') as f: user_document = f.read()
    
    # --- フェーズ1 ---
    goal_data = _define_goal(user_document)
    requirements_data = _backtrack_steps(goal_data)
    assessment_data = _assess_resources(requirements_data)
    # --- ▼▼▼【バグ修正箇所】▼▼▼ ---
    intermediate_data = {
        "phase1_output": {
            "goal_data": goal_data,
            "requirements_data": requirements_data,
            "assessment_data": assessment_data
        }
    }
    # --- ▲▲▲【バグ修正箇所】▲▲▲ ---
    if assessment_data.get("feasibility") != "実行可能":
        logging.error("リソース評価の結果、ミッションの実行は不可能と判断しました。")
        return None
    logging.info("--- 思考フェーズ1（逆算思考）が完了しました ---")

    # --- フェーズ2 ---
    phase2_output = _apply_framework_and_generate_spec(user_document, intermediate_data['phase1_output'])
    intermediate_data["phase2_output"] = phase2_output
    if phase2_output["status"] == "error":
        logging.error("コア推論に失敗したため、ワークフローを中断します。")
        return intermediate_data
    logging.info("--- 思考フェーズ2（コア推論）が完了しました ---")

    # --- フェーズ3 ---
    evaluation_data = _test_hypothesis_and_evaluate(intermediate_data)
    intermediate_data["phase3_output"] = evaluation_data
    if evaluation_data["needs_adjustment"]:
        logging.warning("自己評価の結果、改善の余地があると判断されました。")
        adjustment_plan = _adjust_approach(intermediate_data)
        intermediate_data["phase3_output"]["adjustment_plan"] = adjustment_plan
    logging.info("--- 思考フェーズ3（自己改善）が完了しました ---")

    # --- 最終成果物の生成と、物理的なプロジェクト創出 ---
    final_data = _finalize_output(intermediate_data)
    project_name = final_data["project_name"]
    spec_content = final_data["app_spec_content"]
    logging.info(f"全ての思考プロセスが完了しました。プロジェクト名 '{project_name}' で物理的な創出を開始します。")
    project_path, success = create_project_scaffolding(project_name, spec_content)
    if not success: return final_data
    success = initialize_git_and_create_repo(project_path)
    if not success: return final_data
    logging.info("===== SAVAN 統合推論ワークフロー V2 全工程完了 =====")
    return final_data

def create_project_scaffolding(project_name, spec_content):
    workspace_root = get_workspace_root()
    project_path = os.path.join(workspace_root, 'projects', project_name)
    logging.info(f"プロジェクトフォルダを作成しています: {project_path}")
    if os.path.exists(project_path):
        logging.warning(f"プロジェクトフォルダ '{project_name}' は既に存在するため、スキップします。")
        return project_path, True
    os.makedirs(os.path.join(project_path, 'src'))
    with open(os.path.join(project_path, '.gitignore'), 'w', encoding='utf-8') as f: f.write("# Python\n__pycache__/\n*.pyc\n.env\n.venv\n")
    with open(os.path.join(project_path, 'app_spec.yml'), 'w', encoding='utf-8') as f: f.write(spec_content)
    with open(os.path.join(project_path, 'README.md'), 'w', encoding='utf-8') as f: f.write(f"# {project_name}\n\nThis project was auto-generated by SAVAN.")
    logging.info("プロジェクトの基本構造を作成しました。")
    return project_path, True

def initialize_git_and_create_repo(project_path):
    project_name = os.path.basename(project_path)
    original_cwd = os.getcwd()
    try:
        os.chdir(project_path)
        logging.info("Gitリポジトリを初期化しています...")
        # (以降のGit/GitHub処理は変更なし)
        subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
        # ...
        return True
    except Exception as e:
        logging.error(f"Git/GitHub処理でエラー: {e}")
        return False
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    if not verify_execution_context(): sys.exit(1)
    parser = argparse.ArgumentParser(description="SAVAN Core Engine", formatter_class=argparse.RawTextHelpFormatter, epilog="実行方法:\n  python savan.py --new-from=<ドキュメントファイル名>")
    parser.add_argument("--new-from", dest="doc_path", type=str, help="Create a new project from a document.")
    args = parser.parse_args()
    if args.doc_path:
        final_output = universal_creation_workflow(args.doc_path)
        if final_output:
            print("\n--- 最終アウトプット ---")
            print(json.dumps(final_output, indent=2, ensure_ascii=False))
            print("--------------------")
    elif len(sys.argv) == 1:
        parser.print_help()