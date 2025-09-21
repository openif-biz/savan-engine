import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd
import unicodedata
import os
import gspread # gspreadライブラリをインポート
import json # JSONキーを読み込むためにインポート

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# --- ▼▼▼【ここから大幅に変更】▼▼▼ ---

# キャッシュを使い、一度読み込んだデータは再利用する
@st.cache_data(ttl=600)
def load_data_from_google_sheet():
    """
    Google Drive上のスプレッドシートからデータを読み込む関数
    """
    try:
        # GitHub Secretsから渡された環境変数を読み込む
        creds_json_str = os.environ.get("GCP_SA_KEY")
        if not creds_json_str:
            st.error("エラー: サービスアカウントの認証情報が設定されていません。")
            return pd.DataFrame()

        creds_dict = json.loads(creds_json_str)
        
        # 認証情報を使ってGoogleスプレッドシートにアクセス
        gc = gspread.service_account_from_dict(creds_dict)
        
        # クライアントのフォルダ名とファイル名を指定（将来的には動的に変更）
        spreadsheet_name = "日本総合技術株式会社様"
        
        spreadsheet = gc.open(spreadsheet_name)
        worksheet = spreadsheet.sheet1 # 最初のシートを読み込む
        
        # シートのデータをPandas DataFrameに変換
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        st.success(f"'{spreadsheet_name}'からのデータ読み込みに成功しました。")
        return df

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"エラー: Google Drive内に '{spreadsheet_name}' という名前のスプレッドシートが見つかりません。")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"データの読み込み中に予期せぬエラーが発生しました: {e}")
        return pd.DataFrame()

# 既存のデータ処理・描画関数は変更なし
@st.cache_data
def transform_and_clean_data(_df):
    if _df.empty:
        return pd.DataFrame()
    df = _df.copy()
    df = df.rename(columns=lambda x: x.strip())
    
    # ... (この関数の以降の中身は以前と同じなので省略) ...
    # (The rest of this function's content is the same as before, so it's omitted)
    column_mapping = {
        'カード表示名': '案件名', '営業担当': '担当者名', '初期売上': '契約金額',
        '初期導入費（税込）': '入金額実績', '契約日(実績)': '契約', '完工日(実績)': '工事',
        '初期費用入金日（実績）': '入金'
    }
    df.rename(columns=column_mapping, inplace=True)
    required_cols = ['案件名', '担当者名', '契約金額', '入金額実績']
    if not all(col in df.columns for col in required_cols):
        st.error(f"必須列（{required_cols}）が見つかりません。")
        return pd.DataFrame()
    def clean_and_convert_to_numeric(series):
        s = series.fillna('0').astype(str)
        s = s.apply(lambda x: unicodedata.normalize('NFKC', x))
        s = s.str.replace(r'[^\d.]', '', regex=True)
        return pd.to_numeric(s, errors='coerce').fillna(0)
    df['契約金額'] = clean_and_convert_to_numeric(df['契約金額'])
    df['入金額実績'] = clean_and_convert_to_numeric(df['入金額実績'])
    id_vars = ['案件名', '担当者名', '契約金額', '入金額実績']
    value_vars = ['契約', '工事', '入金']
    value_vars = [v for v in value_vars if v in df.columns]
    if not value_vars:
        return df
    tidy_df = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='タスク', value_name='日付')
    tidy_df['日付'] = pd.to_datetime(tidy_df['日付'], errors='coerce')
    tidy_df.dropna(subset=['日付'], inplace=True)
    return tidy_df


def create_gantt_chart(df, title=""):
    # ... (この関数の中身は以前と同じなので省略) ...
    # (This function's content is the same as before, so it's omitted)
    if df.empty or 'タスク' not in df.columns:
        st.warning("表示対象の案件データがありません。")
        return
    pivoted_df = df.pivot_table(index=['案件名', '担当者名'], columns='タスク', values='日付', aggfunc='first').reset_index()
    pivoted_df = pivoted_df.sort_values(by=['担当者名', '案件名']).reset_index(drop=True)
    gantt_data = []
    colors = {'契約': 'rgb(220, 53, 69)', '工事': 'rgb(25, 135, 84)', '請求': 'rgb(13, 110, 253)', '入金': 'rgb(255, 193, 7)'}
    for _, row in pivoted_df.iterrows():
        y_label = f"{row['案件名']} - {row['担当者名']}"
        tasks = ['契約', '工事', '請求', '入金']
        for task in tasks:
            if task in row and pd.notna(row[task]):
                gantt_data.append(dict(Task=y_label, Start=row[task], Finish=row[task] + timedelta(days=1), Resource=task))
    if gantt_data:
        fig = ff.create_gantt(gantt_data, colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, showgrid_x=True, showgrid_y=True)
        unique_tasks = len(pivoted_df)
        chart_height = unique_tasks * 35 + 150
        fig.update_layout(height=chart_height, title=dict(text=title, x=0.5))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

# --- メインロジック ---
# ファイルアップローダーの代わりに、Google Sheetからデータをロードする
raw_df = load_data_from_google_sheet()

if not raw_df.empty:
    tidy_df = transform_and_clean_data(raw_df)
    
    if not tidy_df.empty:
        # ... (フィルターとサマリー表示のロジックは以前と同じなので省略) ...
        # (The filtering and summary display logic is the same as before, so it's omitted)
        st.markdown("---")
        st.subheader("担当営業フィルター")
        all_reps = sorted(tidy_df['担当者名'].dropna().unique())
        selected_reps = st.multiselect("担当者を選択してください（複数選択可）:", options=all_reps)
        filtered_tidy_df = tidy_df[tidy_df['担当者名'].isin(selected_reps)] if selected_reps else tidy_df
        st.markdown("---")
        st.header("全体サマリー")
        # ... (Summary logic continues) ...
        st.header("経営タイムライン全体（実績）")
        create_gantt_chart(filtered_tidy_df, title="経営タイムライン全体（実績）")

# --- ▲▲▲【ここまで大幅に変更】▲▲▲ ---