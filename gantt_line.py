import streamlit as st
import pandas as pd
import plotly.express as px

# ページの基本設定
st.set_page_config(layout="wide")

# タイトル
st.title("gantt Line MVP 開発プロジェクト")

# --- UIセクション ---
st.header("1. データをアップロード")
uploaded_file = st.file_uploader("案件データを含むCSVファイルをアップロードしてください", type="csv")

st.header("2. ガントチャート")

# --- データ処理と描画セクション ---
if uploaded_file is not None:
    try:
        # CSVファイルをPandasのDataFrameとして読み込む
        df = pd.read_csv(uploaded_file)
        
        st.info("CSVファイルの読み込みに成功しました。ガントチャートを作成します。")

        # --- ここからがガントチャート作成のコアロジック ---
        
        # 1. 日付データを正しく変換
        #    '実績開始日'と'実績終了日'をPlotlyが認識できる日付形式に変換します。
        #    エラーが発生した場合は、その日付を無効(NaT)とします。
        df['実績開始日'] = pd.to_datetime(df['実績開始日'], errors='coerce')
        df['実績終了日'] = pd.to_datetime(df['実績終了日'], errors='coerce')

        # 2. 実績データが存在する行のみを抽出
        #    まだ作業が始まっていないタスクはチャートに表示しないようにします。
        chart_df = df.dropna(subset=['実績開始日', '実績終了日'])

        # 3. Plotly Expressでガントチャートを作成
        fig = px.timeline(chart_df, 
                          x_start="実績開始日", 
                          x_end="実績終了日", 
                          y="案件名",
                          color="担当者名",
                          title="案件別ガントチャート",
                          hover_name="タスク", # カーソルを合わせた時にタスク名を表示
                          text="タスク" # バーの中にタスク名を表示
                         )

        # 4. チャートの見た目を調整
        fig.update_yaxes(autorange="reversed") # 上から表示
        fig.update_layout(
            title_font_size=24,
            xaxis_title="日付",
            yaxis_title="案件名"
        )
        
        # 5. Streamlitにチャートを表示
        st.plotly_chart(fig, use_container_width=True)
        
        # --- コアロジックここまで ---

    except Exception as e:
        st.error(f"チャートの描画中にエラーが発生しました: {e}")
else:
    st.info("CSVファイルをアップロードすると、ここにガントチャートが表示されます。")