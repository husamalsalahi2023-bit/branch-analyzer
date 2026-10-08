import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="منصة التحليل المالي - مؤسسة حسام الصلاحي", layout="wide")

st.markdown("""
<style>
    .reportview-container, .main .block-container { direction: rtl; text-align: right; }
    h1, h2, h3, h4, p, span, div { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 منصة التحليل المالي وحركة الحسابات")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | تحليل تقارير أونكس برو")

tab1, tab2 = st.tabs(["📊 التحليل المالي الشامل (PDF)", "📷 مسح الإشعارات وتوليد القيود"])

with tab1:
    st.subheader("تحليل كشوفات الحساب وحركة الفرع")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري قراءة واستخراج العمليات والبنود..."):
            records = []
            curr_code = "YER"

            with pdfplumber.open(uploaded_pdf) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split("\n")
                    for line in lines:
                        # كشف العملة
                        if "SAR" in line or "سعودي" in line:
                            curr_code = "SAR"
                        elif "YER" in line or "يمني" in line:
                            curr_code = "YER"
                        elif "USD" in line or "دولار" in line:
                            curr_code = "USD"

                        # التحقق من وجود تاريخ
                        d_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if d_match:
                            tx_date = d_match.group(1)

                            # استخراج المبالغ
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

                            if len(v_nums) >= 2:
                                debit, credit = v_nums[0], v_nums[1]
                            elif len(v_nums) == 1:
                                if any(x in line for x in ["مبيعات", "قبض", "وارد", "توريد", "دفعه"]):
                                    debit = v_nums[0]
                                else:
                                    credit = v_nums[0]

                            # تصنيف مرن يشمل الحروف العربية بشتى أشكالها
                            cat = "حركات أخرى"
                            if any(x in line for x in ["مردود", "مرتجع"]):
                                cat = "مردودات مبيعات"
                            elif any(x in line for x in ["مبيعات نقدية", "فاتورة مبيعات", "مبيعات"]):
                                cat = "مبيعات"
                            elif any(x in line for x in ["حوالة", "حواله", "اشعار حوالة"]):
                                cat = "حوالات مستلمة"
                            elif any(x in line for x in ["سند قبض", "دفعه", "سداد"]):
                                cat = "مقبوضات ودفعات عملاء"
                            elif any(x in line for x in ["ايداع", "القطيبي", "دره الجزيره", "السيله"]):
                                cat = "توريدات وإيداعات بنكية"
                            elif any(x in line for x in ["مصاريف", "مصروف", "بترول", "حماله", "نقل", "طحانه", "كهرباء"]):
                                cat = "مصاريف تشغيلية ونقل"
                            elif any(x in line for x in ["سلف", "راتب"]):
                                cat = "سلف ومستحقات موظفين"
                            elif any(x in line for x in ["مشتريات"]):
                                cat = "مشتريات"
                            elif any(x in line for x in ["صرف عملة", "مصارفه"]):
                                cat = "مصارفة وصرف عملة"

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
                st.success(f"تم تحليل {len(df):,} حركة مالية بنجاح!")

                currencies = df["العملة"].unique().tolist()
                sel_curr = st.selectbox("اختر العملة:", currencies)
                df_c = df[df["العملة"] == sel_curr]

                # حسابات المؤشرات
                sales = df_c[df_c["التصنيف"] == "مبيعات"]["مدين (وارد)"].sum()
                returns = df_c[df_c["التصنيف"] == "مردودات مبيعات"]["دائن (صادر)"].sum()
                if returns == 0:
                    returns = df_c[df_c["التصنيف"] == "مردودات مبيعات"]["مدين (وارد)"].sum()

                remit = df_c[df_c["التصنيف"] == "حوالات مستلمة"]["مدين (وارد)"].sum()
                if remit == 0:
                    remit = df_c[df_c["التصنيف"] == "حوالات مستلمة"]["دائن (صادر)"].sum()

                receipts = df_c[df_c["التصنيف"] == "مقبوضات ودفعات عملاء"]["مدين (وارد)"].sum()
                expenses = df_c[df_c["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]["دائن (صادر)"].sum()
                deposits = df_c[df_c["التصنيف"] == "توريدات وإيداعات بنكية"]["دائن (صادر)"].sum()

                # عرض المؤشرات
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"إجمالي المبيعات ({sel_curr})", f"{sales:,.2f}")
                c2.metric(f"المردودات ({sel_curr})", f"{returns:,.2f}")
                c3.metric(f"صافي المبيعات ({sel_curr})", f"{sales - returns:,.2f}")
                c4.metric(f"الحوالات المستلمة ({sel_curr})", f"{remit:,.2f}")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("مقبوضات ودفعات", f"{receipts:,.2f}")
                c6.metric("المصروفات والسلف", f"{expenses:,.2f}")
                c7.metric("الإيداعات والتوريدات", f"{deposits:,.2f}")
                c8.metric("صافي النقد التقديري", f"{(sales + receipts - expenses - deposits):,.2f}")

                st.markdown("---")
                st.write("### ملخص الحركات حسب البند المالي:")
                cat_sum = df_c.groupby("التصنيف")[["مدين (وارد)", "دائن (صادر)"]].sum().reset_index()
                st.dataframe(cat_sum, use_container_width=True)

                st.write("### كشف الحركات التفصيلي:")
                st.dataframe(df_c[["التاريخ", "التصنيف", "مدين (وارد)", "دائن (صادر)", "البيان"]], use_container_width=True)

                # تنزيل ملف CSV بدون أخطاء مكتبات
                csv_data = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل التقرير كملف CSV (يفتح مباشرة في Excel)",
                    data=csv_data,
                    file_name="تقرير_تحليل_حساب_اونكس.csv",
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
