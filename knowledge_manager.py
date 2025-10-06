# 【通番21改2】knowledge_manager.py (バグ修正版 v2)
import json
import os
import shutil
import argparse
import tempfile
import time
import logging
import hashlib
import io  # <<<【修正点1】ioライブラリをインポート

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- 定数定義 ---
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAVAN_ENGINE_ROOT = os.path.join(WORKSPACE_ROOT, "savan-engine")
NEW_EXPERIENCES_DIR = os.path.join(SAVAN_ENGINE_ROOT, "new_experiences")
PROCESSED_DIR = os.path.join(SAVAN_ENGINE_ROOT, "processed_experiences")
KNOWLEDGE_BASE_PATH = os.path.join(SAVAN_ENGINE_ROOT, "savan_knowledge_base.json")
KNOWLEDGE_INDEX_PATH = os.path.join(SAVAN_ENGINE_ROOT, "savan_knowledge.index")

# --- ユーティリティ関数 ---
def save_atomic(data, path, is_json=True):
    """データをアトミックにファイル保存する"""
    dirpath = os.path.dirname(path)
    os.makedirs(dirpath, exist_ok=True)
    
    fd, tmp_path = tempfile.mkstemp(dir=dirpath, prefix="tmp_", suffix=".tmp")
    try:
        if is_json:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            # <<<【修正点2】バイナリデータを直接書き込むように修正
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
        os.replace(tmp_path, path)
        logging.info(f"データが安全に保存されました: {path}")
    except Exception as e:
        logging.error(f"データの保存に失敗しました: {e}")
        # finallyブロックを使わずとも、例外時にtmp_pathが残っていれば削除
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise # エラーを再送出して、呼び出し元に問題を知らせる

# --- ingest & approve_meta ---
def ingest_and_approve_experiences():
    # (この関数は変更なし)
    logging.info("--- ステップ1: 知識の取り込みと承認プロセスを開始 ---")
    os.makedirs(NEW_EXPERIENCES_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    ingested_count = 0
    for filename in os.listdir(NEW_EXPERIENCES_DIR):
        if not filename.endswith('.json'): continue
        source_path = os.path.join(NEW_EXPERIENCES_DIR, filename)
        destination_path = os.path.join(PROCESSED_DIR, filename)
        try:
            with open(source_path, 'r', encoding='utf-8') as f: data = json.load(f)
            if 'approved_meta' not in data:
                data['approved_meta'] = {"approved_by": "auto_approve_script", "approved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
                if 'knowledge_axis' not in data:
                    content_for_axis = data.get('summary', '') + data.get('content', '')
                    if "原則" in content_for_axis or "思想" in content_for_axis or "フレームワーク" in content_for_axis: data['knowledge_axis'] = "abstract"
                    else: data['knowledge_axis'] = "detail"
            save_atomic(data, destination_path, is_json=True)
            os.remove(source_path)
            logging.info(f"知識 '{filename}' を承認済みとして処理しました。")
            ingested_count += 1
        except Exception as e: logging.error(f"ファイル '{filename}' の処理中にエラーが発生しました: {e}")
    if ingested_count > 0: logging.info(f"合計 {ingested_count} 件の新しい知識を取り込み、承認しました。")
    else: logging.info("新しい知識は見つかりませんでした。")

# --- build_base ---
def build_knowledge_base():
    # (重複排除ロジックは前回の修正を維持)
    logging.info("--- ステップ2: 統合知識ベースの構築プロセスを開始 ---")
    all_knowledge = []
    if not os.path.exists(PROCESSED_DIR):
        logging.warning("承認済みの知識フォルダが見つかりません。")
        return
    for filename in os.listdir(PROCESSED_DIR):
        if filename.endswith('.json'):
            with open(os.path.join(PROCESSED_DIR, filename), 'r', encoding='utf-8') as f:
                all_knowledge.append(json.load(f))
    if not all_knowledge:
        logging.info("構築対象の承認済み知識がありません。")
        return

    unique_knowledge_dict = {}
    knowledge_to_process = []
    for exp in all_knowledge:
        exp_id = exp.get('experience_id')
        if exp_id:
            if exp_id not in unique_knowledge_dict:
                unique_knowledge_dict[exp_id] = exp
                knowledge_to_process.append(exp)
        else:
            logging.warning(f"experience_idが見つからない知識があります。Title: {exp.get('title', 'N/A')}")
            knowledge_to_process.append(exp)
    
    unique_knowledge_count = len(knowledge_to_process)
    logging.info(f"{unique_knowledge_count}件の知識を処理対象とします。")
    
    save_atomic(knowledge_to_process, KNOWLEDGE_BASE_PATH, is_json=True)

    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np

        logging.info("知識のベクトル化とインデックス構築を開始します...")
        model = SentenceTransformer('all-MiniLM-L6-v2', cache_folder='./.cache')
        texts_to_embed = [f"{exp.get('title', '')}\n{exp.get('summary', '')}" for exp in knowledge_to_process]
        embeddings = model.encode(texts_to_embed, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)
        
        # <<<【修正点3】インデックスをここでバイナリに変換し、save_atomicに渡す
        with io.BytesIO() as bio:
            faiss.write_index(index, faiss.PyCallbackIOWriter(bio.write))
            index_binary = bio.getvalue()
        
        save_atomic(index_binary, KNOWLEDGE_INDEX_PATH, is_json=False)
        logging.info("ベクトルインデックスの構築と保存が完了しました。")

    except ImportError:
        logging.warning("sentence-transformersまたはfaiss-cpuがインストールされていません。")
    except Exception as e:
        logging.error(f"ベクトルインデックスの構築中にエラーが発生しました: {e}", exc_info=True)

    logging.info("--- 統合知識ベースの構築が完了しました ---")

def main():
    parser = argparse.ArgumentParser(description="SAVAN Knowledge Refinery")
    parser.add_argument("--ingest", action="store_true", help="Process new experiences.")
    parser.add_argument("--build", action="store_true", help="Build the master knowledge base.")
    args = parser.parse_args()
    if args.ingest:
        ingest_and_approve_experiences()
    elif args.build:
        build_knowledge_base()
    else:
        print("コマンドを指定してください。--ingest または --build")

if __name__ == "__main__":
    main()