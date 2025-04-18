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
            # Assuming `df` is already defined and `second_col` is the name of the second column
            if len(df.columns) >= 2:
                second_col = df.columns[1]

                # Extract the name (before the first '\n')
                df['Name'] = df[second_col].astype(str).str.strip().str.split('\n').str[0]

                # Extract the account number (between the first and second '\n')
                df['Second Col Account Number'] = df[second_col].astype(str).str.strip().str.split('\n').str[1]

                # Combine the name and account number into a single column
                df['Second Col Account Number'] = df['Name'] + '' + df['Second Col Account Number']

                # Extract the transaction ID (after the second '\n')
                df['Second Col Transaction ID'] = df[second_col].astype(str).str.strip().str.split('\n').str[2:]

                # Join the parts after the second '\n' if there are multiple parts
                df['Second Col Transaction ID'] = df['Second Col Transaction ID'].apply(lambda x: ''.join(x) if isinstance(x, list) else x)

                # Extract the Layer number using a regular expression
                df['Layer'] = df['Second Col Transaction ID'].str.extract(r'Layer : (\d+)').astype(float).astype(pd.Int64Dtype())

                # Remove the 'Layer : <number>' part from the Transaction ID
                df['Second Col Transaction ID'] = df['Second Col Transaction ID'].str.split('Layer :').str[0].str.strip()

                # Drop the original second column and the temporary 'Name' column
                df = df.drop(columns=[second_col, 'Name'])
                # df = df.drop(columns=[second_col])
            combined_col = "Account Details"
            # Assuming `df` is already defined and `combined_col` contains the raw account details
            if combined_col in df.columns:
                # Define patterns for Account Number and IFSC Code
                account_pattern = r'\b\d{10,20}\b'
                ifsc_pattern = r'\b[A-Z]{4}\d[A-Z0-9]{6}\b'

                # Extract data up to the second newline
                df['Truncated Data'] = df[combined_col].apply(
                    lambda x: ''.join(str(x).split('\n')[:2]) if '\n' in str(x) else str(x)
                )

                # Extract all numeric sequences from the truncated data
                df['Account Number'] = df['Truncated Data'].apply(
                    lambda x: ' '.join(re.findall(r'\d+', str(x))) if re.findall(r'\d+', str(x)) else None
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