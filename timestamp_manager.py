#!/usr/bin/env python3
"""
TimestampManager - Sistema robusto para manejo de timestamps usando Firestore
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
import logging

class TimestampManager:
    """
    Maneja timestamps de procesamiento usando Firestore como backend
    Proporciona operaciones atómicas y recuperación automática
    """
    
    def __init__(self, db: firestore.Client):
        self.db = db
        self.collection_name = 'system_state'
        self.doc_id = 'notification_timestamps'
        self.logger = logging.getLogger(__name__)
    
    def get_last_timestamp(self, source: str = 'caba') -> datetime:
        """
        Obtiene el último timestamp procesado para una fuente específica
        
        Args:
            source: Fuente de datos ('caba', 'nacion', etc.)
            
        Returns:
            datetime: Último timestamp procesado
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(self.doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                timestamp_key = f'{source}_last_timestamp'
                
                if timestamp_key in data and data[timestamp_key]:
                    # Convertir string a datetime
                    timestamp_str = data[timestamp_key]
                    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    self.logger.warning(f"No timestamp found for source: {source}")
            else:
                self.logger.info("No timestamp document exists, creating default")
                self._initialize_document()
            
            # Retornar timestamp por defecto
            return self._get_default_timestamp(source)
            
        except Exception as e:
            self.logger.error(f"Error getting timestamp for {source}: {e}")
            return self._get_default_timestamp(source)
    
    def update_timestamp(self, timestamp: datetime, source: str = 'caba', 
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Actualiza el timestamp de forma atómica
        
        Args:
            timestamp: Nuevo timestamp a guardar
            source: Fuente de datos
            metadata: Información adicional (documentos procesados, etc.)
            
        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(self.doc_id)
            
            # Preparar datos para actualización
            update_data = {
                f'{source}_last_timestamp': timestamp.isoformat(),
                f'{source}_updated_at': datetime.now(timezone.utc).isoformat(),
                'last_update': datetime.now(timezone.utc).isoformat()
            }
            
            # Agregar metadata si se proporciona
            if metadata:
                update_data[f'{source}_metadata'] = metadata
            
            # Actualización atómica
            doc_ref.set(update_data, merge=True)
            
            self.logger.info(f"Timestamp updated for {source}: {timestamp.isoformat()}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating timestamp for {source}: {e}")
            return False
    
    def get_processing_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado completo del sistema de procesamiento
        
        Returns:
            Dict con el estado de todas las fuentes
        """
        try:
            doc_ref = self.db.collection(self.collection_name).document(self.doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return {"status": "not_initialized"}
                
        except Exception as e:
            self.logger.error(f"Error getting processing status: {e}")
            return {"error": str(e)}
    
    def rollback_timestamp(self, source: str = 'caba', minutes: int = 60) -> bool:
        """
        Retrocede el timestamp para reprocesar documentos recientes
        
        Args:
            source: Fuente de datos
            minutes: Minutos a retroceder
            
        Returns:
            bool: True si el rollback fue exitoso
        """
        try:
            current_timestamp = self.get_last_timestamp(source)
            rollback_timestamp = current_timestamp.replace(
                minute=current_timestamp.minute - minutes
            )
            
            metadata = {
                "rollback_performed": True,
                "rollback_minutes": minutes,
                "previous_timestamp": current_timestamp.isoformat(),
                "rollback_at": datetime.now(timezone.utc).isoformat()
            }
            
            return self.update_timestamp(rollback_timestamp, source, metadata)
            
        except Exception as e:
            self.logger.error(f"Error performing rollback for {source}: {e}")
            return False
    
    def mark_document_processed(self, document_id: str, source: str, 
                              timestamp: datetime) -> bool:
        """
        Marca un documento específico como procesado
        
        Args:
            document_id: ID del documento
            source: Fuente de datos
            timestamp: Timestamp del documento
            
        Returns:
            bool: True si se marcó correctamente
        """
        try:
            # Crear registro de documento procesado
            processed_doc = {
                'document_id': document_id,
                'source': source,
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'document_timestamp': timestamp.isoformat()
            }
            
            # Guardar en colección de documentos procesados
            self.db.collection('processed_documents').add(processed_doc)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error marking document as processed: {e}")
            return False
    
    def get_unprocessed_documents_count(self, source: str = 'caba') -> int:
        """
        Obtiene el número aproximado de documentos sin procesar
        
        Args:
            source: Fuente de datos
            
        Returns:
            int: Número de documentos sin procesar
        """
        try:
            last_timestamp = self.get_last_timestamp(source)
            
            # Determinar colección según fuente
            collection_name = 'procesos-bac' if source == 'caba' else 'procesos-nacion'
            
            # Consultar documentos posteriores al último timestamp
            query = self.db.collection(collection_name).where(
                filter=FieldFilter('timestamp', '>', last_timestamp.isoformat())
            )
            
            # Contar documentos (limitado para performance)
            docs = list(query.limit(1000).stream())
            return len(docs)
            
        except Exception as e:
            self.logger.error(f"Error counting unprocessed documents: {e}")
            return -1
    
    def _initialize_document(self):
        """Inicializa el documento de timestamps con valores por defecto"""
        try:
            doc_ref = self.db.collection(self.collection_name).document(self.doc_id)
            
            initial_data = {
                'created_at': datetime.now(timezone.utc).isoformat(),
                'caba_last_timestamp': self._get_default_timestamp('caba').isoformat(),
                'nacion_last_timestamp': self._get_default_timestamp('nacion').isoformat(),
                'version': '1.0'
            }
            
            doc_ref.set(initial_data)
            self.logger.info("Timestamp document initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing document: {e}")
    
    def _get_default_timestamp(self, source: str) -> datetime:
        """Retorna timestamp por defecto según la fuente"""
        # Usar fechas recientes para evitar procesar demasiados documentos históricos
        if source == 'caba':
            return datetime(2024, 12, 1, tzinfo=timezone.utc)
        elif source == 'nacion':
            return datetime(2024, 12, 1, tzinfo=timezone.utc)
        else:
            return datetime(2024, 11, 1, tzinfo=timezone.utc)


# Funciones de utilidad para migración desde el sistema actual
def migrate_from_file_system(db: firestore.Client, file_path: str, source: str = 'caba'):
    """
    Migra timestamps desde el sistema de archivos al nuevo sistema
    
    Args:
        db: Cliente de Firestore
        file_path: Ruta del archivo de timestamp actual
        source: Fuente de datos
    """
    import os
    
    timestamp_manager = TimestampManager(db)
    
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                timestamp_str = f.read().strip()
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                
                metadata = {
                    "migrated_from_file": True,
                    "original_file": file_path,
                    "migration_date": datetime.now(timezone.utc).isoformat()
                }
                
                if timestamp_manager.update_timestamp(timestamp, source, metadata):
                    print(f"✅ Migración exitosa para {source}: {timestamp}")
                    return True
                else:
                    print(f"❌ Error en migración para {source}")
                    return False
        else:
            print(f"⚠️ Archivo no encontrado: {file_path}")
            return False
            
    except Exception as e:
        print(f"❌ Error en migración: {e}")
        return False


if __name__ == "__main__":
    # Ejemplo de uso
    import firebase_admin
    from firebase_admin import credentials
    
    # Inicializar Firebase (ajustar ruta según necesidad)
    if not firebase_admin._apps:
        cred = credentials.Certificate('pipeline_licitaciones/procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json')
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    timestamp_manager = TimestampManager(db)
    
    # Ejemplo de operaciones
    print("=== TimestampManager Demo ===")
    
    # Obtener estado actual
    status = timestamp_manager.get_processing_status()
    print(f"Estado actual: {status}")
    
    # Obtener último timestamp
    last_timestamp = timestamp_manager.get_last_timestamp('caba')
    print(f"Último timestamp CABA: {last_timestamp}")
    
    # Contar documentos sin procesar
    unprocessed = timestamp_manager.get_unprocessed_documents_count('caba')
    print(f"Documentos sin procesar: {unprocessed}")