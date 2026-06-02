# agent_tool.py
import os
from data_df_store.data_store import store
from langchain_core.tools import tool
import pandas as pd
import streamlit as st
from ad_analyzers.budget_analyzer import get_budget_analysis
from ad_analyzers.placement_analyzer import get_placement_analysis
from ad_analyzers.keyword_analyzer import get_keyword_analysis
from ad_analyzers.search_analyzer import get_search_analysis
from ad_analyzers.search_term_trend import get_search_term_trend

# 懒加载实现
_rag = None
def get_rag():
    global _rag
    if _rag is None:
        from Rag.rag_service import RagSummarizeService
        _rag = RagSummarizeService()
    return _rag
@tool(description = "从向量存储中检索参考资料。回答关于广告分析模块的功能、指标含义、设计原因等问题。")
def rag_summarize(query: str) -> str:
    return get_rag().rag_summarize(query)


@tool(
    description="分析预算报表。如果不提供活动名称，返回所有异常活动的摘要；如果提供活动名称，返回该活动的详细信息。参数为广告活动名称（可选）。")
def analyze_budget_tool(activity_name: str = "") -> str:
    df = store.get("budget")
    if df is None:
        return "请先在左侧上传预算报表。"
    result = get_budget_analysis(df)
    if result.get("error"):
        return f"分析出错：{result['error']}"

    # 如果没有异常活动
    if not result["problem_activities"]:
        return "✅ 所有活动预算使用率正常，未超过90%。"

    # 如果传入了活动名称，且该活动在问题列表中
    if activity_name and activity_name in result["problem_activities"]:
        # 查找该活动的汇总信息
        summary_item = next((item for item in result["summary"] if item["广告活动名称"] == activity_name), None)
        if not summary_item:
            return f"未找到活动 '{activity_name}' 的预算数据。"
        msg = f"📊 活动「{activity_name}」预算详情：\n"
        msg += f"- 总预算: {summary_item['总预算']:.2f}\n"
        msg += f"- 总花费: {summary_item['总花费']:.2f}\n"
        msg += f"- 最高使用率: {summary_item['最高使用率']:.1%}\n"
        msg += f"- 平均使用率: {summary_item['平均使用率']:.1%}\n"
        # 可选：附上超标日期
        if activity_name in result["daily_details"]:
            daily = result["daily_details"][activity_name]
            over_days = [d for d in daily if d['使用率'] > 0.9]
            if over_days:
                dates = ', '.join([d['日期'].strftime('%Y-%m-%d') for d in over_days])
                msg += f"- 超标日期: {dates}\n"
        msg += "\n💡 详细每日明细请切换到【手动分析】标签页。"
        return msg

    # 没有传参或传参无效，输出所有异常活动的摘要（只列出名称和最高使用率）
    sorted_summary = sorted(result["summary"], key=lambda x: x["最高使用率"], reverse=True)
    top5 = sorted_summary[:5]
    total = len(result["problem_activities"])
    msg = f"⚠️ 发现 {total} 个活动预算消耗过快，其中最严重的{len(top5)}个：\n"
    for item in top5:
        msg += f"- {item['广告活动名称']}: 最高使用率 {item['最高使用率']:.0%}\n"
    if total > 5:
        msg += f"（其余 {total - 5} 个请指定活动名称查看详情）\n"
    msg += "\n💡 详细每日明细请切换到【手动分析】标签页。"
    return msg


@tool(description="分析广告位报表。如果不提供活动名称，返回所有活动的异常摘要（最差广告位）；如果提供活动名称，返回该活动的广告位详情。参数为广告活动名称（可选）。")
def analyze_placement_tool(activity_name: str = "") -> str:
    df = store.get("placement")
    if df is None:
        return "请先在左侧上传广告位报表。"
    result = get_placement_analysis(df)
    if result.get("error"):
        return f"分析出错：{result['error']}"
    if not result["summary"]:
        return "没有有效的广告位数据。"

    # 如果传入了活动名称
    if activity_name:
        # 查找该活动的汇总记录
        activity_summary = [item for item in result["summary"] if item['广告活动名称'] == activity_name]
        if not activity_summary:
            return f"未找到活动 '{activity_name}' 的广告位数据。"
        msg = f"📊 活动「{activity_name}」广告位详情：\n"
        for item in activity_summary:
            acos = item.get('整体ACOS', 0)
            msg += f"- {item['放置']}: ACOS {acos:.1%}\n"
        # 可选：附上每日明细的提示
        msg += "\n💡 详细每日明细请切换到【手动分析】标签页。"
        return msg

    # 无参：返回所有活动的异常摘要（只列出每个活动的**最差广告位**，且只展示前5个活动）
    # 按整体ACOS最高的广告位排序，但这里需要每个活动的最差广告位，可以从 `worst_placements_by_activity` 中获取
    worst_list = result.get("worst_placements_by_activity", [])
    if not worst_list:
        return "✅ 所有活动广告位表现正常。"
    # 去重活动（取每个活动的第一个最差广告位，因为可能有多个）
    unique_worst = {}
    for w in worst_list:
        act = w['广告活动名称']
        if act not in unique_worst:
            unique_worst[act] = w
    # 按ACOS降序排序，取前5个最差的活动
    sorted_worst = sorted(unique_worst.values(), key=lambda x: x.get('整体ACOS', 0), reverse=True)[:5]
    msg = "⚠️ 以下活动的广告位表现最差（ACOS最高）：\n"
    for w in sorted_worst:
        msg += f"- {w['广告活动名称']}: {w['放置']} ACOS {w['整体ACOS']:.1%}\n"
    if len(unique_worst) > 5:
        msg += f"（其余 {len(unique_worst) - 5} 个活动请指定名称查看详情）\n"
    msg += "\n💡 详细数据请切换到【手动分析】标签页。"
    return msg


@tool(description="分析投放词报表。支持参数：activity_name(活动名), adgroup_name(广告组名), keyword(关键词)。可任意组合。")
def analyze_keyword_tool(activity_name: str = "", adgroup_name: str = "", keyword: str = "") -> str:
    df = store.get("keyword")
    if df is None:
        return "请先在左侧上传投放词报表。"
    result = get_keyword_analysis(df)
    if result.get("error"):
        return f"分析出错：{result['error']}"
    if not result["summary"]:
        return "没有有效的投放词数据。"

    matches = result["summary"]
    if activity_name:
        matches = [m for m in matches if m['广告活动名称'] == activity_name]
    if adgroup_name:
        matches = [m for m in matches if m['广告组名称'] == adgroup_name]
    if keyword:
        matches = [m for m in matches if m['投放'] == keyword]

    if not matches:
        return "未找到匹配的数据。"
    if len(matches) == 1:
        m = matches[0]
        return (f"📊 投放词详情：\n活动: {m['广告活动名称']}\n广告组: {m['广告组名称']}\n关键词: {m['投放']}\n"
                f"总花费: {m['总花费']:.2f}\n总销售额: {m['总销售额']:.2f}\n订单数: {m['总订单数']}\n"
                f"平均CPC: {m['平均CPC']:.2f}\n点击率: {m['总点击率']:.1%}\n转化率: {m['总转化率']:.1%}\nACOS: {m['总ACOS']:.1%}")
    else:
        abnormal = [m for m in matches if m['总订单数'] == 0 and m['总花费'] > 0]
        if abnormal:
            top = sorted(abnormal, key=lambda x: x['总花费'], reverse=True)[:5]
            msg = f"⚠️ 发现 {len(abnormal)} 个高花费零订单的组合，最严重的{len(top)}个：\n"
            for m in top:
                msg += f"- {m['广告活动名称']}/{m['广告组名称']}/{m['投放']}: 花费 {m['总花费']:.2f}\n"
            return msg
        else:
            return f"✅ 指定范围内所有关键词都有订单，共 {len(matches)} 个组合。"


@tool(description="分析搜索词报表。支持按广告活动、广告组、搜索词查询。不传参数返回全局摘要（否定词候选和高潜力词候选的数量）。")
def analyze_search_tool(activity_name: str = "", adgroup_name: str = "", search_term: str = "") -> str:
    df = store.get("search")
    if df is None:
        return "请先在左侧上传搜索词报表。"
    result = get_search_analysis(df)
    if result.get("error"):
        return f"分析出错：{result['error']}"
    if not result["summary"]:
        return "没有有效的搜索词数据。"

    summary_list = result["summary"]

    # 按参数过滤
    matches = summary_list
    if activity_name:
        matches = [m for m in matches if m['广告活动名称'] == activity_name]
    if adgroup_name:
        matches = [m for m in matches if m['广告组名称'] == adgroup_name]
    if search_term:
        matches = [m for m in matches if m['客户搜索词'] == search_term]

    if not matches:
        return "未找到匹配的数据。"

    # 如果只有一条，返回详情
    if len(matches) == 1:
        m = matches[0]
        msg = f"📊 搜索词详情：\n"
        msg += f"- 客户搜索词: {m['客户搜索词']}\n"
        msg += f"- 广告活动: {m['广告活动名称']}\n"
        msg += f"- 广告组: {m['广告组名称']}\n"
        msg += f"- 触发投放词: {m['投放']}\n"
        msg += f"- 总花费: {m['总花费']:.2f}\n"
        msg += f"- 总点击量: {m['总点击量']}\n"
        msg += f"- 总订单数: {m['总订单数']}\n"
        msg += f"- 平均CPC: {m['平均CPC']:.2f}\n"
        msg += f"- ACOS: {m['总ACOS']:.1%}\n"
        msg += "\n💡 详细每日明细请切换到【手动分析】标签页。"
        return msg

    df_all = pd.DataFrame(matches)
    # 否定词候选：按活动分组阈值（类似手动分析逻辑）
    group_means = df_all.groupby('广告活动名称')[['总点击量', '总花费']].mean().rename(
        columns={'总点击量': 'mean_clicks', '总花费': 'mean_spend'})
    df_with_means = df_all.merge(group_means, left_on='广告活动名称', right_index=True)
    negation = df_with_means[
        (df_with_means['总订单数'] == 0) &
        (df_with_means['总点击量'] > 0.4 * df_with_means['mean_clicks']) &
        (df_with_means['总花费'] > 0.4 * df_with_means['mean_spend'])
        ]

    # 高潜力词候选
    potential = df_all[(df_all['总订单数'] > 0) & (df_all['客户搜索词'] != df_all['投放']) & (df_all['总点击量'] > 2)]
    msg = f"🔍 搜索词分析（共 {len(df_all)} 个组合）：\n"
    if not negation.empty:
        msg += f"🚫 否定词候选（高点击高花费零订单）: {len(negation)} 个\n"
    if not potential.empty:
        msg += f"🌟 高潜力拓词候选（有订单未投放）: {len(potential)} 个\n"
    if negation.empty and potential.empty:
        msg += "✅ 未发现明显异常的搜索词。"
    msg += "\n💡 详细列表请切换到【手动分析】标签页，或使用更具体的参数查询（例如指定搜索词）。"
    return msg


from ad_analyzers.search_term_trend import get_search_term_trend


@tool(
    description="分析搜索词的市场趋势（店铺级别）。参数：search_term（必填，客户搜索词），返回该词的每日排名、份额、ACOS 趋势及主要贡献广告活动。")
def analyze_search_term_tool(search_term: str) -> str:
    df = store.get("search_share")
    if df is None:
        return "请先在左侧上传搜索词份额报告。"
    result = get_search_term_trend(df)
    if not result["search_terms"]:
        return "没有有效的搜索词数据。"
    if search_term not in result["search_terms"]:
        return f"未找到搜索词 '{search_term}' 的数据。"

    data = result["data"][search_term]
    trend = data['trend']
    attribution = data['attribution']

    if not trend:
        return f"搜索词 '{search_term}' 无趋势数据。"

    # 获取最近7天的趋势（取最后7条）
    recent = trend[-7:] if len(trend) > 7 else trend
    msg = f"📊 搜索词「{search_term}」市场趋势（店铺级别）：\n"
    for day in recent:
        date = day['date'].strftime('%Y-%m-%d')
        rank = day.get('impression_rank', '-')
        share = day.get('impression_share', 0)
        acos = day.get('acos', 0)
        msg += f"- {date}: 排名 {rank}, 份额 {share:.1%}, ACOS {acos:.1%}\n"

    # 统计主要贡献的广告活动（按花费或点击量）
    if attribution:
        # 按广告活动聚合总花费
        from collections import defaultdict
        campaign_spend = defaultdict(float)
        for item in attribution:
            campaign_spend[item['campaign']] += item['spend']
        top_campaigns = sorted(campaign_spend.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_campaigns:
            msg += "\n💰 主要贡献的广告活动（按花费）：\n"
            for camp, spend in top_campaigns:
                msg += f"- {camp}: {spend:.2f}\n"

    msg += "\n💡 详细每日明细请切换到【手动分析】标签页。"
    return msg

@tool(description="无入参，无返回值，调用后触发中间件自动为广告报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"






