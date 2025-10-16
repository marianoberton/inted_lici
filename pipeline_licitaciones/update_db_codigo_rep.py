import firebase_admin
from firebase_admin import credentials, firestore
import re

# Inicializar Firebase de manera segura
from firebase_config import get_firestore_client
db = get_firestore_client()

def actualizar_codigo_reparticion():
    docs = db.collection('procesos-bac').stream()
    for doc in docs:
        data = doc.to_dict()
        numero_proceso = data.get('numero_proceso', '')
        # Extraer codigo_reparticion
        codigo_reparticion = numero_proceso.split('-')[0] if '-' in numero_proceso else ''
        if codigo_reparticion:
            try:
                # Actualizar el documento con el nuevo campo
                db.collection('procesos-bac').document(doc.id).update({
                    'codigo_reparticion': codigo_reparticion
                })
                print(f"Documento {doc.id} actualizado con codigo_reparticion: {codigo_reparticion}")
            except Exception as e:
                print(f"Error al actualizar el documento {doc.id}: {e}")
        else:
            print(f"No se pudo extraer codigo_reparticion del documento {doc.id}")

if __name__ == '__main__':
    actualizar_codigo_reparticion()
