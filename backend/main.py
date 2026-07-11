from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from database import db

# App

app = FastAPI(
    title="MAADB Polyglot API",
    description="API per query poliglotte su MongoDB e Neo4j"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    db.connect()


@app.on_event("shutdown")
async def shutdown_event():
    db.disconnect()


@app.get("/")
def read_root():
    return {"message": "MAADB API is running!"}


# Categoria 1 — Query di Lookup

# L1 — (MongoDB) Anagrafica persona
@app.get("/api/lookup/person/{person_id}")
def get_person(person_id: int):
    """Restituisce i dati anagrafici di una persona dalla collezione MongoDB 'person'.
    Utilizzata dalla pagina /person (PersonLookup).
    """
    person = db.mongo_db.person.find_one(
        {"id": person_id}, {"_id": 0}
    )
    if not person:
        raise HTTPException(status_code=404, detail="Persona non trovata")
    return person


# L2 — (Neo4j) Catena di trasferimenti di un conto
@app.get("/api/lookup/account/{account_id}/transfers")
def get_account_transfers(account_id: int, hops: int = 2):
    """Percorre il grafo delle transazioni da un account per N hop.
    Utilizzata dalla pagina /transfers (TransferChain).
    """
    query = f"""
    MATCH path = (start:Account {{id: $account_id}})-[:TRANSFERS*1..{hops}]->(b:Account)
    RETURN
        [n IN nodes(path) | toString(n.id)] AS path_nodes,
        length(path) AS depth,
        false AS is_target_blocked
    ORDER BY depth
    """
    with db.neo4j_driver.session() as session:
        paths = [dict(r) for r in session.run(query, account_id=account_id)]

    if not paths:
        with db.neo4j_driver.session() as session:
            if not session.run(
                "MATCH (a:Account {id: $id}) RETURN a LIMIT 1", id=account_id
            ).single():
                raise HTTPException(status_code=404, detail="Account non trovato")

    return {"account_id": account_id, "hops": hops, "paths": paths}


# L3 — (Cross-DB) Portafoglio aziendale
@app.get("/api/lookup/company/{company_id}/portfolio")
def get_company_portfolio(company_id: int):
    """Query in due passi:
      1. Neo4j : trova gli account posseduti dall'azienda (relazione OWNS).
      2. MongoDB > recupera i dettagli di quegli account dalla collezione 'account'.
    Utilizzata dalla pagina /company (CompanyPortfolio).
    """
    # Step 1: grafo Neo4j — restituisce gli id degli account come stringhe
    with db.neo4j_driver.session() as session:
        result = session.run(
            "MATCH (c:Company {id: $cid})-[:OWNS]->(a:Account) RETURN a.id AS account_id",
            cid=company_id
        )
        # Neo4j memorizza gli id come interi
        account_ids = [r["account_id"] for r in result]

    if not account_ids:
        if not db.mongo_db.company.find_one({"id": company_id}):
            raise HTTPException(status_code=404, detail="Azienda non trovata")
        return {"company_id": company_id, "accounts": [], "message": "Nessun conto associato"}

    # Step 2: documenti MongoDB — i account_ids sono già interi
    accounts_details = list(
        db.mongo_db.account.find({"id": {"$in": account_ids}}, {"_id": 0})
    )
    return {
        "company_id": company_id,
        "total_accounts": len(accounts_details),
        "accounts": accounts_details
    }


# Endpoint di supporto — Home & Suggestions

@app.get("/api/search/{entity_type}")
def search_entity(
    entity_type: str,
    q: str = Query("", description="Testo da cercare")
):
    """Ricerca asincrona leggera per popolare le dropdown del frontend."""
    if len(q) < 2:
        return []

    limit = 20

    if entity_type == "person":
        results = db.mongo_db.person.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1, "country": 1}
        ).limit(limit)
        # Convertiamo l'ID in stringa prima di inviarlo al frontend per evitare
        # la perdita di precisione di JavaScript con i numeri a 64-bit (> Number.MAX_SAFE_INTEGER).
        return [
            {"id": str(p["id"]), "label": p.get("name") or f"ID: {p['id']}"}
            for p in results
        ]

    elif entity_type == "company":
        results = db.mongo_db.company.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1, "country": 1}
        ).limit(limit)
        # Come sopra, proteggiamo l'ID 64-bit trasformandolo in stringa per il JSON
        return [
            {"id": str(c["id"]), "label": c.get("name") or f"ID: {c['id']}"}
            for c in results
        ]

    elif entity_type == "account":
        # Per gli account, cerchiamo il proprietario (persona o azienda) in MongoDB,
        # poi troviamo i loro account in Neo4j.
        
        # 1. Trova proprietari
        owners = list(db.mongo_db.person.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1}
        ).limit(limit))
        
        companies = list(db.mongo_db.company.find(
            {"name": {"$regex": q, "$options": "i"}},
            {"_id": 0, "id": 1, "name": 1}
        ).limit(limit))
        
        # Usiamo stringhe come chiavi della mappa per consistenza,
        # e per proteggere gli ID a 64-bit quando verranno inseriti nel JSON finale
        owner_map = {str(p["id"]): p.get("name") for p in owners}
        owner_map.update({str(c["id"]): c.get("name") for c in companies})
        
        owner_ids = [int(k) for k in owner_map.keys()]
        if not owner_ids:
            return []
            
        # 2. Trova account di questi proprietari
        query = """
        UNWIND $owner_ids AS oid
        MATCH (owner {id: oid})-[:OWNS]->(a:Account)
        RETURN a.id AS account_id, owner.id AS owner_id
        LIMIT $limit
        """
        with db.neo4j_driver.session() as session:
            result = session.run(query, owner_ids=owner_ids, limit=limit)
            accounts = []
            for r in result:
                # Cast a stringa per evitare che Javascript sul frontend 
                # arrotondi l'ID distruggendone il valore (es. ...9000).
                acc_id = str(r["account_id"])
                own_id = str(r["owner_id"])
                owner_name = owner_map.get(own_id, "Sconosciuto")
                accounts.append({
                    "id": acc_id,
                    "label": f"Account {acc_id} — {owner_name}"
                })
            return accounts

    else:
        raise HTTPException(status_code=400, detail="Entity type non supportato")

@app.get("/api/home/stats")
def get_home_stats():
    """Metriche globali per la Home page (conteggi su MongoDB).
    Utilizzato dalla pagina / (Home).
    """
    return {
        "total_persons":    db.mongo_db.person.count_documents({}),
        "total_accounts":   db.mongo_db.account.count_documents({}),
        "blocked_accounts": db.mongo_db.account.count_documents({"isBlocked": True}),
        "total_companies":  db.mongo_db.company.count_documents({}),
        "blocked_companies":db.mongo_db.company.count_documents({"isBlocked": True})
    }


# Categoria 2 — Query Analitiche

# A1 — (MongoDB Aggregation) Statistiche aziende per nazione
@app.get("/api/analytics/companies/stats")
def get_companies_stats():
    """Aggregazione MongoDB: raggruppa le aziende per nazione, conta il totale e
    quante sono bloccate, calcola la percentuale.
    Utilizzata dalla pagina /company-stats (CompanyStats).
    """
    pipeline = [
        {
            "$group": {
                "_id": "$country",
                "total_companies": {"$sum": 1},
                "blocked_companies": {
                    "$sum": {"$cond": [{"$eq": ["$isBlocked", True]}, 1, 0]}
                }
            }
        },
        {
            "$project": {
                "country": "$_id",
                "_id": 0,
                "total_companies": 1,
                "blocked_companies": 1,
                "blocked_percentage": {
                    "$multiply": [
                        {"$divide": ["$blocked_companies", "$total_companies"]},
                        100
                    ]
                }
            }
        },
        {"$sort": {"total_companies": -1}}
    ]
    stats = list(db.mongo_db.company.aggregate(pipeline))
    return {"analytics": stats}


# A2 — (Neo4j) Shortest path tra due account
@app.get("/api/analytics/network/shortest-path")
def get_shortest_path(from_id: int, to_id: int):
    """Usa l'algoritmo shortestPath nativo di Neo4j per trovare il percorso
    minimo tra due account nella rete di trasferimenti.
    Utilizzata dalla pagina /shortest-path (ShortestPath).
    """
    query = """
    MATCH (start:Account {id: $from_id}), (end:Account {id: $to_id})
    MATCH path = shortestPath((start)-[:TRANSFERS*]-(end))
    RETURN length(path) AS jumps, [n IN nodes(path) | toString(n.id)] AS path_nodes
    """
    with db.neo4j_driver.session() as session:
        result = session.run(query, from_id=from_id, to_id=to_id).single()

    if not result:
        return {
            "from": from_id, "to": to_id,
            "path_found": False,
            "message": "Nessun percorso trovato tra questi due conti"
        }
    return {
        "from": from_id,
        "to": to_id,
        "path_found": True,
        "jumps": result["jumps"],
        "path": result["path_nodes"]
    }


# A3 — (Cross-DB) Ciclo di riciclaggio sospetto
@app.get("/api/analytics/suspicious-cycle/{account_id}")
def get_suspicious_cycle(
    account_id: int,
    depth: int = Query(3, description="Profondità massima del ciclo")
):
    """Query in due passi:
      1. Neo4j  > cerca un ciclo chiuso TRANSFERS*2..depth a partire dall'account.
      2. MongoDB > recupera nome e nazione dei proprietari degli account nel ciclo.
    Restituisce anche il flag 'international_laundering' se coinvolte più nazioni.
    Utilizzata dalla pagina /laundering-cycle (LaunderingCycle).
    """
    # Step 1: Neo4j — ricerca ciclo; i nodi del path vengono restituiti come int
    # terminate node start per permmetere di rivisitare il nodo di partenza 
    # uniqueness: "RELATIONSHIP_PATH" evita cicli multipli tra gli stessi nodi
    cycle_query = """
    MATCH (start:Account {id: $account_id})
    CALL apoc.path.expandConfig(start, {
        relationshipFilter: "TRANSFERS>",
        terminatorNodes: [start],
        uniqueness: "RELATIONSHIP_PATH",
        minLevel: 2,
        maxLevel: $depth
    })
    YIELD path
    RETURN [n IN nodes(path) | toString(n.id)] AS cycle_accounts
    ORDER BY length(path) DESC
    LIMIT 1
    """
    with db.neo4j_driver.session() as session:
        cycle_result = session.run(cycle_query, account_id=account_id, depth=depth).single()

    if not cycle_result:
        return {"account_id": account_id, "suspicious_cycle_found": False}

    cycle_account_ids = list(set(cycle_result["cycle_accounts"]))

    # Step 2a: Neo4j — proprietari degli account nel ciclo (id come int)
    owners_query = """
    UNWIND $account_ids AS acc_id
    MATCH (owner)-[:OWNS]->(a:Account {id: acc_id})
    RETURN owner.id AS owner_id, labels(owner)[0] AS owner_type
    """
    with db.neo4j_driver.session() as session:
        owner_ids = [
            r["owner_id"]
            for r in session.run(owners_query, account_ids=cycle_account_ids)
        ]

    # Step 2b: MongoDB — i owner_ids sono già interi
    owner_details = []
    
    for p in db.mongo_db.person.find(
        {"id": {"$in": owner_ids}},
        {"_id": 0, "id": 1, "name": 1, "country": 1}
    ):
        owner_details.append({
            "id": p["id"],
            "name": p.get("name", "N/A"),
            "country": p.get("country", "N/A"),
            "type": "Person"
        })

    for c in db.mongo_db.company.find(
        {"id": {"$in": owner_ids}},
        {"_id": 0, "id": 1, "name": 1, "country": 1}
    ):
        owner_details.append({
            "id": c["id"],
            "name": c.get("name", "N/A"),
            "country": c.get("country", "N/A"),
            "type": "Company"
        })

    countries = list({o["country"] for o in owner_details if o["country"] != "N/A"})

    return {
        "account_id": account_id,
        "suspicious_cycle_found": True,
        "cycle_length": len(cycle_result["cycle_accounts"]) - 1,
        "cycle_path": cycle_result["cycle_accounts"],
        "owners": owner_details,
        "international_laundering": len(countries) > 1,
        "nations_involved": countries
    }


