"""
    # First run — build the vector store
    await rag_engine.ingest()

    # Query
    answer = await rag_engine.query("Which card is best for Marriott?")
"""

import os
import glob
from pathlib import Path
from typing import Optional

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

from app.core.config import settings

# ─── Paths ────────────────────────────────────────────────────────────────────
KB_DIR      = Path(__file__).parent / "knowledge_base"
CHROMA_DIR  = Path(__file__).parent / "chroma_db"


# ─── Prompt Template ──────────────────────────────────────────────────────────
RAG_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are Optivoy's loyalty rewards expert. You help users maximize
the value of their credit card points when booking hotels.

Use the context below to answer the question. Be specific, cite transfer ratios
and valuations where relevant, and always tell the user which card gives the
best value and why. Keep answers concise but complete.

If the context doesn't contain enough information, say so clearly rather than
making things up.

Context:
{context}

Question: {question}

Answer:"""
)


class RAGEngine:
    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY
        self.embeddings     = None
        self.vectorstore    = None
        self.qa_chain       = None
        self._initialized   = False

    def _get_embeddings(self) -> OpenAIEmbeddings:
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=self.openai_api_key,
        )

    def _get_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,          # low temp = factual, consistent answers
            openai_api_key=self.openai_api_key,
        )

    async def ingest(self, force_rebuild: bool = False) -> int:
        """
        Load all .txt files from knowledge_base/, chunk them,
        embed with OpenAI, and store in ChromaDB.
        Returns number of documents ingested.
        """
        # Skip if already built unless forced
        if CHROMA_DIR.exists() and not force_rebuild:
            print("[RAG] Vector store already exists — loading from disk.")
            await self._load_existing()
            return 0

        print("[RAG] Building vector store from knowledge base...")

        # Load all knowledge base documents
        docs = self._load_documents()
        if not docs:
            raise FileNotFoundError(f"No .txt files found in {KB_DIR}")

        # Chunk documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(docs)
        print(f"[RAG] Loaded {len(docs)} documents → {len(chunks)} chunks")

        # Embed and store
        self.embeddings  = self._get_embeddings()
        self.vectorstore = Chroma.from_documents(
            documents       = chunks,
            embedding       = self.embeddings,
            persist_directory = str(CHROMA_DIR),
        )

        self._build_chain()
        self._initialized = True
        print(f"[RAG] Vector store built and saved to {CHROMA_DIR}")
        return len(chunks)

    async def _load_existing(self):
        """Load an already-built vector store from disk."""
        self.embeddings  = self._get_embeddings()
        self.vectorstore = Chroma(
            persist_directory = str(CHROMA_DIR),
            embedding_function = self.embeddings,
        )
        self._build_chain()
        self._initialized = True

    def _build_chain(self):
        """Build the RetrievalQA chain."""
        retriever = self.vectorstore.as_retriever(
            search_type = "similarity",
            search_kwargs = {"k": 4},   # retrieve top 4 chunks
        )
        self.qa_chain = RetrievalQA.from_chain_type(
            llm             = self._get_llm(),
            chain_type      = "stuff",
            retriever       = retriever,
            chain_type_kwargs = {"prompt": RAG_PROMPT},
            return_source_documents = True,
        )

    def _load_documents(self) -> list[Document]:
        """Load all .txt files from knowledge base directory."""
        docs = []
        for filepath in sorted(KB_DIR.glob("*.txt")):
            text = filepath.read_text(encoding="utf-8")
            docs.append(Document(
                page_content = text,
                metadata     = {
                    "source":   filepath.name,
                    "filename": filepath.stem,
                }
            ))
            print(f"[RAG]   Loaded: {filepath.name}")
        return docs

    async def _ensure_initialized(self):
        """Auto-ingest if vector store not yet built."""
        if not self._initialized:
            if CHROMA_DIR.exists():
                await self._load_existing()
            else:
                await self.ingest()

    async def query(
        self,
        question: str,
        user_context: Optional[dict] = None,
    ) -> dict:
        """
        Answer a natural language question using the knowledge base.

        user_context (optional): dict with user-specific data to prepend
        e.g. {"cards": ["Chase Sapphire", "Amex Gold"], "balance": 42000}
        """
        await self._ensure_initialized()

        # Enrich question with user context if provided
        enriched_question = question
        if user_context:
            context_str = self._format_user_context(user_context)
            enriched_question = f"{context_str}\n\nQuestion: {question}"

        result = self.qa_chain.invoke({"query": enriched_question})

        sources = list({
            doc.metadata.get("filename", "unknown")
            for doc in result.get("source_documents", [])
        })

        return {
            "question": question,
            "answer":   result["result"],
            "sources":  sources,
        }

    async def query_with_recommendation(
        self,
        question: str,
        recommendations: list,
    ) -> dict:
        """
        Answer a question in the context of specific agent recommendations.
        Used for follow-up questions after the agent shows top 3 options.
        """
        rec_context = "\n".join([
            f"Option {r.rank}: {r.card_name} → {r.loyalty_program} | "
            f"{r.points_to_use:,} pts | ratio {r.transfer_ratio}x | "
            f"${r.cash_remainder} cash | {r.value_per_point}¢/pt"
            for r in recommendations
        ])

        enriched = (
            f"The user has been shown these top redemption options:\n"
            f"{rec_context}\n\n"
            f"Question: {question}"
        )

        return await self.query(enriched)

    def _format_user_context(self, context: dict) -> str:
        lines = ["User context:"]
        if "cards" in context:
            lines.append(f"Cards: {', '.join(context['cards'])}")
        if "balances" in context:
            for card, bal in context["balances"].items():
                lines.append(f"  {card}: {bal:,} points")
        if "hotel" in context:
            lines.append(f"Target hotel: {context['hotel']}")
        return "\n".join(lines)


# Singleton
rag_engine = RAGEngine()