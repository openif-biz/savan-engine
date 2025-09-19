import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd
import unicodedata

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# --- データ変換関数 ---
@st.cache_data
def transform_and_clean_data(_df):
    if _df.empty:
        return pd.DataFrame()
    df = _df.copy()
    df = df.rename(columns=lambda x: x.strip())
    
    column_mapping = {
        'カード表示名': '案件名',
        '営業担当': '担当者名',
        '初期売上': '契約金額',
        '初期導入費（税込）': '入金額実績',
        '契約日(実績)': '契約',
        '完工日(実績)': '工事',
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

    # 税抜きの「契約金額」に1.1を掛けて税込に統一
    df['契約金額'] = clean_and_convert_to_numeric(df['契約金額']) * 1.1
    df['入金額実績'] = clean_and_convert_to_numeric(df['入金額実績'])

    id_vars = ['案件名', '担当者名', '契約金額', '入金額実績']
    value_vars = ['契約', '工事', '入金']
    value_vars = [v for v in value_vars if v in df.columns]

    if not value_vars:
        return pd.DataFrame()

    tidy_df = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='タスク', value_name='日付')
    
    tidy_df['日付'] = pd.to_datetime(tidy_df['日付'], errors='coerce')
    tidy_df.dropna(subset=['日付'], inplace=True)
    
    return tidy_df

def clamp_date(dt, min_dt, max_dt):
    return max(min_dt, min(dt, max_dt))

def create_gantt_chart(df, title="", display_mode="実績のみ"):
    if df.empty or 'タスク' not in df.columns:
        st.warning("表示対象の案件データがありません。")
        return

    gantt_data = []
    pivoted_df = df.pivot_table(index=['案件名', '担当者名'], columns='タスク', values='日付', aggfunc='first').reset_index()
    pivoted_df = pivoted_df.sort_values(by=['担当者名', '案件名']).reset_index(drop=True)

    colors = {
        '契約 (予定)': 'rgba(128, 128, 128, 0.4)', '工事 (予定)': 'rgba(128, 128, 128, 0.4)',
        '請求 (予定)': 'rgba(128, 128, 128, 0.4)', '入金 (予定)': 'rgba(128, 128, 128, 0.4)',
        '契約 (実績)': 'rgb(220, 53, 69)', '工事 (実績)': 'rgb(25, 135, 84)',
        '入金 (実績)': 'rgb(255, 193, 7)'
    }

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

# ファイル更新時のキャッシュクリアロジック
if "previous_filename" not in st.session_state:
    st.session_state.previous_filename = None
if "tidy_df" not in st.session_state:
    st.session_state.tidy_df = pd.DataFrame()

if uploaded_file is not None and uploaded_file.name != st.session_state.previous_filename:
    if uploaded_file.name.endswith('.xlsx'):
        raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
    else:
        raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
    st.session_state.tidy_df = transform_and_clean_data(raw_df)
    st.session_state.previous_filename = uploaded_file.name
    # フィルター状態をリセット
    if 'overall_filtered' in st.session_state:
        del st.session_state.overall_filtered
    if 'monthly_filtered' in st.session_state:
        del st.session_state.monthly_filtered


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
        # お客様の正しいロジックを適用
        pivoted_summary_df = tidy_df.pivot_table(index=['案件名', '契約金額', '入金額実績'], columns='タスク', values='日付', aggfunc='first').reset_index()
        
        total_contract = pivoted_summary_df['契約金額'].sum()
        total_payment = pivoted_summary_df[pivoted_summary_df['入金'].notna()]['入金額実績'].sum() if '入金' in pivoted_summary_df.columns else 0
        
        s_col1, s_col2 = st.columns(2)
        s_col1.metric("契約金額 合計 (税込)", f"{total_contract/1000000:,.1f} 百万円")
        s_col2.metric("入金額 合計 (税込)", f"{total_payment/1000000:,.1f} 百万円")
    else:
        st.info("集計対象のデータがありません。")

    contracts_df = tidy_df[tidy_df['タスク'] == '契約'].copy()
    if not contracts_df.empty:
        contracts_df['契約日'] = contracts_df['日付'].dt.date

        st.markdown("---")
        st.header("経営タイムライン全体（実績）")
        
        # セッションステートの初期化を修正
        if 'start_date' not in st.session_state or 'overall_filtered' not in st.session_state:
            st.session_state.overall_filtered = True
            st.session_state.start_date = contracts_df['契約日'].min()
            st.session_state.end_date = contracts_df['契約日'].max()

        with st.form("overall_form"):
            min_cal_date = date(2022, 4, 1)
            max_cal_date = date(2030, 12, 31)
            col1, col2 = st.columns(2)
            start_date = col1.date_input("表示開始日", value=st.session_state.start_date, min_value=min_cal_date, max_value=max_cal_date)
            end_date = col2.date_input("表示終了日", value=st.session_state.end_date, min_value=min_cal_date, max_value=max_cal_date)
            submitted_overall = st.form_submit_button("OK")

        if submitted_overall:
            st.session_state.start_date = start_date
            st.session_state.end_date = end_date
        
        mask_all = (contracts_df['契約日'] >= st.session_state.start_date) & (contracts_df['契約日'] <= st.session_state.end_date)
        projects_in_range_names = contracts_df[mask_all]['案件名'].unique()
        display_df_all = tidy_df[tidy_df['案件名'].isin(projects_in_range_names)]
        
        if not display_df_all.empty:
            st.info(f"指定期間内の案件（{len(projects_in_range_names)}件）を表示しています。")
            create_gantt_chart(display_df_all, title="経営タイムライン全体（実績）", display_mode="実績のみ")
        else:
            st.warning("指定期間に該当する案件がありません。")
        
        st.markdown("---")
        st.header("月次 予実サマリー＆タイムライン")
        
        with st.form("monthly_form"):
            min_cal_date = date(2022, 4, 1)
            max_cal_date = date(2030, 12, 31)
            col1, col2 = st.columns(2)
            default_contract_date = contracts_df['契約日'].min()
            contract_date_selection = col1.date_input("基準となる「契約月」を選択", value=default_contract_date, min_value=min_cal_date, max_value=max_cal_date)
            ideal_default_payment_date = contract_date_selection + relativedelta(months=6)
            clamped_default_payment_date = clamp_date(ideal_default_payment_date, min_cal_date, max_cal_date)
            payment_date_selection = col2.date_input("比較対象の「入金確認月」を選択", value=clamped_default_payment_date, min_value=min_cal_date, max_value=max_cal_date)
            submitted_monthly = st.form_submit_button("OK")

        if submitted_monthly:
            selected_contract_month = pd.Period(contract_date_selection, 'M')
            selected_payment_month = pd.Period(payment_date_selection, 'M')
            
            contracts_df['契約月'] = contracts_df['日付'].dt.to_period('M')
            target_contracts = contracts_df[contracts_df['契約月'] == selected_contract_month]
            unique_target_contracts = target_contracts[['案件名', '契約金額', '入金額実績']].drop_duplicates()
            total_contract_value = unique_target_contracts['契約金額'].sum()
            
            target_project_names = target_contracts['案件名'].unique()
            payments_df = tidy_df[tidy_df['案件名'].isin(target_project_names) & (tidy_df['タスク'] == '入金')]
            payment_deadline = (selected_payment_month.to_timestamp() + MonthEnd(1))
            paid_payments = payments_df[payments_df['日付'] <= payment_deadline]
            paid_project_names = paid_payments['案件名'].unique()
            
            total_paid_value = unique_target_contracts[unique_target_contracts['案件名'].isin(paid_project_names)]['入金額実績'].sum()
            total_unpaid_value = total_contract_value - total_paid_value

            st.subheader(f"【サマリー】{selected_contract_month.strftime('%Y-%m')}契約 → {selected_payment_month.strftime('%Y-%m')}時点での入金状況")
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric(f"{selected_contract_month.strftime('%Y-%m')}月 契約総額 (税込)", f"{total_contract_value/1000000:,.1f} 百万円")
            m_col2.metric("入金済 合計 (税込)", f"{total_paid_value/1000000:,.1f} 百万円")
            m_col3.metric("未入金 合計 (税込)", f"{total_unpaid_value/1000000:,.1f} 百万円")

            display_df_monthly = tidy_df[tidy_df['案件名'].isin(target_project_names)]
            if not display_df_monthly.empty:
                create_gantt_chart(display_df_monthly, title=f"{selected_contract_month.strftime('%Y-%m')}月契約案件 予実タイムライン", display_mode="予実両方")
else:
    st.info("ファイルをアップロードすると、タイムラインが表示されます。")
