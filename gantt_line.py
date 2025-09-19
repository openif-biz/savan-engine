import streamlit as st
import pandas as pd
import plotly.figure_factory as ff
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("Gantt Line 経営タイムライン")

# ---------------------------
# データ変換・クレンジング処理
# ---------------------------
def transform_and_clean_data(df):
    # 列名の前後スペース除去
    df = df.rename(columns=lambda x: str(x).strip())

    # 想定カラム名への正規化（Excelの全角半角差異にも対応）
    column_mapping = {
        'カード表示名': '案件名',
        '営業担当': '担当者名',
        '初期売上': '契約金額',
        '契約日(実績)': '契約',
        '契約日（実績）': '契約',  # 全角括弧対応
        '完工日(実績)': '工事',
        '完工日（実績）': '工事',
        '請求書発行日(実績)': '請求',
        '請求書発行日（実績）': '請求',
        '初期費用入金日(実績)': '入金',
        '初期費用入金日（実績）': '入金'
    }
    df.rename(columns=column_mapping, inplace=True)

    required_cols = ['案件名', '担当者名']
    if not all(col in df.columns for col in required_cols):
        st.error(f"必須列（{required_cols}）が見つかりません。")
        return pd.DataFrame()

    # 金額列クレンジング（全角→半角, 数字抽出）
    for col in ['契約金額']:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                .str.replace(r"[^\d.]", "", regex=True)
                .replace("", "0")
                .astype(float)
            )

    id_vars = ['案件名', '担当者名', '契約金額']
    value_vars = ['契約', '工事', '請求', '入金']
    value_vars = [v for v in value_vars if v in df.columns]

    if not value_vars:
        st.warning("日付データを含むタスク列（契約、工事など）が見つかりません。")
        return pd.DataFrame()

    tidy_df = pd.melt(
        df,
        id_vars=id_vars,
        value_vars=value_vars,
        var_name='タスク',
        value_name='実績終了日'
    )

    # 日付型変換
    tidy_df['実績終了日'] = pd.to_datetime(
        tidy_df['実績終了日'],
        errors='coerce',
        infer_datetime_format=True
    )
    tidy_df.dropna(subset=['実績終了日'], inplace=True)
    tidy_df['実績開始日'] = tidy_df['実績終了日']

    return tidy_df

# ---------------------------
# Gantt Chart 作成
# ---------------------------
def create_gantt_chart(df, title=""):
    df['案件担当者'] = df['案件名'] + ' - ' + df['担当者名']
    gantt_data = []
    colors = {
        '契約': 'rgb(220, 53, 69)',
        '工事': 'rgb(25, 135, 84)',
        '請求': 'rgb(13, 110, 253)',
        '入金': 'rgb(255, 193, 7)'
    }

    for _, row in df.iterrows():
        start_date = row['実績開始日']
        finish_date = row['実績終了日']
        if start_date == finish_date:
            finish_date += timedelta(hours=12)
        gantt_data.append(dict(
            Task=row['案件担当者'],
            Start=start_date,
            Finish=finish_date,
            Resource=row['タスク']
        ))

    if gantt_data:
        fig = ff.create_gantt(
            gantt_data,
            colors=colors,
            index_col='Resource',
            show_colorbar=True,
            group_tasks=True,
            title=title
        )
        fig.update_layout(margin=dict(t=100), legend_title_text='凡例')
        fig.update_yaxes(tickfont=dict(size=14))
        fig.update_xaxes(side="top", tickformat="%Y年%m月", tickfont=dict(size=16))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("指定された期間に該当する案件データがありません。")

# ---------------------------
# UI部分
# ---------------------------
st.header("1. データをアップロード")
uploaded_file = st.file_uploader(
    "案件データを含むExcelまたはCSVファイルをアップロードしてください",
    type=["csv", "xlsx"]
)

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.xlsx'):
            raw_df = pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            raw_df = pd.read_csv(uploaded_file, encoding='utf-8-sig')

        tidy_df = transform_and_clean_data(raw_df)

        if not tidy_df.empty:
            st.header("2. 表示期間の設定")

            # 契約日だけ抽出（案件フィルタの基準）
            contract_dates = tidy_df[tidy_df['タスク'] == '契約'][['案件名', '実績開始日']]
            contract_dates.rename(columns={'実績開始日': '契約日'}, inplace=True)

            min_date = contract_dates['契約日'].min().date()
            max_date = contract_dates['契約日'].max().date()

            st.subheader("経営タイムライン全体")
            col1, col2 = st.columns(2)
            start_date_all = col1.date_input("表示開始日（全体）", value=min_date)
            end_date_all = col2.date_input("表示終了日（全体）", value=max_date)

            st.subheader("経営タイムライン（月次）")
            col3, col4 = st.columns(2)
            start_date_monthly = col3.date_input("表示開始日（月次）", value=min_date)
            end_date_monthly = col4.date_input("表示終了日（月次）", value=max_date)

            if st.button("タイムラインを表示", key="show_button"):
                st.header("3. 経営タイムライン")

                # --- 全体タイムライン（契約基準） ---
                mask_contract_all = (contract_dates['契約日'].dt.date >= start_date_all) & \
                                    (contract_dates['契約日'].dt.date <= end_date_all)
                valid_projects_all = contract_dates.loc[mask_contract_all, '案件名'].unique()
                filtered_df_all = tidy_df[tidy_df['案件名'].isin(valid_projects_all)]

                with st.container():
                    st.subheader("経営タイムライン全体")
                    create_gantt_chart(filtered_df_all, title="実績タイムライン")

                # --- 月次タイムライン（契約基準） ---
                mask_contract_monthly = (contract_dates['契約日'].dt.date >= start_date_monthly) & \
                                        (contract_dates['契約日'].dt.date <= end_date_monthly)
                valid_projects_monthly = contract_dates.loc[mask_contract_monthly, '案件名'].unique()
                filtered_df_monthly = tidy_df[tidy_df['案件名'].isin(valid_projects_monthly)]

                with st.container():
                    st.subheader("経営タイムライン（月次）")
                    create_gantt_chart(filtered_df_monthly, title="月次タイムライン")

    except Exception as e:
        st.error(f"処理中にエラーが発生しました: {e}")
else:
    st.info("ファイルをアップロードすると、期間設定カレンダーが表示されます。")
