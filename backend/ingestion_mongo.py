import os
import pandas as pd
from pymongo import MongoClient

# Costanti e Percorsi
MONGO_URI = "mongodb://root:password@localhost:27017/"
DB_NAME = "maadb"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "dataset", "raw"))

# Funzione per trovare i file CSV in una cartella
def get_csv_files(folder_name):
    folder_path = os.path.join(DATASET_PATH, folder_name)
    if not os.path.exists(folder_path):
        return []
    # Ritorna tutti i file che iniziano con "part-" e finiscono in ".csv"
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.startswith("part-") and f.endswith(".csv")]
    return files

def ingest_to_mongo():
    print("Connessione a MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # Collezioni da importare
    collections_to_import = ['person', 'company', 'account']
    
    for coll_name in collections_to_import:
        print(f"\nInizio Ingestion per: {coll_name}")
        csv_files = get_csv_files(coll_name)
        
        if not csv_files:
            print(f"Nessun file CSV trovato per {coll_name}")
            continue
            
        # Svuotiamo la collezione prima di importare (utile se ri-eseguiamo lo script)
        db[coll_name].drop()
        
        total_inserted = 0
        for file in csv_files:
            # Leggiamo il CSV con pandas, notare il separatore '|' usato dal FinBench Datagen
            df = pd.read_csv(file, sep='|')
            
            # Convertiamo il dataframe in una lista di dizionari per MongoDB
            records = df.to_dict(orient='records')
            
            if records:
                db[coll_name].insert_many(records)
                total_inserted += len(records)
                
        print(f"[OK] Inseriti {total_inserted} documenti nella collezione '{coll_name}'")
        
if __name__ == "__main__":
    ingest_to_mongo()
