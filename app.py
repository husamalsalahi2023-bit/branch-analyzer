import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="منصة التحليل المالي - مؤسسة حسام الصلاحي", layout="wide")

st.markdown("""
<style>
    .reportview-container, .main .block-container { direction: rtl; text-align: right; }
    h1, h2, h3, h4, p, span, div { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stMetric { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 منصة التحليل المالي وحركة الحسابات")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | تحليل تقارير أونكس برو")

tab1, tab2 = st.tabs(["📊 التحليل المالي الشامل (PDF)", "📷 مسح الإشعارات وتوليد القيود"])

with tab1:
    st.subheader("تحليل كشوفات الحساب وحركة الفرع")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري قراءة وتحليل الحركات والكلمات المعكوسة في التقرير..."):
            records = []
            curr_code = "YER"

            with pdfplumber.open(uploaded_pdf) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split("\n")
                    for line in lines:
                        # كشف العملة (عادي ومعكوس)
                        if any(w in line for w in ["SAR", "سعودي", "يدوعس"]):
                            curr_code = "SAR"
                        elif any(w in line for w in ["YER", "يمني", "ينمي"]):
                            curr_code = "YER"
                        elif any(w in line for w in ["USD", "دولار", "رالود"]):
                            curr_code = "USD"

                        # التقاط التاريخ DD/MM/YYYY
                        d_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if d_match:
                            tx_date = d_match.group(1)

                            # استخراج الأرقام المحاسبية
                            nums = re.findall(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', line)
                            v_nums = []
                            for n in nums:
                                cln = n.replace(",", "")
                                try:
                                    v = float(cln)
                                    if 0.01 <= v < 50000000 and len(cln.split('.')[0]) <= 8:
                                        v_nums.append(v)
                                except:
                                    pass

                            debit = 0.0
                            credit = 0.0

                            # تحديد نوع العملية أولاً لدقة توزيع المدين والدائن
                            # الكلمات مكتوبة بالشكل الطبيعي والشكل المعكوس الناتج عن استخراج أونكس
                            cat = "حركات عامة أخرى"
                            
                            is_sales = any(w in line for w in ["مبيعات", "تاعيبم", "فاتورة مبيعات", "دقن تاعيبم ةروتاف"])
                            is_return = any(w in line for w in ["مردود", "دودرم", "مرتجع", "عجترم"])
                            is_receipt = any(w in line for w in ["قبض", "ضبق", "دفعه", "هعفد", "سداد", "دادس"])
                            is_deposit = any(w in line for w in ["ايداع", "عاديإ", "القطيبي", "يبيطقلا", "دره الجزيره", "السيله", "هليسلا"])
                            is_remittance = any(w in line for w in ["حوالة", "ةلاوح", "حواله", "هلاوح"])
                            is_expense = any(w in line for w in ["مصاريف", "فيراصم", "بترول", "لورتب", "حماله", "هلاح", "نقل", "لقن", "طحانه", "كهرباء"])
                            is_salary = any(w in line for w in ["سلف", "فلس", "راتب", "بتار"])

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

                            if len(v_nums) >= 2:
                                debit, credit = v_nums[0], v_nums[1]
                            elif len(v_nums) == 1:
                                if cat in ["مبيعات نقدية", "مقبوضات ودفعات عملاء", "حوالات مستلمة"]:
                                    debit = v_nums[0]
                                else:
                                    credit = v_nums[0]

                            records.append({
                                "التاريخ": tx_date,
                                "العملة": curr_code,
                                "التصنيف": cat,
                                "مدين (وارد)": debit,
                                "دائن (صادر)": credit,
                                "البيان": line.strip()
                            })

            if records:
                df = pd.DataFrame(records)
                st.success(f"تم تصنيف وتحليل {len(df):,} حركة مالية بنجاح!")

                currencies = df["العملة"].unique().tolist()
                sel_curr = st.selectbox("اختر العملة لعرض التحليل:", currencies)
                df_c = df[df["العملة"] == sel_curr]

                # الحسابات الإجمالية
                sales = df_c[df_c["التصنيف"] == "مبيعات نقدية"]["مدين (وارد)"].sum()
                if sales == 0:
                    sales = df_c[df_c["التصنيف"] == "مبيعات نقدية"]["دائن (صادر)"].sum()

                returns = df_c[df_c["التصنيف"] == "مردودات مبيعات"]["دائن (صادر)"].sum()
                if returns == 0:
                    returns = df_c[df_c["التصنيف"] == "مردودات مبيعات"]["مدين (وارد)"].sum()

                remit = df_c[df_c["التصنيف"] == "حوالات مستلمة"]["مدين (وارد)"].sum()
                if remit == 0:
                    remit = df_c[df_c["التصنيف"] == "حوالات مستلمة"]["دائن (صادر)"].sum()

                receipts = df_c[df_c["التصنيف"] == "مقبوضات ودفعات عملاء"]["مدين (وارد)"].sum()
                if receipts == 0:
                    receipts = df_c[df_c["التصنيف"] == "مقبوضات ودفعات عملاء"]["دائن (صادر)"].sum()

                expenses = df_c[df_c["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]["دائن (صادر)"].sum()
                if expenses == 0:
                    expenses = df_c[df_c["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]["مدين (وارد)"].sum()

                deposits = df_c[df_c["التصنيف"] == "توريدات وإيداعات بنكية"]["دائن (صادر)"].sum()
                if deposits == 0:
                    deposits = df_c[df_c["التصنيف"] == "توريدات وإيداعات بنكية"]["مدين (وارد)"].sum()

                net_sales = sales - returns

                # الكروت العلوية
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"إجمالي المبيعات ({sel_curr})", f"{sales:,.2f}")
                c2.metric(f"المردودات ({sel_curr})", f"{returns:,.2f}")
                c3.metric(f"صافي المبيعات ({sel_curr})", f"{net_sales:,.2f}")
                c4.metric(f"الحوالات المستلمة ({sel_curr})", f"{remit:,.2f}")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric(f"مقبوضات ودفعات", f"{receipts:,.2f}")
                c6.metric(f"المصروفات والسلف", f"{expenses:,.2f}")
                c7.metric(f"الإيداعات والتوريدات", f"{deposits:,.2f}")
                c8.metric(f"صافي النقد التقديري", f"{(sales + receipts - expenses - deposits):,.2f}")

                st.markdown("---")
                st.write("### ملخص الحركات حسب البند المالي:")
                cat_sum = df_c.groupby("التصنيف")[["مدين (وارد)", "دائن (صادر)"]].sum().reset_index()
                st.dataframe(cat_sum.style.format({"مدين (وارد)": "{:,.2f}", "دائن (صادر)": "{:,.2f}"}), use_container_width=True)

                st.write("### كشف الحركات التفصيلي:")
                filter_cat = st.multiselect("تصفية بحسب البند:", options=df_c["التصنيف"].unique(), default=df_c["التصنيف"].unique())
                st.dataframe(df_c[df_c["التصنيف"].isin(filter_cat)][["التاريخ", "التصنيف", "مدين (وارد)", "دائن (صادر)", "البيان"]], use_container_width=True)

                csv_data = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل التقرير كملف CSV (Excel)",
                    data=csv_data,
                    file_name="تحليل_كشف_اونكس.csv",
                    mime="text/csv"
                )
            else:
                st.warning("لم يتم العثور على أسطر عمليات صالحة.")

with tab2:
    st.subheader("📷 قراءة الإشعارات وتوليد القيود")
    key = st.text_input("مفتاح Gemini API:", type="password")
    up_img = st.file_uploader("صورة الإشعار", type=["jpg", "png", "jpeg"])
    if up_img and key:
        st.image(up_img, width=300)
        if st.button("توليد القيد المحاسبي"):
            try:
                import google.generativeai as genai
                from PIL import Image
                genai.configure(api_key=key)
                m = genai.GenerativeModel("gemini-2.5-flash")
                p = "استخرج من صورة الإشعار اسم العميل، المبلغ، الصراف، والتاريخ، ثم اكتب قيد اليومية لأونكس برو."
                with st.spinner("جاري التحليل..."):
                    res = m.generate_content([p, Image.open(up_img)])
                    st.markdown(res.text)
            except Exception as e:
                st.error(f"خطأ: {e}")
