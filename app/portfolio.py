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

    def load_portfolio(self):
        """Loads data from CSV into ChromaDB collection if collection is empty."""
        if self.collection.count() == 0 and os.path.exists(self.file_path):
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
        """Retrieves all indexed portfolios as a pandas DataFrame."""
        if os.path.exists(self.file_path):
            return pd.read_csv(self.file_path)
        data = self.collection.get()
        records = []
        for doc, meta in zip(data.get("documents", []), data.get("metadatas", [])):
            records.append({
                "Techstack": doc,
                "Links": meta.get("links", "")
            })
        return pd.DataFrame(records)

    def add_portfolio(self, techstack: str, links: str) -> bool:
        """Adds a new techstack and link entry to both ChromaDB and CSV."""
        techstack = techstack.strip()
        links = links.strip()
        if not techstack or not links:
            return False

        self.collection.add(
            documents=[techstack],
            metadatas=[{"links": links}],
            ids=[str(uuid.uuid4())]
        )

        # Update CSV if exists
        try:
            if os.path.exists(self.file_path):
                df = pd.read_csv(self.file_path)
                new_row = pd.DataFrame([{"Techstack": techstack, "Links": links}])
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(self.file_path, index=False)
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            
        return True
