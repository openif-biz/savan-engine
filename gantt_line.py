import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from pandas.tseries.offsets import MonthEnd

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# --- データ変換関数 ---
def transform_and_clean_data(df):
    df = df.rename(columns=lambda x: x.strip())
    
    # <<< 修正点: 「初期導入費（税込）」を「契約金額」の正解データとして使用 >>>
    column_mapping = {
        'カード表示名': '案件名',
        '営業担当': '担当者名',
        '初期導入費（税込）': '契約金額', # ★ 正解データを「契約金額」とする
        '契約日(実績)': '契約',
        '完工日(実績)': '工事',
        '初期費用入金日（実績）': '入金'
    }
    df.rename(columns=column_mapping, inplace=True)

    # 契約金額を基に入金額実績の列を作成（理論上同額になるため）
    df['入金額実績'] = df['契約金額']
    
    required_cols = ['案件名', '担当者名', '契約金額']
    if not all(col in df.columns for col in required_cols):
        st.error(f"必須列（カード表示名, 営業担当, 初期導入費（税込））が見つかりません。")
        return pd.DataFrame()

    # <<< 修正点: 1.1倍の計算を廃止し、正解データを直接クレンジング >>>
    df['契約金額'] = pd.to_numeric(df['契約金額'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
    df['入金額実績'] = pd.to_numeric(df['入金額実績'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')

    id_vars = ['案件名', '担当者名', '契約金額', '入金額実績']
    value_vars = ['契約', '工事', '入金']
    value_vars = [v for v in value_vars if v in df.columns]
    
    tidy_df = pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name='タスク', value_name='日付')
    
    tidy_df['日付'] = pd.to_datetime(tidy_df['日付'], errors='coerce')
    tidy_df.dropna(subset=['日付'], inplace=True)
    
    return tidy_df

# --- 日付を安全な範囲に丸めるヘルパー関数 ---
def clamp_date(dt, min_dt, max_dt):
    return max(min_dt, min(dt, max_dt))

# --- ガントチャート作成関数 ---
def create_gantt_chart(df, title="", display_mode="実績のみ"):
    if df.empty:
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
            df_gantt['base_task'] = df_gantt['Task'].str.replace(' (予定)', '').str.replace(' (実績)', '')
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

# --- UI部分 ---
st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むExcelまたはCSVファイルをアップロードしてください", type=["csv", "xlsx"])

if 'overall_filtered' not in st.session_state:
    st.session_state.overall_filtered = False
if 'monthly_filtered' not in st.session_state:
    st.session_state.monthly_filtered = False

if uploaded_file:
    try:
        if 'tidy_df' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
            if uploaded_file.name.endswith('.xlsx'):
                raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
            else:
                raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.session_state.tidy_df = transform_and_clean_data(raw_df)
            st.session_state.file_name = uploaded_file.name
            st.session_state.overall_filtered = False
            st.session_state.monthly_filtered = False

        base_tidy_df = st.session_state.tidy_df
        if not base_tidy_df.empty:
            
            st.markdown("---")
            st.subheader("担当営業フィルター")
            all_reps = sorted(base_tidy_df['担当者名'].dropna().unique())
            selected_reps = st.multiselect("担当者を選択してください（複数選択可）:", options=all_reps)
            
            if selected_reps:
                tidy_df = base_tidy_df[base_tidy_df['担当者名'].isin(selected_reps)]
            else:
                tidy_df = base_tidy_df
            
            st.markdown("---")
            st.header("全体サマリー")
            if not tidy_df.empty:
                unique_projects_df = tidy_df[['案件名', '契約金額', '入金額実績']].drop_duplicates()
                total_contract = unique_projects_df['契約金額'].sum()

                paid_project_names = tidy_df[tidy_df['タスク'] == '入金']['案件名'].unique()
                total_payment = unique_projects_df[unique_projects_df['案件名'].isin(paid_project_names)]['入金額実績'].sum()
                
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
                with st.form("overall_form"):
                    min_cal_date = date(2022, 4, 1)
                    max_cal_date = date(2030, 12, 31)
                    
                    col1, col2 = st.columns(2)
                    all_start = col1.date_input("表示開始日", value=contracts_df['契約日'].min(), min_value=min_cal_date, max_value=max_cal_date)
                    all_end = col2.date_input("表示終了日", value=contracts_df['契約日'].max(), min_value=min_cal_date, max_value=max_cal_date)
                    submitted_overall = st.form_submit_button("OK")

                if submitted_overall:
                    mask_all = (contracts_df['契約日'] >= all_start) & (contracts_df['契約日'] <= all_end)
                    projects_all_df = contracts_df[mask_all].sort_values(by='契約日', ascending=False)
                    projects_all_names = projects_all_df['案件名'].unique()
                    
                    st.session_state.display_df_all = tidy_df[tidy_df['案件名'].isin(projects_all_names)]
                    st.session_state.total_projects_in_range = len(projects_all_df['案件名'].unique())
                    st.session_state.overall_filtered = True
                    st.session_state.monthly_filtered = False

                if st.session_state.overall_filtered:
                    display_df_all = st.session_state.display_df_all
                    if not display_df_all.empty:
                        st.info(f"指定期間内の案件（{st.session_state.total_projects_in_range}件）を表示しています。")
                        create_gantt_chart(display_df_all, title="経営タイムライン全体（実績）", display_mode="実績のみ")
                    else:
                        st.warning("指定期間に該当する案件がありません。")
                
                if st.session_state.overall_filtered:
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
                        st.session_state.selected_contract_month = pd.Period(contract_date_selection, 'M')
                        st.session_state.selected_payment_month = pd.Period(payment_date_selection, 'M')
                        st.session_state.monthly_filtered = True

                    if st.session_state.monthly_filtered:
                        selected_contract_month = st.session_state.selected_contract_month
                        selected_payment_month = st.session_state.selected_payment_month
                        
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
                st.warning("フィルタリング対象の契約データが見つかりません。")

    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
        st.exception(e)
else:
    st.info("ファイルをアップロードすると、タイムラインが表示されます。")

