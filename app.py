import streamlit as st
import pandas as pd
from pathlib import Path
import html
import re

# ========== 配置页面 ==========
st.set_page_config(page_title="亚马逊否定词查询", page_icon="📱", layout="wide")
st.title("📱 手机线广告否定词查询")
st.caption("数据来源：苹果机型否定 & 安卓机型否定")

# ========== 读取 Excel ==========
EXCEL_PATH = Path(__file__).parent / "手机线否词 (1).xlsx"

@st.cache_data(show_spinner=False)
def load_data(path):
    # 同时读取两个 sheet
    df_apple = pd.read_excel(path, sheet_name="苹果机型否定", header=0)
    df_android = pd.read_excel(path, sheet_name="安卓机型否定", header=0)
    return df_apple, df_android

try:
    df_apple, df_android = load_data(EXCEL_PATH)
except Exception as e:
    st.error(f"读取文件失败，请确认 Excel 文件已放在与 app.py 同一目录。\n错误信息：{e}")
    st.stop()

# ========== 解析数据，构建 机型 → 否定词 的映射 ==========
def build_model_dict(df):
    """
    返回字典:
    {
      "iphone17": {
         "normal": ["关键词A", "关键词B"],
         "手机膜共用不否": ["关键词C"],
         ...
      },
      ...
    }
    """
    model_dict = {}
    # 第一列是关键词，其余都是机型
    keywords = df.iloc[:, 0].dropna().astype(str).tolist()
    model_columns = df.columns[1:]  # 机型列名
    
    for col in model_columns:
        model_name = str(col).strip()
        if model_name not in model_dict:
            model_dict[model_name] = {"normal": [], "special": {}}  # special 是 {备注: [词列表]}
        
        for idx, keyword in enumerate(keywords):
            cell_value = df.iloc[idx][col]
            if pd.isna(cell_value) or str(cell_value).strip() == "":
                continue
            
            cell_str = str(cell_value).strip()
            # 判断是否为 NP 或 NP(备注)
            if cell_str == "NP":
                model_dict[model_name]["normal"].append(keyword)
            elif cell_str.startswith("NP(") or cell_str.startswith("NP（"):
                # 提取括号内的备注
                match = re.search(r'NP[（(](.+)[）)]', cell_str)
                remark = match.group(1).strip() if match else "备注"
                if remark not in model_dict[model_name]["special"]:
                    model_dict[model_name]["special"][remark] = []
                model_dict[model_name]["special"][remark].append(keyword)
            else:
                # 以防出现其他类似 NP 的值，按普通否定处理
                if "NP" in cell_str.upper():
                    model_dict[model_name]["normal"].append(keyword)
    return model_dict

# 合并两个 sheet 的机型字典（同一机型出现多次，取并集）
def merge_dicts(d1, d2):
    merged = {}
    for d in [d1, d2]:
        for model, data in d.items():
            if model not in merged:
                merged[model] = {"normal": [], "special": {}}
            merged[model]["normal"].extend(data["normal"])
            for remark, words in data["special"].items():
                merged[model]["special"].setdefault(remark, []).extend(words)
    # 去重
    for model in merged:
        merged[model]["normal"] = list(set(merged[model]["normal"]))
        for remark in merged[model]["special"]:
            merged[model]["special"][remark] = list(set(merged[model]["special"][remark]))
    return merged

apple_dict = build_model_dict(df_apple)
android_dict = build_model_dict(df_android)
full_dict = merge_dicts(apple_dict, android_dict)

# 所有机型列表（按字母排序）
all_models = sorted(full_dict.keys())

# ========== 界面：多选机型 ==========
selected_models = st.multiselect(
    "🔍 选择机型（可多选，支持联合筛选）：",
    options=all_models,
    default=None,
    help="选择一个或多个机型，只要任一机型标记为 NP，该关键词就会展示"
)

if not selected_models:
    st.info("👆 请在上方选择至少一个机型")
    st.stop()

# ========== 合并所选机型的否定词 ==========
aggregated_normal = []
aggregated_special = {}  # {备注: [词列表]}

for model in selected_models:
    if model in full_dict:
        aggregated_normal.extend(full_dict[model]["normal"])
        for remark, words in full_dict[model]["special"].items():
            aggregated_special.setdefault(remark, []).extend(words)

# 去重并排序
aggregated_normal = sorted(set(aggregated_normal))
for remark in aggregated_special:
    aggregated_special[remark] = sorted(set(aggregated_special[remark]))

# ========== 展示结果 ==========
col1, col2 = st.columns(2)

with col1:
    st.subheader("✅ 普通否定词")
    if aggregated_normal:
        normal_text = "\n".join(aggregated_normal)
        st.code(normal_text, language="")
        # 一键复制按钮（使用 HTML + JS）
        st.markdown(
            f"""<button onclick="navigator.clipboard.writeText(`{html.escape(normal_text)}`)">📋 复制普通否定词 ({len(aggregated_normal)}个)</button>""",
            unsafe_allow_html=True
        )
    else:
        st.write("无")

with col2:
    st.subheader("⚠️ 特殊备注否定词")
    if aggregated_special:
        for remark, words in aggregated_special.items():
            st.markdown(f"**{remark}**")
            text = "\n".join(words)
            st.code(text, language="")
            st.markdown(
                f"""<button onclick="navigator.clipboard.writeText(`{html.escape(text)}`)">📋 复制「{html.escape(remark)}」 ({len(words)}个)</button>""",
                unsafe_allow_html=True
            )
    else:
        st.write("无")

# 底部：复制全部否定词（普通+所有特殊）
all_words = aggregated_normal.copy()
for words in aggregated_special.values():
    all_words.extend(words)
all_words = sorted(set(all_words))
all_text = "\n".join(all_words)

st.divider()
col_all, _ = st.columns([1, 3])
with col_all:
    st.subheader("📦 全部否定词（合并去重）")
    st.code(all_text, language="")
    st.markdown(
        f"""<button onclick="navigator.clipboard.writeText(`{html.escape(all_text)}`)">📋 一键复制全部 ({len(all_words)}个)</button>""",
        unsafe_allow_html=True
    )
