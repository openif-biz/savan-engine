import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd
import unicodedata

# --- アプリケーション設定 ---
st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# --- ▼▼▼ お客様のExcel形式に合わせてマッピングを修正 ▼▼▼ ---
COLUMN_MAPPING = {
    '物件名': '案件名',
    '営業担当': '担当者名',
    '初期売上': '契約金額',
    '入金': '入金額実績',
    '契約日': '契約',
    # '完工日(実績)': '工事', # ファイルに存在しないためコメントアウト
    # '初期費用入金日（実績）': '入金' # ファイルに存在しないためコメントアウト
}
# 存在する日付列のみを指定
ID_VARS_FOR_MELT = ['案件名', '担当者名', '契約金額', '入金額実績']
DATE_COLS_TO_MELT = ['契約'] # ファイルに存在する契約日のみ
# --- ▲▲▲ ここまで修正 ▲▲▲ ---

@st.cache_data
def transform_and_clean_data(_df):
    if _df.empty:
        return pd.DataFrame()
    df = _df.copy()
    df = df.rename(columns=lambda x: x.strip())
    df.rename(columns=COLUMN_MAPPING, inplace=True)
    
    # 必須列をファイル形式に合わせる
    required_cols = ['案件名', '担当者名', '契約金額', '入金額実績']
    if not all(col in df.columns for col in required_cols):
        st.error(f"必須列（{required_cols}）が見つかりません。お手元のファイルの列名が {list(COLUMN_MAPPING.keys())} と一致しているかご確認ください。")
        return pd.DataFrame()

    def clean_and_convert_to_numeric(series):
        s = series.fillna('').astype(str)
        s = s.apply(lambda x: unicodedata.normalize('NFKC', x))
        s = s.str.replace(r'[^\d.]', '', regex=True)
        return pd.to_numeric(s, errors='coerce').fillna(0) # NaNを0で埋める

    df['契約金額'] = clean_and_convert_to_numeric(df['契約金額'])
    df['入金額実績'] = clean_and_convert_to_numeric(df['入金額実績'])

    value_vars = [v for v in DATE_COLS_TO_MELT if v in df.columns]
    
    # 日付列がない場合はmeltしない
    if not value_vars:
        return df

    tidy_df = pd.melt(df, id_vars=ID_VARS_FOR_MELT, value_vars=value_vars, var_name='タスク', value_name='日付')
    tidy_df['日付'] = pd.to_datetime(tidy_df['日付'], errors='coerce')
    tidy_df.dropna(subset=['日付'], inplace=True)
    return tidy_df

def create_gantt_chart(df, title=""):
    # (この関数に変更はありませんが、'工事'と'入金'タスクがないため表示は契約のみになります)
    if df.empty or 'タスク' not in df.columns:
        st.warning("表示対象の案件データがありません。")
        return
    gantt_data = []
    pivoted_df = df.pivot_table(index=['案件名', '担当者名'], columns='タスク', values='日付', aggfunc='first').reset_index()
    pivoted_df = pivoted_df.sort_values(by=['担当者名', '案件名']).reset_index(drop=True)
    colors = {'契約 (実績)': 'rgb(220, 53, 69)'}
    for _, row in pivoted_df.iterrows():
        y_label_base = f"{row['案件名']} - {row['担当者名']}"
        contract_date = row.get('契約')
        if pd.notna(contract_date):
            contract_finish = contract_date + timedelta(days=4)
            gantt_data.append(dict(Task=y_label_base, Start=contract_date, Finish=contract_finish, Resource='契約 (実績)'))
    if gantt_data:
        fig = ff.create_gantt(pd.DataFrame(gantt_data).to_dict('records'), colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, showgrid_x=True, showgrid_y=True)
        unique_tasks = len(pd.DataFrame(gantt_data)['Task'].unique())
        chart_height = unique_tasks * 20 + 150
        fig.update_layout(margin=dict(t=80, b=50), legend_title_text='凡例', height=chart_height, title=dict(text=title, x=0.5))
        fig.update_yaxes(tickfont=dict(size=16)) 
        fig.update_xaxes(tickformat="%Y年%m月", tickfont=dict(size=16))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

# --- UI部分 ---
st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むExcelまたはCSVファイルをアップロードしてください", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.xlsx'):
            raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        
        data_df = transform_and_clean_data(raw_df)

        if not data_df.empty:
            st.markdown("---")
            st.subheader("担当営業フィルター")
            all_reps = sorted(data_df['担当者名'].dropna().unique())
            selected_reps = st.multiselect("担当者を選択してください（複数選択可）:", options=all_reps)
            
            filtered_df = data_df[data_df['担当者名'].isin(selected_reps)] if selected_reps else data_df
            
            st.markdown("---")
            st.header("全体サマリー")
            if not filtered_df.empty:
                # --- ▼▼▼ 入金額の集計ロジックをファイル形式に合わせて修正 ▼▼▼ ---
                unique_projects_df = filtered_df[['案件名', '契約金額', '入金額実績']].drop_duplicates(subset=['案件名'])
                total_contract = unique_projects_df['契約金額'].sum()
                
                # 「入金額実績」が0より大きいものを合計する
                paid_projects_df = unique_projects_df[unique_projects_df['入金額実績'] > 0]
                total_payment = paid_projects_df['入金額実績'].sum()
                # --- ▲▲▲ ここまで修正 ▲▲▲ ---
                
                s_col1, s_col2 = st.columns(2)
                s_col1.metric("契約金額 合計", f"{total_contract/1000000:,.1f} 百万円")
                s_col2.metric("入金額 合計", f"{total_payment/1000000:,.1f} 百万円")
            else:
                st.info("フィルター条件に合うデータがありません。")

            contracts_df = filtered_df[filtered_df['タスク'] == '契約'].copy() if 'タスク' in filtered_df.columns else pd.DataFrame()
            if not contracts_df.empty:
                contracts_df['契約日'] = contracts_df['日付'].dt.date
                st.markdown("---")
                st.header("経営タイムライン全体（実績）")
                # (月次サマリーは日付列が契約日しかないため、一旦機能を省略)
                # (ガントチャートは契約日のみで表示)
                create_gantt_chart(contracts_df, title="経営タイムライン全体（実績）")
            else:
                 st.info("ガントチャートを表示するための日付データ（契約日）が見つかりません。")
        else:
            st.info("アップロードされたファイルに計算対象のデータがありません。")
    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
        st.exception(e)
else:
    st.info("ファイルをアップロードすると、タイムラインが表示されます。")
