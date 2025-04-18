from flask import request, jsonify
import os
from werkzeug.utils import secure_filename
import pandas as pd
import json
import networkx as nx
from pyvis.network import Network

def handle_file_upload(app, process_pdf):
    """
    Handles file upload, processing, and generation of Excel, JSON, and graph files.
    """
    def upload_file():
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)

            upload_folder = app.config['UPLOAD_FOLDER']
            processed_folder = app.config['PROCESSED_FOLDER']

            # Ensure folders exist
            os.makedirs(upload_folder, exist_ok=True)
            os.makedirs(processed_folder, exist_ok=True)

            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)

            # Process the uploaded PDF
            df = process_pdf(filepath)
            if df is None:
                return jsonify({'error': 'Failed to process the PDF file'}), 500

            # Save the processed data as Excel
            excel_filename = os.path.splitext(filename)[0] + '.xlsx'
            excel_path = os.path.join(app.config['PROCESSED_FOLDER'], excel_filename)
            df.to_excel(excel_path, index=False)

            # Step 1: Read the Excel file
            data = pd.read_excel(excel_path)

            # Step 2: Transform the data
            result = {}
            for column_name in data.columns:
                for index, value in data[column_name].items():
                    if index not in result:
                        result[index] = {}
                    result[index][column_name] = value

            # Step 3: Convert the result dictionary to a DataFrame
            df_transformed = pd.DataFrame.from_dict(result, orient='index')

            # Transform the Excel data into a nested dictionary and save as JSON
            json_filename = os.path.splitext(filename)[0] + '.json'
            json_path = os.path.join(app.config['PROCESSED_FOLDER'], json_filename)

            # Step 4: Save the DataFrame as a JSON file
            df_transformed.to_json(json_path, orient='index', force_ascii=False)

            # Generate the graph visualization
            graph_html_filename = os.path.splitext(filename)[0] + '_graph.html'
            graph_html_path = os.path.join(app.config['PROCESSED_FOLDER'], graph_html_filename)

            # Read the JSON file
            with open(json_path, "r") as f:
                data = json.load(f)

            # Create a directed graph
            G = nx.DiGraph()

            # Add nodes and edges with metadata
            for key, record in data.items():
                # Extract fields and replace None with "Not available"
                parent_account = record.get("Second Col Account Number", "Not available")
                if parent_account is None:
                    parent_account = "Not available"

                child_account = record.get("Account Number", "Not available")
                if child_account is None:
                    child_account = "Not available"

                layer = record.get("Layer", "Not available")
                if layer is None:  # Check if layer is None
                    print("Layer is None. Breaking the loop.")
                    break  # Exit the loop

                transaction_id = "Not available"
                if "Transaction ID / UTR Number" in record and record["Transaction ID / UTR Number"] is not None:
                    transaction_id = record["Transaction ID / UTR Number"]
                elif "Transaction ID \/ UTR Number" in record and record["Transaction ID \/ UTR Number"] is not None:
                    transaction_id = record["Transaction ID \/ UTR Number"]

                transaction_amount = record.get("Transaction Amount", "Not available")
                if transaction_amount is None:
                    transaction_amount = "Not available"

                disputed_amount = record.get("Disputed Amount", "Not available")
                if disputed_amount is None:
                    disputed_amount = "Not available"

                # Add parent and child nodes with attributes
                G.add_node(parent_account, type="account", layer=layer)
                G.add_node(child_account, type="account", layer=layer + 1)

                # Add edge with transaction details
                G.add_edge(
                    parent_account,
                    child_account,
                    title=f"Transaction ID: {transaction_id}\nAmount: {transaction_amount}\nDisputed: {disputed_amount}",
                )

            # Visualize using Pyvis
            net = Network(notebook=True, height="750px", width="100%", directed=True)

            # Add nodes to Pyvis network
            for node, attributes in G.nodes(data=True):
                node_title = f"Account: {node}\nLayer: {attributes['layer']}"
                net.add_node(node, label=node, title=node_title, group=attributes["layer"])

            # Add edges to Pyvis network
            for source, target, attributes in G.edges(data=True):
                net.add_edge(source, target, title=attributes["title"])

            # Display the graph
            net.show(graph_html_path)

            return jsonify({
                'message': 'File uploaded and processed successfully',
                'excel_download_url': f'/download-excel?filename={excel_filename}',
                'json_download_url': f'/download-json?filename={json_filename}',
                'graph_html_url': f'/download-graph?filename={graph_html_filename}'
            }), 200

        return jsonify({'error': 'Invalid file type'}), 400

    return upload_file