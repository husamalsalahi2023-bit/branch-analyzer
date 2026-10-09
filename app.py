import streamlit as st
import pdfplumber
import pandas as pd
import re
import json
from datetime import datetime
from PIL import Image

st.set_page_config(page_title="منصة العمليات اليومية - مؤسسة حسام الصلاحي", layout="wide")

st.markdown("""
<style>
    .reportview-container, .main .block-container { direction: rtl; text-align: right; }
    h1, h2, h3, h4, p, span, div { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

if "daily_transactions" not in st.session_state:
    st.session_state.daily_transactions = []

if "extracted_data" not in st.session_state:
    st.session_state.extracted_data = {
        "amount": 0.0,
        "currency": "YER",
        "ref": "",
        "party": ""
    }

st.title("🏢 منصة العمليات واليومية الميدانية")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | توثيق الإشعارات والمطابقة")

tab1, tab2 = st.tabs(["📝 تسجيل إشعار وسند يومي (مع كشف الإقفال)", "📊 مطابقة وتحليل كشف أونكس برو (PDF)"])

# ======================= التبويب الأول: قراءة الإشعارات =======================
with tab1:
    st.subheader("تسجيل العمليات الميدانية للإقفال اليومي والمطابقة")
    
    col_input, col_view = st.columns([1, 1])

    with col_input:
        st.write("##### 1. ارفع صورة السند أو الإشعار:")
        
        doc_type = st.selectbox(
            "نوع السند / العملية:",
            [
                "سند قبض نقدي (من عميل)",
                "سند صرف (سداد حساب مورد)",
                "سند صرف (مصروفات ونثريات)",
                "إشعار توريد / إيداع بنكي أو صراف",
                "سلف ومستحقات موظفين",
                "أخرى"
            ]
        )

        up_img = st.file_uploader("التقط أو ارفع صورة السند / الإشعار", type=["jpg", "png", "jpeg"])

        env_key = st.secrets.get("GEMINI_API_KEY", "")
        if not env_key:
            env_key = st.text_input("أدخل مفتاح Gemini API:", type="password")

        if up_img:
            if st.button("🔍 قراءة بيانات الإشعار بالذكاء الاصطناعي"):
                if not env_key:
                    st.error("يرجى التأكد من إضافة مفتاح Gemini API.")
                else:
                    with st.spinner("جاري قراءة المبلغ والعملة ورقم الإشعار..."):
                        try:
                            from google import genai
                            client = genai.Client(api_key=env_key)
                            
                            prompt = """
                            أنت محاسب مالي خبير. قم بتحليل صورة السند أو الإشعار المرفق واستخرج بدقة:
                            - المبلغ (amount) كرقم فقط بدون نصوص
                            - العملة (currency) وتكون إما YER أو SAR أو USD
                            - رقم المرجع أو الحوالة أو السند (ref)
                            - اسم العميل أو المورد أو المستفيد (party)
                            
                            أعد النتيجة بصيغة JSON فقط بهذا الشكل:
                            {"amount": 1000, "currency": "YER", "ref": "12345", "party": "اسم الشخص"}
                            """
                            
                            img = Image.open(up_img)
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=[prompt, img]
                            )
                            
                            clean_text = response.text.strip().replace("```json", "").replace("```", "")
                            data = json.loads(clean_text)

                            st.session_state.extracted_data["amount"] = float(data.get("amount", 0.0))
                            curr = str(data.get("currency", "YER")).upper()
                            st.session_state.extracted_data["currency"] = curr if curr in ["YER", "SAR", "USD"] else "YER"
                            st.session_state.extracted_data["ref"] = str(data.get("ref", ""))
                            st.session_state.extracted_data["party"] = str(data.get("party", ""))
                            st.success("تم استخراج البيانات بنجاح!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ أثناء التحليل: {e}")

        party_name = st.text_input(
            "اسم العميل / المورد / بيان الغرض:",
            value=st.session_state.extracted_data["party"]
        )

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            amount = st.number_input(
                "المبلغ:",
                min_value=0.0,
                step=100.0,
                format="%.2f",
                value=float(st.session_state.extracted_data["amount"])
            )
        with col_m2:
            default_curr = st.session_state.extracted_data["currency"]
            c_idx = ["YER", "SAR", "USD"].index(default_curr) if default_curr in ["YER", "SAR", "USD"] else 0
            currency = st.selectbox("العملة:", ["YER", "SAR", "USD"], index=c_idx)

        doc_ref = st.text_input(
            "رقم المرجع / الحوالة / السند:",
            value=st.session_state.extracted_data["ref"]
        )

        if st.button("➕ حفظ العملية في كشف اليوم"):
            if amount <= 0:
                st.error("يرجى إدخال المبلغ.")
            else:
                now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
                st.session_state.daily_transactions.append({
                    "الوقت": now_str,
                    "نوع السند": doc_type,
                    "البيان / المستفيد": party_name if party_name else "غير محدد",
                    "المبلغ": amount,
                    "العملة": currency,
                    "رقم المرجع": doc_ref if doc_ref else "بدون",
                    "الحالة": "لم يُرحل بعد ⏳"
                })
                st.session_state.extracted_data = {"amount": 0.0, "currency": "YER", "ref": "", "party": ""}
                st.success("تمت الإضافة إلى كشف اليوم بنجاح!")
                st.rerun()

    with col_view:
        st.write("##### 2. حركة الصندوق المسجلة اليوم:")
        if st.session_state.daily_transactions:
            df_daily = pd.DataFrame(st.session_state.daily_transactions)
            st.dataframe(df_daily[["الوقت", "نوع السند", "البيان / المستفيد", "المبلغ", "العملة", "رقم المرجع"]], use_container_width=True)

            s_yer = df_daily[df_daily["العملة"] == "YER"]["المبلغ"].sum()
            s_sar = df_daily[df_daily["العملة"] == "SAR"]["المبلغ"].sum()
            
            mc1, mc2 = st.columns(2)
            mc1.metric("إجمالي حركات اليوم (YER)", f"{s_yer:,.2f}")
            mc2.metric("إجمالي حركات اليوم (SAR)", f"{s_sar:,.2f}")

            st.markdown("---")
            csv_daily = df_daily.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 تحميل كشف المطابقة اليومي للمحاسب (CSV / Excel)",
                data=csv_daily,
                file_name=f"كشف_حركة_اليوم_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv"
            )

            if st.button("🗑️ مسح كشف اليوم وبدء يوم جديد"):
                st.session_state.daily_transactions = []
                st.rerun()
        else:
            st.info("لم تسجل أي حركة اليوم بعد.")

# ======================= التبويب الثاني: تحليل كشف أونكس برو =======================
with tab2:
    st.subheader("تحليل كشوفات الحساب وحركة الفرع من أونكس برو (PDF)")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري تحليل التقرير..."):
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

                            debit = real_amount if cat in ["مبيعات نقدية", "مقبوضات ودفعات عملاء", "حوالات مستلمة"] else 0.0
                            credit = real_amount if cat in ["مردودات مبيعات", "مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين", "توريدات وإيداعات بنكية"] else 0.0

                            if real_amount > 0:
                                records.append({
                                    "التاريخ": tx_date,
                                    "العملة": curr_code,
                                    "التصنيف": cat,
                                    "مدين (وارد)": debit,
                                    "دائن (صادر)": credit,
                                    "المبلغ": real_amount,
                                    "البيان": line.strip()
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
                st.dataframe(view_df[["التاريخ", "العملة", "التصنيف", "المبلغ", "البيان"]], use_container_width=True)

                csv_data = view_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل تقرير أونكس كملف Excel (CSV)",
                    data=csv_data,
                    file_name=f"تقرير_اونكس_{sel_curr}_{filter_option}.csv",
                    mime="text/csv"
                )
