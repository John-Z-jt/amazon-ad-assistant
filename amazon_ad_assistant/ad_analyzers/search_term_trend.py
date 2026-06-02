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


def clean_search_share_report(df: pd.DataFrame) -> pd.DataFrame:
    """清洗搜索词份额报告，通过关键词自动匹配列名，不再依赖精确空格"""
    df_clean = df.copy()

    # 定义标准列名及其可能的中文关键词（支持模糊匹配）
    col_rules = [
        ('date', ['日期', 'date']),
        ('search_term', ['客户搜索词', '搜索词']),
        ('impression_rank', ['搜索词展示量排名', '展示量排名', '排名']),
        ('impression_share', ['搜索词展示量份额', '展示量份额', '份额']),
        ('campaign', ['广告活动名称', '活动名称']),
        ('ad_group', ['广告组名称', '组名称']),
        ('keyword', ['投放', '关键词']),
        ('match_type', ['匹配类型', '匹配']),
        ('clicks', ['点击量', '点击']),
        ('spend', ['花费', '消耗']),
        ('orders', ['总订单量', '订单量', '订单数']),
        ('sales', ['总销售额', '销售额'])
    ]

    rename_map = {}
    for std, keywords in col_rules:
        for col in df_clean.columns:
            if any(kw in col for kw in keywords):
                rename_map[col] = std
                break

    if rename_map:
        df_clean.rename(columns=rename_map, inplace=True)

    # 必要列检查（使用标准名）
    required = ['date', 'search_term', 'campaign', 'ad_group', 'clicks', 'spend', 'orders', 'sales']
    missing = [r for r in required if r not in df_clean.columns]
    if missing:
        st.error(f"搜索词份额报告缺少必要列: {missing}。实际列名: {list(df_clean.columns)}")
        return pd.DataFrame()

    # 日期转换
    df_clean['date'] = pd.to_datetime(df_clean['date'], errors='coerce')
    # 数值转换
    df_clean['spend'] = to_float(df_clean['spend'])
    df_clean['sales'] = to_float(df_clean['sales'])
    df_clean['clicks'] = pd.to_numeric(df_clean['clicks'], errors='coerce')
    df_clean['orders'] = pd.to_numeric(df_clean['orders'], errors='coerce')
    if 'impression_rank' in df_clean.columns:
        df_clean['impression_rank'] = pd.to_numeric(df_clean['impression_rank'], errors='coerce')
    if 'impression_share' in df_clean.columns:
        df_clean['impression_share'] = to_percent_float(df_clean['impression_share'])

    df_clean = df_clean.dropna(subset=['date', 'search_term'])
    return df_clean


def get_search_term_trend(df_clean: pd.DataFrame) -> Dict[str, Any]:
    if df_clean.empty:
        return {"search_terms": [], "data": {}}

    # 每日整体趋势
    daily_trend = df_clean.groupby(['search_term', 'date']).agg(
        total_clicks=('clicks', 'sum'),
        total_spend=('spend', 'sum'),
        total_orders=('orders', 'sum'),
        total_sales=('sales', 'sum'),
        impression_rank=('impression_rank', 'first') if 'impression_rank' in df_clean.columns else None,
        impression_share=('impression_share', 'first') if 'impression_share' in df_clean.columns else None
    ).reset_index()
    daily_trend['acos'] = daily_trend['total_spend'] / daily_trend['total_sales']
    daily_trend['acos'] = daily_trend['acos'].replace([np.inf, -np.inf], np.nan)

    # 每日归因明细（按投放词/匹配类型等）
    attribution = df_clean.groupby(['search_term', 'date', 'campaign', 'ad_group', 'keyword', 'match_type']).agg(
        clicks=('clicks', 'sum'),
        spend=('spend', 'sum'),
        orders=('orders', 'sum'),
        sales=('sales', 'sum')
    ).reset_index()

    data = {}
    for term in daily_trend['search_term'].unique():
        term_trend = daily_trend[daily_trend['search_term'] == term].sort_values('date').to_dict(orient='records')
        term_attribution = attribution[attribution['search_term'] == term].sort_values('date').to_dict(orient='records')
        data[term] = {
            'trend': term_trend,
            'attribution': term_attribution
        }
    return {
        "search_terms": sorted(daily_trend['search_term'].unique()),
        "data": data
    }


def analyze_search_term_trend(df_clean: pd.DataFrame) -> None:
    if df_clean.empty:
        st.info("没有有效的搜索词份额数据")
        return

    result = get_search_term_trend(df_clean)
    if not result["search_terms"]:
        st.info("未找到搜索词")
        return

    st.subheader("📈 搜索词趋势分析（每日排名与份额变化）")
    selected_term = st.selectbox("选择要分析的客户搜索词", result["search_terms"], key="trend_term")
    if not selected_term:
        return

    data = result["data"][selected_term]
    trend = data['trend']
    attribution = data['attribution']

    # ---- 处理趋势表格 ----
    if trend:
        trend_df = pd.DataFrame(trend)
        # 添加象限分类
        is_threshold = 0.30  # 展示量份额 ≥30% 视为高
        rank_threshold = 3  # 排名 ≤3 视为高排名

        def classify(row):
            share = row.get('impression_share', 0)
            rank = row.get('impression_rank', 999)
            if share >= is_threshold and rank <= rank_threshold:
                return '高份额高排名 (核心贡献)'
            elif share >= is_threshold and rank > rank_threshold:
                return '高份额低排名 (竞争激烈)'
            elif share < is_threshold and rank <= rank_threshold:
                return '低份额高排名 (曝光不足)'
            else:
                return '低份额低排名 (待优化)'

        trend_df['广告表现象限'] = trend_df.apply(classify, axis=1)

        # 格式化日期
        trend_df['date'] = trend_df['date'].dt.strftime('%Y-%m-%d')
        # 格式化份额和ACOS为百分比
        if 'impression_share' in trend_df.columns:
            trend_df['impression_share'] = trend_df['impression_share'].apply(
                lambda x: f"{x:.1%}" if pd.notna(x) else '-')
        if 'acos' in trend_df.columns:
            trend_df['acos'] = trend_df['acos'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else '-')
        # 格式化金额
        if 'total_spend' in trend_df.columns:
            trend_df['total_spend'] = trend_df['total_spend'].apply(lambda x: f"{x:.2f}")
        if 'total_sales' in trend_df.columns:
            trend_df['total_sales'] = trend_df['total_sales'].apply(lambda x: f"{x:.2f}")
        # 重命名列名为中文
        trend_df.rename(columns={
            'date': '日期',
            'total_clicks': '总点击量',
            'total_spend': '总花费',
            'total_orders': '总订单数',
            'total_sales': '总销售额',
            'impression_rank': '展示量排名',
            'impression_share': '展示量份额',
            'acos': 'ACOS',
            'search_term': '客户搜索词'
        }, inplace=True)
        # 调整列顺序
        cols_order = ['日期', '总点击量', '总花费', '总订单数', '总销售额', '展示量排名', '展示量份额', 'ACOS',
                      '广告表现象限']
        available_cols = [c for c in cols_order if c in trend_df.columns]
        st.markdown("### 每日整体趋势")
        # 高亮“高份额高排名”行
        styled = trend_df[available_cols].style.apply(
            lambda row: ['background-color: #d4efdf' if row['广告表现象限'] == '高份额高排名 (核心贡献)' else '' for _
                         in row],
            axis=1
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("无趋势数据")

    # ---- 处理归因明细表格 ----
    st.markdown("### 每日归因明细（哪些投放词触发了该搜索词）")
    if attribution:
        attr_df = pd.DataFrame(attribution)
        # 格式化日期
        if 'date' in attr_df.columns:
            attr_df['date'] = pd.to_datetime(attr_df['date']).dt.strftime('%Y-%m-%d')
        # 格式化金额
        if 'spend' in attr_df.columns:
            attr_df['spend'] = attr_df['spend'].apply(lambda x: f"{x:.2f}")
        if 'sales' in attr_df.columns:
            attr_df['sales'] = attr_df['sales'].apply(lambda x: f"{x:.2f}")
        # 重命名
        attr_df.rename(columns={
            'date': '日期',
            'campaign': '广告活动名称',
            'ad_group': '广告组名称',
            'keyword': '投放词',
            'match_type': '匹配类型',
            'clicks': '点击量',
            'spend': '花费',
            'orders': '订单数',
            'sales': '销售额'
        }, inplace=True)
        # 选择并排序列
        cols_show = ['日期', '广告活动名称', '广告组名称', '投放词', '匹配类型', '点击量', '花费', '订单数', '销售额']
        available_attr = [c for c in cols_show if c in attr_df.columns]
        st.dataframe(attr_df[available_attr], use_container_width=True)
    else:
        st.info("无归因明细数据")