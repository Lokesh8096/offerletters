import streamlit as st
import pandas as pd
from io import BytesIO, StringIO
from zipfile import ZipFile
from datetime import date
import re
import os
import time
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from dotenv import load_dotenv

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# --------------------------------------------------
# Load .env
# --------------------------------------------------

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD", "")
FROM_NAME = os.getenv("FROM_NAME", "NIAT Team")
REPLY_TO = os.getenv("REPLY_TO", "")
EMAIL_DELAY_SECONDS = int(os.getenv("EMAIL_DELAY_SECONDS", "2"))


# --------------------------------------------------
# Streamlit Config
# --------------------------------------------------

st.set_page_config(
    page_title="PDF Offer Letter Generator", page_icon="📄", layout="wide"
)


# --------------------------------------------------
# Fixed Values
# --------------------------------------------------

FIXED_OFFER_DATE = "01-06-2026"
FIXED_START_DATE = "01-06-2026"
FIXED_END_DATE = "30-06-2026"
FIXED_LOCATION = "Remote"

REQUIRED_COLUMNS = ["company_name", "student_name", "email", "phone", "role"]


# --------------------------------------------------
# Helper Functions
# --------------------------------------------------


def normalize_column_name(col):
    col = str(col).strip().lower()
    col = re.sub(r"[^a-z0-9]+", "_", col)
    col = col.strip("_")
    return col


def prepare_dataframe(df):
    df = df.copy()
    df.columns = [normalize_column_name(col) for col in df.columns]
    df = df.dropna(how="all")
    df = df.fillna("")
    return df.astype(str)


def safe_filename(value):
    value = str(value).strip()
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value if value else "student"


def clean_mobile_number(phone):
    phone = str(phone).strip()
    phone_digits = re.sub(r"\D", "", phone)

    if phone_digits:
        return phone_digits

    return "no_mobile"


def generate_pdf_filename(student_name, phone, index=None):
    clean_name = safe_filename(student_name)
    clean_phone = clean_mobile_number(phone)

    if index is not None:
        return f"Offer_Letter_{clean_name}_{clean_phone}_{index}.pdf"

    return f"Offer_Letter_{clean_name}_{clean_phone}.pdf"


def read_pasted_data(pasted_data):
    first_line = pasted_data.splitlines()[0]

    if "\t" in first_line:
        return pd.read_csv(StringIO(pasted_data), sep="\t", dtype=str)
    else:
        return pd.read_csv(StringIO(pasted_data), dtype=str)


def validate_columns(df):
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return missing_columns


def is_valid_email(email):
    email = str(email).strip()
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email))


def escape_html(text):
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --------------------------------------------------
# PDF Generation
# --------------------------------------------------


def generate_offer_letter_pdf(row_data):
    buffer = BytesIO()

    company_name = str(row_data.get("company_name", "")).strip()
    student_name = str(row_data.get("student_name", "")).strip()
    email = str(row_data.get("email", "")).strip()
    phone = str(row_data.get("phone", "")).strip()
    role = str(row_data.get("role", "")).strip()

    offer_date = FIXED_OFFER_DATE
    start_date = FIXED_START_DATE
    end_date = FIXED_END_DATE
    location = FIXED_LOCATION

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=24,
        bottomMargin=24,
    )

    styles = getSampleStyleSheet()

    company_style = ParagraphStyle(
        "CompanyStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=17,
        leading=20,
        spaceAfter=6,
        textColor=colors.black,
    )

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        alignment=TA_CENTER,
        fontSize=15,
        leading=18,
        spaceAfter=12,
        textColor=colors.black,
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=13.5,
        alignment=TA_LEFT,
        spaceAfter=6,
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=12,
        leading=14,
        spaceBefore=5,
        spaceAfter=6,
        textColor=colors.black,
    )

    story = []

    story.append(Paragraph(f"<b>{escape_html(company_name)}</b>", company_style))
    story.append(Paragraph("<b> Confirmation Letter</b>", title_style))

    story.append(Paragraph(f"<b>Date:</b> {offer_date}", normal_style))
    story.append(Spacer(1, 4))

    story.append(Paragraph(f"Dear <b>{escape_html(student_name)}</b>,", normal_style))

    story.append(
        Paragraph(
            f"Greetings from <b>{escape_html(company_name)}</b>.",
            normal_style,
        )
    )

    # UPDATED LINE
    story.append(
        Paragraph(
            f"We are pleased to offer you the position of "
            f"<b>{escape_html(role)}</b> at our company.",
            normal_style,
        )
    )

    story.append(
        Paragraph(
            "Intended to provide practical exposure, real-time training, "
            "and work experience aligned with your growth.",
            normal_style,
        )
    )

    story.append(Paragraph("<b>Offer Details</b>", section_style))

    table_data = [
        ["Field", "Details"],
        ["Student Name", student_name],
        ["Email", email],
        ["Phone", phone],
        ["Role", role],
        ["Start Date", start_date],
        ["End Date", end_date],
        ["Location", location],
    ]

    table = Table(table_data, colWidths=[2.05 * inch, 4.75 * inch])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ]
        )
    )

    story.append(table)

    story.append(Spacer(1, 7))
    story.append(Paragraph("<b>Terms and Expectations</b>", section_style))

    story.append(
        Paragraph(
            "1. Maintain professionalism and complete assigned tasks within the given timelines.",
            normal_style,
        )
    )

    story.append(
        Paragraph(
            "2. Keep all business, customer, and work-related information confidential.",
            normal_style,
        )
    )

    story.append(
        Paragraph(
            "3. Internship completion certificate may be issued based on attendance, "
            "work completion, and performance.",
            normal_style,
        )
    )

    story.append(Spacer(1, 14))
    story.append(Paragraph("<b>Best Regards,</b>", normal_style))
    story.append(Paragraph(f"{escape_html(company_name)}", normal_style))

    doc.build(story)

    buffer.seek(0)
    return buffer


def create_pdf_records(df):
    records = []
    used_file_names = set()

    for index, row in df.iterrows():
        row_data = row.to_dict()

        pdf_buffer = generate_offer_letter_pdf(row_data)
        pdf_bytes = pdf_buffer.getvalue()

        student_name = row_data.get("student_name", f"student_{index + 1}")
        phone = row_data.get("phone", "no_mobile")

        file_name = generate_pdf_filename(student_name, phone)

        if file_name in used_file_names:
            file_name = generate_pdf_filename(student_name, phone, index + 1)

        used_file_names.add(file_name)

        records.append(
            {
                "index": index + 1,
                "company_name": str(row_data.get("company_name", "")).strip(),
                "student_name": str(row_data.get("student_name", "")).strip(),
                "email": str(row_data.get("email", "")).strip(),
                "phone": str(row_data.get("phone", "")).strip(),
                "role": str(row_data.get("role", "")).strip(),
                "file_name": file_name,
                "pdf_bytes": pdf_bytes,
            }
        )

    return records


def create_zip_from_records(records):
    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, "w") as zip_file:
        for record in records:
            zip_file.writestr(record["file_name"], record["pdf_bytes"])

    zip_buffer.seek(0)
    return zip_buffer


# --------------------------------------------------
# Email Sending
# --------------------------------------------------


def build_email_message(record):
    company_name = record["company_name"]
    student_name = record["student_name"]
    student_email = record["email"]
    file_name = record["file_name"]
    pdf_bytes = record["pdf_bytes"]

    subject = f"Offer Letter - {company_name}"

    plain_body = f"""Dear {student_name},

Please find attached your Confirmation letter for the opportunity at {company_name}.

Best Regards,
NIAT Team"""

    html_body = f"""
<p>Dear <b>{escape_html(student_name)}</b>,</p>

<p>Please find attached your Confirmation letter for the opportunity at <b>{escape_html(company_name)}</b>.</p>

<p>Best Regards,<br>
NIAT Team</p>
"""

    msg = EmailMessage()
    msg["From"] = formataddr((FROM_NAME, SMTP_EMAIL))
    msg["To"] = student_email
    msg["Subject"] = subject

    if REPLY_TO:
        msg["Reply-To"] = REPLY_TO

    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    msg.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=file_name
    )

    return msg


def send_emails_with_smtp(records, skip_duplicates=True):
    results = []

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise Exception("SMTP_EMAIL or SMTP_APP_PASSWORD is missing in .env file.")

    sent_keys = set()

    progress_bar = st.progress(0)
    status_box = st.empty()

    total = len(records)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)

        for idx, record in enumerate(records):
            student_name = record["student_name"]
            student_email = record["email"]
            phone = record["phone"]
            mobile_key = clean_mobile_number(phone)[-10:]
            duplicate_key = f"{student_email.lower()}_{mobile_key}"

            progress_bar.progress((idx + 1) / total)

            if not is_valid_email(student_email):
                results.append(
                    {
                        "student_name": student_name,
                        "email": student_email,
                        "phone": phone,
                        "file_name": record["file_name"],
                        "status": "FAILED",
                        "error": "Invalid email address",
                    }
                )
                status_box.warning(
                    f"Skipped invalid email: {student_name} - {student_email}"
                )
                continue

            if skip_duplicates and duplicate_key in sent_keys:
                results.append(
                    {
                        "student_name": student_name,
                        "email": student_email,
                        "phone": phone,
                        "file_name": record["file_name"],
                        "status": "DUPLICATE_SKIPPED",
                        "error": "Duplicate email + phone skipped",
                    }
                )
                status_box.info(f"Duplicate skipped: {student_name}")
                continue

            try:
                msg = build_email_message(record)
                server.send_message(msg)

                sent_keys.add(duplicate_key)

                results.append(
                    {
                        "student_name": student_name,
                        "email": student_email,
                        "phone": phone,
                        "file_name": record["file_name"],
                        "status": "SENT",
                        "error": "",
                    }
                )

                status_box.success(
                    f"Sent {idx + 1}/{total}: {student_name} - {student_email}"
                )

                if idx < total - 1:
                    time.sleep(EMAIL_DELAY_SECONDS)

            except Exception as e:
                results.append(
                    {
                        "student_name": student_name,
                        "email": student_email,
                        "phone": phone,
                        "file_name": record["file_name"],
                        "status": "FAILED",
                        "error": str(e),
                    }
                )

                status_box.error(f"Failed: {student_name} - {str(e)}")

    return pd.DataFrame(results)


# --------------------------------------------------
# Streamlit UI
# --------------------------------------------------

st.title("📄 Bulk PDF Offer Letter Generator + Email Sender")

st.write(
    "Generate internship offer letters as PDFs and send each student their own PDF by email."
)

st.divider()

st.subheader("Fixed Fields Used in Every Offer Letter")

fixed_col1, fixed_col2, fixed_col3, fixed_col4 = st.columns(4)

with fixed_col1:
    st.info(f"Offer Date: {FIXED_OFFER_DATE}")

with fixed_col2:
    st.info(f"Start Date: {FIXED_START_DATE}")

with fixed_col3:
    st.info(f"End Date: {FIXED_END_DATE}")

with fixed_col4:
    st.info(f"Location: {FIXED_LOCATION}")


st.divider()

st.subheader("SMTP Email Settings Status")

smtp_col1, smtp_col2, smtp_col3 = st.columns(3)

with smtp_col1:
    st.write(f"SMTP Host: `{SMTP_HOST}`")

with smtp_col2:
    st.write(f"SMTP Port: `{SMTP_PORT}`")

with smtp_col3:
    if SMTP_EMAIL and SMTP_APP_PASSWORD:
        st.success("SMTP configured")
    else:
        st.error("SMTP not configured. Check .env file.")


st.divider()

input_method = st.radio(
    "Choose Input Method",
    ["Single Offer Letter", "Paste Bulk Data", "Upload CSV / Excel"],
)

df = None


# --------------------------------------------------
# Single Offer Letter
# --------------------------------------------------

if input_method == "Single Offer Letter":
    st.subheader("Enter Student Details")

    col1, col2 = st.columns(2)

    with col1:
        company_name = st.text_input("Company Name")
        student_name = st.text_input("Student Name")
        email = st.text_input("Email")

    with col2:
        phone = st.text_input("Phone Number")
        role = st.text_input("Internship Role")

    if company_name and student_name and email and phone and role:
        df = pd.DataFrame(
            [
                {
                    "company_name": company_name,
                    "student_name": student_name,
                    "email": email,
                    "phone": phone,
                    "role": role,
                }
            ]
        )


# --------------------------------------------------
# Paste Bulk Data
# --------------------------------------------------

elif input_method == "Paste Bulk Data":
    st.subheader("Paste Bulk Data")

    sample_data = """company_name,student_name,email,phone,role
NXTWAVE,Lokesh,lokeshk80964@gmail.com,8096470590,SDE-1
NXTWAVE,Tirupathi Rao,kellatirupathirao049@gmail.com,6303639014,AI Automation Intern"""

    pasted_data = st.text_area(
        "Paste CSV data or copied Google Sheet data", value=sample_data, height=220
    )

    if pasted_data.strip():
        try:
            df = read_pasted_data(pasted_data)
            df = prepare_dataframe(df)
        except Exception as e:
            st.error(f"Invalid pasted data: {e}")


# --------------------------------------------------
# Upload CSV / Excel
# --------------------------------------------------

elif input_method == "Upload CSV / Excel":
    st.subheader("Upload CSV / Excel File")

    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file, dtype=str)
            else:
                df = pd.read_excel(uploaded_file, dtype=str)

            df = prepare_dataframe(df)

        except Exception as e:
            st.error(f"Unable to read file: {e}")


# --------------------------------------------------
# Preview, Generate, Send
# --------------------------------------------------

if df is not None and not df.empty:
    st.divider()

    missing_columns = validate_columns(df)

    if missing_columns:
        st.error("Missing required columns: " + ", ".join(missing_columns))
        st.write("Required columns are:")
        st.code("company_name, student_name, email, phone, role")

    else:
        st.subheader("Preview Data")
        st.dataframe(df, use_container_width=True)

        invalid_emails = df[~df["email"].apply(is_valid_email)]

        if not invalid_emails.empty:
            st.warning("Some emails are invalid. Fix them before sending.")
            st.dataframe(invalid_emails, use_container_width=True)

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            generate_clicked = st.button("Generate All PDFs", type="primary")

        with col_b:
            skip_duplicates = st.checkbox(
                "Skip duplicate email + phone while sending", value=True
            )

        if generate_clicked:
            records = create_pdf_records(df)
            zip_buffer = create_zip_from_records(records)

            st.session_state["pdf_records"] = records
            st.session_state["zip_bytes"] = zip_buffer.getvalue()

            st.success(f"{len(records)} PDF offer letters generated successfully.")

        if "zip_bytes" in st.session_state:
            st.download_button(
                label="Download Generated Offer Letters ZIP",
                data=st.session_state["zip_bytes"],
                file_name="Generated_Offer_Letters.zip",
                mime="application/zip",
            )

        st.divider()

        st.subheader("Send Emails")

        st.warning(
            f"Emails will be sent one by one with {EMAIL_DELAY_SECONDS} seconds gap. "
            "Keep this browser tab open until completion."
        )

        if "pdf_records" not in st.session_state:
            st.info("First click `Generate All PDFs`, then send emails.")

        else:
            if st.button("Send Emails with PDF Attachments"):
                try:
                    send_status_df = send_emails_with_smtp(
                        st.session_state["pdf_records"], skip_duplicates=skip_duplicates
                    )

                    st.session_state["send_status_df"] = send_status_df

                    st.success("Email sending process completed.")
                    st.dataframe(send_status_df, use_container_width=True)

                except Exception as e:
                    st.error(f"Email sending failed: {e}")

        if "send_status_df" in st.session_state:
            status_csv = (
                st.session_state["send_status_df"].to_csv(index=False).encode("utf-8")
            )

            st.download_button(
                label="Download Email Sending Status CSV",
                data=status_csv,
                file_name="email_sending_status.csv",
                mime="text/csv",
            )

else:
    st.warning("Enter, paste, or upload data to generate offer letters.")
