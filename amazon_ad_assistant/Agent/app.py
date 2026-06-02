# 临时将当前文件所在目录加入 sys.path，以便能导入 utils（因为此时还没添加根目录）
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from data_df_store.data_store import store   # 直接导入 store 对象
#导入动态路径函数
from utils.path_tool import get_project_root
from react_agent import ReactAgent
from user_history_store import FileHistoryStore
import time

# 将真正的项目根目录加入 sys.path（其实 _parent_dir 就是根目录，但调用函数更统一）
project_root = get_project_root()
if project_root not in sys.path:
    sys.path.insert(0, project_root)
import streamlit as st
import pandas as pd
import io
from ad_analyzers.budget_analyzer import analyze_budget
from ad_analyzers.placement_analyzer import analyze_placement, clean_placement_data
from ad_analyzers.keyword_analyzer import clean_keyword_report, analyze_keyword,analyze_keyword_cross_activities
from ad_analyzers.search_analyzer import clean_search_report, analyze_search
from ad_analyzers.search_term_trend import clean_search_share_report, analyze_search_term_trend


st.set_page_config(layout="wide")
st.title("亚马逊广告诊断助手")

# 初始化session_state
if "user_history_store" not in st.session_state:
    st.session_state["user_history_store"] = FileHistoryStore()
if "agent" not in st.session_state:
    st.session_state.agent = ReactAgent()  # 实例化你的Agent
if "messages" not in st.session_state:
    st.session_state.messages = []
if "df_budget" not in st.session_state:
    st.session_state.df_budget = None
if "df_placement" not in st.session_state:
    st.session_state.df_placement = None
if "df_keyword" not in st.session_state:
    st.session_state.df_keyword = None
if "df_search" not in st.session_state:
    st.session_state.df_search = None
if "df_search_share" not in st.session_state:
    st.session_state.df_search_share = None


st.info("💡 提示：刷新页面后需要重新上传文件。请先上传所有需要的报表。")

with st.sidebar:
    st.header("上传广告报表")
    budget_file = st.file_uploader("预算报表 (CSV)", type="csv")
    placement_file = st.file_uploader("广告活动广告位 (CSV)", type="csv")
    keyword_file = st.file_uploader("投放词报表 (CSV)", type="csv")
    search_file = st.file_uploader("搜索词报表 (CSV)", type="csv")
    search_share_file = st.file_uploader("搜索词份额报告 (CSV)", type="csv")
    # 推广的商品报告暂未使用，注释掉
    # product_report_file = st.file_uploader("推广的商品报告 (CSV)", type="csv")

@st.cache_data
def load_csv(uploaded_file):
    if uploaded_file is None:
        return None
    # 尝试常见编码
    encodings = ['gbk', 'utf-8', 'gb2312', 'gb18030']
    for enc in encodings:
        try:
            # 将文件指针重置到开头（重要！）
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding=enc)
            return df
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
    # 如果都失败，返回 None 并提示
    st.error("无法解码文件，请确认文件编码为 GBK 或 UTF-8。")
    return None


if budget_file is not None:
    df = load_csv(budget_file)
    if df is not None:
        store.set("budget", df)  # 存入统一存储
        st.session_state.df_budget = df  # 保持手动分析兼容（可选）

if placement_file is not None:
    df = load_csv(placement_file)
    if df is not None:
        df = clean_placement_data(df)
        store.set("placement", df)  # 存入统一存储
        st.session_state.df_placement = df  # 保持手动分析兼容（可选）

if keyword_file is not None:
    df = load_csv(keyword_file)
    if df is not None:
        df_keyword_clean = clean_keyword_report(df)
        st.session_state.df_keyword = df_keyword_clean
        store.set("keyword", df_keyword_clean)

if search_file is not None:
    df = load_csv(search_file)
    if df is not None:
        df_search_clean = clean_search_report(df)
        st.session_state.df_search = df_search_clean
        store.set("search", df_search_clean)   # 如果后续 Agent 需要，可以存入 store

if search_share_file is not None:
    df = load_csv(search_share_file)
    if df is not None:
        df_clean = clean_search_share_report(df)
        st.session_state.df_search_share = df_clean
        store.set("search_share", df_clean)


# 两个标签页
tab1, tab2 = st.tabs(["📊 手动分析", "🤖 AI助手"])

with tab1:
    if st.session_state.df_budget is not None:
        with st.expander("📊 预算分析", expanded=False):
            analyze_budget(st.session_state.df_budget)  # 你的UI分析函数
    else:
        st.info("请先在左侧上传预算报表")

    if st.session_state.df_placement is not None:
        with st.expander("📈 广告位分析", expanded=False):
            analyze_placement(st.session_state.df_placement)  # 你的UI分析函数
    else:
        st.info("请先在左侧上传广告活动_广告位报表")

    if st.session_state.get('df_keyword') is not None:
        with st.expander("🔑 广告活动内投放词分析 + 关键词跨活动对比分析", expanded=False):
            analyze_keyword(st.session_state.df_keyword)
            st.markdown("---")
            analyze_keyword_cross_activities(st.session_state.df_keyword)
    else:
        st.info("请先在左侧上传投放词报表")

    # 搜索词分析（添加外层折叠）
    if st.session_state.get('df_search') is not None:
        with st.expander("🔍 搜索词分析", expanded=False):
            analyze_search(st.session_state.df_search)
    else:
        st.info("请先在左侧上传搜索词报表")

    # 搜索词趋势分析（基于搜索词份额报告）
    if st.session_state.get('df_search_share') is not None:
        with st.expander("📈 搜索词趋势分析（每日排名与份额）", expanded=False):
            analyze_search_term_trend(st.session_state.df_search_share)
    else:
        st.info("请先在左侧上传搜索词份额报告")


with tab2:
    # 给定用户id
    session_id = "user016"
    # 显示历史消息
    for message in st.session_state["user_history_store"].get_history(session_id):
        st.chat_message(message["role"]).write(message["content"])

    # 用户输入提示词
    prompt = st.chat_input()

    if prompt:
        st.chat_message("user").write(prompt)
        history = st.session_state["user_history_store"].get_history(session_id)

        message_with_historys = history + [{"role": "user", "content": prompt}]
        response_message = []
        with st.spinner("智能客服思考中..."):
            res_stream = st.session_state["agent"].execute_stream(message_with_historys)


            def capture(generate, cache_list):
                for chunk in generate:
                    cache_list.append(chunk)
                    for char in chunk:
                        time.sleep(0.01)
                        yield char

            st.chat_message("assistant").write_stream(capture(res_stream, response_message))
            st.session_state["user_history_store"].add_message(session_id=session_id, role="user", content=prompt)
            st.session_state["user_history_store"].add_message(session_id=session_id, role="assistant",
                                                               content=response_message[-1])

        st.rerun()

