import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="منصة التحليل المالي والعمليات - مؤسسة حسام الصلاحي", layout="wide")

# تنسيق الاتجاه والواجهة للغة العربية
st.markdown("""
<style>
    .reportview-container, .main .block-container { direction: rtl; text-align: right; }
    h1, h2, h3, h4, p, span, div { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stMetric {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 منصة التحليل المالي وحركة الحسابات")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة | نظام التحليل الذكي لتقارير أونكس برو")

tab1, tab2 = st.tabs(["📊 التحليل المالي الشامل (PDF)", "📷 مسح الإشعارات وتوليد القيود"])

# ======================= التبويب الأول: التحليل المالي =======================
with tab1:
    st.subheader("تحليل كشوفات الحساب، المبيعات، الحوالات، والمخزون")
    uploaded_pdf = st.file_uploader("ارفع تقرير أونكس برو بصيغة PDF (كشف حساب، مبيعات، تكلفة، حركة مخزون)", type=["pdf"])

    if uploaded_pdf:
        with st.spinner("جاري قراءة صفحات التقرير واستخراج الحركات المالية والعملات..."):
            records = []
            current_currency = "YER"
            current_account_name = "الصندوق الرئيسي"
            current_account_no = ""

            with pdfplumber.open(uploaded_pdf) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    lines = text.split("\n")
                    for line in lines:
                        # 1. كشف العملة
                        if "SAR" in line or "سعودي" in line:
                            current_currency = "SAR"
                        elif "YER" in line or "يمني" in line:
                            current_currency = "YER"
                        elif "USD" in line or "دولار" in line:
                            current_currency = "USD"

                        # 2. كشف الحساب
                        if "رقم الحساب" in line:
                            acc_m = re.search(r'\b(12\d{7})\b', line)
                            if acc_m:
                                current_account_no = acc_m.group(1)
                        if "الصناديق" in line:
                            current_account_name = "الصناديق"
                        elif "العملاء" in line:
                            current_account_name = "العملاء"
                        elif "المخزون" in line:
                            current_account_name = "المخزون وتكلفة المبيعات"

                        # 3. استخراج أسطر العمليات بحسب التاريخ DD/MM/YYYY
                        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', line)
                        if date_match:
                            tx_date = date_match.group(1)
                            
                            # التقاط كل المبالغ العددية
                            raw_nums = re.findall(r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', line)
                            valid_nums = []
                            for n in raw_nums:
                                clean = n.replace(",", "")
                                try:
                                    v = float(clean)
                                    # استبعاد التواريخ وأرقام الحسابات
                                    if 0.01 <= v < 50000000 and len(clean.split('.')[0]) <= 8:
                                        valid_nums.append(v)
                                except:
                                    pass

                            debit = 0.0   # مدين / وارد
                            credit = 0.0  # دائن / صادر

                            if len(valid_nums) >= 2:
                                debit = valid_nums[0]
                                credit = valid_nums[1]
                            elif len(valid_nums) == 1:
                                val = valid_nums[0]
                                if any(k in line for k in ["مبيعات", "قبض", "وارد", "توريد", "دفعه من الحساب", "حوالة مستلمة", "إستلام"]):
                                    debit = val
                                else:
                                    credit = val

                            # 4. تصنيف دقيق وذكي للبند المحاسبي
                            category = "حركات عامة أخرى"
                            if "مردود" in line:
                                category = "مردودات مبيعات"
                            elif "مبيعات" in line and "تكلفة" not in line:
                                category = "مبيعات"
                            elif "تكلفة مبيعات" in line or "المجموعة 201" in line:
                                category = "تكلفة مبيعات (بضاعة مباعة)"
                            elif any(k in line for k in ["حوالة مستلمة", "حواله مستلمه", "حواله نقديه", "حوالة مستلمة", "اشعار حوالة"]):
                                category = "حوالات مستلمة"
                            elif any(k in line for k in ["سند قبض", "دفعه من الحساب", "دفعه مناولة", "سداد"]):
                                category = "مقبوضات ودفعات عملاء"
                            elif any(k in line for k in ["ايداع صندوق", "القطيبي", "دره الجزيره", "السيله", "ايداع"]):
                                category = "توريدات وإيداعات بنكية"
                            elif any(k in line for k in ["مصاريف الفرع", "بترول", "كهرباء", "حماله", "نقل", "طحانه"]):
                                category = "مصاريف تشغيلية ونقل"
                            elif any(k in line for k in ["سلف", "راتب"]):
                                category = "سلف ومستحقات موظفين"
                            elif "مشتريات" in line:
                                category = "مشتريات"
                            elif any(k in line for k in ["صرف عملة", "مصارفه"]):
                                category = "مصارفة وصرف عملة"

                            records.append({
                                "التاريخ": tx_date,
                                "الحساب": f"{current_account_name} ({current_account_no})" if current_account_no else current_account_name,
                                "العملة": current_currency,
                                "التصنيف": category,
                                "مدين (وارد)": debit,
                                "دائن (صادر)": credit,
                                "البيان الكامل": line.strip()
                            })

            if records:
                df = pd.DataFrame(records)
                st.success(f"تم تحليل {len(df):,} عملية مالية بنجاح عبر صفحات الكشف!")

                # شريط خيارات الفلترة
                col_sel1, col_sel2 = st.columns([1, 2])
                with col_sel1:
                    currencies = df["العملة"].unique().tolist()
                    chosen_curr = st.selectbox("اختر العملة المطلوبة:", currencies)
                with col_sel2:
                    view_mode = st.radio("نوع العرض:", ["📊 ملخص إجمالي ومؤشرات الربحية", "📑 جدول تحليلي تفصيلي"], horizontal=True)

                df_curr = df[df["العملة"] == chosen_curr]

                # حساب المجاميع
                total_sales = df_curr[df_curr["التصنيف"] == "مبيعات"]["مدين (وارد)"].sum()
                total_returns = df_curr[df_curr["التصنيف"] == "مردودات مبيعات"]["دائن (صادر)"].sum()
                if total_returns == 0:
                    total_returns = df_curr[df_curr["التصنيف"] == "مردودات مبيعات"]["مدين (وارد)"].sum()

                net_sales = total_sales - total_returns

                total_remittances = df_curr[df_curr["التصنيف"] == "حوالات مستلمة"]["مدين (وارد)"].sum()
                if total_remittances == 0:
                    total_remittances = df_curr[df_curr["التصنيف"] == "حوالات مستلمة"]["دائن (صادر)"].sum()

                total_receipts = df_curr[df_curr["التصنيف"] == "مقبوضات ودفعات عملاء"]["مدين (وارد)"].sum()
                total_expenses = df_curr[df_curr["التصنيف"].isin(["مصاريف تشغيلية ونقل", "سلف ومستحقات موظفين"])]["دائن (صادر)"].sum()
                total_deposits = df_curr[df_curr["التصنيف"] == "توريدات وإيداعات بنكية"]["دائن (صادر)"].sum()
                
                total_cogs = df_curr[df_curr["التصنيف"] == "تكلفة مبيعات (بضاعة مباعة)"]["دائن (صادر)"].sum()
                if total_cogs == 0:
                    total_cogs = df_curr[df_curr["التصنيف"] == "تكلفة مبيعات (بضاعة مباعة)"]["مدين (وارد)"].sum()

                gross_profit = net_sales - total_cogs if total_cogs > 0 else 0.0
                profit_margin = (gross_profit / net_sales * 100) if (net_sales > 0 and total_cogs > 0) else 0.0

                if view_mode == "📊 ملخص إجمالي ومؤشرات الربحية":
                    # صف المبيعات والتحصيلات
                    r1_1, r1_2, r1_3, r1_4 = st.columns(4)
                    r1_1.metric(f"إجمالي المبيعات ({chosen_curr})", f"{total_sales:,.2f}")
                    r1_2.metric(f"المردودات ({chosen_curr})", f"{total_returns:,.2f}")
                    r1_3.metric(f"صافي المبيعات ({chosen_curr})", f"{net_sales:,.2f}")
                    r1_4.metric(f"الحوالات المستلمة ({chosen_curr})", f"{total_remittances:,.2f}")

                    # صف التكاليف والأرباح
                    r2_1, r2_2, r2_3, r2_4 = st.columns(4)
                    r2_1.metric(f"دفعات ومقبوضات نقدية", f"{total_receipts:,.2f}")
                    r2_2.metric(f"إجمالي المصروفات والسلف", f"{total_expenses:,.2f}")
                    r2_3.metric(f"إجمالي الإيداعات والتوريدات", f"{total_deposits:,.2f}")
                    if total_cogs > 0:
                        r2_4.metric(f"هامش الربح التقديري", f"{profit_margin:.1f}%", f"ربح: {gross_profit:,.2f}")
                    else:
                        r2_4.metric(f"تكلفة المبيعات (COGS)", "غير متوفرة بالكشف", "يتطلب كشف تكلفة")

                    st.markdown("---")
                    st.write("#### توزيع الحركات حسب البند المالي:")
                    cat_summary = df_curr.groupby("التصنيف")[["مدين (وارد)", "دائن (صادر)"]].sum().reset_index()
                    cat_summary["صافي الحركة"] = cat_summary["مدين (وارد)"] - cat_summary["دائن (صادر)"]
                    st.dataframe(cat_summary.style.format({"مدين (وارد)": "{:,.2f}", "دائن (صادر)": "{:,.2f}", "صافي الحركة": "{:,.2f}"}), use_container_width=True)

                else:
                    st.write("#### جدول العمليات التفصيلي:")
                    filter_cat = st.multiselect("تصفية بحسب نوع الحركة:", options=df_curr["التصنيف"].unique(), default=df_curr["التصنيف"].unique())
                    filtered_df = df_curr[df_curr["التصنيف"].isin(filter_cat)]
                    st.dataframe(filtered_df[["التاريخ", "الحساب", "التصنيف", "مدين (وارد)", "دائن (صادر)", "البيان الكامل"]], use_container_width=True)

                # زر تحميل Excel مدمج
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='كل العمليات')
                st.download_button(
                    label="📥 تحميل التقرير المالي كاملاً بصيغة Excel",
                    data=excel_buffer.getvalue(),
                    file_name="تحليل_اونكس_المالي_الشامل.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("لم يتم العثور على حركات مالية واضحة في الملف.")

# ======================= التبويب الثاني: فاحص الإشعارات =======================
with tab2:
    st.subheader("📷 قراءة صور الحوالات والسندات وتوليد قيود أونكس برو")
    key = st.text_input("أدخل مفتاح Gemini API:", type="password")
    uploaded_image = st.file_uploader("اختر صورة إشعار بنكي (القطيبي، الكريمي، البسيري، بن دول، إلخ)", type=["jpg", "png", "jpeg"])

    if uploaded_image and key:
        st.image(uploaded_image, width=320, caption="الإشعار المرفوع")
        if st.button("تحليل الإشعار وتوليد القيد المحاسبي"):
            try:
                import google.generativeai as genai
                from PIL import Image
                genai.configure(api_key=key)
                ai_model = genai.GenerativeModel("gemini-2.5-flash")
                
                prompt = """
                أنت مدقق ومحاسب لنظام أونكس برو في مؤسسة تجارية. استخرج من هذا الإشعار بدقة تامة:
                1. اسم العميل أو المحول
                2. المبلغ بدقة والعملة (SAR أو YER)
                3. الصراف / البنك (مثل القطيبي، الكريمي، إلخ)
                4. رقم الحوالة / المرجع
                5. تاريخ العملية
                ثم اكتب القيد المحاسبي المزدوج الجاهز للإدخال في أونكس برو (من حـ/ ... إلى حـ/ ...).
                """
                with st.spinner("جاري التحليل واستخراج القيد..."):
                    res = ai_model.generate_content([prompt, Image.open(uploaded_image)])
                    st.success("تم استخراج تفاصيل القيد:")
                    st.markdown(res.text)
            except Exception as err:
                st.error(f"خطأ: {err}")
