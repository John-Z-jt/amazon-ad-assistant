import pandas as pd
import numpy as np
import streamlit as st

# 核心函数逻辑，用于Agent和UI界面
@st.cache_data(ttl=3600)
def get_budget_analysis(df: pd.DataFrame) -> dict:
    """
    纯数据分析函数，返回预算分析结果字典，不包含任何 UI 渲染。
    返回格式：
    {
        "problem_activities": [...],  # 问题活动名称列表
        "summary": [{"广告活动名称": ..., "总预算": ..., "总花费": ..., "最高使用率": ..., "平均使用率": ...}, ...],
        "daily_details": {  # 可选，如果不需要可以省略或置空
            "活动名称": [{"日期": ..., "预算": ..., "花费": ..., "使用率": ...}, ...]
        }
    }
    """
    if df is None or df.empty:
        return {"problem_activities": [], "summary": [], "daily_details": {}}

    col_budget = '预算'
    col_spent = '花费'
    col_date = '日期'
    col_activity = '广告活动名称'

    # 检查必要列
    needed = [col_budget, col_spent, col_date, col_activity]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return {"problem_activities": [], "summary": [], "daily_details": {}, "error": f"缺少列: {missing}"}

    # 清洗函数
    def clean_series(series):
        s = series.astype(str).str.strip()
        s = s.str.replace(r'[¥$€]', '', regex=True)
        s = s.str.replace(',', '', regex=False)
        s = s.str.replace(r'\s+', '', regex=True)
        s = s.replace('', pd.NA)
        return pd.to_numeric(s, errors='coerce')

    df_clean = df.copy()
    df_clean['预算'] = clean_series(df_clean[col_budget])
    df_clean['花费'] = clean_series(df_clean[col_spent])
    df_clean['日期'] = pd.to_datetime(df_clean[col_date], errors='coerce')
    df_clean = df_clean.dropna(subset=['日期', '预算', '花费'])

    if df_clean.empty:
        return {"problem_activities": [], "summary": [], "daily_details": {}}

    df_clean['使用率'] = df_clean['花费'] / df_clean['预算']

    # 找出问题活动（至少有一天使用率 > 0.9）
    problem_mask = df_clean.groupby(col_activity)['使用率'].apply(lambda x: (x > 0.9).any())
    problem_activities = problem_mask[problem_mask].index.tolist()

    if not problem_activities:
        return {"problem_activities": [], "summary": [], "daily_details": {}}

    # 汇总问题活动的统计数据
    problem_df = df_clean[df_clean[col_activity].isin(problem_activities)]
    summary_df = problem_df.groupby(col_activity).agg(
        总预算=('预算', 'sum'),
        总花费=('花费', 'sum'),
        最高使用率=('使用率', 'max'),
        平均使用率=('使用率', 'mean')
    ).reset_index()
    summary_df['最高使用率'] = summary_df['最高使用率'].round(4)
    summary_df['平均使用率'] = summary_df['平均使用率'].round(4)
    summary_records = summary_df.to_dict(orient='records')

    # 每日明细（可选，如果 Agent 不需要可以省略，但留着便于以后扩展）
    daily_details = {}
    for act in problem_activities:
        daily = df_clean[df_clean[col_activity] == act][[col_date, '预算', '花费', '使用率']].copy()
        daily = daily.sort_values(col_date)
        daily_details[act] = daily.to_dict(orient='records')

    return {
        "problem_activities": problem_activities,
        "summary": summary_records,
        "daily_details": daily_details
    }

def analyze_budget(df: pd.DataFrame) -> None:
    result = get_budget_analysis(df)
    if result.get("error"):
        st.warning(result["error"])
        return
    if not result["problem_activities"]:
        st.success("✅ 所有广告活动预算使用率正常，未发现超过90%的日期。")
        return

    st.warning(f"⚠️ 以下 {len(result['problem_activities'])} 个广告活动存在某日预算消耗过快（>90%）：")

    # 获取所有问题活动的名称列表
    all_activities = sorted(set(item['广告活动名称'] for item in result["summary"]))
    selected_activities = st.multiselect("选择广告活动查看每日明细", all_activities, default=[], key="budget_activity_filter")

    # 过滤汇总表和每日明细
    filtered_summary = [item for item in result["summary"] if item['广告活动名称'] in selected_activities]
    if not filtered_summary:
        st.info("没有符合筛选条件的数据")
        return

    # 展示汇总表格
    summary_df = pd.DataFrame(filtered_summary)
    # 格式化百分比显示
    if '最高使用率' in summary_df.columns:
        summary_df['最高使用率'] = summary_df['最高使用率'].apply(lambda x: f"{x:.1%}")
    if '平均使用率' in summary_df.columns:
        summary_df['平均使用率'] = summary_df['平均使用率'].apply(lambda x: f"{x:.1%}")
    st.dataframe(summary_df, use_container_width=True)

    # 每日明细折叠面板：仅对筛选出的活动创建 expander
    if result["daily_details"] and selected_activities:
        st.markdown("---")
        with st.expander("📅 问题活动每日预算明细（点击展开）"):
            for act in selected_activities:
                if act not in result["daily_details"]:
                    continue
                daily_records = result["daily_details"][act]
                daily_df = pd.DataFrame(daily_records)
                # 确保数据类型
                daily_df['预算'] = pd.to_numeric(daily_df['预算'])
                daily_df['花费'] = pd.to_numeric(daily_df['花费'])
                daily_df['使用率'] = pd.to_numeric(daily_df['使用率'])

                total_budget = daily_df['预算'].sum()
                total_spent = daily_df['花费'].sum()
                avg_usage = total_spent / total_budget if total_budget > 0 else 0

                with st.expander(f"📁 {act} | 总预算: {total_budget:.2f} | 总花费: {total_spent:.2f} | 平均使用率: {avg_usage:.1%}"):
                    # 高亮显示使用率 > 0.9 的行，并格式化数字
                    styled = daily_df.style.apply(
                        lambda row: ['background: #ffcccc' if row['使用率'] > 0.9 else '' for _ in row], axis=1
                    ).format({
                        '预算': '{:.2f}',
                        '花费': '{:.2f}',
                        '使用率': '{:.1%}'
                    })
                    st.dataframe(styled, use_container_width=True)
            st.markdown("**建议**：检查这些活动的每日投放情况，适当提高预算或降低出价，确保全天覆盖。")


