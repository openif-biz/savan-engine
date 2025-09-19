import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd
import unicodedata

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

@st.cache_data
def transform_and_clean_data(_df):
    if _df.empty:
        return pd.DataFrame()
    df = _df.copy()
    df = df.rename(columns=lambda x: x.strip())
    
    column_mapping = {
        'カード表示名': '案件名', '営業担当': '担当者名', '初期売上': '契約金額',
        '初期導入費（税込）': '入金額実績', '契約日(実績)': '契約',
        '完工日(実績)': '工事', '初期費用入金日（実績）': '入金'
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

def clamp_date(dt, min_dt, max_dt):
    return max(min_dt, min(dt, max_dt))

def create_gantt_chart(df, title=""):
    if df.empty or 'タスク' not in df.columns:
        st.warning("表示対象の案件データがありません。")
        return
    gantt_data = []
    pivoted_df = df.pivot_table(index=['案件名', '担当者名'], columns='タスク', values='日付', aggfunc='first').reset_index()
    pivoted_df = pivoted_df.sort_values(by=['担当者名', '案件名']).reset_index(drop=True)
    colors = { '契約 (実績)': 'rgb(220, 53, 69)', '工事 (実績)': 'rgb(25, 135, 84)', '入金 (実績)': 'rgb(255, 193, 7)' }
    for _, row in pivoted_df.iterrows():
        y_label_base = f"{row['案件名']} - {row['担当者名']}"
        contract_date = row.get('契約')
        construction_date = row.get('工事')
        payment_date = row.get('入金')
        if pd.notna(contract_date):
            contract_finish = contract_date + timedelta(days=4)
            gantt_data.append(dict(Task=y_label_base, Start=contract_date, Finish=contract_finish, Resource='契約 (実績)'))
            if pd.notna(construction_date):
                construction_start = contract_finish + timedelta(days=1)
                gantt_data.append(dict(Task=y_label_base, Start=construction_start, Finish=construction_date, Resource='工事 (実績)'))
                if pd.notna(payment_date):
                    payment_start = construction_date + timedelta(days=1)
                    gantt_data.append(dict(Task=y_label_base, Start=payment_start, Finish=payment_date, Resource='入金 (実績)'))
    if gantt_data:
        df_gantt = pd.DataFrame(gantt_data)
        gantt_data_sorted = df_gantt.to_dict('records')
        unique_tasks = len(df_gantt['Task'].unique())
        chart_height = unique_tasks * 20 + 150
        fig = ff.create_gantt(gantt_data_sorted, colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, showgrid_x=True, showgrid_y=True)
        fig.update_layout(margin=dict(t=80, b=50), legend_title_text='凡例', height=chart_height, title=dict(text=title, x=0.5))
        fig.update_yaxes(tickfont=dict(size=16)) 
        fig.update_xaxes(tickformat="%Y年%m月", tickfont=dict(size=16))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むExcelまたはCSVファイルをアップロードしてください", type=["csv", "xlsx"])

if "previous_filename" not in st.session_state:
    st.session_state.previous_filename = None
if "tidy_df" not in st.session_state:
    st.session_state.tidy_df = pd.DataFrame()

if uploaded_file is not None:
    if uploaded_file.name != st.session_state.previous_filename:
        if uploaded_file.name.endswith('.xlsx'):
            raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
        st.session_state.tidy_df = transform_and_clean_data(raw_df)
        st.session_state.previous_filename = uploaded_file.name
        st.session_state.overall_filtered = False
        st.session_state.monthly_filtered = False
        if 'start_date' in st.session_state:
            del st.session_state.start_date
        if 'end_date' in st.session_state:
            del st.session_state.end_date

if not st.session_state.tidy_df.empty:
    base_tidy_df = st.session_state.tidy_df
    st.markdown("---")
    st.subheader("担当営業フィルター")
    all_reps = sorted(base_tidy_df['担当者名'].dropna().unique())
    selected_reps = st.multiselect("担当者を選択してください（複数選択可）:", options=all_reps)
    
    tidy_df = base_tidy_df[base_tidy_df['担当者名'].isin(selected_reps)] if selected_reps else base_tidy_df
    
    st.markdown("---")
    st.header("全体サマリー")
    if not tidy_df.empty:
        unique_projects_df = tidy_df[['案件名', '契約金額', '入金額実績']].drop_duplicates()
        total_contract_tax_exc = unique_projects_df['契約金額'].sum()
        total_payment = unique_projects_df['入金額実績'].sum()
        
        s_col1, s_col2 = st.columns(2)
        s_col1.metric("契約金額 合計 (税抜)", f"{total_contract_tax_exc/1000000:,.1f} 百万円")
        s_col2.metric("入金額 合計 (税込)", f"{total_payment/1000000:,.1f} 百万円")
    else:
        st.info("集計対象のデータがありません。")

    contracts_df = tidy_df[tidy_df['タスク'] == '契約'].copy()
    if not contracts_df.empty:
        contracts_df['契約日'] = contracts_df['日付'].dt.date

        st.markdown("---")
        st.header("経営タイムライン全体（実績）")
        
        with st.form("overall_form"):
            min_cal_date = contracts_df['契約日'].min()
            max_cal_date = contracts_df['契約日'].max()
            col1, col2 = st.columns(2)
            start_date = col1.date_input("表示開始日", value=min_cal_date, min_value=min_cal_date, max_value=max_cal_date)
            end_date = col2.date_input("表示終了日", value=max_cal_date, min_value=min_cal_date, max_value=max_cal_date)
            submitted_overall = st.form_submit_button("タイムラインを表示")

        if submitted_overall:
            mask_all = (contracts_df['契約日'] >= start_date) & (contracts_df['契約日'] <= end_date)
            projects_in_range_names = contracts_df[mask_all]['案件名'].unique()
            display_df_all = tidy_df[tidy_df['案件名'].isin(projects_in_range_names)]
            
            if not display_df_all.empty:
                st.info(f"指定期間内の案件（{len(projects_in_range_names)}件）を表示しています。")
                create_gantt_chart(display_df_all, title="経営タイムライン全体（実績）")
            else:
                st.warning("指定期間に該当する案件がありません。")
