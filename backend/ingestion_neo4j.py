import os
import pandas as pd
from neo4j import GraphDatabase

# Costanti e Percorsi
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "password1234")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "dataset", "raw"))

def get_csv_files(folder_name):
    folder_path = os.path.join(DATASET_PATH, folder_name)
    if not os.path.exists(folder_path):
        return []
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.startswith("part-") and f.endswith(".csv")]

def create_constraints(session):
    """Crea constraint di unicità su id per ogni label.
    I constraint creano automaticamente un B-tree index su 'id',
    e accelerano i MERGE durante l'ingestion stessa.
    """
    constraints = [
        "CREATE CONSTRAINT person_id_unique  IF NOT EXISTS FOR (p:Person)  REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT company_id_unique IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE",
    ]
    for cypher in constraints:
        session.run(cypher)
    print("[OK] Constraint di unicità (+ indici B-tree) creati su Person, Company, Account.")


def create_nodes(tx, label, id_col, batch):
    query = f"""
    UNWIND $batch AS row
    MERGE (n:{label} {{id: row.{id_col}}})
    """
    tx.run(query, batch=batch)


def create_relationships(tx, rel_type, from_label, to_label, from_id_col, to_id_col, batch):
    """Crea le relazioni tra nodi già esistenti.
    Per le relazioni TRANSFERS aggiunge anche le proprietà 'amount' e 'payType'
    presenti nel dataset FinBench, utili per future query analitiche.
    Le relazioni OWNS non hanno proprietà rilevanti oltre agli ID.
    """
    if rel_type == "TRANSFERS":
        # Arricchiamo i TRANSFERS con le proprietà finanziarie del dataset
        query = f"""
        UNWIND $batch AS row
        MATCH (from:{from_label} {{id: row.{from_id_col}}})
        MATCH (to:{to_label}   {{id: row.{to_id_col}}})
        MERGE (from)-[r:{rel_type}]->(to)
        SET r.amount  = toFloat(row.amount),
            r.payType = row.payType
        """
    else:
        query = f"""
        UNWIND $batch AS row
        MATCH (from:{from_label} {{id: row.{from_id_col}}})
        MATCH (to:{to_label}   {{id: row.{to_id_col}}})
        MERGE (from)-[r:{rel_type}]->(to)
        """
    tx.run(query, batch=batch)

def ingest_to_neo4j():
    print("Connessione a Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    
    with driver.session() as session:
        # Pulisci il database per sicurezza (essendo un ambiente locale di test)
        session.run("MATCH (n) DETACH DELETE n")
        print("[OK] Database Neo4j ripulito.")

        # Constraint di unicità → creano automaticamente indici B-tree su 'id'.
        # Vanno creati PRIMA dei nodi: così ogni MERGE successivo usa l'indice.
        create_constraints(session)

        # --- 1. Creazione dei Nodi (Person, Company, Account) ---
        nodes_to_create = [
            ('person', 'Person', 'id'),
            ('company', 'Company', 'id'),
            ('account', 'Account', 'id')
        ]
        
        for folder, label, id_col in nodes_to_create:
            csv_files = get_csv_files(folder)
            for file in csv_files:
                df = pd.read_csv(file, sep='|', usecols=[id_col])
                records = df.to_dict('records')
                # Suddividiamo in chunk da 1000 per non sovraccaricare Neo4j
                for i in range(0, len(records), 1000):
                    batch = records[i:i+1000]
                    session.execute_write(create_nodes, label, id_col, batch)
            print(f"[OK] Creati i nodi per {label}")

        # --- 2. Creazione delle Relazioni (Owns, Transfers) ---
        rels_to_create = [
            ('personOwnAccount', 'OWNS', 'Person', 'Account', 'personId', 'accountId'),
            ('companyOwnAccount', 'OWNS', 'Company', 'Account', 'companyId', 'accountId'),
            ('transfer', 'TRANSFERS', 'Account', 'Account', 'fromId', 'toId')
        ]
        
        for folder, rel_type, from_label, to_label, from_col, to_col in rels_to_create:
            csv_files = get_csv_files(folder)
            for file in csv_files:
                # Per i TRANSFERS leggiamo anche le proprietà finanziarie;
                # per le altre relazioni bastano i soli ID degli estremi.
                if rel_type == "TRANSFERS":
                    cols = [from_col, to_col, 'amount', 'payType']
                else:
                    cols = [from_col, to_col]
                df = pd.read_csv(file, sep='|', usecols=cols)
                records = df.to_dict('records')
                for i in range(0, len(records), 1000):
                    batch = records[i:i+1000]
                    session.execute_write(create_relationships, rel_type, from_label, to_label, from_col, to_col, batch)
            print(f"[OK] Create le relazioni {rel_type} per i file in {folder}")

    driver.close()
    print("[OK] Ingestion su Neo4j completata con successo!")

if __name__ == "__main__":
    ingest_to_neo4j()
