import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ページの基本設定
st.set_page_config(layout="wide")

# タイトル
st.title("Gantt Line 経営タイムライン")

# --- 分析ロジックを関数として定義 ---
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

# --- ガントチャート描画用の共通関数 ---
def create_gantt_chart(df, title):
    df['案件担当者'] = df['案件名'] + ' - ' + df['担当者名']
    date_cols = ['実績開始日', '実績終了日']
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    
    task_order = ['契約', '工事', '請求', '入金']
    df['タスク'] = pd.Categorical(df['タスク'], categories=task_order, ordered=True)
    df = df.sort_values(by=['案件名', 'タスク'])

    gantt_data = []
    colors = {'契約': '#DC3545', '工事': '#198754', '請求': '#0D6EFD', '入金': '#FFC107'}

    for i, row in df.iterrows():
        if pd.notna(row['実績開始日']) and pd.notna(row['実績終了日']):
            gantt_data.append(dict(
                Task=row['案件担当者'],
                Start=row['実績開始日'],
                Finish=row['実績終了日'],
                Resource=row['タスク'],
                Description=f"担当: {row['担当者名']}<br>タスク: {row['タスク']}"
            ))
    
    if gantt_data:
        fig = ff.create_gantt(gantt_data, colors=colors, index_col='Resource', show_colorbar=True, group_tasks=True, title=title)
        fig.update_layout(margin=dict(t=100), legend_traceorder="normal")
        fig.update_yaxes(tickfont=dict(size=14))
        fig.update_xaxes(side="top", tickformat="%Y/%m月", tickfont=dict(size=16))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("表示可能な案件データがありません。")

# --- UIセクション ---
st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むCSVファイルをアップロードしてください", type="csv")

# --- データ処理と表示セクション ---
if uploaded_file is not None:
    try:
        main_df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str).applymap(
            lambda x: x.strip() if isinstance(x, str) else x
        ).replace('', None)
        main_df['契約金額'] = pd.to_numeric(main_df['契約金額'], errors='coerce')

        # --- 全案件ガントチャート ---
        st.header("経営タイムライン全体")
        create_gantt_chart(main_df.copy(), "")

        # --- 月次分析セクション ---
        st.header("月次入金状況分析")
        analysis_df = analyze_payment_data(main_df.copy())
        contract_months = sorted(analysis_df['契約月'].unique(), reverse=True)
        selected_month = st.selectbox('分析・表示したい契約月を選択してください', contract_months)
        
        if selected_month:
            monthly_data = analysis_df[analysis_df['契約月'] == selected_month]
            total_contract_value = monthly_data['契約金額'].sum()
            paid_data = monthly_data.dropna(subset=['入金日'])
            total_paid_value = paid_data['契約金額'].sum()
            total_unpaid_value = total_contract_value - total_paid_value
            col1, col2, col3 = st.columns(3)
            col1.metric("契約月 合計金額", f"{total_contract_value/1000000:,.1f} 百万円")
            col2.metric("入金済 合計金額", f"{total_paid_value/1000000:,.1f} 百万円")
            col3.metric("未入金 合計金額", f"{total_unpaid_value/1000000:,.1f} 百万円")

            # --- 月別ガントチャート ---
            st.header(f"経営タイムライン（{selected_month}月契約）")
            monthly_project_names = monthly_data['案件名'].unique()
            monthly_gantt_df = main_df[main_df['案件名'].isin(monthly_project_names)]
            create_gantt_chart(monthly_gantt_df, "")

    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
else:
    st.info("CSVファイルをアップロードすると、タイムラインが表示されます。")