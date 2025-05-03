import pdfplumber
import pandas as pd
import re


# Function to process the PDF
def process_pdf(pdf_path):
        expected_keywords = [
            "s. no.", "account no.", "action taken", "bank", "account details",
            "transaction details", "branch", "manager", "reference no.", "atm id",
            "place", "location", "action taken by", "date of action"
        ]
        all_data = []
        headers = None
        table_found = False

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table_found:
                        if table and len(table) > 1:
                            potential_headers = [str(cell).strip().lower() for cell in table[0] if cell is not None]
                            keyword_matches = sum(any(keyword in header for header in potential_headers)
                                                for keyword in expected_keywords)
                            if keyword_matches >= 8:
                                headers = table[0]
                                data = table[1:]
                                all_data.extend(data)
                                table_found = True
                    else:
                        if table and len(table) > 0:
                            first_row = [str(cell).strip().lower() for cell in table[0] if cell is not None]
                            if all(header.lower() in first_row for header in headers if header):
                                data = table[1:]
                            else:
                                data = table
                            all_data.extend(data)

        if table_found and all_data:
            df = pd.DataFrame(all_data, columns=headers)
            # Assuming df is already your DataFrame and column 4 is the bank column
            bank_col = df.columns[3]  # Adjust index if needed

            if bank_col in df.columns:
                  df['Extracted Bank Name'] = (
                                      df[bank_col]
                                      .astype(str)
                                      .str.split('\n')  # Split into list of lines
                                      .str[:2]          # Take first two lines
                                      .str.join('\n')    # Rejoin with newline (optional)
                                      )
            # Keywords to check (case-insensitive)
            KEYWORDS = {'bank', 'ltd', 'limited'}
            def process_lines(text):
                lines = str(text).split('\n')  # Split into lines
                first_line = lines[0].strip()  # Keep first line

                # Check remaining lines for keywords
                for line in lines[1:]:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in KEYWORDS):
                        first_line += " " + line.strip()  # Append if keyword found

                return first_line
            # Apply to DataFrame
            df['Processed_Bank_Name'] = df['Extracted Bank Name'].apply(process_lines)

            third_col = df.columns[2]  # assuming third column exists
            if third_col in df.columns:
                # Clean and normalize the third column: remove newlines and trim spaces
                df[third_col] = df[third_col].astype(str).str.replace('\n', ' ', regex=False).str.strip()

                # Extract text before "Txn Date:" or "Date:"
                def extract_before_date(text):
                    text = text.replace('\n', ' ').strip()
                    match_txn = re.split(r'Txn Date:', text, flags=re.IGNORECASE)
                    if len(match_txn) > 1:
                        return match_txn[0].strip()
                    match_date = re.split(r'Date:', text, flags=re.IGNORECASE)
                    if len(match_date) > 1:
                        return match_date[0].strip()
                    return text  # fallback if neither is found

                df['Transaction status'] = df[third_col].apply(extract_before_date)

                # Extract cheque number
                df['Cheque No'] = df[third_col].apply(
                  lambda x: re.search(r'Cheque\s*No\s*[:\-]?\s*(\d+)', x, re.IGNORECASE).group(1)
                  if re.search(r'Cheque\s*No\s*[:\-]?\s*(\d+)', x, re.IGNORECASE) else None
                )
                # Extract Transaction Date (Txn Date: or Date:)
                def extract_txn_date(text):
                    text = text.replace('\n', ' ').strip()
                    match_txn = re.search(r'Txn Date:\s*([\d:/\sAPMapm]+)', text)
                    if match_txn:
                        return match_txn.group(1).strip()
                    match_date = re.search(r'Date:\s*([\d:/\sAPMapm]+)', text)
                    if match_date:
                        return match_date.group(1).strip()
                    return None

                df['Transaction Date'] = df[third_col].apply(extract_txn_date)

                # Drop the original third column
                df = df.drop(columns=[third_col])

            if len(df.columns) >= 2:
                second_col = df.columns[1]

                # Extract account number logic
                def extract_account_number(text):
                    lines = str(text).strip().split('\n')
                    if len(lines) < 2:
                        return lines[0]  # Only one line exists

                    line1 = lines[0]
                    line2 = lines[1]

                    # Condition 1: Non-digit characters in line2 → return line1 only
                    if not re.fullmatch(r'\d+', line2.strip()):
                        return line1

                    # Condition 2: Digits in line2 (check count)
                    if len(line2.strip()) <= 7:
                        return line1 + line2  # Combine if ≤7 digits
                    else:
                        return line1  # Discard if >7 digits

                df['Second Col Account Number'] = df[second_col].apply(extract_account_number)

                # Extract the transaction ID (after the second '\n')
                df['Second Col Transaction ID'] = df[second_col].astype(str).str.strip().str.split('\n').str[2:]

                # Join the parts after the second '\n' if there are multiple parts
                df['Second Col Transaction ID'] = df['Second Col Transaction ID'].apply(lambda x: ''.join(x) if isinstance(x, list) else x)

                # Extract the Layer number using a regular expression
                df['Layer'] = df['Second Col Transaction ID'].str.extract(r'Layer : (\d+)').astype(float).astype(pd.Int64Dtype())

                # Remove the 'Layer : <number>' part from the Transaction ID
                df['Second Col Transaction ID'] = df['Second Col Transaction ID'].str.split('Layer :').str[0].str.strip()

                # Drop the original second column and the temporary 'Name' column
                df = df.drop(columns=[second_col])
                # df = df.drop(columns=[second_col])
            combined_col = "Account Details"
            # Assuming `df` is already defined and `combined_col` contains the raw account details
            if combined_col in df.columns:
                # Define patterns for Account Number and IFSC Code
                # account_pattern = r'\b\d{10,20}\b'
                ifsc_pattern = r'\b[A-Z]{4}\d[A-Z0-9]{6}\b'

                ifsc_keyword_pattern = r'\bifsc\b'  # Case-insensitive "ifsc" keyword

                def extract_data(text):
                    text = str(text)

                    # Check if "ifsc" keyword exists (case-insensitive)
                    ifsc_keyword_match = re.search(ifsc_keyword_pattern, text, flags=re.IGNORECASE)

                    if ifsc_keyword_match:
                        # Extract everything before "ifsc" keyword
                        truncated = text[:ifsc_keyword_match.start()].strip()
                    else:
                        # Fallback: Extract up to second newline
                        lines = text.split('\n')
                        truncated = ''.join(lines[:2]).strip()

                    return truncated

                # Apply extraction logic
                df['Truncated Data'] = df[combined_col].apply(extract_data)
                # After extracting the truncated data
                df['Truncated Data'] = df['Truncated Data'].str.replace('\n', '', regex=False)

                # Extract all numeric sequences from the truncated data
                df['Account Number'] = df['Truncated Data'].apply(
                  lambda x: str(x)[9:] if pd.notna(x) and len(str(x)) > 9 else None
                )
                # Extract IFSC Code
                df['IFSC Code'] = df[combined_col].apply(
                    lambda x: re.search(ifsc_pattern, str(x)).group() if re.search(ifsc_pattern, str(x)) else None
                )

                # Extract the Reported Count using a specific regex pattern
                reported_pattern = r'Reported (\d+) times'
                df['Reported Count'] = df[combined_col].apply(
                    lambda x: re.search(reported_pattern, str(x)).group(1) if re.search(reported_pattern, str(x)) else None
                )

                # Create the combined report column
                df['Account Details Report'] = df.apply(
                    lambda row: f"Account: {row['Account Number']} - IFSC: {row['IFSC Code']} - Reported: {row['Reported Count']} times"
                                if pd.notna(row['Account Number']) or pd.notna(row['IFSC Code']) or pd.notna(row['Reported Count'])
                                else row[combined_col],
                    axis=1
                )

                # Drop the original combined column
                df = df.drop(columns=[combined_col,'Truncated Data'])
            transactional_col = "Transaction Details"
            if transactional_col in df.columns:
                # Preprocess the combined_col to handle multi-line strings
                df[transactional_col] = df[transactional_col].str.replace('\n', ' ').str.strip()
                transaction_id_pattern =  r'Transaction ID / UTR\s+Number-:\s*([A-Z]*\d+)'
                transaction_amount_pattern = r'Transaction Amount-:\s*(\d+(?:\.\d+)?)'
                disputed_amount_pattern = r'Disputed Amount:\s*(\d+(?:\.\d+)?)'
                df['Transaction ID / UTR Number'] = df[transactional_col].apply(
                    lambda x: re.search(transaction_id_pattern, str(x)).group(1) if re.search(transaction_id_pattern, str(x)) else None
                )
                df['Transaction Amount'] = df[transactional_col].apply(
                    lambda x: re.search(transaction_amount_pattern, str(x)).group(1) if re.search(transaction_amount_pattern, str(x)) else None
                )
                df['Disputed Amount'] = df[transactional_col].apply(
                    lambda x: re.search(disputed_amount_pattern, str(x)).group(1) if re.search(disputed_amount_pattern, str(x)) else None
                )
                df['Transaction Amount'] = pd.to_numeric(df['Transaction Amount'], errors='coerce')
                df['Disputed Amount'] = pd.to_numeric(df['Disputed Amount'], errors='coerce')
                df = df.drop(columns=[transactional_col])

            return df
        else:
            return None