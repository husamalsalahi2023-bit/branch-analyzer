import streamlit as st
import pdfplumber
import pandas as pd
import re
from PIL import Image
from google import genai

st.set_page_config(
    page_title="المساعد المالي والتشغيلي - مؤسسة حسام الصلاحي",
    page_icon="🏢",
    layout="centered"
)

st.markdown("""
<style>
    .reportview-container { direction: rtl; }
    div[data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 منصة العمليات والقيود اليومية")
st.caption("مؤسسة حسام الصلاحي التجارية - الإدارة العامة")

tab_scanner, tab_pdf = st.tabs(["📸 ماسح الإشعارات ومولد القيود", "📊 تحليل كشف الفرع (PDF)"])

# ========================================================
# التبويب الأول: الماسح الذكي لإشعارات وسندات البنوك والصرافة
# ========================================================
with tab_scanner:
    st.subheader("📸 استخراج القيود آلياً من صور الإشعارات")
    st.write("التقط صورة بكاميرا الجوال أو ارفع صورة إشعار (القطيبي، الكريمي، البسيري، أبو وجدي، ...إلخ).")

    api_key = st.text_input("أدخل مفتاح Gemini API:", type="password", help="احصل عليه مجاناً من Google AI Studio")

    input_mode = st.radio("مصدر الإشعار:", ["رفع صورة / ملف من المعرض", "استخدام كاميرا الجوال مباشرة"], horizontal=True)

    uploaded_image = None
    if input_mode == "استخدام كاميرا الجوال مباشرة":
        uploaded_image = st.camera_input("التقط صورة السند / الإشعار")
    else:
        uploaded_image = st.file_uploader("اختر صورة الإشعار (JPG, PNG)", type=["jpg", "jpeg", "png"])

    nature_hint = st.selectbox(
        "نوع الحركة (اختياري لتوجيه الذكاء الاصطناعي):",
        ["اكتشاف تلقائي ذكي", "سند قبض / استلام حوالة من عميل", "سند صرف / سداد لمورد", "سند صرف مصاريف تشغيلية ونقل", "تحويل نقدي بين الحسابات"]
    )

    if uploaded_image and st.button("🚀 تحليل الإشعار وتوليد القيد المحاسبي", type="primary"):
        if not api_key:
            st.error("⚠️ يرجى إدخال مفتاح Gemini API أولاً لإتمام التحليل بالذكاء الاصطناعي.")
        else:
            with st.spinner("جاري قراءة نص السند وتفكيك الحسابات والمبالغ..."):
                try:
                    img = Image.open(uploaded_image)
                    client = genai.Client(api_key=api_key)

                    prompt = f"""
                    أنت خبير محاسبي معتمد لنظام Onyx Pro ERP في مؤسسة تجارية باليمن.
                    قم بفحص صورة الإشعار المرفقة واستخرج البيانات وصياغة القيد المحاسبي المزدوج بدقة.
                    توجيه المستخدم: {nature_hint}.

                    المطلوب استخراجه وعرضه بالترتيب التالي بشكل احترافي ومنسق:
                    1. نوع المستند والحركة: (مثلاً: سند قبض بنكي، سند صرف حوالة، إشعار قيد دائن/مدين).
                    2. المبلغ والعملة: بدقة تامة (ريال يمني YER أو ريال سعودي SAR أو دولار USD).
                    3. التاريخ ورقم المرجع / الإشعار / الحوالة.
                    4. الطرف الأول (المصدر/المحول): اسمه ورقم حسابه إن وجد.
                    5. الطرف الثاني (المستفيد/المستلم): اسمه ورقم حسابه إن وجد.
                    6. القيد المحاسبي المزدوج الجاهز للترحيل في أونكس برو:
                       - من حـ/ [اسم الحساب والجهة المنفذة - مدين] : المبلغ العملة
                       - إلى حـ/ [اسم الحساب والجهة المقابلة - دائن] : المبلغ العملة
                    7. نص البيان النموذجي (الشرح) المكتوب في السند.
                    8. ملخص واتساب جاهز للنسخ والإرسال للمحاسب بنقرة واحدة.
                    """

                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[img, prompt]
                    )

                    st.success("✅ تم تحليل الإشعار بنجاح!")
                    st.markdown(response.text)

                except Exception as e:
                    st.error(f"حدث خطأ أثناء المعالجة: {str(e)}")

# ========================================================
# التبويب الثاني: تحليل كشف PDF اليومي للفرع
# ========================================================
with tab_pdf:
    st.subheader("تحليل كشف الحساب التحليلي للفرع (PDF)")
    uploaded_pdf = st.file_uploader("ارفع كشف أونكس برو اليومي بصيغة PDF", type=["pdf"], key="pdf_tab_uploader")

    def process_branch_pdf(pdf_stream):
        yer_sales = 0.0
        yer_expenses = 0.0
        sar_expenses = 0.0
        rows_data = []

        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                tables = page.extract_tables()
                is_yer = "YER" in text or "ريال يمني" in text
                curr = "YER" if is_yer else "SAR"

                for table in tables:
                    for r in table:
                        cleaned = [c.replace("\n", " ").strip() if c else "" for c in r]
                        line = " ".join(cleaned)

                        if "مبيعات نقدية" in line or "فاتورة مبيعات نقد" in line:
                            for cell in cleaned:
                                val = cell.replace(",", "")
                                if re.match(r"^\d+(\.\d+)?$", val) and float(val) > 0:
                                    if is_yer: yer_sales += float(val)
                                    rows_data.append({"البيان": "مبيعات نقدية", "المبلغ": float(val), "العملة": curr, "النوع": "إيراد"})
                                    break

                        if "سند صرف نقدي" in line:
                            for cell in cleaned:
                                val = cell.replace(",", "")
                                if re.match(r"^\d+(\.\d+)?$", val) and float(val) > 0:
                                    if is_yer: yer_expenses += float(val)
                                    else: sar_expenses += float(val)
                                    rows_data.append({"البيان": line[:40], "المبلغ": float(val), "العملة": curr, "النوع": "صرف"})
                                    break

        return yer_sales, yer_expenses, sar_expenses, rows_data

    if uploaded_pdf:
        with st.spinner("جاري تفكيك الكشف المحاسبي..."):
            sales_y, exp_y, exp_s, items = process_branch_pdf(uploaded_pdf)

        st.success("تم استخراج حركة الفرع بنجاح!")
        m1, m2 = st.columns(2)
        m1.metric("إجمالي المبيعات (YER)", f"{sales_y:,.0f}")
        m2.metric("المصروفات النقدية (YER)", f"{exp_y:,.0f}")

        m3, m4 = st.columns(2)
        m3.metric("صافي النقد المتبقي (YER)", f"{(sales_y - exp_y):,.0f}")
        m4.metric("منصرف نقدي (SAR)", f"{exp_s:,.2f}")

        if items:
            st.divider()
            df = pd.DataFrame(items)
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 تنزيل كملف Excel (CSV)", data=csv, file_name="حركة_الفرع_اليومية.csv", mime="text/csv")