import streamlit as st
import pandas as pd
from io import BytesIO
from PIL import Image
from rapidfuzz import process, fuzz
from indic_transliteration.sanscript import transliterate, DEVANAGARI, ITRANS
import re

# Convert Nepali numbers to English
def convert_nepali_number_to_english(text):
    mapping = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
               '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}
    if not isinstance(text, str):
        return text
    return ''.join(mapping.get(char, char) for char in text)

def convert_numbers(df):
    return df.apply(lambda x: x.map(convert_nepali_number_to_english) if x.dtype == "object" else x)

def clean_column(df, column):
    df[column] = df[column].astype(str).str.strip()
    df[column] = df[column].replace(['nan', '', ' '], None)
    return df

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def clean_name(name):
    if not isinstance(name, str):
        return ''
    name = name.strip().lower()
    name = re.sub(r'[^\w\s]', '', name)  # Remove punctuation
    return name

def fix_devanagari_abbreviations(text):
    """Fix common Devanagari name abbreviations like के.सि → केसी"""
    if not isinstance(text, str):
        return text
    text = text.replace('के.सि', 'केसी') \
               .replace('कु.', 'कुमार') \
               .replace('श.', 'शर्मा')  # Add more as needed
    return text

def romanize_name(name):
    if pd.isna(name):
        return ''
    name = fix_devanagari_abbreviations(name)
    try:
        return transliterate(name, DEVANAGARI, ITRANS)
    except:
        return str(name)

def match_by_name(df_nrb, df_adbl, nrb_name_col, adbl_name_col, threshold=85):
    df_nrb['romanized_name'] = df_nrb[nrb_name_col].apply(romanize_name).apply(clean_name)
    df_adbl['romanized_name'] = df_adbl[adbl_name_col].astype(str).apply(clean_name)

    matches = []
    for _, row in df_nrb.iterrows():
        name = row['romanized_name']
        if not name:
            continue
        match, score, _ = process.extractOne(name, df_adbl['romanized_name'], scorer=fuzz.token_sort_ratio)
        if score >= threshold:
            matched_row = df_adbl[df_adbl['romanized_name'] == match].iloc[0]
            # Drop romanized_name from matched_row to avoid duplicate columns
            matched_row = matched_row.drop(labels=['romanized_name'])
            # Concatenate with suffixes to ensure unique column names
            merged_row = pd.concat([row, matched_row], axis=0, keys=['nrb', 'adbl']).reset_index(level=0, drop=True)
            merged_row['match_score'] = score
            matches.append(merged_row)

    # Convert matches to DataFrame, ensuring unique columns
    result = pd.DataFrame(matches)
    if not result.empty:
        # Rename columns to include source prefix (nrb_ or adbl_)
        columns = result.columns
        new_columns = []
        for col in columns:
            if col.startswith('nrb_'):
                new_columns.append(col.replace('nrb_', 'nrb_'))
            elif col.startswith('adbl_'):
                new_columns.append(col.replace('adbl_', 'adbl_'))
            else:
                new_columns.append(col)
        result.columns = new_columns
    return result

def main():
    st.set_page_config(page_title="NRB Block List Matcher", layout="centered")
    st.title("🔍 NRB–ADBL Blocklist Matcher App")

    st.header("📥 Step 1: Upload NRB Excel File")
    excel_file = st.file_uploader("Upload NRB Excel (.xlsx)", type=["xlsx", "xls"])

    if excel_file:
        df_nrb = pd.read_excel(excel_file)
        df_nrb = convert_numbers(df_nrb)
        st.success("✅ NRB Excel loaded!")
        st.dataframe(df_nrb.head())

        st.header("📥 Step 2: Upload ADBL Customer CSV")
        csv_file = st.file_uploader("Upload ADBL CSV (.csv)", type=["csv"])

        if csv_file:
            df_adbl = pd.read_csv(csv_file, encoding='utf-8')
            st.success("✅ ADBL CSV loaded!")
            st.dataframe(df_adbl.head())

            # Let user choose columns for matching
            st.subheader("🔧 Select Columns for Matching")
            nrb_cit_col = st.selectbox("NRB: Citizenship Number Column", df_nrb.columns)
            nrb_name_col = st.selectbox("NRB: Name Column (Nepali)", df_nrb.columns)
            adbl_cit_col = st.selectbox("ADBL: Citizenship Number Column", df_adbl.columns)
            adbl_name_col = st.selectbox("ADBL: Name Column (English)", df_adbl.columns)

            # Clean selected columns
            df_nrb = clean_column(df_nrb, nrb_cit_col)
            df_adbl = clean_column(df_adbl, adbl_cit_col)

            # Separate NRB into with and without citizenship number
            df_nrb_citizenship = df_nrb.dropna(subset=[nrb_cit_col])
            df_nrb_no_citizenship = df_nrb[df_nrb[nrb_cit_col].isna()]

            # Step 1: Exact citizenship match
            merged_cit = pd.merge(
                df_nrb_citizenship, df_adbl,
                how='inner',
                left_on=nrb_cit_col,
                right_on=adbl_cit_col,
                suffixes=('_nrb', '_adbl')
            )
            merged_cit['match_type'] = 'Citizenship Match'

            # Step 2: Fuzzy name match for remaining NRB entries
            fuzzy_matches = match_by_name(df_nrb_no_citizenship.copy(), df_adbl.copy(), nrb_name_col, adbl_name_col)
            if not fuzzy_matches.empty:
                fuzzy_matches['match_type'] = 'Name Match'

            # Display results
            st.subheader(f"🎯 Total Matches Found: {len(merged_cit) + len(fuzzy_matches)}")

            # Table 1: Citizenship Matches
            st.markdown("### 🔐 Table 1: Citizenship Matches")
            if not merged_cit.empty:
                st.dataframe(merged_cit)
                st.download_button(
                    "⬇️ Download Citizenship Matches (Excel)",
                    to_excel(merged_cit),
                    file_name="nrb_adbl_citizenship_matches.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("❌ No citizenship matches found.")

            # Table 2: Name Matches
            st.markdown("### 🧠 Table 2: Name Matches (Fuzzy ≥85%)")
            if not fuzzy_matches.empty:
                st.dataframe(fuzzy_matches)
                st.download_button(
                    "⬇️ Download Name Matches (Excel)",
                    to_excel(fuzzy_matches),
                    file_name="nrb_adbl_name_matches.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("❌ No name matches found.")

if __name__ == "__main__":
    main()
