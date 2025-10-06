# 【通番22】knowledge_engine.py (精密な検索ライブラリ版)
import json
import os
import logging
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- 定数定義 ---
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAVAN_ENGINE_ROOT = os.path.join(WORKSPACE_ROOT, "savan-engine")
KNOWLEDGE_BASE_PATH = os.path.join(SAVAN_ENGINE_ROOT, "savan_knowledge_base.json")
KNOWLEDGE_INDEX_PATH = os.path.join(SAVAN_ENGINE_ROOT, "savan_knowledge.index")
MODEL_NAME = 'all-MiniLM-L6-v2'

class KnowledgeEngine:
    """
    SAVANの思考の心臓部。
    統合された知識ベースとベクトルインデックスを使い、
    高度な検索機能を提供する。
    """
    def __init__(self):
        self.knowledge_base = []
        self.index = None
        self.model = None
        self.is_loaded = False
        logging.info("KnowledgeEngineがインスタンス化されました。")

    def load_knowledge_base(self):
        """
        仕様書3.2: 知識ベースとベクトルインデックスをメモリにロードする
        """
        logging.info("知識ベースとベクトルインデックスのロードを開始します...")
        
        try:
            # 知識本体(JSON)のロード
            if not os.path.exists(KNOWLEDGE_BASE_PATH):
                logging.error(f"知識ベースファイルが見つかりません: {KNOWLEDGE_BASE_PATH}")
                return False
            with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
            logging.info(f"{len(self.knowledge_base)}件の知識エントリーをロードしました。")

            # ベクトルインデックス(FAISS)のロード
            if not os.path.exists(KNOWLEDGE_INDEX_PATH):
                logging.error(f"ベクトルインデックスファイルが見つかりません: {KNOWLEDGE_INDEX_PATH}")
                return False
            self.index = faiss.read_index(KNOWLEDGE_INDEX_PATH)
            logging.info(f"ベクトルインデックスをロードしました。{self.index.ntotal}件のベクトルが登録されています。")

            # AIモデル(SentenceTransformer)のロード
            logging.info(f"AIモデル '{MODEL_NAME}' をロードしています...")
            self.model = SentenceTransformer(MODEL_NAME, cache_folder='./.cache')
            logging.info("AIモデルのロードが完了しました。")
            
            self.is_loaded = True
            logging.info("KnowledgeEngineのロードが正常に完了しました。検索準備OKです。")
            return True

        except Exception as e:
            logging.error(f"知識ベースのロード中に致命的なエラーが発生しました: {e}", exc_info=True)
            self.is_loaded = False
            return False

    def search(self, query_text: str, top_k: int = 5, mode: str = 'human_consult', context: dict = None):
        """
        仕様書3.2: クエリに基づき、ベクトル検索とフィルタリングを実行する
        """
        if not self.is_loaded:
            logging.warning("KnowledgeEngineがロードされていないため、検索を実行できません。")
            return []

        logging.info(f"検索を開始します... Query: '{query_text}', Mode: {mode}, Top_k: {top_k}")

        try:
            # 1. クエリをベクトル化
            query_vector = self.model.encode([query_text])
            query_vector = np.array(query_vector).astype('float32')

            # 2. ベクトル検索 (FAISSによる類似度検索)
            distances, indices = self.index.search(query_vector, top_k)
            
            # 3. 結果の取得
            results = [self.knowledge_base[i] for i in indices[0]]
            logging.info(f"{len(results)}件の類似知識を発見しました。")

            # 4. フィルタリング (将来の実装)
            # if context and context.get('knowledge_axis'):
            #    results = [r for r in results if r.get('knowledge_axis') == context['knowledge_axis']]
            #    logging.info(f"Axisフィルタ適用後、{len(results)}件に絞り込みました。")
            
            # 5. モードに応じた結果保証 (将来の実装)
            # if mode == 'automation':
            #    results = [r for r in results if r.get('machine_tags', {}).get('automation_ready')]

            return results

        except Exception as e:
            logging.error(f"検索処理中にエラーが発生しました: {e}", exc_info=True)
            return []