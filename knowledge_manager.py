# knowledge_manager.py (修正版)

import json

KB_FILE_PATH = 'savan_knowledge_base.json'

def load_knowledge_base():
    """ナレッジベースJSONファイルを読み込む"""
    try:
        with open(KB_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [] # ファイルがない、または空の場合は空のリストを返す

def save_experience(new_experience):
    """新しい経験をナレッジベースに追記して保存する"""
    knowledge_base = load_knowledge_base()
    # 既に同じIDの経験がないか確認
    if not any(exp.get('experience_id') == new_experience.get('experience_id') for exp in knowledge_base):
        knowledge_base.append(new_experience)
        with open(KB_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(knowledge_base, f, indent=2, ensure_ascii=False)
        print(f"INFO: 新しい経験（ID: {new_experience.get('experience_id')}）を記憶しました。")
        return True
    return False

def find_solution_in_kb(new_error_message):
    """新しいエラーメッセージに類似した過去の解決策を探す（キーワード検索強化版）"""
    knowledge_base = load_knowledge_base()
    
    new_error_str = str(new_error_message).lower()
    
    best_match = None
    highest_score = 0

    for experience in knowledge_base:
        symptom = experience.get('symptom', {})
        
        # キーワードベースの類似度スコアを計算
        keywords = symptom.get('keywords', [])
        match_count = sum(1 for keyword in keywords if keyword.lower() in new_error_str)
        
        if match_count > 0:
            # スコアリングロジック：キーワードの一致数をスコアとする
            score = match_count
            if score > highest_score:
                highest_score = score
                best_match = experience

    if best_match:
        solution = best_match.get('final_solution', {})
        print("\n--- 過去の類似経験を発見 ---")
        print(f"プロジェクト: {best_match.get('project_name')}")
        print(f"原因の可能性: {solution.get('root_cause')}")
        print("▼ 過去の成功した解決策 ▼")
        print(f"```\n{solution.get('successful_code_snippet')}\n```")
        return solution
    else:
        return None