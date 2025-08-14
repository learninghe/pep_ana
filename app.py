import streamlit as st
import pandas as pd
import re
import os
import glob
from io import BytesIO

# 正则表达式：仅保留氨基酸字母
aa_only = re.compile(r'[ACDEFGHIKLMNPQRSTVWY]', flags=re.I)

# 标题
st.title("酶制剂与生物催化：肽段序列匹配工具")
st.write("上传数据文件注意：文件后缀必须为.xlsx，.xlsx文件内容必须包含标题行，且所有数据必须在第一列，第一列第一行的标题行内容必须为Peptide，后续行依次接要分析的肽段")
st.write("demo_peptides.xlsx为对应格式的测试用数据，可直接下载打开查看数据格式要求")
st.write("上传 Excel 文件，自动匹配功能肽数据库并返回结果")

# 上传文件
uploaded_file = st.file_uploader("上传 Excel 文件", type=["xlsx"])
# -------------------- 测试数据下载 --------------------
with open("demo_peptides.xlsx", "rb") as f:
    st.download_button(
        label="📎 下载示例文件（demo_peptides.xlsx）",
        data=f,
        file_name="demo_peptides.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ✅ 匹配模式选择
match_mode = st.radio(
    "选择匹配模式",
    ["完全匹配（完全一致才算匹配）", "片段匹配（只要上传序列中存在连续片段与数据库序列完全一致即可）"]
)

# ✅ 新增：直接在网页粘贴蛋白序列
st.subheader("2️⃣ 蛋白序列（可选）")
protein_seq_input = st.text_area(
    "请输入一条蛋白序列（纯字母即可，无需 FASTA 标题行，留空则不进行定位）",
    placeholder="MKTLL...",
    height=100
)

if uploaded_file:
    # 读取用户上传的肽段
    pep_data = pd.read_excel(uploaded_file, sheet_name='Sheet1')
    peptide_sequences = pep_data['Peptide'].dropna().tolist()
    cleaned_sequences = [''.join(aa_only.findall(str(s))).upper() for s in peptide_sequences]

    st.write("✅ 已读取并标准化肽段序列")

    # 读取本地肽段数据库
    pepdatalist = []
    file_path_pepdata = '肽段分析/功能肽'
    pattern = os.path.join(file_path_pepdata, '*.csv')
    file_list = glob.glob(pattern)

    if not file_list:
        st.error("未找到本地肽段数据库（请确认 '肽段分析/功能肽' 文件夹存在且包含 CSV 文件）")
        st.stop()

    for file in file_list:
        df = pd.read_csv(file)
        df.columns = [c.strip() for c in df.columns]
        pepdatalist.append(df)

    merged_pep_data = pd.concat(pepdatalist, ignore_index=True)
    merged_pep_data_list = merged_pep_data.to_dict(orient='records')

    # 匹配逻辑
    def find_matching_peptides(sequence, pep_data_list, mode):
        if mode == 'exact':
            return [p for p in pep_data_list if sequence == p['sequence']]
        else:
            return [p for p in pep_data_list if p['sequence'] in sequence]

    mode_flag = 'exact' if match_mode.startswith("完全匹配") else 'fragment'

    results = []
    for seq in cleaned_sequences:
        matches = find_matching_peptides(seq, merged_pep_data_list, mode=mode_flag)
        if matches:
            results.append({
                'sequence': seq,
                'matched_sequence': '; '.join([str(m['sequence']) for m in matches]),
                'PepLab ID': '; '.join([str(m['PepLab ID']) for m in matches]),
                'length': '; '.join([str(m['length']) for m in matches]),
                'Activity': '; '.join([str(m['activity']) for m in matches])
            })
        else:
            results.append({
                'sequence': seq,
                'matched_sequence': None,
                'PepLab ID': None,
                'length': None,
                'Activity': None
            })



