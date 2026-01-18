"""
Admin panel for managing insurance law knowledge base.
Allows uploading new documents and monitoring system status.
"""

import os
from flask import Flask, render_template, request, jsonify
from pathlib import Path
from core import InsuranceLawChatbot
from manager import KnowledgeManager

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# Initialize components
knowledge_manager = KnowledgeManager()
chatbot = None


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get knowledge base status."""
    return jsonify(knowledge_manager.get_knowledge_base_info())


@app.route('/api/documents', methods=['GET'])
def list_documents():
    """List all loaded documents."""
    docs = knowledge_manager.get_knowledge_base_info()
    return jsonify({
        "count": docs["total_documents"],
        "documents": docs["documents"],
        "last_update": docs["last_update"]
    })


@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload and process new document."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if not file.filename.endswith('.docx'):
        return jsonify({"error": "Only DOCX files allowed"}), 400

    try:
        # Save file
        upload_dir = Path('./insurance_laws')
        upload_dir.mkdir(exist_ok=True)
        file_path = upload_dir / file.filename
        file.save(file_path)

        # Rebuild knowledge base
        global chatbot
        if chatbot:
            chatbot.build()

        return jsonify({
            "success": True,
            "message": f"Document '{file.filename}' uploaded and processed",
            "status": knowledge_manager.get_knowledge_base_info()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/terminology', methods=['GET'])
def get_terminology():
    """Get extracted terminology."""
    return jsonify(knowledge_manager.terminology)


@app.route('/api/rebuild', methods=['POST'])
def rebuild_knowledge_base():
    """Rebuild knowledge base from documents."""
    try:
        global chatbot
        chatbot = InsuranceLawChatbot(
            docx_files_path="./insurance_laws",
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        chatbot.build()

        return jsonify({
            "success": True,
            "message": "Knowledge base rebuilt successfully",
            "status": knowledge_manager.get_knowledge_base_info()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
