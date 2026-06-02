# ad_analyzers/keyword_analyzer.py
import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, Any

# ---------- 清洗函数 ----------
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

def clean_keyword_report(df: pd.DataFrame) -> pd.DataFrame:
    """清洗投放词报表"""
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

    keep_cols = ['日期', '广告活动名称', '广告组名称', '投放', '展示量', '点击量', '点击率', '转化率',
                 '花费_数值', '7天总销售额_数值', '7天总订单数(#)', '单次点击成本 (CPC)_数值', 'ACOS_数值']
    keep_cols = [c for c in keep_cols if c in df_clean.columns]
    df_clean = df_clean[keep_cols]
    df_clean = df_clean.dropna(subset=['花费_数值', '7天总销售额_数值'], how='all')
    return df_clean

# ---------- 核心分析函数 ----------
@st.cache_data(ttl=3600)
def get_keyword_analysis(df_clean: pd.DataFrame) -> Dict[str, Any]:
    """按广告活动、广告组、关键词分组聚合，返回汇总和每日明细"""
    if df_clean is None or df_clean.empty:
        return {"summary": [], "daily_details": {}}

    required = ['广告活动名称', '广告组名称', '投放', '展示量', '点击量', '花费_数值', '7天总销售额_数值', '7天总订单数(#)']
    missing = [c for c in required if c not in df_clean.columns]
    if missing:
        return {"summary": [], "daily_details": {}, "error": f"缺少列: {missing}"}

    # 汇总表（包含广告组名称）
    summary_df = df_clean.groupby(['广告活动名称', '广告组名称', '投放']).agg(
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

    # 每日明细
    daily_details = {}
    if '日期' in df_clean.columns:
        df_clean = df_clean.dropna(subset=['日期'])
        for (act, adg, kw), group in df_clean.groupby(['广告活动名称', '广告组名称', '投放']):
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
            daily_details[(act, adg, kw)] = daily.to_dict(orient='records')

    return {
        "summary": summary_df.to_dict(orient='records'),
        "daily_details": daily_details
    }

# ---------- UI 展示 ----------
def analyze_keyword(df_clean: pd.DataFrame) -> None:
    """三级联动：活动→广告组→关键词"""
    result = get_keyword_analysis(df_clean)
    if result.get("error"):
        st.warning(result["error"])
        return
    if not result["summary"]:
        st.info("没有有效的投放词数据")
        return

    st.subheader("🔑 投放词分析 (活动/广告组/关键词)")
    summary_df = pd.DataFrame(result["summary"])

    # 三级联动控件
    all_activities = sorted(summary_df['广告活动名称'].unique())
    selected_activities = st.multiselect("选择广告活动查看每日明细", all_activities, default=[], key="kw_act")

    # 根据选中活动，更新广告组列表
    if selected_activities:
        filtered_by_act = summary_df[summary_df['广告活动名称'].isin(selected_activities)]
        all_adgroups = sorted(filtered_by_act['广告组名称'].unique())
    else:
        all_adgroups = []
    selected_adgroups = st.multiselect("选择广告组查看每日明细", all_adgroups, default=[], key="kw_adg")

    # 根据选中的活动和广告组，更新关键词列表
    if selected_adgroups:
        filtered_by_adg = summary_df[
            summary_df['广告活动名称'].isin(selected_activities) &
            summary_df['广告组名称'].isin(selected_adgroups)
        ]
        all_keywords = sorted(filtered_by_adg['投放'].unique())
    else:
        all_keywords = []
    selected_keywords = st.multiselect("选择关键词查看每日明细", all_keywords, default=[], key="kw_kw")

    # 构建筛选掩码
    mask = pd.Series(True, index=summary_df.index)
    if selected_activities:
        mask &= summary_df['广告活动名称'].isin(selected_activities)
    if selected_adgroups:
        mask &= summary_df['广告组名称'].isin(selected_adgroups)
    if selected_keywords:
        mask &= summary_df['投放'].isin(selected_keywords)

    filtered_df = summary_df[mask]
    if filtered_df.empty:
        st.info("没有符合筛选条件的数据")
        return

    # 格式化显示
    display_df = filtered_df.copy()
    for col in ['总点击率', '总转化率', '总ACOS']:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else '-')
    if '平均CPC' in display_df.columns:
        display_df['平均CPC'] = display_df['平均CPC'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '-')
    st.dataframe(display_df, use_container_width=True)

    # 每日明细折叠面板：仅对筛选出的（活动,广告组,关键词）组合创建 expander
    if result["daily_details"] and selected_activities and selected_adgroups and selected_keywords:
        st.markdown("---")
        with st.expander("📅 各关键词每日明细（点击展开）"):
            # 遍历筛选出的组合（注意：三个筛选器是逐步联动的，最终 selected_keywords 已经反映用户最终选择）
            # 但为了完整性，我们遍历所有可能组合，只显示有数据的
            for act in selected_activities:
                for adg in selected_adgroups:
                    for kw in selected_keywords:
                        if (act, adg, kw) not in result["daily_details"]:
                            continue
                        daily_records = result["daily_details"][(act, adg, kw)]
                        daily_df = pd.DataFrame(daily_records)
                        total_spend = daily_df['花费'].sum()
                        total_sales = daily_df['销售额'].sum()
                        total_orders = daily_df['订单数'].sum()
                        avg_acos = total_spend / total_sales if total_sales > 0 else 0
                        with st.expander(
                                f"📁 {act} / {adg} / {kw} | 花费: {total_spend:.2f} | 销售额: {total_sales:.2f} | 订单: {int(total_orders)} | ACOS: {avg_acos:.1%}"):
                            display_daily = daily_df.copy()
                            for col in ['点击率', '转化率', 'ACOS']:
                                if col in display_daily.columns:
                                    display_daily[col] = display_daily[col].apply(
                                        lambda x: f"{x:.1%}" if pd.notna(x) else '-')
                            if 'CPC' in display_daily.columns:
                                display_daily['CPC'] = display_daily['CPC'].apply(
                                    lambda x: f"{x:.2f}" if pd.notna(x) else '-')
                            st.dataframe(display_daily, use_container_width=True)
            st.markdown("**建议**：关注高花费低转化的关键词，适当降低出价或暂停。")

def analyze_keyword_cross_activities(df_clean: pd.DataFrame) -> None:
    st.subheader("🔗 关键词跨活动对比")
    """关键词跨广告活动+广告组对比"""
    result = get_keyword_analysis(df_clean)
    if result.get("error"):
        st.warning(result["error"])
        return
    if not result["summary"]:
        st.info("没有有效的投放词数据")
        return

    summary_df = pd.DataFrame(result["summary"])
    all_keywords = sorted(summary_df['投放'].unique())
    selected_keyword = st.selectbox("选择关键词", all_keywords, key="cross_kw")

    if selected_keyword:
        data = summary_df[summary_df['投放'] == selected_keyword]
        if data.empty:
            st.info(f"未找到关键词「{selected_keyword}」的数据")
            return

        st.subheader(f"关键词「{selected_keyword}」跨广告活动/广告组表现")
        display = data.copy()
        for col in ['总点击率', '总转化率', '总ACOS']:
            if col in display.columns:
                display[col] = display[col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else '-')
        if '平均CPC' in display.columns:
            display['平均CPC'] = display['平均CPC'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '-')
        st.dataframe(display, use_container_width=True)

        abnormal = data[(data['总订单数'] == 0) & (data['总花费'] > 0)]
        if not abnormal.empty:
            st.warning("⚠️ 以下组合花费>0无订单，建议暂停或调整")
            st.dataframe(abnormal[['广告活动名称', '广告组名称', '总花费', '平均CPC']], use_container_width=True)

        if len(data) > 1:
            st.info(f"💡 该关键词出现在 {len(data)} 个组合中，可能存在内部竞争，建议集中预算到转化最佳的组合。")
