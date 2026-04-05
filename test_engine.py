# KnowledgeEngineの性能をテストするための専用スクリプト
import logging
from knowledge_engine import KnowledgeEngine

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_test():
    logging.info("--- KnowledgeEngine 性能テストを開始 ---")

    # 1. エンジンをインスタンス化
    engine = KnowledgeEngine()

    # 2. 知識ベースとインデックスをロード
    load_success = engine.load_knowledge_base()
    
    if not load_success:
        logging.error("テスト失敗: 知識ベースのロードに失敗しました。")
        return

    # 3. 実際に検索を実行
    logging.info("--- 検索テストを実行 ---")
    query = "CI/CDパイプラインの認証"
    results = engine.search(query, top_k=3)

    # 4. 結果を表示して確認
    if results:
        logging.info(f"クエリ「{query}」に対する検索結果:")
        print("-------------------------------------------")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('title', '無題の経験')}")
        print("-------------------------------------------")
        logging.info("テスト成功: 正常に検索結果を取得できました。")
    else:
        logging.warning("テスト結果: 検索結果が0件でした。知識ベースの内容を確認してください。")

    logging.info("--- KnowledgeEngine 性能テストを終了 ---")

if __name__ == "__main__":
    run_test()