# reproduce_error.py
import pandas as pd

def process_faulty_data():
    """
    本番データで起こりがちな列名の不一致によるKeyErrorを意図的に発生させる関数。
    """
    print("[テスト] わざとエラーを発生させます...")

    # '担当者' 列があるべきなのに、'担当' という不完全な列名しかないデータフレームを模擬
    faulty_data = {'案件名': ['案件A'], '担当': ['佐藤']}
    df = pd.DataFrame(faulty_data)

    # 存在しない '担当者' 列にアクセスしようとするため、ここでKeyErrorが発生する
    responsible_person = df['担当者']

    print("この行は実行されません。")
    return responsible_person