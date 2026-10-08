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
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | نظام الفرز والتحليل الذكي")

tab1, tab2 = st.tabs(["📊 التحليل المالي الشامل (PDF)", "📷 مسح الإشعارات وتوليد القيود"])

with tab1:
    st.subheader("تحليل كشوفات الحساب وحركة الفرع")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري قراءة واستخراج الحركات بدقة..."):
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
                        if any(w in line for w in ["SAR", "سعودي", "يدوعس"]):
                            curr_code = "SAR"
                        elif any(w in line for w in ["YER", "يمني", "ينمي"]):
                            curr_code = "YER"
                        elif any(w in line for w in ["USD", "دولار", "رالود"]):
                            curr_code = "USD"

                        # استخراج التاريخ
                        d_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if d_match:
                            tx_date = d_match.group(1)

                            # تصنيف الحركة أولاً لتحديد العمود الصحيح
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

                            # استخراج الأرقام التي تحتوي على فواصل عشرية أو آلاف (المبالغ المالية فقط)
                            # واستبعاد أرقام المستندات العادية المكونة من 3-4 أرقام بدون فواصل
                            money_matches = re.findall(r'(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2})', line)
                            
                            real_amount = 0.0
                            if money_matches:
                                # أخذ أكبر مبلغ مالي تم العثور عليه في السطر
                                amounts_clean = [float(m.replace(",", "")) for m in money_matches]
                                real_amount = max(amounts_clean)
                            else:
                                # البحث الاحتياطي عن الأرقام العادية واستبعاد أرقام المستندات القصيرة
                                simple_nums = re.findall(r'\b\d+\b', line)
                                candidates = [float(x) for x in simple_nums if len(x) >= 4 and float(x) < 50000000]
                                if candidates:
                                    real_amount = candidates[0]

                            debit = 0.0
                            credit = 0.0

                            # توجيه المبلغ بحسب طبيعة الحساب
                            if cat in ["مبيعات نقدية", "مقبوضات ودفعات عملاء", "حوالات مستلمة"]:
                                debit = real_amount
                            elif cat in ["مردودات مبيعات", "مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين", "توريدات وإيداعات بنكية"]:
                                credit = real_amount
                            else:
                                debit = real_amount

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
                    currencies = df["العملة"].unique().tolist()
                    sel_curr = st.selectbox("العملة:", currencies)
                with col_f:
                    # تصفية سهلة ومباشرة بضغطة واحدة
                    filter_option = st.selectbox(
                        "🔍 الاستعلام عن بند محدد:",
                        ["عرض كل العمليات", "المبيعات النقدية فقط", "المقبوضات والدفعات فقط", "المصروفات والسلف فقط", "التوريدات والإيداعات فقط", "المردودات فقط"]
                    )

                df_c = df[df["العملة"] == sel_curr]

                # المجاميع الأساسية
                total_sales = df_c[df_c["التصنيف"] == "مبيعات نقدية"]["المبلغ"].sum()
                total_returns = df_c[df_c["التصنيف"] == "مردودات مبيعات"]["المبلغ"].sum()
                total_receipts = df_c[df_c["التصنيف"] == "مقبوضات ودفعات عملاء"]["المبلغ"].sum()
                total_expenses = df_c[df_c["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]["المبلغ"].sum()
                total_deposits = df_c[df_c["التصنيف"] == "توريدات وإيداعات بنكية"]["المبلغ"].sum()
                net_sales = total_sales - total_returns

                # عرض المؤشرات المالية
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"إجمالي المبيعات ({sel_curr})", f"{total_sales:,.2f}")
                c2.metric(f"المردودات ({sel_curr})", f"{total_returns:,.2f}")
                c3.metric(f"صافي المبيعات ({sel_curr})", f"{net_sales:,.2f}")
                c4.metric(f"المقبوضات والدفعات ({sel_curr})", f"{total_receipts:,.2f}")

                c5, c6, c7, c8 = st.columns(4)
                c5.metric("المصروفات والسلف", f"{total_expenses:,.2f}")
                c6.metric("الإيداعات والتوريدات", f"{total_deposits:,.2f}")
                c7.metric("صافي النقد التقديري", f"{(net_sales + total_receipts - total_expenses - total_deposits):,.2f}")
                c8.metric("عدد العمليات", f"{len(df_c):,}")

                st.markdown("---")

                # تطبيق الاستعلام المختار
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

                st.write(f"### جدول العمليات ({filter_option}) - الإجمالي: {view_df['المبلغ'].sum():,.2f} {sel_curr}:")
                st.dataframe(view_df[["التاريخ", "التصنيف", "المبلغ", "البيان"]], use_container_width=True)

                csv_data = view_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 تحميل النتائج كملف Excel (CSV)",
                    data=csv_data,
                    file_name=f"تقرير_{filter_option}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("لم يتم العثور على أسطر صالحة.")

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
