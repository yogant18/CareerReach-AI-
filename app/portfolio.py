import os
import uuid
import weakref
import chromadb
import pandas as pd
from typing import Any, Dict, List, Optional

# Upper bound on items in one visitor's portfolio, to protect server memory.
MAX_ITEMS = 200

COLUMNS = ["Techstack", "Links"]


def _drop_collection(client, name: str) -> None:
    try:
        client.delete_collection(name)
    except Exception:
        pass


class Portfolio:
    """
    One visitor's private portfolio.

    Each instance owns its own in-memory ChromaDB collection, so items added,
    uploaded or cleared by one visitor are never visible to another. Nothing is
    written to disk. The collection is deleted when the instance is garbage
    collected (i.e. when the visitor's session ends).

    ``seed_csv_path`` is an optional read-only starter CSV (Techstack, Links)
    copied into every new portfolio.
    """

    def __init__(self, client=None, seed_csv_path: Optional[str] = None):
        self.client = client if client is not None else chromadb.EphemeralClient()
        self.seed_csv_path = seed_csv_path
        self.collection_name = f"portfolio_{uuid.uuid4().hex}"
        self.collection = self.client.get_or_create_collection(name=self.collection_name)
        weakref.finalize(self, _drop_collection, self.client, self.collection_name)
        self.load_portfolio()

    # ------------------------------------------------------------------
    # Loading / resetting
    # ------------------------------------------------------------------
    def _seed_dataframe(self) -> pd.DataFrame:
        if self.seed_csv_path and os.path.exists(self.seed_csv_path):
            try:
                return pd.read_csv(self.seed_csv_path)
            except Exception:
                pass
        return pd.DataFrame(columns=COLUMNS)

    def has_seed(self) -> bool:
        return not self._seed_dataframe().empty

    def load_portfolio(self, force_reload: bool = False):
        """Fills an empty portfolio from the starter CSV; with force_reload, resets to it."""
        if force_reload:
            self._delete_all()
        if self.collection.count() == 0:
            seed = self._seed_dataframe()
            if not seed.empty:
                self.load_from_dataframe(seed, force_reload=False)

    def _delete_all(self) -> None:
        try:
            all_ids = self.collection.get().get("ids", [])
            if all_ids:
                self.collection.delete(ids=all_ids)
        except Exception as e:
            print(f"Error resetting collection: {e}")

    def clear_portfolio(self):
        """Removes every item from this visitor's portfolio."""
        self._delete_all()

    def is_empty(self) -> bool:
        return self.collection.count() == 0

    def load_from_dataframe(self, df: pd.DataFrame, force_reload: bool = True) -> int:
        """
        Loads rows (Techstack, Links) into this portfolio and returns how many were added.
        Rows beyond MAX_ITEMS in total are skipped.
        """
        if force_reload:
            self._delete_all()

        room = max(0, MAX_ITEMS - self.collection.count())
        documents, metadatas, ids = [], [], []
        seen = set()
        for _, row in df.iterrows():
            if len(documents) >= room:
                break
            raw_tech, raw_links = row.get("Techstack"), row.get("Links")
            if pd.isna(raw_tech) or pd.isna(raw_links):
                continue  # blank cell
            techstack = str(raw_tech).strip()
            links = str(raw_links).strip()
            if not techstack or not links:
                continue
            key = (techstack.lower(), links)
            if key in seen:
                continue
            seen.add(key)
            documents.append(techstack)
            metadatas.append({"links": links})
            ids.append(str(uuid.uuid4()))

        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return len(documents)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------
    def query_links(self, skills: Any, n_results: int = 2, base_portfolio_url: str = "") -> List[Dict[str, str]]:
        """
        Queries ChromaDB for links matching given skills (list of strings or a single query string).
        Returns a list of unique metadata dictionaries containing 'links'.
        If base_portfolio_url is provided, it can be appended or used as custom proof URL.
        """
        count = self.collection.count()
        if count == 0:
            if base_portfolio_url and base_portfolio_url.strip():
                return [{"links": base_portfolio_url.strip()}]
            return []

        if not skills:
            if base_portfolio_url and base_portfolio_url.strip():
                return [{"links": base_portfolio_url.strip()}]
            return []

        query_texts = []
        if isinstance(skills, list):
            query_texts = [str(s).strip() for s in skills if str(s).strip()]
        elif isinstance(skills, str):
            query_texts = [skills.strip()]

        if not query_texts:
            return []

        try:
            results = self.collection.query(query_texts=query_texts, n_results=min(n_results, count))
            metadatas = results.get("metadatas", [])

            seen_links = set()
            unique_links = []
            for meta_list in metadatas:
                for item in meta_list:
                    link = item.get("links")
                    if link and link not in seen_links:
                        seen_links.add(link)
                        unique_links.append({"links": link})

            # If user provided their own portfolio URL in the sidebar, prioritize or append it
            if base_portfolio_url and base_portfolio_url.strip():
                clean_base = base_portfolio_url.strip()
                if clean_base not in seen_links:
                    unique_links.insert(0, {"links": clean_base})

            return unique_links
        except Exception as e:
            print(f"Error querying portfolio: {e}")
            return []

    def get_all_portfolios(self) -> pd.DataFrame:
        """
        Retrieves all items in this visitor's portfolio.
        Returns an empty DataFrame when nothing is indexed.
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

        return pd.DataFrame(columns=COLUMNS)

    def to_csv(self) -> str:
        """This visitor's portfolio as CSV text, for download and later re-upload."""
        return self.get_all_portfolios().to_csv(index=False)

    def add_portfolio(self, techstack: str, links: str) -> bool:
        """
        Adds a techstack and link entry to this visitor's portfolio.
        Rejects links not starting with http:// or https://, and raises
        ValueError when the portfolio is full.
        """
        techstack = techstack.strip()
        links = links.strip()
        if not techstack or not links:
            return False

        # item 12: Validate URL scheme
        if not (links.startswith("http://") or links.startswith("https://")):
            raise ValueError("Portfolio link must start with http:// or https://")

        # Skip exact duplicates
        current = self.get_all_portfolios()
        if not current.empty:
            is_dup = ((current["Techstack"].astype(str).str.strip().str.lower() == techstack.lower()) &
                      (current["Links"].astype(str).str.strip() == links)).any()
            if is_dup:
                return True

        if self.collection.count() >= MAX_ITEMS:
            raise ValueError(f"Portfolio is full ({MAX_ITEMS} items). Remove items before adding more.")

        self.collection.add(
            documents=[techstack],
            metadatas=[{"links": links}],
            ids=[str(uuid.uuid4())]
        )
        return True
