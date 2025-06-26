import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image

# Mapping for Nepali Devanagari numbers to English numbers
nepali_to_english_numbers = {
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
}

def convert_nepali_number_to_english(text):
    """Convert Nepali Devanagari numbers to English."""
    if not isinstance(text, str):
        return text
    return ''.join(nepali_to_english_numbers.get(char, char) for char in text)

def convert_numbers(df):
    """Apply Nepali to English conversion across DataFrame."""
    return df.apply(lambda x: x.map(convert_nepali_number_to_english) if x.dtype == "object" else x)

def clean_column(df, column):
    """Strip whitespace and replace empty values with None."""
    if column in df.columns:
        df[column] = df[column].astype(str).str.strip()
        df[column] = df[column].replace(['nan', '', ' '], None)
    return df

def to_excel(df):
    """Convert DataFrame to Excel bytes."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def merge_csvs_by_columns(df1, df2):
    """Merge DataFrames based on citizenship_number and CUS_LEG_ID."""
    required_col1 = 'citizenship_number'
    required_col2 = 'CUS_LEG_ID'
    
    if required_col1 not in df1.columns:
        raise ValueError(f"Column '{required_col1}' is missing in NRB Excel.")
    if required_col2 not in df2.columns:
        raise ValueError(f"Column '{required_col2}' is missing in ADBL CSV.")
    
    df1 = clean_column(df1, required_col1)
    df2 = clean_column(df2, required_col2)
    
    original_len = len(df1)
    df1 = df1.dropna(subset=[required_col1])
    st.info(f"Filtered out {original_len - len(df1)} rows with empty citizenship numbers.")

    merged_df = pd.merge(
        df1,
        df2,
        how='inner',
        left_on=required_col1,
        right_on=required_col2
    )
    return merged_df

def main():
    st.set_page_config(page_title="NRB Block List Finder", layout="centered")

    # Optional: Add a logo or banner (make sure image is in your working directory)
    try:
        logo = Image.open("nrb_logo.png")  # Replace with your actual file
        st.image(logo, width=150)
    except:
        pass  # Skip if image not found

    st.title("🔍 NRB Block List Finder App")
    st.markdown("Welcome! This app helps identify **NRB-blacklisted customers** who hold accounts in **ADBL**.")
    st.markdown("Upload your **NRB Excel file** and **ADBL customer CSV** to begin.")

    st.header("📥 Step 1: Upload NRB Excel File")
    excel_file = st.file_uploader("Upload NRB Excel (.xlsx or .xls)", type=["xlsx", "xls"])

    if excel_file:
        try:
            df_nrb = pd.read_excel(excel_file)
            st.success("✅ Excel file loaded successfully!")

            st.subheader("👀 Preview of Original Data")
            st.dataframe(df_nrb.head(10))

            df_nrb_converted = convert_numbers(df_nrb)
            st.subheader("🔄 Converted Data (Devanagari → English Numbers)")
            st.dataframe(df_nrb_converted.head(10))

            # Download buttons for converted file
            st.subheader("⬇️ Download Converted File")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("Download CSV", df_nrb_converted.to_csv(index=False, encoding="utf-8-sig"),
                                   "converted_output.csv", "text/csv")
            with col2:
                st.download_button("Download Excel", to_excel(df_nrb_converted),
                                   "converted_output.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # Step 2
            st.header("📥 Step 2: Upload ADBL Customer CSV File")
            csv_file = st.file_uploader("Upload ADBL Customer CSV", type=["csv"])

            if csv_file:
                try:
                    df_adbl = pd.read_csv(csv_file, encoding='utf-8')
                    st.success("✅ CSV file loaded successfully!")

                    merged_df = merge_csvs_by_columns(df_nrb_converted, df_adbl)

                    st.subheader("🔍 Matched Records: Blacklisted Customers in ADBL")
                    if not merged_df.empty:
                        st.dataframe(merged_df)
                        st.info(f"🎯 Total Matches Found: {len(merged_df)}")

                        col3, col4 = st.columns(2)
                        with col3:
                            st.download_button("Download Matched CSV",
                                               merged_df.to_csv(index=False, encoding="utf-8-sig"),
                                               "matched_output.csv", "text/csv")
                        with col4:
                            st.download_button("Download Matched Excel",
                                               to_excel(merged_df),
                                               "matched_output.xlsx",
                                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    else:
                        st.warning("❌ No matches found.")
                except UnicodeDecodeError:
                    st.error("❗ CSV is not UTF-8 encoded. Please re-save the file with UTF-8 encoding.")
                except Exception as e:
                    st.error(f"❗ Error during matching: {e}")
        except Exception as e:
            st.error(f"❗ Failed to process Excel file: {e}")

    st.markdown("---")
    st.markdown("🙏 **Thank you for using the NRB Block List Finder App!**")

if __name__ == "__main__":
    main()
