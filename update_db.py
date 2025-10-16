import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin SDK
cred = credentials.Certificate("/home/marianoberton/pipeline_licitaciones/procesos-inted-firebase-adminsdk-qwt8a-8324a99c15.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def update_field_names():
    docs = db.collection("procesos-bac").stream()
    for doc in docs:
        data = doc.to_dict()
        if "Número de proceso" in data:
            numero_proceso = data["Número de proceso"]
            data["numero_proceso"] = numero_proceso
            del data["Número de proceso"]
            doc.reference.set(data)
            print(f"Updated document {doc.id}")

if __name__ == "__main__":
    update_field_names()
