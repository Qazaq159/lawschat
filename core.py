import os
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.documents import Document as LangchainDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


class InsuranceLawChatbot:
    def __init__(self, docx_files_path, api_key=None):
        """
        Initialize the RAG chatbot for Kazakhstani insurance laws using Mistral AI.

        Args:
            docx_files_path: Path to folder containing .docx files or list of file paths
            api_key: Mistral API key (or set MISTRAL_API_KEY env variable)
        """
        if api_key:
            os.environ["MISTRAL_API_KEY"] = api_key

        self.docx_files_path = docx_files_path
        self.vectorstore = None
        self.retriever = None
        self.chain = None

    def load_docx_files(self):
        """Load all .docx files from the specified path."""
        documents = []

        # Handle both single file and directory
        if isinstance(self.docx_files_path, str):
            if os.path.isfile(self.docx_files_path):
                files = [self.docx_files_path]
            else:
                files = [
                    os.path.join(self.docx_files_path, f)
                    for f in os.listdir(self.docx_files_path)
                    if f.endswith('.docx')
                ]
        else:
            files = self.docx_files_path

        for file_path in files:
            doc = Document(file_path)
            full_text = []

            # Extract text from paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)

            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            full_text.append(cell.text)

            # Create a document with metadata
            text_content = '\n'.join(full_text)
            documents.append(
                LangchainDocument(
                    page_content=text_content,
                    metadata={"source": os.path.basename(file_path)}
                )
            )

        print(f"Loaded {len(documents)} documents")
        return documents

    def chunk_documents(self, documents):
        """
        Split documents into smaller chunks for better retrieval.

        Chunk size of 1000 with 200 overlap is a good starting point.
        Adjust based on your document structure.
        """
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = text_splitter.split_documents(documents)
        print(f"Created {len(chunks)} chunks from documents")
        return chunks

    def create_vectorstore(self, chunks):
        """Create a vector database from document chunks using Mistral embeddings."""
        # Use Mistral embeddings (fast API-based)
        embeddings = MistralAIEmbeddings(
            model="mistral-embed"  # Mistral's embedding model
        )

        # Create Chroma vector store
        self.vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory="./insurance_law_db"
        )

        # Create retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}  # Retrieve top 4 most relevant chunks
        )

        print("Vector store created successfully")
        return self.vectorstore

    def setup_chain(self, model_name="mistral-large-2512"):
        """
        Set up the RAG chain with Mistral AI.

        Available models:
        - mistral-large-2512: Most capable, best for complex reasoning
        - mistral-medium-latest: Balanced performance/cost
        - mistral-small-latest: Fast and economical
        - open-mistral-7b: Open source, cheapest
        """
        llm = ChatMistralAI(
            model=model_name,
            temperature=0  # Low temperature for factual legal responses
        )

        # Custom prompt for insurance law queries - OPTIMIZED FOR SHORT ANSWERS
        template = """Вы - помощник по страховому законодательству Казахстана. 

ВАЖНО: Давайте КРАТКИЕ ответы (2-4 предложения). Выделяйте только самую важную информацию.

Используйте следующий контекст из законодательных документов для ответа на вопрос.
Если вы не знаете ответа, скажите об этом. Не придумывайте информацию.
Указывайте номера статей закона, если они есть в контексте.

Контекст: {context}

Вопрос: {question}

Краткий ответ (2-4 предложения):"""

        prompt = ChatPromptTemplate.from_template(template)

        # Format documents function
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Build the chain
        self.chain = (
                {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
        )

        print(f"RAG chain ready with {model_name}")
        return self.chain

    def build(self, model_name="mistral-large-2512"):
        """Build the complete RAG system."""
        print("Building RAG system with Mistral AI...")

        # Step 1: Load documents
        documents = self.load_docx_files()

        # Step 2: Chunk documents
        chunks = self.chunk_documents(documents)

        # Step 3: Create vector store
        self.create_vectorstore(chunks)

        # Step 4: Setup chain
        self.setup_chain(model_name)

        print("RAG system built successfully!")

    def ask(self, question, detailed=False):
        """
        Ask a question about insurance laws.

        Args:
            question: Question in Russian or Kazakh
            detailed: If True, request detailed answer. If False (default), get short answer.

        Returns:
            dict with 'answer' and 'sources'
        """
        if not self.chain:
            raise ValueError("Please run build() first to initialize the system")

        # Modify question if detailed answer is requested
        if detailed:
            modified_question = f"{question}\n\nДай подробный ответ со всеми деталями."
        else:
            modified_question = question

        # Get relevant documents
        relevant_docs = self.retriever.invoke(modified_question)

        # Get answer from chain
        answer = self.chain.invoke(modified_question)

        return {
            "answer": answer,
            "sources": [doc.metadata["source"] for doc in relevant_docs],
            "source_documents": relevant_docs  # Full chunks for reference
        }

    def load_existing_vectorstore(self):
        """Load previously created vector store without rebuilding."""
        embeddings = MistralAIEmbeddings(model="mistral-embed")

        self.vectorstore = Chroma(
            persist_directory="./insurance_law_db",
            embedding_function=embeddings
        )

        # Create retriever
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4}
        )

        print("Loaded existing vector store")


# Example usage
if __name__ == "__main__":
    # Initialize the chatbot
    chatbot = InsuranceLawChatbot(
        docx_files_path="./insurance_laws",  # Path to your .docx files
        api_key="your mistral token"  # Get from https://console.mistral.ai
    )

    # Build the RAG system (do this once)
    # Choose your model based on needs:
    # - "mistral-large-2512" for best quality
    # - "mistral-small-latest" for speed/cost
    chatbot.build(model_name="mistral-large-2512")

    # For subsequent runs, just load the existing vectorstore:
    # chatbot.load_existing_vectorstore()
    # chatbot.setup_chain("mistral-large-2512")

    # Ask questions in Russian or Kazakh
    questions = [
        "Какие виды страхования предусмотрены законом?",
        "Каковы права страхователя?",
        "Какие требования к страховым компаниям?",
        "Что такое обязательное страхование?"
    ]

    for question in questions:
        print(f"\n{'=' * 60}")
        print(f"Вопрос: {question}")
        print('=' * 60)
        result = chatbot.ask(question)  # Short answer by default
        print(f"Ответ: {result['answer']}")
        print(f"\nИсточники: {', '.join(set(result['sources']))}")

        # For detailed answer, use: chatbot.ask(question, detailed=True)