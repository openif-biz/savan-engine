import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

def analyze_payment_data(df):
    contracts = df[df['タスク'] == '契約'][['案件名', '担当者名', '契約金額', '実績終了日']].copy()
    payments = df[df['タスク'] == '入金'][['案件名', '実績終了日']].copy()
    
    contracts.rename(columns={'実績終了日': '契約日'}, inplace=True)
    payments.rename(columns={'実績終了日': '入金日'}, inplace=True)

    contracts['契約日'] = pd.to_datetime(contracts['契約日'], errors='coerce')
    payments['入金日'] = pd.to_datetime(payments['入金日'], errors='coerce')

    analysis_df = pd.merge(contracts, payments, on='案件名', how='left')
    analysis_df['契約月'] = analysis_df['契約日'].dt.strftime('%Y-%m')
    return analysis_df.dropna(subset=['契約月'])

def create_gantt_chart(df, title="", display_mode="実績のみ"):
    df['案件担当者'] = df['案件名'] + ' - ' + df['担当者名']
    task_order = ['契約', '工事', '請求', '入金']
    
    # 【透明度を修正】予定のバーのrgbaの最後の値を0.4に変更
    colors = {
        '契約_予定': 'rgba(220, 53, 69, 0.4)', '工事_予定': 'rgba(25, 135, 84, 0.4)', 
        '請求_予定': 'rgba(13, 110, 253, 0.4)', '入金_予定': 'rgba(255, 193, 7, 0.4)',
        '契約_実績': 'rgb(220, 53, 69)', '工事_実績': 'rgb(25, 135, 84)', 
        '請求_実績': 'rgb(13, 110, 253)', '入金_実績': 'rgb(255, 193, 7)'
    }
    gantt_data = []

    for name, group in df.groupby(['案件名', '担当者名']):
        proj_name, assignee_name = name
        y_label = f"{proj_name} - {assignee_name}"
        
        if display_mode == '予実両方':
            contract_row_df = group[group['タスク'] == '契約']
            if not contract_row_df.empty:
                base_date = pd.to_datetime(contract_row_df['実績終了日'].iloc[0], errors='coerce')
                if pd.notna(base_date):
                    plan_dates = {
                        '契約': (base_date, base_date + timedelta(days=1)),
                        '工事': (base_date + timedelta(days=2), base_date + timedelta(days=1) + relativedelta(months=3)),
                        '請求': (base_date + timedelta(days=2) + relativedelta(months=3), base_date + timedelta(days=1) + relativedelta(months=4)),
                        '入金': (base_date + timedelta(days=2) + relativedelta(months=4), base_date + timedelta(days=1) + relativedelta(months=6))
                    }
                    for task in task_order:
                        gantt_data.append(dict(Task=f"{y_label} (予定)", Start=plan_dates[task][0], Finish=plan_dates[task][1], Resource=f"{task}_予定"))
        
        for i, row in group.iterrows():
            s_date = pd.to_datetime(row['実績開始日'], errors='coerce')
            f_date = pd.to_datetime(row['実績終了日'], errors='coerce')
            if pd.notna(s_date) and pd.notna(f_date):
                if s_date == f_date:
                    f_date += timedelta(hours=12)
                task_label = f"{y_label} (実績)" if display_mode == '予実両方' else y_label
                gantt_data.append(dict(Task=task_label, Start=s_date, Finish=f_date, Resource=f"{row['タスク']}_実績"))

    if gantt_data:
        if display_mode == '予実両方':
             gantt_data.sort(key=lambda x: (x['Task'].replace(' (予定)', '').replace(' (実績)', ''), x['Task']))
        
        fig = ff.create_gantt(gantt_data, colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, title=title)
        
        for trace in fig.data:
            trace.name = trace.name.replace('_予定', ' (予定)').replace('_実績', '')
        
        fig.update_layout(
            legend_title_text='凡例',
            margin=dict(t=120)
        )
        fig.update_yaxes(tickfont=dict(size=20))
        fig.update_xaxes(
            side="top",
            tickformat="%Y年%m月", 
            tickfont=dict(size=24)
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むCSVファイルをアップロードしてください", type="csv")

if uploaded_file:
    try:
        main_df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str).applymap(
            lambda x: x.strip() if isinstance(x, str) else x
        ).replace('', None)
        main_df['契約金額'] = pd.to_numeric(main_df['契約金額'], errors='coerce')
        
        st.header("経営タイムライン全体")
        create_gantt_chart(main_df.copy(), title="実績タイムライン", display_mode="実績のみ")

        st.header("経営タイムライン（月別契約）")
        analysis_df = analyze_payment_data(main_df.copy())
        contracts_df = main_df[main_df['タスク']=='契約'].copy()
        contracts_df['契約月'] = pd.to_datetime(contracts_df['実績終了日'], errors='coerce').dt.strftime('%Y-%m')
        
        contract_months = sorted(contracts_df['契約月'].dropna().unique(), reverse=True)
        if contract_months:
            selected_month = st.selectbox("月別表示対象を選択", options=contract_months)
            
            # --- サマリー指標（復活） ---
            monthly_data = analysis_df[analysis_df['契約月'] == selected_month]
            if not monthly_data.empty:
                total_contract_value = monthly_data['契約金額'].sum()
                paid_data = monthly_data.dropna(subset=['入金日'])
                total_paid_value = paid_data['契約金額'].sum()
                total_unpaid_value = total_contract_value - total_paid_value
                col1, col2, col3 = st.columns(3)
                col1.metric("契約月 合計金額", f"{total_contract_value/1000000:,.1f} 百万円")
                col2.metric("入金済 合計金額", f"{total_paid_value/1000000:,.1f} 百万円")
                col3.metric("未入金 合計金額", f"{total_unpaid_value/1000000:,.1f} 百万円")

            selected_projects = contracts_df[contracts_df['契約月'] == selected_month]['案件名'].unique()
            monthly_df = main_df[main_df['案件名'].isin(selected_projects)]
            create_gantt_chart(monthly_df.copy(), title=f"{selected_month}月契約案件（予実比較）", display_mode="予実両方")
        else:
            st.info("月次タイムラインを表示するための契約データがありません。")
            
    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
else:
    st.info("CSVファイルをアップロードすると、タイムラインが表示されます。")