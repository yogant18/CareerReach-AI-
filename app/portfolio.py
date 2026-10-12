import os
import uuid
import chromadb
import pandas as pd
from typing import List, Dict, Any


class Portfolio:
    def __init__(self, file_path: str = "my_portfolio.csv", vectorstore_path: str = "vectorstore"):
        self.file_path = file_path
        self.vectorstore_path = vectorstore_path
        
        # Ensure path resolution relative to workspace root if not absolute
        if not os.path.isabs(self.file_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidate = os.path.join(base_dir, self.file_path)
            if os.path.exists(candidate):
                self.file_path = candidate

        if not os.path.isabs(self.vectorstore_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.vectorstore_path = os.path.join(base_dir, self.vectorstore_path)

        os.makedirs(self.vectorstore_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.vectorstore_path)
        self.collection = self.chroma_client.get_or_create_collection(name="portfolio")
        
        self.load_portfolio()

    def load_portfolio(self, force_reload: bool = False):
        """Loads data from CSV into ChromaDB collection. Re-syncs if force_reload is True."""
        if force_reload:
            try:
                # Delete existing documents to re-sync
                all_ids = self.collection.get().get("ids", [])
                if all_ids:
                    self.collection.delete(ids=all_ids)
            except Exception as e:
                print(f"Error resetting collection: {e}")

        if (self.collection.count() == 0 or force_reload) and os.path.exists(self.file_path):
            df = pd.read_csv(self.file_path)
            for _, row in df.iterrows():
                techstack = str(row.get("Techstack", "")).strip()
                links = str(row.get("Links", "")).strip()
                if techstack and links:
                    self.collection.add(
                        documents=[techstack],
                        metadatas=[{"links": links}],
                        ids=[str(uuid.uuid4())]
                    )

    def query_links(self, skills: Any, n_results: int = 2) -> List[Dict[str, str]]:
        """
        Queries ChromaDB for links matching given skills (list of strings or a single query string).
        Returns a list of unique metadata dictionaries containing 'links'.
        """
        if not skills:
            return []

        query_texts = []
        if isinstance(skills, list):
            query_texts = [str(s).strip() for s in skills if str(s).strip()]
        elif isinstance(skills, str):
            query_texts = [skills.strip()]

        if not query_texts:
            return []

        try:
            results = self.collection.query(query_texts=query_texts, n_results=n_results)
            metadatas = results.get("metadatas", [])
            
            seen_links = set()
            unique_links = []
            for meta_list in metadatas:
                for item in meta_list:
                    link = item.get("links")
                    if link and link not in seen_links:
                        seen_links.add(link)
                        unique_links.append({"links": link})
            return unique_links
        except Exception as e:
            print(f"Error querying portfolio: {e}")
            return []

    def get_all_portfolios(self) -> pd.DataFrame:
        """
        Retrieves all indexed portfolios directly from ChromaDB.
        Falls back to CSV if ChromaDB collection is empty.
        """
        data = self.collection.get()
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])
        if documents:
            records = []
            for doc, meta in zip(documents, metadatas):
                records.append({
                    "Techstack": doc,
                    "Links": (meta or {}).get("links", "")
                })
            return pd.DataFrame(records)

        if os.path.exists(self.file_path):
            return pd.read_csv(self.file_path)
        return pd.DataFrame(columns=["Techstack", "Links"])

    def add_portfolio(self, techstack: str, links: str) -> bool:
        """
        Adds a new techstack and link entry to both ChromaDB and CSV.
        Rejects links not starting with http:// or https://.
        Raises an exception or returns False if CSV saving fails.
        """
        techstack = techstack.strip()
        links = links.strip()
        if not techstack or not links:
            return False

        # item 12: Validate URL scheme
        if not (links.startswith("http://") or links.startswith("https://")):
            raise ValueError("Portfolio link must start with http:// or https://")

        self.collection.add(
            documents=[techstack],
            metadatas=[{"links": links}],
            ids=[str(uuid.uuid4())]
        )

        # Update CSV (item 14: propagate error on failure)
        try:
            if os.path.exists(self.file_path):
                df = pd.read_csv(self.file_path)
                new_row = pd.DataFrame([{"Techstack": techstack, "Links": links}])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(self.file_path, index=False)
            else:
                # File path specified does not exist or cannot be written
                parent = os.path.dirname(self.file_path)
                if parent and not os.path.exists(parent):
                    raise IOError(f"Directory for CSV file does not exist: {parent}")
                df = pd.DataFrame([{"Techstack": techstack, "Links": links}])
                df.to_csv(self.file_path, index=False)
        except Exception as e:
            raise IOError(f"Added to ChromaDB, but failed to save to CSV file: {e}") from e

        return True
