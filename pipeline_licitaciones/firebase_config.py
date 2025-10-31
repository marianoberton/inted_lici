"""
Configuración segura de Firebase para el Pipeline de Licitaciones.

Este módulo maneja la inicialización de Firebase de manera segura,
soportando múltiples métodos de autenticación:
1. Variables de entorno (JSON como string)
2. Archivo de credenciales (desarrollo local)
3. Credenciales por defecto de Google Cloud (producción)
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import logging
import base64

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FirebaseConfig:
    """Clase para manejar la configuración segura de Firebase."""
    
    def __init__(self):
        self.db = None
        self.app = None
        
    def initialize_firebase(self):
        """
        Inicializa Firebase usando el método de autenticación disponible.
        
        Orden de prioridad:
        1. FIREBASE_CREDENTIALS_JSON (variable de entorno con JSON)
        2. FIREBASE_CREDENTIALS_PATH (ruta al archivo de credenciales)
        3. Credenciales por defecto de Google Cloud
        
        Returns:
            firestore.Client: Cliente de Firestore inicializado
        """
        if self.db is not None:
            return self.db
            
        try:
            # Método 1: JSON desde variable de entorno
            credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            if credentials_json:
                logger.info("Usando credenciales desde FIREBASE_CREDENTIALS_JSON")
                # Intentar cargar JSON y aplicar saneado si falla
                try:
                    cred_dict = json.loads(credentials_json)
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON de FIREBASE_CREDENTIALS_JSON inválido, aplicando saneado: {je}")
                    cleaned = credentials_json.strip()
                    # Remover comillas envolventes si existen
                    if (cleaned.startswith("'") and cleaned.endswith("'")) or (
                        cleaned.startswith('"') and cleaned.endswith('"')
                    ):
                        cleaned = cleaned[1:-1]
                    # Normalizar saltos de línea en claves (\r\n -> \n) y evitar saltos reales
                    cleaned = cleaned.replace("\r\n", "\\n").replace("\n", "\\n")
                    try:
                        cred_dict = json.loads(cleaned)
                    except Exception as je2:
                        logger.warning(f"Reintento de carga tras saneado falló: {je2}. Probando base64...")
                        try:
                            decoded = base64.b64decode(credentials_json).decode('utf-8')
                            cred_dict = json.loads(decoded)
                        except Exception as je3:
                            logger.error(f"No se pudo decodificar FIREBASE_CREDENTIALS_JSON ni tras saneado ni como base64: {je3}")
                            raise
                cred = credentials.Certificate(cred_dict)
                self.app = firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                return self.db
            
            # Método 2: Archivo de credenciales
            credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
            if credentials_path and os.path.exists(credentials_path):
                logger.info(f"Usando archivo de credenciales: {credentials_path}")
                cred = credentials.Certificate(credentials_path)
                self.app = firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                return self.db
            
            # Método 3: Buscar archivo en ubicaciones conocidas (fallback)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(script_dir, 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json'),
                os.path.join(os.path.dirname(script_dir), 'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json'),
                'procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json'
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    logger.info(f"Usando archivo de credenciales encontrado: {path}")
                    cred = credentials.Certificate(path)
                    self.app = firebase_admin.initialize_app(cred)
                    self.db = firestore.client()
                    return self.db
            
            # Método 4: Credenciales por defecto (Google Cloud)
            logger.info("Intentando usar credenciales por defecto de Google Cloud")
            self.app = firebase_admin.initialize_app()
            self.db = firestore.client()
            return self.db
            
        except Exception as e:
            logger.error(f"Error al inicializar Firebase: {e}")
            raise Exception(f"No se pudo inicializar Firebase. Verifica las credenciales. Error: {e}")
    
    def get_firestore_client(self):
        """
        Obtiene el cliente de Firestore, inicializándolo si es necesario.
        
        Returns:
            firestore.Client: Cliente de Firestore
        """
        if self.db is None:
            return self.initialize_firebase()
        return self.db
    
    def close(self):
        """Cierra la conexión de Firebase."""
        if self.app:
            firebase_admin.delete_app(self.app)
            self.app = None
            self.db = None

# Instancia global para reutilizar la conexión
_firebase_config = FirebaseConfig()

def get_firestore_client():
    """
    Función de conveniencia para obtener el cliente de Firestore.
    
    Returns:
        firestore.Client: Cliente de Firestore inicializado
    """
    return _firebase_config.get_firestore_client()

def initialize_firebase():
    """
    Función de conveniencia para inicializar Firebase.
    
    Returns:
        firestore.Client: Cliente de Firestore inicializado
    """
    return _firebase_config.initialize_firebase()