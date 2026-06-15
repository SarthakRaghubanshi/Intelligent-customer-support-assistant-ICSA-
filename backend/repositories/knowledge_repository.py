from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from backend.models.knowledge_document import KnowledgeDocument

class KnowledgeRepository:
    @staticmethod
    def create(
        db: Session,
        restaurant_id: str,
        title: str,
        content: str,
        document_type: str
    ) -> KnowledgeDocument:
        """
        Creates and persists a new KnowledgeDocument record.
        """
        doc = KnowledgeDocument(
            restaurant_id=restaurant_id,
            title=title.strip(),
            content=content.strip(),
            document_type=document_type.strip().lower()
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def get_by_id(db: Session, doc_id: str) -> Optional[KnowledgeDocument]:
        """
        Retrieves an active (non-soft-deleted) KnowledgeDocument by ID.
        """
        return db.query(KnowledgeDocument).filter(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.deleted_at.is_(None)
        ).first()

    @staticmethod
    def list_by_restaurant(db: Session, restaurant_id: str) -> List[KnowledgeDocument]:
        """
        Lists all active, non-soft-deleted documents belonging to a restaurant.
        """
        return db.query(KnowledgeDocument).filter(
            KnowledgeDocument.restaurant_id == restaurant_id,
            KnowledgeDocument.deleted_at.is_(None)
        ).all()

    @staticmethod
    def search_by_document_type(
        db: Session,
        restaurant_id: str,
        document_type: str
    ) -> List[KnowledgeDocument]:
        """
        Searches active documents of a specific type for a restaurant (case-insensitive).
        """
        return db.query(KnowledgeDocument).filter(
            KnowledgeDocument.restaurant_id == restaurant_id,
            KnowledgeDocument.deleted_at.is_(None),
            func.lower(KnowledgeDocument.document_type) == document_type.strip().lower()
        ).all()

    @staticmethod
    def search_by_title(
        db: Session,
        restaurant_id: str,
        title_query: str
    ) -> List[KnowledgeDocument]:
        """
        Searches active documents by title substring match for a restaurant (case-insensitive).
        """
        return db.query(KnowledgeDocument).filter(
            KnowledgeDocument.restaurant_id == restaurant_id,
            KnowledgeDocument.deleted_at.is_(None),
            KnowledgeDocument.title.ilike(f"%{title_query.strip()}%")
        ).all()

    @staticmethod
    def update(
        db: Session,
        doc_id: str,
        update_dict: Dict[str, Any]
    ) -> Optional[KnowledgeDocument]:
        """
        Updates the fields of an active KnowledgeDocument.
        """
        doc = KnowledgeRepository.get_by_id(db, doc_id)
        if not doc:
            return None

        for key, value in update_dict.items():
            if hasattr(doc, key):
                if isinstance(value, str):
                    value = value.strip()
                setattr(doc, key, value)

        db.commit()
        db.refresh(doc)
        return doc

    @staticmethod
    def soft_delete(db: Session, doc_id: str) -> bool:
        """
        Flags a KnowledgeDocument as soft-deleted by setting the deleted_at timestamp.
        """
        doc = KnowledgeRepository.get_by_id(db, doc_id)
        if not doc:
            return False
        doc.deleted_at = func.now()
        db.commit()
        return True
