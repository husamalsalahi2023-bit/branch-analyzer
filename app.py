import streamlit as st
import pdfplumber
import pandas as pd
import re
import json
import base64
import requests
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display

st.set_page_config(page_title="منصة العمليات واليومية الميدانية - مؤسسة حسام الصلاحي", layout="wide")

st.markdown("""
<style>
    .reportview-container, .main .block-container { direction: rtl; text-align: right; }
    h1, h2, h3, h4, p, span, div { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
    .entry-box { background-color: #f1f5f9; border-right: 5px solid #2563eb; padding: 15px; border-radius: 6px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def fix_arabic_text(text):
    """تصحيح اتجاه الحروف العربية والكلمات المعكوسة من تقارير أونكس برو"""
    if not text:
        return ""
    words = text.split()
    fixed_words = []
    for w in words:
        if any(rev in w for rev in ["تاعيبم", "ةروتاف", "دقن", "ضبق", "دودرم", "فالصأ", "فلست"]):
            fixed_words.append(w[::-1])
        else:
            try:
                reshaped = arabic_reshaper.reshape(w)
                fixed_words.append(get_display(reshaped))
            except:
                fixed_words.append(w)
    return " ".join(fixed_words)

if "daily_transactions" not in st.session_state:
    st.session_state.daily_transactions = []

if "parsed_receipt" not in st.session_state:
    st.session_state.parsed_receipt = {
        "amount": 0.0,
        "currency": "YER",
        "ref": "",
        "sender": "",
        "bank": ""
    }

st.title("🏢 منصة العمليات والقيود اليومية الميدانية")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | قراءة الإشعارات وتوليد قيود أونكس برو")

tab1, tab2 = st.tabs(["📷 قراءة الإشعار وتوليد القيد الميداني", "📊 مطابقة وتحليل كشف أونكس برو (PDF)"])

# ======================= التبويب الأول: قراءة وتوليد القيود =======================
with tab1:
    st.subheader("مسح الإشعارات وتوجيه القيود المحاسبية")
    
    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("##### 1. ارفع صورة السند أو الإشعار:")
        up_img = st.file_uploader("التقط أو ارفع صورة الإشعار / السند", type=["jpg", "png", "jpeg"], key="receipt_file")

        env_key = st.secrets.get("GEMINI_API_KEY", "")
        if not env_key:
            env_key = st.text_input("أدخل مفتاح Gemini API:", type="password")

        if up_img:
            if st.button("🔍 قراءة بيانات الإشعار بالذكاء الاصطناعي"):
                if not env_key:
                    st.error("يرجى إدخال مفتاح Gemini API أولاً.")
                else:
                    with st.spinner("جاري استخراج المبلغ والعملة واسم المرسل والمرجع من الإشعار..."):
                        try:
                            img_bytes = up_img.getvalue()
                            mime_type = up_img.type if up_img.type else "image/jpeg"
                            b64_data = base64.b64encode(img_bytes).decode("utf-8")

                            prompt_text = """
                            أنت محاسب مالي خبير. حلل صورة الإشعار واستخرج فقط JSON خالص بالصيغة التالية:
                            {
                                "amount": رقم المبلغ فقط كقيمة رقمية بدون نصوص وبدون فواصل,
                                "currency": العملة (YER أو SAR أو USD),
                                "ref": "رقم الحوالة أو السند أو المرجع إن وجد",
                                "sender": "اسم الشخص أو الجهة المرسلة المكتوبة في الورقة",
                                "bank": "اسم الصراف أو البنك المذكور في الإشعار"
                            }
                            أرجع كود JSON فقط بدون شروح إضافية.
                            """

                            headers = {"Content-Type": "application/json"}
                            if env_key.strip().startswith("AQ."):
                                headers["Authorization"] = f"Bearer {env_key.strip()}"
                                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
                            else:
                                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={env_key.strip()}"

                            payload = {
                                "contents": [{
                                    "parts": [
                                        {"text": prompt_text},
                                        {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                                    ]
                                }]
                            }

                            res = requests.post(url, json=payload, headers=headers, timeout=30)
                            if res.status_code == 200:
                                res_json = res.json()
                                raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
                                clean_json = raw_text.strip().replace("```json", "").replace("```", "").strip()
                                data = json.loads(clean_json)

                                st.session_state.parsed_receipt["amount"] = float(data.get("amount", 0.0))
                                c = str(data.get("currency", "YER")).upper()
                                st.session_state.parsed_receipt["currency"] = c if c in ["YER", "SAR", "USD"] else "YER"
                                st.session_state.parsed_receipt["ref"] = str(data.get("ref", ""))
                                st.session_state.parsed_receipt["sender"] = str(data.get("sender", ""))
                                st.session_state.parsed_receipt["bank"] = str(data.get("bank", ""))
                                st.success("تمت قراءة بيانات الإشعار بنجاح!")
                                st.rerun()
                            else:
                                st.error(f"خطأ في الاتصال: {res.text}")
                        except Exception as e:
                            st.error(f"خطأ أثناء التحليل: {e}")

        st.markdown("---")
        st.write("##### 2. مراجعة وتوضيح طبيعة العملية:")

        c_a1, c_a2 = st.columns(2)
        with c_a1:
            amount_val = st.number_input("المبلغ:", min_value=0.0, step=100.0, format="%.2f", value=float(st.session_state.parsed_receipt["amount"]))
        with c_a2:
            currs = ["YER", "SAR", "USD"]
            c_idx = currs.index(st.session_state.parsed_receipt["currency"]) if st.session_state.parsed_receipt["currency"] in currs else 0
            curr_val = st.selectbox("العملة:", currs, index=c_idx)

        c_r1, c_r2 = st.columns(2)
        with c_r1:
            ref_val = st.text_input("رقم الحوالة / المرجع:", value=st.session_state.parsed_receipt["ref"])
        with c_r2:
            sender_val = st.text_input("المرسل المذكور في الإشعار:", value=st.session_state.parsed_receipt["sender"])

        bank_or_box = st.text_input(
            "حساب الصراف / البنك / الصندوق المستلم:",
            value=st.session_state.parsed_receipt["bank"],
            placeholder="مثال: حساب صرافة القطيبي / درة الجزيرة / صندوق الفرع"
        )

        op_type = st.selectbox(
            "توضيح نوع العملية:",
            [
                "قبض من عميل (سداد حساب عميل)",
                "مبيعات نقدية مباشرة",
                "صرف وسداد حساب مورد",
                "صرف مصروفات ونثريات تشغيلية",
                "سلف ومستحقات موظفين",
                "توريد / تحويل بين الحسابات"
            ]
        )

        party_detail = st.text_input(
            "اسم العميل الفعلي / المورد / بند المصروف:",
            placeholder="مثال: العميل باحكيم / المورد بن داعر / مصاريف بترول"
        )

        if st.button("⚖️ إصدار القيد المحاسبي وحفظه في كشف اليوم"):
            if amount_val <= 0:
                st.error("يرجى التأكد من كتابة المبلغ.")
            else:
                from_acc = ""
                to_acc = ""
                if "قبض من عميل" in op_type:
                    from_acc = f"حـ/ {bank_or_box if bank_or_box else 'الصندوق / الصراف'}"
                    to_acc = f"حـ/ العميل: {party_detail if party_detail else sender_val}"
                elif "مبيعات" in op_type:
                    from_acc = f"حـ/ {bank_or_box if bank_or_box else 'الصندوق'}"
                    to_acc = "حـ/ المبيعات النقدية"
                elif "سداد حساب مورد" in op_type:
                    from_acc = f"حـ/ المورد: {party_detail}"
                    to_acc = f"حـ/ {bank_or_box if bank_or_box else 'الصندوق / الصراف'}"
                elif "مصروفات" in op_type:
                    from_acc = f"حـ/ المصروفات: {party_detail}"
                    to_acc = f"حـ/ {bank_or_box if bank_or_box else 'الصندوق'}"
                elif "سلف" in op_type:
                    from_acc = f"حـ/ سلف العاملين: {party_detail}"
                    to_acc = f"حـ/ {bank_or_box if bank_or_box else 'الصندوق'}"
                else:
                    from_acc = f"حـ/ {party_detail}"
                    to_acc = f"حـ/ {bank_or_box}"

                entry_text = f"من {from_acc}  |  إلى {to_acc}"

                now_time = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                st.session_state.daily_transactions.append({
                    "الوقت": now_time,
                    "النوع": op_type,
                    "المبلغ": amount_val,
                    "العملة": curr_val,
                    "الطرف / البيان": party_detail if party_detail else sender_val,
                    "الصراف / الصندوق": bank_or_box,
                    "رقم المرجع": ref_val if ref_val else "بدون",
                    "القيد المحاسبي (أونكس)": entry_text
                })

                st.session_state.parsed_receipt = {"amount": 0.0, "currency": "YER", "ref": "", "sender": "", "bank": ""}
                st.success("تم إصدار القيد بنجاح!")
                st.rerun()

    with col2:
        st.write("##### 3. كشف العمليات والقيود المسجلة اليوم:")
        if st.session_state.daily_transactions:
            df_entries = pd.DataFrame(st.session_state.daily_transactions)
            for idx, r in df_entries.iterrows():
                st.markdown(f"""
                <div class="entry-box">
                    📌 <b>{r['النوع']}</b> | {r['المبلغ']:,.2f} {r['العملة']} (مرجع: {r['رقم المرجع']})<br>
                    البيان: {r['الطرف / البيان']} | الصراف/الصندوق: {r['الصراف / الصندوق']}<br>
                    <span style="color: #1e3a8a;"><b>القيد:</b> {r['القيد المحاسبي (أونكس)']}</span>
                </div>
                """, unsafe_allow_html=True)
                st.write("")

            st.markdown("---")
            sum_yer = df_entries[df_entries["العملة"] == "YER"]["المبلغ"].sum()
            sum_sar = df_entries[df_entries["العملة"] == "SAR"]["المبلغ"].sum()
            mc1, mc2 = st.columns(2)
            mc1.metric("إجمالي اليومية (YER)", f"{sum_yer:,.2f}")
            mc2.metric("إجمالي اليومية (SAR)", f"{sum_sar:,.2f}")

            csv_data = df_entries.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 تحميل كشف القيود اليومية (Excel / CSV)",
                data=csv_data,
                file_name=f"قيود_حركة_اليوم_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )

            if st.button("🗑️ مسح كشف اليوم وبدء يوم جديد"):
                st.session_state.daily_transactions = []
                st.rerun()
        else:
            st.info("لم تصدر أي قيود بعد اليوم.")

# ======================= التبويب الثاني: تحليل كشف أونكس برو =======================
with tab2:
    st.subheader("تحليل كشوفات الحساب وحركة الفرع من أونكس برو (PDF)")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري تحليل التقرير وتصحيح أسماء الأصناف..."):
            records = []
            curr_code = "YER"

            with pdfplumber.open(uploaded_pdf) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split("\n")
                    for line in lines:
                        if any(w in line for w in ["إجمالي العمليات", "الرصيد الحالي", "إجمالي الرصيد", "تاريخ التقرير", "طبع بواسطة"]):
                            continue

                        if any(w in line for w in ["SAR", "سعودي", "يدوعس"]):
                            curr_code = "SAR"
                        elif any(w in line for w in ["YER", "يمني", "ينمي"]):
                            curr_code = "YER"
                        elif any(w in line for w in ["USD", "دولار", "رالود"]):
                            curr_code = "USD"

                        d_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if d_match:
                            tx_date = d_match.group(1)

                            is_sales = any(w in line for w in ["مبيعات", "تاعيبم", "فاتورة مبيعات", "دقن تاعيبم ةروتاف"])
                            is_return = any(w in line for w in ["مردود", "دودرم", "مرتجع", "عجترم"])
                            is_receipt = any(w in line for w in ["قبض", "ضبق", "دفعه", "هعفد", "سداد", "دادس"])
                            is_deposit = any(w in line for w in ["ايداع", "عاديإ", "القطيبي", "يبيطقلا", "دره الجزيره", "السيله", "هليسلا"])
                            is_remittance = any(w in line for w in ["حوالة", "ةلاوح", "حواله", "هلاوح"])
                            is_expense = any(w in line for w in ["مصاريف", "فيراصم", "بترول", "لورتب", "حماله", "نقل", "طحانه", "كهرباء"])
                            is_salary = any(w in line for w in ["سلف", "فلس", "راتب", "بتار"])

                            cat = "حركات عامة أخرى"
                            if is_return:
                                cat = "مردودات مبيعات"
                            elif is_sales:
                                cat = "مبيعات نقدية"
                            elif is_remittance:
                                cat = "حوالات مستلمة"
                            elif is_deposit:
                                cat = "توريدات وإيداعات بنكية"
                            elif is_salary:
                                cat = "سلف ومستحقات موظفين"
                            elif is_expense:
                                cat = "مصاريف تشغيلية ونقل"
                            elif is_receipt:
                                cat = "مقبوضات ودفعات عملاء"

                            money_matches = re.findall(r'(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2})', line)
                            real_amount = 0.0

                            if money_matches:
                                amounts_clean = [float(m.replace(",", "")) for m in money_matches]
                                valid_amounts = [a for a in amounts_clean if a < 30000000]
                                if valid_amounts:
                                    real_amount = valid_amounts[0]
                            else:
                                simple_nums = re.findall(r'\b\d+\b', line)
                                candidates = [float(x) for x in simple_nums if len(x) >= 4 and float(x) < 30000000]
                                if candidates:
                                    real_amount = candidates[0]

                            # استخراج وتنظيف البيان واسم الصنف
                            clean_desc = re.sub(r'\d{2}/\d{2}/\d{4}', '', line)
                            clean_desc = re.sub(r'\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b', '', clean_desc)
                            clean_desc = re.sub(r'\b\d+\.\d{2}\b', '', clean_desc)
                            clean_desc = re.sub(r'\b\d{6,}\b', '', clean_desc)
                            fixed_item_name = fix_arabic_text(clean_desc.strip())

                            if real_amount > 0:
                                records.append({
                                    "التاريخ": tx_date,
                                    "العملة": curr_code,
                                    "التصنيف": cat,
                                    "المبلغ": real_amount,
                                    "بيان العملية / الصنف": fixed_item_name if fixed_item_name else line.strip()
                                })

            if records:
                df = pd.DataFrame(records)
                st.success(f"تم تحليل وتصنيف {len(df):,} حركة مالية بنجاح!")

                col_c, col_f = st.columns([1, 2])
                with col_c:
                    curr_options = ["الكل (جميع العملات)"] + df["العملة"].unique().tolist()
                    sel_curr = st.selectbox("نوع العملة للكشف:", curr_options)

                with col_f:
                    filter_option = st.selectbox(
                        "🔍 الاستعلام عن بند محدد:",
                        ["عرض كل العمليات", "المبيعات النقدية فقط", "المقبوضات والدفعات فقط", "المصروفات والسلف فقط", "التوريدات والإيداعات فقط", "المردودات فقط"]
                    )

                df_c = df if sel_curr == "الكل (جميع العملات)" else df[df["العملة"] == sel_curr]

                if filter_option == "المبيعات النقدية فقط":
                    view_df = df_c[df_c["التصنيف"] == "مبيعات نقدية"]
                elif filter_option == "المقبوضات والدفعات فقط":
                    view_df = df_c[df_c["التصنيف"] == "مقبوضات ودفعات عملاء"]
                elif filter_option == "المصروفات والسلف فقط":
                    view_df = df_c[df_c["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]
                elif filter_option == "التوريدات والإيداعات فقط":
                    view_df = df_c[df_c["التصنيف"] == "توريدات وإيداعات بنكية"]
                elif filter_option == "المردودات فقط":
                    view_df = df_c[df_c["التصنيف"] == "مردودات مبيعات"]
                else:
                    view_df = df_c

                st.write(f"### جدول عمليات أونكس ({filter_option}) - الإجمالي: {view_df['المبلغ'].sum():,.2f}:")
                st.dataframe(view_df[["التاريخ", "العملة", "التصنيف", "المبلغ", "بيان العملية / الصنف"]], use_container_width=True)

                csv_data = view_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل تقرير أونكس كملف Excel (CSV)",
                    data=csv_data,
                    file_name=f"تقرير_اونكس_{sel_curr}_{filter_option}.csv",
                    mime="text/csv"
                )
