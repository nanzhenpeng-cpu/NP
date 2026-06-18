import streamlit as st
import pandas as pd
from pathlib import Path
import re
import streamlit.components.v1 as components

# ========== 配置页面 ==========
st.set_page_config(page_title="亚马逊否定词查询", page_icon="📱", layout="wide")
st.title("📱 手机线广告否定词查询")
st.caption("数据来源：苹果机型否定 & 安卓机型否定")

# ========== 读取 Excel ==========
EXCEL_PATH = Path(__file__).parent / "手机线否词 (1).xlsx"

@st.cache_data(show_spinner=False)
def load_data(path):
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
    返回:
    {
      "iphone17": {
         "normal": ["xiaomi", "ipad"],          # 纯 NP 的词
         "special": {"手机膜共用不否": ["keyword1"], ...}  # 带备注的 NP
      },
      ...
    }
    """
    model_dict = {}
    keywords = df.iloc[:, 0].dropna().astype(str).tolist()
    model_columns = df.columns[1:]

    for col in model_columns:
        model_name = str(col).strip()
        if model_name not in model_dict:
            model_dict[model_name] = {"normal": [], "special": {}}
        
        for idx, keyword in enumerate(keywords):
            cell_value = df.iloc[idx][col]
            if pd.isna(cell_value) or str(cell_value).strip() == "":
                continue
            cell_str = str(cell_value).strip()
            
            if cell_str == "NP":
                model_dict[model_name]["normal"].append(keyword)
            elif cell_str.startswith("NP(") or cell_str.startswith("NP（"):
                match = re.search(r'NP[（(](.+)[）)]', cell_str)
                remark = match.group(1).strip() if match else "备注"
                model_dict[model_name]["special"].setdefault(remark, []).append(keyword)
            elif "NP" in cell_str.upper():  # 其他包含 NP 的都当普通否定词处理
                model_dict[model_name]["normal"].append(keyword)
    return model_dict

def merge_dicts(d1, d2):
    merged = {}
    for d in [d1, d2]:
        for model, data in d.items():
            if model not in merged:
                merged[model] = {"normal": [], "special": {}}
            merged[model]["normal"].extend(data["normal"])
            for remark, words in data["special"].items():
                merged[model]["special"].setdefault(remark, []).extend(words)
    for model in merged:
        merged[model]["normal"] = list(set(merged[model]["normal"]))
        for remark in merged[model]["special"]:
            merged[model]["special"][remark] = list(set(merged[model]["special"][remark]))
    return merged

apple_dict = build_model_dict(df_apple)
android_dict = build_model_dict(df_android)
full_dict = merge_dicts(apple_dict, android_dict)

all_models = sorted(full_dict.keys())

# ========== 界面：多选机型 ==========
selected_models = st.multiselect(
    "🔍 选择机型（可多选，只有当所有选中机型都标记为 NP 时，该词才否定）：",
    options=all_models,
    default=None,
)

if not selected_models:
    st.info("👆 请在上方选择至少一个机型")
    st.stop()

# ========== 新逻辑：全部机型都出现 NP 才算否定 ==========
# 先收集所有选中机型中都出现的关键词（交集逻辑）
# 将每个机型的所有否定词（normal+special）合并成一个集合，然后取交集
def get_all_neg_words(model_name):
    """返回该机型所有否定词的集合（不区分备注）"""
    if model_name in full_dict:
        data = full_dict[model_name]
        normal = set(data["normal"])
        special = set()
        for words in data["special"].values():
            special.update(words)
        return normal.union(special)
    return set()

# 取所有选中机型否定词的交集
neg_sets = [get_all_neg_words(m) for m in selected_models]
common_neg_words = neg_sets[0]
for s in neg_sets[1:]:
    common_neg_words = common_neg_words.intersection(s)

if not common_neg_words:
    st.warning("所选机型没有共同否定词（没有在所有机型中都标记为 NP 的关键词）。")
    st.stop()

# 现在需要知道这些交集词中有没有带备注的，以及对应的备注是什么
# 遍历交集词，查询它们在各选中机型中的备注情况（只要在任意机型中出现过备注就保留备注）
word_remarks = {}  # {keyword: set of remarks}
for word in common_neg_words:
    word_remarks[word] = set()
    for m in selected_models:
        if m in full_dict:
            data = full_dict[m]
            # 检查该词的备注
            for remark, words in data["special"].items():
                if word in words:
                    word_remarks[word].add(remark)

# 构建最终展示列表
display_lines = []
for word in sorted(common_neg_words):
    if word_remarks[word]:
        # 多个备注用逗号连接（比如极少情况）
        remark_str = "、".join(sorted(word_remarks[word]))
        display_lines.append(f"{word}  ( {remark_str} )")
    else:
        display_lines.append(word)

plain_keywords = sorted(common_neg_words)  # 纯关键词，用于复制
display_text = "\n".join(display_lines)
plain_text = "\n".join(plain_keywords)

# ========== 展示结果 ==========
st.subheader(f"📋 共 {len(plain_keywords)} 个否定词")
st.code(display_text, language="")

# ========== 可靠的一键复制组件 ==========
def copy_button(text_to_copy, button_label, success_msg="已复制到剪贴板！"):
    """生成一个真正能用的复制按钮，使用组件注入 JS"""
    escaped_text = text_to_copy.replace("`", "\\`").replace("$", "\\$")
    components.html(f"""
    <div style="margin: 10px 0;">
        <button onclick="
            navigator.clipboard.writeText(`{escaped_text}`).then(function() {{
                var btn = document.getElementById('copy-btn');
                btn.innerText = '{success_msg}';
                setTimeout(function(){{ btn.innerText = '{button_label}'; }}, 2000);
            }}).catch(function(err) {{
                alert('复制失败，请手动全选复制：' + err);
            }});
        " id="copy-btn" style="padding:8px 16px; cursor:pointer; background:#FF4B4B; color:white; border:none; border-radius:4px;">
            {button_label}
        </button>
    </div>
    """, height=50)

# 复制纯关键词
copy_button(plain_text, "📋 复制纯关键词（每行一个）")

# 如果存在带备注的词，额外提供一个带备注的版本复制
if any(word_remarks[w] for w in plain_keywords):
    copy_button(display_text, "📋 复制关键词（含备注）", "已复制（含备注）")

st.caption("💡 列表中灰色小字为备注信息，点击复制纯关键词可直接用于广告后台。")
