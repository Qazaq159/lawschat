import os
import unicodedata
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.documents import Document as LangchainDocument
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage


class InsuranceLawChatbot:
    def __init__(self, docx_files_path, api_key=None, redis_url="redis://localhost:6379"):
        """
        Initialize the RAG chatbot for Kazakhstani insurance laws using Mistral AI.

        Args:
            docx_files_path: Path to folder containing .docx files or list of file paths
            api_key: Mistral API key (or set MISTRAL_API_KEY env variable)
            redis_url: Redis connection URL (default: redis://localhost:6379)
        """
        if api_key:
            os.environ["MISTRAL_API_KEY"] = api_key

        self.docx_files_path = docx_files_path
        self.redis_url = redis_url
        self.vectorstore = None
        self.retriever = None
        self.chain = None

    @staticmethod
    def normalize_text(text):
        """
        Normalize text to avoid tokenizer issues with special characters.
        Converts special Cyrillic/Latin lookalikes to standard characters.
        """
        # Normalize unicode (NFC normalization)
        text = unicodedata.normalize('NFC', text)

        # Replace common problematic characters
        replacements = {
            'һ': 'h',  # Cyrillic 'һ' to Latin 'h'
            'ә': 'ə',  # Kazakh 'ә'
            'ғ': 'ғ',  # Kazakh 'ғ'
            'қ': 'қ',  # Kazakh 'қ'
            'ң': 'ң',  # Kazakh 'ң'
            'ө': 'ө',  # Kazakh 'ө'
            'ұ': 'ұ',  # Kazakh 'ұ'
            'ү': 'ү',  # Kazakh 'ү'
            'і': 'і',  # Kazakh 'і'
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

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

        # Custom prompt for insurance law queries - WITH CONVERSATION HISTORY
        template = """Вы - помощник по страховому законодательству Казахстана. 

ВАЖНО: 
- Если вопрос простой или пользователь НЕ просит подробности - давайте КРАТКИЙ ответ (2-4 предложения).
- Если пользователь явно просит подробный ответ (слова: "подробно", "детально", "расскажи полностью", "все детали") - давайте развернутый ответ.
- По умолчанию всегда отвечайте КРАТКО.
- Если пользователь задает уточняющий вопрос (например, "а что такое п. 2.1?", "расскажи подробнее об этом"), используйте историю разговора для понимания контекста.

История разговора:
{chat_history}

Используйте следующий контекст из законодательных документов для ответа на вопрос.
Если вы не знаете ответа, скажите об этом. Не придумывайте информацию.
Указывайте номера статей закона, если они есть в контексте.

Контекст: {context}

Текущий вопрос: {question}

Ответ:"""

        prompt = ChatPromptTemplate.from_template(template)

        # Format documents function
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # Format chat history function
        def format_chat_history(history):
            if not history:
                return "Нет предыдущих сообщений."
            formatted = []
            for msg in history[-6:]:  # Last 3 exchanges (6 messages)
                if isinstance(msg, HumanMessage):
                    formatted.append(f"Пользователь: {msg.content}")
                elif isinstance(msg, AIMessage):
                    formatted.append(f"Ассистент: {msg.content}")
            return "\n".join(formatted)

        # Store format functions for later use
        self.format_docs = format_docs
        self.format_chat_history = format_chat_history

        # Build the chain
        self.chain = (
                {"context": self.retriever | format_docs,
                 "question": RunnablePassthrough(),
                 "chat_history": lambda x: ""}  # Will be filled in ask() method
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

    def ask(self, question, user_id="default"):
        """
        Ask a question about insurance laws.

        Args:
            question: Question in Russian or Kazakh
            user_id: Unique identifier for the user (to maintain separate chat histories)

        Returns:
            dict with 'answer' and 'sources'
        """
        if not self.chain:
            raise ValueError("Please run build() first to initialize the system")

        # Normalize text to avoid tokenizer issues
        normalized_question = self.normalize_text(question)

        # Get or create Redis chat history for this user
        chat_history = RedisChatMessageHistory(
            session_id=f"user:{user_id}",
            url=self.redis_url,
            ttl=86400  # Keep history for 24 hours (optional)
        )

        # Get relevant documents
        relevant_docs = self.retriever.invoke(normalized_question)

        # Format chat history
        formatted_history = self.format_chat_history(chat_history.messages)

        # Prepare context with history
        context_with_history = {
            "context": self.format_docs(relevant_docs),
            "question": normalized_question,
            "chat_history": formatted_history
        }

        # Get answer from chain
        answer = self.chain.invoke(context_with_history)

        # Add ORIGINAL question to chat history (not normalized)
        chat_history.add_user_message(question)
        chat_history.add_ai_message(answer)

        return {
            "answer": answer,
            "sources": [doc.metadata["source"] for doc in relevant_docs],
            "source_documents": relevant_docs  # Full chunks for reference
        }

    def clear_history(self, user_id="default"):
        """Clear chat history for a specific user."""
        chat_history = RedisChatMessageHistory(
            session_id=f"user:{user_id}",
            url=self.redis_url
        )
        chat_history.clear()

    def get_history(self, user_id="default"):
        """Get chat history for a specific user."""
        chat_history = RedisChatMessageHistory(
            session_id=f"user:{user_id}",
            url=self.redis_url
        )
        return chat_history.messages

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
        result = chatbot.ask(question)  # LLM decides short or detailed automatically
        print(f"Ответ: {result['answer']}")
        print(f"\nИсточники: {', '.join(set(result['sources']))}")