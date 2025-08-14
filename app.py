import streamlit as st
import pandas as pd
import re
import os
import glob
from io import BytesIO
import json, os, datetime, streamlit as st

LOG_FILE = "visit_log.json"
SESSION_KEY = "has_counted_this_session"

# ------------- 会话级去重 -------------
if SESSION_KEY not in st.session_state:
    def get_visitor_ip():
        headers = st.context.headers
        # 按优先级检查常见头
        for key in ["CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"]:
            val = headers.get(key)
            if val:
                # X-Forwarded-For 可能有多级，只取第一个
                return val.split(",")[0].strip()
        # 兜底
        return headers.get("Remote-Addr", "127.0.0.1")   # 本地调试显示 127.0.0.1
    
    ip = get_visitor_ip()

    # -------------- 读写日志 --------------
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = {"total": 0, "records": []}

    log["total"] += 1
    log["records"].append({"time": now, "ip": ip})

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    # 标记已计数
    st.session_state[SESSION_KEY] = True

# ------------- UI 展示 -------------
log = json.load(open(LOG_FILE)) if os.path.exists(LOG_FILE) else {"total": 0}
st.sidebar.metric("🔍 累计访问次数", log["total"])
if st.sidebar.checkbox("显示最近 5 条访问记录"):
    st.sidebar.json(log.get("records", [])[-5:])

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
st.subheader(" 蛋白序列（可选）")
protein_seq_input = st.text_area(
    "请输入一条蛋白序列（纯字母即可，无需 FASTA 标题行，留空则不进行定位），输入后按ctrl+enter，demo对应序列MKCLLLALALTCGAQALIVTQTMKGLDIQKVAGTWYSLAMAASDISLLDAQSAPLRVYVEELKPTPEGDLEILLQKWENGECAQKKIIAEKTKIPAVFKIDALNENKVLVLDTDYKKYLLFCMENSAEPEQSLACQCLVRTPEVDDEALEKFDKALKALPMHIRLSFNPTQLEEQCHI",
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

    # --------------------------------------------------
    # ✅ 新增：蛋白定位（可选）
    protein_seq = ''.join(aa_only.findall(protein_seq_input.upper()))
    if protein_seq:
        st.write(f"✅ 已读入蛋白序列，长度 {len(protein_seq)} aa")

        def locate_peptide(peptide, protein):
            peptide = peptide.upper()
            positions = []
            start = 0
            while True:
                idx = protein.find(peptide, start)
                if idx == -1:
                    break
                positions.append((idx + 1, idx + len(peptide)))  # 1-based
                start = idx + 1
            return positions

        for res in results:
            pep = res['sequence']
            locs = locate_peptide(pep, protein_seq)
            if locs:
                res['在蛋白中的位置'] = '; '.join([f"{s}-{e}" for s, e in locs])
                contexts = []
                for s, e in locs:
                    left_start = max(s - 6, 0)  # 取前5位，再减1变成0-based
                    right_end = min(e + 5, len(protein_seq))
                    left = protein_seq[left_start:s - 1]
                    mid = f"[{protein_seq[s - 1:e]}]"
                    right = protein_seq[e:right_end]
                    contexts.append(left + mid + right)
                res['前后5aa上下文'] = '; '.join(contexts)
            else:
                res['在蛋白中的位置'] = None
                res['前后5aa上下文'] = None
    else:
        # 没有输入蛋白序列，直接填 None
        for res in results:
            res['在蛋白中的位置'] = None
            res['前后5aa上下文'] = None

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









