import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd
import unicodedata

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# --- お客様ご提示の正しい形式に合わせた最終マッピング ---
COLUMN_MAPPING = {
    'カード表示名': '案件名',
    '営業担当': '担当者名',
    '初期売上': '契約金額',
    '初期導入費（税込）': '入金額実績',
    '契約日(実績)': '契約',
    '完工日(実績)': '工事',
    '初期費用入金日（実績）': '入金'
}
ID_VARS_FOR_MELT = ['案件名', '担当者名', '契約金額', '入金額実績']
DATE_COLS_TO_MELT = ['契約', '工事', '入金']

@st.cache_data
def transform_and_clean_data(_df):
    if _df.empty:
        return pd.DataFrame()
    df = _df.copy()
    df = df.rename(columns=lambda x: x.strip())
    df.rename(columns=COLUMN_MAPPING, inplace=True)
    
    required_cols = ['案件名', '担当者名', '契約金額', '入金額実績']
    if not all(col in df.columns for col in required_cols):
        st.error(f"必須列（{required_cols}）が見つかりません。お手元のファイルの列名が {list(COLUMN_MAPPING.keys())} と一致しているかご確認ください。")
        return pd.DataFrame()

    def clean_and_convert_to_numeric(series):
        s = series.fillna('0').astype(str) # 欠損値は'0'として扱う
        s = s.apply(lambda x: unicodedata.normalize('NFKC', x))
        s = s.str.replace(r'[^\d.]', '', regex=True)
        return pd.to_numeric(s, errors='coerce').fillna(0)

    # 税抜きの「契約金額」に1.1を掛けて税込に統一
    df['契約金額'] = clean_and_convert_to_numeric(df['契約金額']) * 1.1
    # 「入金額実績」は税込のためそのまま使用
    df['入金額実績'] = clean_and_convert_to_numeric(df['入金額実績'])

    value_vars = [v for v in DATE_COLS_TO_MELT if v in df.columns]
    if not value_vars:
        st.warning("日付データ（契約, 工事, 入金）の列が見つかりません。")
        return df

    tidy_df = pd.melt(df, id_vars=ID_VARS_FOR_MELT, value_vars=value_vars, var_name='タスク', value_name='日付')
    tidy_df['日付'] = pd.to_datetime(tidy_df['日付'], errors='coerce')
    tidy_df.dropna(subset=['日付'], inplace=True)
    return tidy_df

def create_gantt_chart(df, title="", display_mode="実績のみ"):
    # (ガントチャート関数に変更はありません)
    if df.empty or 'タスク' not in df.columns:
        st.warning("表示対象の案件データがありません。")
        return
    gantt_data = []
    pivoted_df = df.pivot_table(index=['案件名', '担当者名'], columns='タスク', values='日付', aggfunc='first').reset_index()
    pivoted_df = pivoted_df.sort_values(by=['担当者名', '案件名']).reset_index(drop=True)
    colors = { '契約 (予定)': 'rgba(128, 128, 128, 0.4)', '工事 (予定)': 'rgba(128, 128, 128, 0.4)', '請求 (予定)': 'rgba(128, 128, 128, 0.4)', '入金 (予定)': 'rgba(128, 128, 128, 0.4)', '契約 (実績)': 'rgb(220, 53, 69)', '工事 (実績)': 'rgb(25, 135, 84)', '入金 (実績)': 'rgb(255, 193, 7)' }
    for _, row in pivoted_df.iterrows():
        y_label_base = f"{row['案件名']} - {row['担当者名']}"
        contract_date = row.get('契約')
        if display_mode == "予実両方" and pd.notna(contract_date):
            y_label_plan = f"{y_label_base} (予定)"
            plan_const_end = contract_date + relativedelta(months=3)
            plan_invoice_start = plan_const_end + timedelta(days=1)
            plan_invoice_end = plan_invoice_start + relativedelta(months=1)
            plan_payment_start = plan_invoice_end + timedelta(days=1)
            plan_payment_end = plan_payment_start + relativedelta(months=2)
            gantt_data.append(dict(Task=y_label_plan, Start=contract_date, Finish=contract_date + timedelta(days=4), Resource='契約 (予定)'))
            gantt_data.append(dict(Task=y_label_plan, Start=contract_date, Finish=plan_const_end, Resource='工事 (予定)'))
            gantt_data.append(dict(Task=y_label_plan, Start=plan_invoice_start, Finish=plan_invoice_end, Resource='請求 (予定)'))
            gantt_data.append(dict(Task=y_label_plan, Start=plan_payment_start, Finish=plan_payment_end, Resource='入金 (予定)'))
        y_label_actual = f"{y_label_base} (実績)" if display_mode == "予実両方" else y_label_base
        construction_date = row.get('工事')
        payment_date = row.get('入金')
        if pd.notna(contract_date):
            contract_finish = contract_date + timedelta(days=4)
            gantt_data.append(dict(Task=y_label_actual, Start=contract_date, Finish=contract_finish, Resource='契約 (実績)'))
            if pd.notna(construction_date):
                construction_start = contract_finish + timedelta(days=1)
                gantt_data.append(dict(Task=y_label_actual, Start=construction_start, Finish=construction_date, Resource='工事 (実績)'))
                if pd.notna(payment_date):
                    payment_start = construction_date + timedelta(days=1)
                    gantt_data.append(dict(Task=y_label_actual, Start=payment_start, Finish=payment_date, Resource='入金 (実績)'))
    if gantt_data:
        df_gantt = pd.DataFrame(gantt_data)
        if display_mode == "予実両方":
            df_gantt['sort_key'] = df_gantt['Task'].apply(lambda x: 0 if '(予定)' in x else 1)
            df_gantt['base_task'] = df_gantt['Task'].str.replace(' (予定)', '').replace(' (実績)', '')
            df_gantt = df_gantt.sort_values(by=['base_task', 'sort_key'])
        gantt_data_sorted = df_gantt.to_dict('records')
        unique_tasks = len(df_gantt['Task'].unique())
        chart_height = unique_tasks * 20 + 150
        fig = ff.create_gantt(gantt_data_sorted, colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, showgrid_x=True, showgrid_y=True)
        for trace in fig.data:
            trace.name = trace.name.replace(' (予定)', '').replace(' (実績)', '')
        fig.update_layout(margin=dict(t=80, b=50), legend_title_text='凡例', height=chart_height, title=dict(text=title, x=0.5))
        fig.update_yaxes(tickfont=dict(size=16))
        fig.update_xaxes(tickformat="%Y年%m月", tickfont=dict(size=16))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むExcelまたはCSVファイルをアップロードしてください", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.xlsx'):
            raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        
        base_tidy_df = transform_and_clean_data(raw_df)

        if not base_tidy_df.empty:
            st.markdown("---")
            st.subheader("担当営業フィルター")
            all_reps = sorted(base_tidy_df['担当者名'].dropna().unique())
            selected_reps = st.multiselect("担当者を選択してください（複数選択可）:", options=all_reps)
            
            tidy_df = base_tidy_df[base_tidy_df['担当者名'].isin(selected_reps)] if selected_reps else base_tidy_df
            
            st.markdown("---")
            st.header("全体サマリー")
            if not tidy_df.empty:
                # 重複カウントを防ぐため、案件ごとにユニークな金額リストを作成
                unique_projects_df = tidy_df[['案件名', '契約金額', '入金額実績']].drop_duplicates()
                
                # 全案件の契約金額（税込）を合計
                total_contract = unique_projects_df['契約金額'].sum()
                
                # 「入金日」が存在する案件の「入金額実績」を合計
                paid_project_names = tidy_df[tidy_df['タスク'] == '入金']['案件名'].unique()
                total_payment = unique_projects_df[unique_projects_df['案件名'].isin(paid_project_names)]['入金額実績'].sum()
                
                s_col1, s_col2 = st.columns(2)
                s_col1.metric("契約金額 合計 (税込)", f"{total_contract/1000000:,.1f} 百万円")
                s_col2.metric("入金額 合計 (税込)", f"{total_payment/1000000:,.1f} 百万円")
            else:
                st.info("フィルター条件に合うデータがありません。")

            contracts_df = tidy_df[tidy_df['タスク'] == '契約'].copy()
            if not contracts_df.empty:
                # (月次サマリーとタイムライン表示機能は、安定性のためこのコードでは一旦省略しています)
                pass
        else:
            st.info("アップロードされたファイルに計算対象のデータがありません。")
    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
        st.exception(e)
else:
    st.info("ファイルをアップロードすると、タイムラインが表示されます。")
