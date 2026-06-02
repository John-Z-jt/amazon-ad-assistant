# ad_analyzers/search_analyzer.py
import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, Any

# ---------- 通用清洗函数 ----------
def to_float(series):
    s = series.astype(str).str.strip()
    s = s.str.replace(r'[¥$€]', '', regex=True)
    s = s.str.replace(',', '', regex=False)
    s = s.str.replace(r'\s+', '', regex=True)
    s = s.replace('', pd.NA)
    return pd.to_numeric(s, errors='coerce')

def to_percent_float(series):
    s = series.astype(str).str.replace('%', '', regex=False).str.strip()
    s = s.replace('', pd.NA)
    return pd.to_numeric(s, errors='coerce') / 100

def clean_search_report(df: pd.DataFrame) -> pd.DataFrame:
    """清洗搜索词报表"""
    df_clean = df.copy()
    if '日期' in df_clean.columns:
        df_clean['日期'] = pd.to_datetime(df_clean['日期'], errors='coerce')

    df_clean['展示量'] = pd.to_numeric(df_clean['展示量'], errors='coerce')
    df_clean['点击量'] = pd.to_numeric(df_clean['点击量'], errors='coerce')
    df_clean['7天总订单数(#)'] = pd.to_numeric(df_clean['7天总订单数(#)'], errors='coerce')

    df_clean['花费_数值'] = to_float(df_clean['花费'])
    df_clean['7天总销售额_数值'] = to_float(df_clean['7天总销售额'])
    df_clean['单次点击成本 (CPC)_数值'] = to_float(df_clean['单次点击成本 (CPC)']).fillna(0)

    if '广告投入产出比 (ACOS) 总计' in df_clean.columns:
        df_clean['ACOS_数值'] = to_percent_float(df_clean['广告投入产出比 (ACOS) 总计'])
    else:
        df_clean['ACOS_数值'] = np.nan

    df_clean['点击率'] = df_clean['点击量'] / df_clean['展示量']
    df_clean['转化率'] = df_clean['7天总订单数(#)'] / df_clean['点击量']

    keep_cols = ['日期', '广告活动名称', '广告组名称', '投放', '客户搜索词', '展示量', '点击量', '点击率', '转化率',
                 '花费_数值', '7天总销售额_数值', '7天总订单数(#)', '单次点击成本 (CPC)_数值', 'ACOS_数值']
    keep_cols = [c for c in keep_cols if c in df_clean.columns]
    df_clean = df_clean[keep_cols]
    df_clean = df_clean.dropna(subset=['花费_数值', '7天总销售额_数值'], how='all')
    return df_clean

def get_search_analysis(df_clean: pd.DataFrame) -> Dict[str, Any]:
    """
    按广告活动、广告组、投放词、客户搜索词分组聚合，返回汇总和每日明细
    """
    if df_clean is None or df_clean.empty:
        return {"summary": [], "daily_details": {}}

    required = ['广告活动名称', '广告组名称', '投放', '客户搜索词', '展示量', '点击量', '花费_数值', '7天总销售额_数值', '7天总订单数(#)']
    missing = [c for c in required if c not in df_clean.columns]
    if missing:
        return {"summary": [], "daily_details": {}, "error": f"缺少列: {missing}"}

    summary_df = df_clean.groupby(['广告活动名称', '广告组名称', '投放', '客户搜索词']).agg(
        总展示量=('展示量', 'sum'),
        总点击量=('点击量', 'sum'),
        总花费=('花费_数值', 'sum'),
        总销售额=('7天总销售额_数值', 'sum'),
        总订单数=('7天总订单数(#)', 'sum')
    ).reset_index()

    summary_df['平均CPC'] = summary_df['总花费'] / summary_df['总点击量']
    summary_df['总点击率'] = summary_df['总点击量'] / summary_df['总展示量']
    summary_df['总转化率'] = summary_df['总订单数'] / summary_df['总点击量']
    summary_df['总ACOS'] = summary_df['总花费'] / summary_df['总销售额']
    summary_df.replace([np.inf, -np.inf], np.nan, inplace=True)

    daily_details = {}
    if '日期' in df_clean.columns:
        df_clean = df_clean.dropna(subset=['日期'])
        for (act, adg, kw, term), group in df_clean.groupby(['广告活动名称', '广告组名称', '投放', '客户搜索词']):
            daily = group[['日期', '花费_数值', '7天总销售额_数值', '点击量', '展示量', '7天总订单数(#)', '单次点击成本 (CPC)_数值']].copy()
            daily = daily.sort_values('日期')
            daily.rename(columns={
                '花费_数值': '花费',
                '7天总销售额_数值': '销售额',
                '点击量': '点击量',
                '展示量': '展示量',
                '7天总订单数(#)': '订单数',
                '单次点击成本 (CPC)_数值': 'CPC'
            }, inplace=True)
            daily['点击率'] = daily['点击量'] / daily['展示量']
            daily['转化率'] = daily['订单数'] / daily['点击量']
            daily['ACOS'] = daily['花费'] / daily['销售额']
            daily_details[(act, adg, kw, term)] = daily.to_dict(orient='records')

    return {
        "summary": summary_df.to_dict(orient='records'),
        "daily_details": daily_details
    }

def analyze_search(df_clean: pd.DataFrame) -> None:
        """搜索词分析：两个Tab，每个Tab内有筛选器，每行带明细按钮"""
        result = get_search_analysis(df_clean)
        if result.get("error"):
            st.warning(result["error"])
            return
        if not result["summary"]:
            st.info("没有有效的搜索词数据")
            return

        # 初始化 session_state 变量（明细状态）
        if 'show_neg_detail' not in st.session_state:
            st.session_state.show_neg_detail = False
        if 'selected_neg_comb' not in st.session_state:
            st.session_state.selected_neg_comb = None
        if 'show_pot_detail' not in st.session_state:
            st.session_state.show_pot_detail = False
        if 'selected_pot_comb' not in st.session_state:
            st.session_state.selected_pot_comb = None

        summary_list = result["summary"]
        daily_details = result["daily_details"]
        df_all_raw = pd.DataFrame(summary_list)

        # ---------- 1. 否定词候选（按广告活动分组阈值）----------
        df_all = df_all_raw.copy()
        # 计算每个广告活动的平均点击量和平均花费（transform 保持行数）
        df_all['mean_clicks'] = df_all.groupby('广告活动名称')['总点击量'].transform('mean')
        df_all['mean_spend'] = df_all.groupby('广告活动名称')['总花费'].transform('mean')

        negation_df = df_all[
            (df_all['总订单数'] == 0) &
            (df_all['总点击量'] > 0.4 * df_all['mean_clicks']) &
            (df_all['总花费'] > 0.4 * df_all['mean_spend'])
            ].copy()
        negation_df = negation_df.drop(columns=['mean_clicks', 'mean_spend'])
        negation_df = negation_df.sort_values('总花费', ascending=False)

        # 2. 高潜力拓词候选：有订单、客户搜索词≠投放词、且点击量>2
        potential_df = df_all_raw[
            (df_all_raw['总订单数'] > 0) &
            (df_all_raw['客户搜索词'] != df_all_raw['投放']) &
            (df_all_raw['总点击量'] > 2)
            ].copy()
        potential_df = potential_df.sort_values('总订单数', ascending=False)

        tab_neg, tab_pot = st.tabs(["🚫 否定词候选", "🌟 高潜力拓词候选"])

        # ---------- 辅助函数：渲染带筛选器的表格 ----------
        def render_search_table(df: pd.DataFrame, title: str, detail_type: str):
            if df.empty:
                st.success(f"✅ 没有{title}")
                return

            st.subheader(title)

            # 模式选择：明确区分“活动级分析”和“跨活动分析”
            mode = st.radio(
                "选择分析模式",
                ["🎯 定位问题（限定在某个活动/广告组内）", "⚡ 诊断内部竞争（跨所有活动查看同一搜索词）"],
                horizontal=True,
                key=f"{detail_type}_mode"
            )

            # ----- 模式1：🎯 定位问题（限定在某个活动/广告组内）（联动）-----
            if mode == "🎯 定位问题（限定在某个活动/广告组内）":
                st.caption("💡 请选择广告活动和广告组以缩小范围。")
                all_activities = sorted(df['广告活动名称'].unique())
                selected_activity = st.selectbox(
                    "选择广告活动",
                    ["全部"] + all_activities,
                    key=f"{detail_type}_activity"
                )
                if selected_activity != "全部":
                    adgroups = sorted(df[df['广告活动名称'] == selected_activity]['广告组名称'].unique())
                    selected_adgroups = st.multiselect(
                        "选择广告组（可多选）",
                        adgroups,
                        default=[],
                        key=f"{detail_type}_adgroup"
                    )
                else:
                    selected_adgroups = []
                    st.info("请先选择广告活动以启用广告组筛选")

                # 获取该模式下可能出现的搜索词（用于筛选器选项）
                range_df = df.copy()
                if selected_activity != "全部":
                    range_df = range_df[range_df['广告活动名称'] == selected_activity]
                if selected_adgroups:
                    range_df = range_df[range_df['广告组名称'].isin(selected_adgroups)]
                all_terms = sorted(range_df['客户搜索词'].unique())
            else:
                # 模式2：跨活动分析（忽略活动/广告组）
                st.caption("💡 跨活动分析将忽略活动/广告组，只按搜索词查看。")
                # 此时不显示活动/广告组筛选器，直接设置默认值
                selected_activity = "全部"
                selected_adgroups = []
                # 搜索词列表为所有候选词
                all_terms = sorted(df['客户搜索词'].unique())

            # ----- 客户搜索词筛选（两种模式共用）-----
            st.markdown("### 🔍 按客户搜索词筛选")
            selected_term = st.selectbox(
                "选择客户搜索词",
                ["全部"] + all_terms,
                key=f"{detail_type}_term"
            )

            # ----- 应用筛选 -----
            filtered_df = df.copy()
            if mode == "🎯 定位问题（限定在某个活动/广告组内）":
                if selected_activity != "全部":
                    filtered_df = filtered_df[filtered_df['广告活动名称'] == selected_activity]
                if selected_adgroups:
                    filtered_df = filtered_df[filtered_df['广告组名称'].isin(selected_adgroups)]
            # 模式2 不额外过滤活动/广告组
            if selected_term != "全部":
                filtered_df = filtered_df[filtered_df['客户搜索词'] == selected_term]

            if filtered_df.empty:
                st.info("没有符合筛选条件的数据")
                return

            # ----- 分页显示（默认10条）-----
            DISPLAY_LIMIT = 10
            limit_key = f"{detail_type}_display_limit"
            if limit_key not in st.session_state:
                st.session_state[limit_key] = DISPLAY_LIMIT

            show_df = filtered_df.head(st.session_state[limit_key]).reset_index(drop=True)

            # 显示每条记录 + 明细按钮
            for idx, row in show_df.iterrows():
                cols = st.columns([6, 1])
                with cols[0]:
                    st.markdown(f"**{row['客户搜索词']}**  |  活动: {row['广告活动名称']}  |  广告组: {row['广告组名称']}  |  触发词: {row['投放']}")
                    st.markdown(f"花费: {row['总花费']:.2f}  |  点击量: {row['总点击量']}  |  订单: {row['总订单数']}  |  CPC: {row['平均CPC']:.2f}")
                with cols[1]:
                    btn_key = f"{detail_type}_detail_{idx}_{row['广告活动名称']}_{row['广告组名称']}_{row['投放']}_{row['客户搜索词']}"[
                        :50]
                    if st.button("📊 明细", key=btn_key):
                        st.session_state[f"selected_{detail_type}_comb"] = (
                            row['广告活动名称'], row['广告组名称'], row['投放'], row['客户搜索词']
                        )
                        st.session_state[f"show_{detail_type}_detail"] = True
                # 添加分隔线（除了最后一条）
                if idx < len(show_df) - 1:
                    st.markdown("---")

            # 控制显示数量的按钮区域
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.session_state[limit_key] < len(filtered_df):
                    if st.button(f"加载更多（当前显示{st.session_state[limit_key]}条，共{len(filtered_df)}条）",
                                 key=f"load_more_{detail_type}"):
                        st.session_state[limit_key] += DISPLAY_LIMIT
                        st.rerun()
            with col_btn2:
                if st.session_state[limit_key] > DISPLAY_LIMIT:
                    if st.button("显示更少（重置为10条）", key=f"reset_limit_{detail_type}"):
                        st.session_state[limit_key] = DISPLAY_LIMIT
                        st.rerun()

            # ----- 显示每日明细（如果已选中）-----
            if st.session_state.get(f"show_{detail_type}_detail", False) and st.session_state.get(
                    f"selected_{detail_type}_comb"):
                comb = st.session_state[f"selected_{detail_type}_comb"]
                key = (comb[0], comb[1], comb[2], comb[3])
                if key in daily_details:
                    st.markdown("---")
                    st.subheader(f"每日明细：{comb[3]} (触发词: {comb[2]})")
                    daily_df = pd.DataFrame(daily_details[key])
                    display_daily = daily_df.copy()
                    for col in ['点击率', '转化率', 'ACOS']:
                        if col in display_daily.columns:
                            display_daily[col] = display_daily[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else '-')
                    if 'CPC' in display_daily.columns:
                        display_daily['CPC'] = display_daily['CPC'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '-')
                    st.dataframe(display_daily, use_container_width=True)
                    if st.button("关闭明细", key=f"close_{detail_type}_detail"):
                        st.session_state[f"show_{detail_type}_detail"] = False
                        st.session_state[f"selected_{detail_type}_comb"] = None
                        st.rerun()
                else:
                    st.info("无每日明细数据")
        with tab_neg:
            render_search_table(negation_df, "否定词候选（高点击高花费零订单）", "neg")
        with tab_pot:
            render_search_table(potential_df, "高潜力拓词候选（有订单未投放）", "pot")






