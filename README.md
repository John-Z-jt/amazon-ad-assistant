# 亚马逊广告诊断助手

> 一键上传亚马逊广告报表，自动分析预算、广告位、投放词、搜索词，集成 AI 助手问答与 RAG 知识库。

## ✨ 功能
- **预算分析**：监控每日预算使用率，预警消耗过快活动（阈值 > 90%）
- **广告位分析**：按活动分组，找出最佳/最差广告位，反推 Listing 竞争力
- **投放词分析**：高花费零订单词检测，跨活动内部竞争分析
- **搜索词分析**：否定词候选 + 高潜力拓词候选，支持联动筛选
- **搜索词份额趋势**：展示量排名/份额变化，市场竞争力象限分析
- **AI 助手**：自然语言查询（预算、广告位、关键词等），RAG 知识库解答“为什么”

## 🛠️ 技术栈
- Python 3.10+
- Streamlit
- Pandas / NumPy
- LangChain
- FAISS
- 阿里云百炼 API

## 🚀 本地运行

1. 克隆仓库
   ```bash
   git clone https://github.com/John-Z-jt/amazon-ad-assistant.git
   cd amazon-ad-assistant
   ```
2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
3. 配置环境变量。创建 .env 文件，填入以下内容（替换 你的阿里云百炼API Key）
   ```bash
   DASHSCOPE_API_KEY=你的阿里云百炼API Key
   LLM_API_KEY=你的阿里云百炼API Key
   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
   LLM_MODEL_ID=deepseek-v3.2
   ```
4. 启动应用
   ```bash
   streamlit run Agent/app.py
   ```
🌐 在线体验
https://amazon-ad-diagnostic.streamlit.app/

📹 演示视频
通过网盘分享的文件：剪辑版.mp4 链接: https://pan.baidu.com/s/1_oEqkwTWPP2sZN4Ou-85_w?pwd=taxe 提取码: taxe

📄 报表格式要求
直接下载亚马逊广告后台的商品推广中的预算、广告位、投放词、搜索词、搜索词展示量份额报告，注意是每日报告不是摘要。然后点击上传到页面即可。

👤 作者
邮箱：2088035429@qq.com
   
   
