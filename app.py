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
# ✅ 新增：匹配模式选择
match_mode = st.radio(
    "选择匹配模式",
    ["完全匹配（完全一致才算匹配）", "片段匹配（只要上传序列中存在连续片段与数据库序列完全一致即可）"]
)

if uploaded_file:
    # 读取用户上传的肽段
    pep_data = pd.read_excel(uploaded_file, sheet_name='Sheet1')
    peptide_sequences = pep_data['Peptide'].dropna().tolist()
    cleaned_sequences = [''.join(aa_only.findall(str(s))).upper() for s in peptide_sequences]

    st.write("✅ 已读取并标准化肽段序列")

    # 读取本地肽段数据库（假设放在 '功能肽' 文件夹）
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

    # 📌 匹配逻辑：根据用户选择切换
    def find_matching_peptides(sequence, pep_data_list, mode):
        """
        mode: 'exact' 或 'fragment'
        """
        if mode == 'exact':
            # 完全匹配
            return [p for p in pep_data_list if sequence == p['sequence']]
        else:
            # 片段匹配：只要数据库中某条序列是上传序列的连续子串即可
            return [p for p in pep_data_list if p['sequence'] in sequence]

    # ✅ 根据模式变量确定匹配函数所需 mode 参数
    mode_flag = 'exact' if match_mode.startswith("完全匹配") else 'fragment'

    results = []
    for seq in cleaned_sequences:
        matches = find_matching_peptides(seq, merged_pep_data_list, mode=mode_flag)
        if matches:
            results.append({
                'sequence': seq,
                'matched_sequence': '; '.join([str(m['sequence']) for m in matches]),  # ✅ 新增
                'PepLab ID': '; '.join([str(m['PepLab ID']) for m in matches]),
                'length': '; '.join([str(m['length']) for m in matches]),
                'Activity': '; '.join([str(m['activity']) for m in matches])
            })
        else:
            results.append({
                'sequence': seq,
                'matched_sequence': None,   # ✅ 新增
                'PepLab ID': None,
                'length': None,
                'Activity': None
            })

    # 显示结果表格
    st.subheader("匹配结果")
    output_df = pd.DataFrame(results)
    st.dataframe(output_df)

    # 提供下载
    def to_excel(df):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()

    st.download_button(
        label="📥 下载结果 Excel",
        data=to_excel(output_df),
        file_name='肽段匹配结果.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# -------------------- 新增：蛋白序列定位 --------------------
st.markdown("---")
st.subheader("🧬 可选：输入蛋白全长序列进行定位")
protein_seq_input = st.text_area(
    "请输入一条完整的蛋白氨基酸序列（仅支持 20 种标准氨基酸字母，大小写均可）：",
    placeholder="例如：MKTLL..."
)

# 如果用户输入了蛋白序列，则进行定位分析
if protein_seq_input.strip():
    # 清洗蛋白序列
    full_protein = ''.join(aa_only.findall(protein_seq_input)).upper()
    if not full_protein:
        st.warning("❗ 未检测到合法的氨基酸字符，请重新输入！")
        st.stop()

    st.success(f"✅ 已读取蛋白序列（长度：{len(full_protein)} aa）")

    # 构建定位结果
    locate_results = []
    for seq in cleaned_sequences:
        seq = seq.upper()
        if not seq:
            continue
        start = 1  # 使用 1-based 索引，便于阅读
        while True:
            idx = full_protein.find(seq, start - 1)
            if idx == -1:
                break
            # 计算上下文区域
            left_start = max(idx - 5, 0)
            right_end = min(idx + len(seq) + 5, len(full_protein))
            context = full_protein[left_start:right_end]
            # 高亮匹配区域
            match_start_in_context = idx - left_start
            match_end_in_context = match_start_in_context + len(seq)
            context_display = (
                context[:match_start_in_context] +
                "**" + context[match_start_in_context:match_end_in_context] + "**" +
                context[match_end_in_context:]
            )
            locate_results.append({
                'Peptide': seq,
                'Start': idx + 1,
                'End': idx + len(seq),
                'Context (±5aa)': context_display
            })
            start = idx + 1  # 继续往后找，允许重复匹配

    if locate_results:
        st.subheader("蛋白定位结果")
        locate_df = pd.DataFrame(locate_results)
        st.dataframe(locate_df)   # Streamlit 会自动渲染 markdown
        # 下载定位结果
        st.download_button(
            label="📥 下载定位结果 Excel",
            data=to_excel(locate_df),
            file_name='肽段蛋白定位结果.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        st.info("⚠️ 当前输入的蛋白序列中未找到任何上传肽段的匹配。")
else:
    # 用户未输入蛋白序列，什么都不做
    pass




