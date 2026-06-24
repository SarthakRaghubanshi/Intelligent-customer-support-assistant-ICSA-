from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from backend.services.auth_service import AuthService
from backend.repositories.knowledge_repository import KnowledgeRepository
from backend.models.knowledge_document import KnowledgeDocument
from backend.core.document_types import DOCUMENT_TYPES

class KnowledgeService:
    @staticmethod
    def _validate_document_type(document_type: str) -> None:
        """
        Validates that the given document type is one of the supported DOCUMENT_TYPES.
        Raises ValueError if invalid.
        """
        normalized_type = document_type.strip().lower()
        if normalized_type not in DOCUMENT_TYPES:
            raise ValueError(f"Invalid document type: '{document_type}'. Must be one of {DOCUMENT_TYPES}")

    @staticmethod
    def create_document(
        db: Session,
        token: str,
        restaurant_id: str,
        title: str,
        content: str,
        document_type: str
    ) -> KnowledgeDocument:
        """
        Enforces tenant isolation, validates the restaurant active status, validates 
        the document type, and persists a new KnowledgeDocument.
        """
        # Validate active restaurant status, tenant isolation, and customer blocks
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        # Service-level document type validation
        KnowledgeService._validate_document_type(document_type)

        # TODO: Record who created this document (created_by mapping)
        # TODO: Trigger audit logging event for document creation
        
        doc = KnowledgeRepository.create(
            db=db,
            restaurant_id=restaurant_id,
            title=title,
            content=content,
            document_type=document_type
        )

        from backend.rag.vector_store import add_document_to_vector_store
        add_document_to_vector_store(
            restaurant_id=restaurant_id,
            doc_id=doc.id,
            title=doc.title,
            content=doc.content,
            document_type=doc.document_type
        )

        return doc

    @staticmethod
    def upload_document_file(
        db: Session,
        token: str,
        restaurant_id: str,
        file_stream: Any,
        filename: str,
        title: str,
        document_type: str,
        reported_mime: str = None
    ) -> KnowledgeDocument:
        """
        Validates tenant isolation, parses the binary document stream, normalizes
        the content, creates the DB record, and registers the vectors in ChromaDB.
        """
        # 1. Enforce tenant isolation and active status checking
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        # 2. Validate document type before parsing
        KnowledgeService._validate_document_type(document_type)
        
        # 3. Call Ingestion Service validator and parser dispatcher
        from backend.services.ingestion_service import DocumentIngestionService
        parsed_content = DocumentIngestionService.validate_and_parse(
            file_stream=file_stream,
            filename=filename,
            reported_mime=reported_mime
        )
        
        # 4. Save to relational DB
        doc = KnowledgeRepository.create(
            db=db,
            restaurant_id=restaurant_id,
            title=title.strip(),
            content=parsed_content,
            document_type=document_type
        )
        
        # 5. Index into ChromaDB vector store
        from backend.rag.vector_store import add_document_to_vector_store
        add_document_to_vector_store(
            restaurant_id=restaurant_id,
            doc_id=doc.id,
            title=doc.title,
            content=doc.content,
            document_type=doc.document_type
        )
        
        return doc

    @staticmethod
    def get_document(db: Session, token: str, doc_id: str) -> Optional[KnowledgeDocument]:
        """
        Retrieves a document by ID. If found, enforces tenant isolation checks.
        """
        doc = KnowledgeRepository.get_by_id(db, doc_id)
        if not doc:
            return None
            
        # Validate tenant access to this document's restaurant context
        AuthService.validate_tenant_access(db, token, doc.restaurant_id)
        return doc

    @staticmethod
    def list_documents(
        db: Session,
        token: str,
        restaurant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[KnowledgeDocument]:
        """
        Enforces tenant isolation and retrieves a paginated list of active documents.
        """
        AuthService.validate_tenant_access(db, token, restaurant_id)
        return KnowledgeRepository.list_by_restaurant(db, restaurant_id, limit, offset)

    @staticmethod
    def search_documents(
        db: Session,
        token: str,
        restaurant_id: str,
        query: str
    ) -> List[KnowledgeDocument]:
        """
        Enforces tenant isolation and searches active documents for a substring match in the title.
        """
        AuthService.validate_tenant_access(db, token, restaurant_id)
        return KnowledgeRepository.search_by_title(db, restaurant_id, query)

    @staticmethod
    def update_document(
        db: Session,
        token: str,
        doc_id: str,
        update_dict: Dict[str, Any]
    ) -> Optional[KnowledgeDocument]:
        """
        Enforces tenant isolation and updates an active document.
        """
        doc = KnowledgeRepository.get_by_id(db, doc_id)
        if not doc:
            raise ValueError("Document not found")
            
        # Validate tenant access to the document's restaurant context
        AuthService.validate_tenant_access(db, token, doc.restaurant_id)
        
        # If document_type is being updated, perform validation
        if "document_type" in update_dict:
            KnowledgeService._validate_document_type(update_dict["document_type"])

        # TODO: Record who updated this document (updated_by mapping)
        # TODO: Trigger audit logging event for document modification
        
        updated_doc = KnowledgeRepository.update(db, doc_id, update_dict)
        if updated_doc:
            from backend.rag.vector_store import delete_document_from_vector_store, add_document_to_vector_store
            delete_document_from_vector_store(
                restaurant_id=updated_doc.restaurant_id,
                doc_id=updated_doc.id
            )
            add_document_to_vector_store(
                restaurant_id=updated_doc.restaurant_id,
                doc_id=updated_doc.id,
                title=updated_doc.title,
                content=updated_doc.content,
                document_type=updated_doc.document_type
            )
        return updated_doc

    @staticmethod
    def delete_document(db: Session, token: str, doc_id: str) -> bool:
        """
        Enforces tenant isolation and soft-deletes a document.
        """
        doc = KnowledgeRepository.get_by_id(db, doc_id)
        if not doc:
            return False
            
        # Validate tenant access to the document's restaurant context
        AuthService.validate_tenant_access(db, token, doc.restaurant_id)

        # TODO: Trigger audit logging event for document deletion
        
        from backend.rag.vector_store import delete_document_from_vector_store
        delete_document_from_vector_store(
            restaurant_id=doc.restaurant_id,
            doc_id=doc.id
        )

        return KnowledgeRepository.soft_delete(db, doc_id)

    @staticmethod
    def get_document_count(db: Session, token: str, restaurant_id: str) -> int:
        """
        Enforces tenant isolation and returns the total count of active documents.
        """
        AuthService.validate_tenant_access(db, token, restaurant_id)
        return KnowledgeRepository.get_document_count(db, restaurant_id)

    @staticmethod
    def rebuild_vector_store(db: Session, token: str, restaurant_id: str) -> None:
        """
        Enforces tenant isolation and active status check, then triggers a full rebuild 
        of the restaurant's vector database.
        """
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        from backend.rag.vector_store import sync_restaurant_knowledge_base
        sync_restaurant_knowledge_base(db, restaurant_id)
