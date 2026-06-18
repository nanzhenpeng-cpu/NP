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
            elif "NP" in cell_str.upper():
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

# ========== 排序：苹果优先 + 数字降序 ==========
def extract_number(name):
    """提取机型名称中的最后一个连续数字，用于排序（无数字返回0）"""
    nums = re.findall(r'\d+', name)
    return int(nums[-1]) if nums else 0

# 从原始列名获取顺序（保持 Excel 中的出现顺序，再去重）
apple_models_raw = [str(col).strip() for col in df_apple.columns[1:]]
android_models_raw = [str(col).strip() for col in df_android.columns[1:]]
apple_ordered = list(dict.fromkeys(apple_models_raw))   # 去重保序
android_ordered = list(dict.fromkeys(android_models_raw))

# 分别按数字降序
apple_sorted = sorted(apple_ordered, key=extract_number, reverse=True)
android_sorted = sorted(android_ordered, key=extract_number, reverse=True)

# 合并，苹果在前，安卓在后，去重（苹果优先）
all_models = apple_sorted.copy()
for m in android_sorted:
    if m not in all_models:
        all_models.append(m)

# 确保 full_dict 中可能有的残留机型也加进去（放在末尾，字母序）
remaining = [m for m in full_dict.keys() if m not in all_models]
all_models.extend(sorted(remaining))

# ========== 界面：多选机型 ==========
selected_models = st.multiselect(
    "🔍 选择机型（可多选，只有当所有选中机型都标记为 NP 时，该词才否定）：",
    options=all_models,
    default=None,
)

if not selected_models:
    st.info("👆 请在上方选择至少一个机型")
    st.stop()

# ========== 否定词交集逻辑 ==========
def get_all_neg_words(model_name):
    if model_name in full_dict:
        data = full_dict[model_name]
        normal = set(data["normal"])
        special = set()
        for words in data["special"].values():
            special.update(words)
        return normal.union(special)
    return set()

neg_sets = [get_all_neg_words(m) for m in selected_models]
common_neg_words = neg_sets[0]
for s in neg_sets[1:]:
    common_neg_words = common_neg_words.intersection(s)

if not common_neg_words:
    st.warning("所选机型没有共同否定词（没有在所有机型中都标记为 NP 的关键词）。")
    st.stop()

# ========== 备注整理 ==========
word_remarks = {}
for word in common_neg_words:
    word_remarks[word] = set()
    for m in selected_models:
        if m in full_dict:
            data = full_dict[m]
            for remark, words in data["special"].items():
                if word in words:
                    word_remarks[word].add(remark)

display_lines = []
for word in sorted(common_neg_words):
    if word_remarks[word]:
        remark_str = "、".join(sorted(word_remarks[word]))
        display_lines.append(f"{word}  ( {remark_str} )")
    else:
        display_lines.append(word)

plain_keywords = sorted(common_neg_words)
display_text = "\n".join(display_lines)
plain_text = "\n".join(plain_keywords)

# ========== 展示结果 ==========
st.subheader(f"📋 共 {len(plain_keywords)} 个否定词")
st.code(display_text, language="")

# ========== 复制按钮（JS实现） ==========
def copy_button(text_to_copy, button_label, success_msg="已复制到剪贴板！"):
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

copy_button(plain_text, "📋 复制纯关键词（每行一个）")

if any(word_remarks[w] for w in plain_keywords):
    copy_button(display_text, "📋 复制关键词（含备注）", "已复制（含备注）")

st.caption("💡 列表中灰色小字为备注信息，点击复制纯关键词可直接用于广告后台。")
