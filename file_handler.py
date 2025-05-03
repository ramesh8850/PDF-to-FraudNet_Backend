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

            # Step 1: Read the Excel file
            # data = pd.read_excel(excel_path)
            data=df

            # Step 2: Transform the data
            result = {}
            for column_name in data.columns:
                for index, value in data[column_name].items():
                    if index not in result:
                        result[index] = {}
                    result[index][column_name] = value

            # Step 3: Convert the result dictionary to a DataFrame
            df_transformed = pd.DataFrame.from_dict(result, orient='index')

            df_transformed.to_excel(excel_path, index=False)

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

            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            bank_icon_file = os.path.join(BASE_DIR, "bank.json")
            with open(bank_icon_file, "r") as f:
                raw_bank_icon_map = json.load(f)
                bank_icon_map = {key.lower(): value for key, value in raw_bank_icon_map.items()}

            # Get default icon URL
            # DEFAULT_ICON = bank_icon_map.get("DEFAULT", None)


            # Create a directed graph
            G = nx.DiGraph()

            root_node_id = None

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

                if root_node_id is None and layer == 1:
                    root_node_id = parent_account

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

                # 🌟 New fields
                pre_date_info = record.get("Transaction status", "").lower()
                cheque_no = record.get("Cheque No", "Not available")
                transaction_date = record.get("Transaction Date", "Not available")

                is_cash_withdrawal_cheque = "cash withdrawal" in pre_date_info and "cheque" in pre_date_info
                is_same_account = parent_account == child_account

                if is_cash_withdrawal_cheque or is_same_account:
                    # Self-loop — do not change layer
                    G.add_node(parent_account, type="account", layer=layer)
                    G.add_edge(
                        parent_account,
                        parent_account,
                        title=f"""
                        Transaction ID: {transaction_id}
                        Amount: {transaction_amount}
                        Disputed: {disputed_amount}
                        Transaction status: {pre_date_info}
                        Cheque No: {cheque_no}
                        Transaction Date: {transaction_date}
                        """.strip()
                    )   

                else:
                    # Normal transaction
                    G.add_node(parent_account, type="account", layer=layer)
                    G.add_node(child_account, type="account", layer=layer + 1)

                    G.add_edge(
                        parent_account,
                        child_account,
                        title=f"""
                        Transaction ID: {transaction_id}
                        Amount: {transaction_amount}
                        Disputed: {disputed_amount}
                        Transaction status: {pre_date_info}
                        Transaction Date: {transaction_date}
                        """.strip()
                        )

            # Visualize using Pyvis
            net = Network(notebook=True, height="750px", width="100%", directed=True)

            # Set visual options
            net.set_options("""
            {
                "layout": {
                    "hierarchical": {
                        "enabled": true,
                        "direction": "UD",
                        "sortMethod": "directed"
                }
                },
                "physics": {
                    "hierarchicalRepulsion": {
                        "nodeDistance": 250
                    },
                 "solver": "hierarchicalRepulsion"
            },
            "edges": {
                "color": {
                    "color": "rgba(100,100,100,0.4)",
                    "highlight": "rgba(100,100,100,1)",
                    "hover": "rgba(100,100,100,0.8)"
                },
                "width": 1.2,
                "hoverWidth": 3.5,
                "selectionWidth": 4,
                "smooth": {
                "type": "cubicBezier",
                "forceDirection": "vertical",
                "roundness": 1
                },
                "arrows": {
                    "to": {
                        "enabled": true
                    }
                }
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200,
                "dragView": true,
                "zoomView": true,
                "dragNodes": false
            }
            }
            """)

            # Add nodes with optional bank icons
            for node, attr in G.nodes(data=True):
                # Match the current node (account number) to a record's Account Number
                bank_name = None
                for key, record in data.items():
                        acc_num = record.get("Account Number")
                        if str(acc_num) == str(node):  # Ensure string comparison
                            raw_bank_name = record.get("Processed_Bank_Name")
                            if raw_bank_name:
                                bank_name = raw_bank_name.lower()  # Convert to lowercase
                            break

                icon_url = None
                if bank_name:
                    icon_url = bank_icon_map.get(bank_name)

                if not icon_url:
                    icon_url = bank_icon_map.get("default")  # Fallback to default icon if defined

                node_title = f"Account: {node}\nLayer: {attr['layer']}\nBank: {bank_name or 'Unknown'}"

                node_options = {
                    "label": node,
                    "title": node_title,
                    "group": attr["layer"],
                    "level": attr["layer"],
                    "size": 30
                }

                if icon_url:
                    node_options.update({
                        "shape": "image",
                        "image": icon_url,
                        "size": 40,
                        "borderWidth": 1.5,
                        "borderWidthSelected": 3
                })
                    
                net.add_node(node, **node_options)

            # Add edges
            for src, tgt, attr in G.edges(data=True):
                net.add_edge(src, tgt, title=attr["title"])

            net.show(graph_html_path)


            # Add nodes to Pyvis network
            for node, attributes in G.nodes(data=True):
                node_title = f"Account: {node}\nLayer: {attributes['layer']}"
                net.add_node(node, label=node, title=node_title, group=attributes["layer"])

            # Add edges to Pyvis network
            for source, target, attributes in G.edges(data=True):
                net.add_edge(source, target, title=attributes["title"])

            # Display the graph
            net.show(graph_html_path)

            # Inject custom styling and zoom-to-root JS
            if root_node_id:
                with open(graph_html_path, "r", encoding="utf-8") as f:
                    html = f.read()

                css_style = """
                <style>
                    .node canvas {
                        filter: drop-shadow(1px 1px 2px rgba(0,0,0,0.3));
                        transition: transform 0.2s ease;
                    }
                    .node:hover canvas {
                        transform: scale(1.1);
                    }
                </style>
                """

                js_focus = f"""
                <script type="text/javascript">
                window.addEventListener("load", function () {{
                    network.once("afterDrawing", function() {{
                        network.focus("{root_node_id}", {{
                            scale: 1.5,
                            animation: {{
                                duration: 1000,
                                easingFunction: "easeInOutQuad"
                            }}
                        }});
                    }});
                }});
                </script>
                </body>"""

                html = html.replace("<head>", "<head>" + css_style)
                html = html.replace("</body>", js_focus)

                with open(graph_html_path, "w", encoding="utf-8") as f:
                    f.write(html)



            return jsonify({
                'message': 'File uploaded and processed successfully',
                'excel_download_url': f'/download-excel?filename={excel_filename}',
                'json_download_url': f'/download-json?filename={json_filename}',
                'graph_html_url': f'/download-graph?filename={graph_html_filename}'
            }), 200

        return jsonify({'error': 'Invalid file type'}), 400

    return upload_file