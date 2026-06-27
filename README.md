# MAADB — Multi-database Fraud Investigation Dashboard

Dashboard di investigazione antifrode che implementa una architettura **Polyglot Persistence** (MongoDB + Neo4j) con un backend FastAPI e un frontend React/TypeScript.

Il sistema analizza il dataset sintetico [LDBC FinBench](https://github.com/ldbc/ldbc_finbench_datagen), composto da persone, aziende e conti bancari connessi da relazioni di proprietà e trasferimento, per rilevare pattern sospetti di riciclaggio di denaro.

---

## Architettura

```
┌─────────────────────────────────────────┐
│           Frontend (React + TS)         │
│         http://localhost:5173           │
└─────────────────┬───────────────────────┘
                  │ HTTP / Vite proxy
┌─────────────────▼───────────────────────┐
│        Backend FastAPI (Python)         │
│         http://localhost:8000           │
└───────┬─────────────────────┬───────────┘
        │                     │
┌───────▼───────┐   ┌─────────▼──────────┐
│   MongoDB     │   │       Neo4j        │
│  (doc store)  │   │   (graph store)    │
│  port 27017   │   │  port 7687 (Bolt)  │
│               │   │  port 7474 (HTTP)  │
└───────────────┘   └────────────────────┘
```

### Perché due database?

| Esigenza | MongoDB | Neo4j |
|---|---|---|
| Dati anagrafici (persona, azienda, conto) | ✅ | — |
| Relazioni di proprietà (OWNS) | — | ✅ |
| Rete di trasferimenti (TRANSFERS) | — | ✅ |
| Aggregazioni statistiche per nazione | ✅ (Aggregation Pipeline) | — |
| Shortest path tra conti | — | ✅ (shortestPath algo) |
| Rilevamento di cicli chiusi | — | ✅ (pattern matching) |
| Investigazioni salvate (flagged) | ✅ | — |

---

## Setup e Avvio

### 1. Prerequisiti

- Docker Desktop
- Python 3.11+
- Node.js 18+

### 2. Avvio dei database

```bash
cd backend
docker compose up -d
```

I container avviati sono:
- `maadb-mongodb` — MongoDB 6.0 su porta 27017 (credenziali: `root` / `password`)
- `maadb-neo4j` — Neo4j 5.12 su porta 7687 (credenziali: `neo4j` / `password1234`)

### 3. Installazione dipendenze Python

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r backend/requirements.txt
```

### 4. Importazione dei dati (ETL)

I dati vengono letti dalla cartella `dataset/raw/` generata da LDBC FinBench Datagen.

```bash
# Importa persone, aziende e conti in MongoDB
python backend/ingestion_mongo.py

# Importa i nodi e le relazioni nel grafo Neo4j
python backend/ingestion_neo4j.py
```

### 5. Avvio del backend

```bash
cd backend
python -m uvicorn main:app --reload
```

API disponibile su `http://localhost:8000`. Documentazione interattiva: `http://localhost:8000/docs`

### 6. Avvio del frontend

```bash
cd frontend/App
npm install
npm run dev
```

App disponibile su `http://localhost:5173`

---

## Struttura della Repository


---

## Dettaglio dei File

### Backend

#### `database.py`
Definisce la classe `Database` e l'istanza globale `db` importata da tutti i moduli.  
Gestisce le due connessioni in modo centralizzato:
- `db.mongo_db` → oggetto database MongoDB (pymongo)
- `db.neo4j_driver` → driver Neo4j (connessione Bolt)

Le connessioni vengono aperte all'avvio FastAPI (`startup_event`) e chiuse allo spegnimento (`shutdown_event`).

#### `main.py`
Cuore dell'applicazione. Contiene tutte le route API raggruppate in tre categorie:

| # | Funzione | Endpoint | Tipo DB |
|---|---|---|---|
| L1 | `get_person` | `GET /api/lookup/person/{id}` | MongoDB |
| L2 | `get_account_transfers` | `GET /api/lookup/account/{id}/transfers` | Neo4j |
| L3 | `get_company_portfolio` | `GET /api/lookup/company/{id}/portfolio` | Cross-DB |
| A1 | `get_companies_stats` | `GET /api/analytics/companies/stats` | MongoDB |
| A2 | `get_shortest_path` | `GET /api/analytics/network/shortest-path` | Neo4j |
| A3 | `get_suspicious_cycle` | `GET /api/analytics/suspicious-cycle/{id}` | Cross-DB |
| — | `get_suggestions` | `GET /api/suggestions` | Cross-DB |
| — | `get_home_stats` | `GET /api/home/stats` | MongoDB |

**Helper `mixed_ids(str_ids)`**: funzione di utilità che, data una lista di ID stringa, restituisce anche le versioni intere. Necessaria per interrogare MongoDB, che può avere gli ID salvati come `int` o `str` a seconda del CSV originale.

> ⚠️ **Nota su Neo4j e gli ID**: tutti gli ID sono importati come *stringhe* in Neo4j. La funzione `parse_id()` (conversione a `int`) è stata quindi rimossa perché superflua e causa di `404` sulle query al grafo.

> ⚠️ **Nota su `hops` e `depth`**: Cypher non supporta parametri (`$var`) come lunghezza di cammino (`*1..$hops`). Questi valori vengono pertanto iniettati nell'f-string Python prima di inviare la query, come documentato inline nel codice.

#### `routes/flagged.py`
Router separato con prefisso `/api/flagged`. Gestisce la persistenza delle investigazioni salvate dall'investigatore in una collezione MongoDB dedicata (`flagged_accounts`).

| Metodo | Endpoint | Azione |
|---|---|---|
| `POST` | `/api/flagged/` | Crea o aggiorna un flag su un account |
| `GET` | `/api/flagged/` | Lista tutti gli account flaggati |
| `DELETE` | `/api/flagged/{id}` | Rimuove il flag |

#### `ingestion_mongo.py`
Script ETL standalone. Per ciascuna entità (`person`, `company`, `account`):
1. Individua i file CSV in `dataset/raw/<entità>/` (pattern `part-*.csv`)
2. Li legge con pandas (separatore `|`)
3. Svuota la collezione MongoDB e reinserisce tutti i record

#### `ingestion_neo4j.py`
Script ETL standalone. Carica nel grafo Neo4j:
- **Nodi**: `Person`, `Company`, `Account` (solo la proprietà `id`)
- **Relazioni**: `OWNS` (Person→Account, Company→Account) e `TRANSFERS` (Account→Account)

I dati vengono inviati a Neo4j in batch da 1000 record tramite `session.execute_write`.

---

### Frontend

#### `api/client.ts`
Client HTTP centralizzato. Espone due funzioni base (`fetchJSON`, `postJSON`) e l'oggetto `api` con tutti i metodi della dashboard:

```typescript
api.getPerson(id)                      // → GET /api/lookup/person/{id}
api.getTransferChain(id, hops)         // → GET /api/lookup/account/{id}/transfers
api.getCompanyPortfolio(id)            // → GET /api/lookup/company/{id}/portfolio
api.getCompanyStats()                  // → GET /api/analytics/companies/stats
api.getShortestPath(from, to)          // → GET /api/analytics/network/shortest-path
api.getLaunderingCycle(id, depth)      // → GET /api/analytics/suspicious-cycle/{id}
api.getFlagged()                       // → GET /api/flagged/
api.flagAccount(body)                  // → POST /api/flagged/
api.removeFlag(id)                     // → DELETE /api/flagged/{id}
```

Il Vite dev-server fa da proxy verso `localhost:8000`, quindi le chiamate usano path relativi (`/api/...`).

#### `context/SuggestionsContext.tsx`
Context React che al mount dell'app chiama `GET /api/suggestions` e mette a disposizione globalmente le liste di persone, aziende e account. Queste alimentano le dropdown `SearchableSelect` in tutte le pagine di query, evitando di ri-fetchare i dati ad ogni navigazione.

#### `components/Sidebar.tsx`
Navigazione laterale. Ogni link ha un badge colorato che indica quale database viene interrogato (`MongoDB`, `Neo4j`, `Cross`).

#### `components/SearchableSelect.tsx`
Dropdown con filtro testuale. Accetta le props `options`, `value`, `onSelect` e `placeholder`. Usata in tutte le pagine di query per selezionare l'entità da interrogare.

#### `components/GraphViewer.tsx`
Wrapper attorno alla libreria `vis-network`. Riceve nodi ed archi e renderizza il grafo interattivo. Usato da `TransferChain` per visualizzare la rete di trasferimenti.

#### `pages/Home.tsx`
Dashboard iniziale. Mostra i contatori globali (da `GET /api/home/stats`) e le card cliccabili per navigare verso ciascuna query.

#### `pages/Explore.tsx`
Pagina di esplorazione libera del dataset. Presenta tre tab (Persone, Aziende, Account) con le entità dal contesto `SuggestionsContext`. Cliccando su un'entità si viene reindirizzati alla pagina di query rilevante con l'ID pre-compilato tramite query parameter URL (es. `/transfers?id=123`).

#### `pages/PersonLookup.tsx` — Query L1
Interroga `GET /api/lookup/person/{id}` e mostra l'anagrafica completa (nome, nazione, genere, data di nascita, città).

#### `pages/TransferChain.tsx` — Query L2
Interroga `GET /api/lookup/account/{id}/transfers?hops=N` e visualizza il grafo delle transazioni con `GraphViewer`. Nodo di partenza in viola, destinazioni standard in grigio.

#### `pages/CompanyPortfolio.tsx` — Query L3
Interroga `GET /api/lookup/company/{id}/portfolio` e mostra la lista dei conti bancari di proprietà dell'azienda con tipo e data di apertura.

#### `pages/CompanyStats.tsx` — Query A1
Interroga `GET /api/analytics/companies/stats` e mostra un `BarChart` (Recharts) e una tabella con la distribuzione delle aziende bloccate per nazione.

#### `pages/ShortestPath.tsx` — Query A2
Interroga `GET /api/analytics/network/shortest-path?from_id=X&to_id=Y` e mostra il percorso minimo tra due account. Include il pulsante per flaggare l'account di partenza.

#### `pages/LaunderingCycle.tsx` — Query A3
Interroga `GET /api/analytics/suspicious-cycle/{id}?depth=N` e mostra, se trovato, il ciclo chiuso di trasferimenti con le nazioni coinvolte e i proprietari degli account. Include il pulsante per salvare l'investigazione.

#### `pages/FlaggedAccounts.tsx`
Interroga `GET /api/flagged/` e mostra tutte le investigazioni salvate con livello di rischio e note. Ogni card ha un pulsante per rimuovere il flag (`DELETE /api/flagged/{id}`).

---

## Mappatura completa Funzione Backend → Pagina Frontend

| Endpoint Backend | Funzione Python | Pagina Frontend | Tipo Query | Database |
|---|---|---|---|---|
| `GET /api/lookup/person/{id}` | `get_person` | `PersonLookup` | Lookup L1 | MongoDB |
| `GET /api/lookup/account/{id}/transfers` | `get_account_transfers` | `TransferChain` | Lookup L2 | Neo4j |
| `GET /api/lookup/company/{id}/portfolio` | `get_company_portfolio` | `CompanyPortfolio` | Lookup L3 | Cross-DB |
| `GET /api/analytics/companies/stats` | `get_companies_stats` | `CompanyStats` | Analitica A1 | MongoDB |
| `GET /api/analytics/network/shortest-path` | `get_shortest_path` | `ShortestPath` | Analitica A2 | Neo4j |
| `GET /api/analytics/suspicious-cycle/{id}` | `get_suspicious_cycle` | `LaunderingCycle` | Analitica A3 | Cross-DB |
| `GET /api/home/stats` | `get_home_stats` | `Home` | Supporto | MongoDB |
| `GET /api/suggestions` | `get_suggestions` | Globale (Context) | Supporto | Cross-DB |
| `GET /api/flagged/` | `get_flagged_accounts` | `FlaggedAccounts` | CRUD | MongoDB |
| `POST /api/flagged/` | `flag_account` | `LaunderingCycle`, `ShortestPath` | CRUD | MongoDB |
| `DELETE /api/flagged/{id}` | `remove_flag` | `FlaggedAccounts` | CRUD | MongoDB |

---

## Credenziali Database

| Database | Host | Porta | Username | Password |
|---|---|---|---|---|
| MongoDB | localhost | 27017 | `root` | `password` |
| Neo4j (Bolt) | localhost | 7687 | `neo4j` | `password1234` |
| Neo4j (Browser) | localhost | 7474 | `neo4j` | `password1234` |
