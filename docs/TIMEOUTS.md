# Timeout prudenziali fino a sei ore

Aggiornamento documentale: 15 novembre 2026. La configurazione è stata applicata
al deployment di riferimento il 14 novembre, senza ricompilare llama.cpp.

**21.600 secondi è una configurazione prudenziale finita per elaborazioni lente,
non una garanzia di completamento entro sei ore, una prestazione misurata o una
deadline globale esatta.** La risposta viene consegnata appena pronta. Non è
stato eseguito un collaudo continuo di sei ore.

## Valori e unità

Il launcher definisce `REQUEST_TIMEOUT_SECONDS = 21600` e deriva
`REQUEST_TIMEOUT_MS = REQUEST_TIMEOUT_SECONDS * 1000`. Il server riceve secondi;
OpenCode riceve millisecondi. I valori non sono false, null o timeout illimitati.

| Componente | Prima dell'aggiornamento | Configurazione | Ambito |
|---|---|---|---|
| llama-server read/write | Flag assente; default compilato 3600 s | --timeout 21600 | I/O HTTP, non durata totale del calcolo |
| OpenCode timeout | false | 21600000 ms | Singola fetch LLM |
| OpenCode headerTimeout | false | 21600000 ms | Attesa header; può includere prefill lento |
| OpenCode chunkTimeout | Non esplicito | 21600000 ms | Attesa di ogni lettura SSE, rinnovata con i dati |
| SSE ping server | Default 30 s | Invariato | Heartbeat, non tempo di completamento |
| HTTP keep-alive | Nessun override | Invariato | Inattività fra richieste, distinta dall'inferenza |
| Health del launcher | 2 s per richiesta | Invariato | Diagnostica breve |
| Attesa startup | 600 s | Invariato | Caricamento, non inferenza |
| Models e statistiche launcher | 10 s | Invariato | Ispezioni brevi |
| Smoke test agente | 900 s | Invariato | Limite del sottoprocesso OpenCode nel test |

Step multipli, strumenti, code, ritentativi e cleanup hanno durate distinte.
Il tool `opencode-local/tools/shell.ts` non imposta un timeout esplicito dello
spawn Bash né un proprio abort: il limite della fetch non termina automaticamente
un comando shell. Non è stato aggiunto un process killer per la pubblicazione.

## Semantica nelle versioni fissate

Il Dockerfile fissa llama.cpp al commit
`61dbf49228c8a96b72e40c89d93cb7c003411f8c`. Nel deployment è stato osservato
`1.0.0-dev (build 1, commit 61dbf49)`, coerente con quel prefisso. Questa versione
pubblica non sostiene che una nuova compilazione sia già stata confrontata bit
per bit con l'immagine locale funzionante.

- [common/common.h](https://github.com/ggml-org/llama.cpp/blob/61dbf49228c8a96b72e40c89d93cb7c003411f8c/common/common.h#L647-L649): default read 3600, write derivato da read e ping SSE 30 s.
- [common/arg.cpp](https://github.com/ggml-org/llama.cpp/blob/61dbf49228c8a96b72e40c89d93cb7c003411f8c/common/arg.cpp#L3580-L3587): --timeout/-to assegna entrambi; supporta anche LLAMA_ARG_TIMEOUT. Il launcher usa il flag esplicito.
- [server-http.cpp](https://github.com/ggml-org/llama.cpp/blob/61dbf49228c8a96b72e40c89d93cb7c003411f8c/tools/server/server-http.cpp#L302-L304): applicazione con set_read_timeout e set_write_timeout di cpp-httplib.

Questi controlli I/O non sono un timer che interrompe necessariamente il prefill
CPU una volta ricevuta la richiesta. L'help può continuare a mostrare il default
compilato 3600: il deployment si verifica nel Cmd effettivo del container.

Per OpenCode **1.18.20**, il [provider fissato](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/provider/provider.ts#L1768-L1798)
combina i segnali di annullamento della fetch, cancella il timer header quando
fetch restituisce gli header e applica il controllo chunk al corpo SSE.
Gli [helper SSE/header](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/provider/provider.ts#L35-L86)
mostrano la diversa semantica. Il limite della fetch non copre tutti gli step
di un incarico; il timer chunk non è un limite totale della conversazione.

## Compatibilità con Hermes English Teacher

Hermes è un progetto distinto, non incluso nella distribuzione Argo Forge. Nel
deployment con namespace condiviso usa il provider custom OpenAI-compatible su
`http://127.0.0.1:8080/v1`; dall'host l'API rimane
`http://127.0.0.1:18080/v1`. L'ID modello va letto da /v1/models.

Nell'integrazione documentata, request/stale e stream_max_lifetime Hermes sono
a 21600 s; run_budget_seconds è un budget cooperativo, non una deadline hard.
Il trasporto Telegram mantiene polling breve e timeout connect/read/write/pool
indipendenti: nell'installazione verificata rispettivamente poll 10, connect 10,
read/write 20 e pool 8 secondi. STT/TTS locali e la coda didattica sono gestiti
nel progetto Hermes, con budget audio distinti; non vengono impostati dal launcher.

L'API LLM streaming può restare aperta a lungo, mentre polling Telegram e invio
della risposta sono operazioni separate. Un solo modello, due thread e uno slot
sono condivisi dai client; il flag server non introduce una coda durevole globale
né il recupero exactly-once. Non sono cambiate credenziali, sessioni o volumi del
consumer per preparare questa versione pubblica.

## Verifiche senza inferenza

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/audit_distribution.py
python3 -B localcode.py dry-run
docker inspect argo-forge-lfm25 --format '{{json .Config.Cmd}}'
curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/v1/models
curl --compressed -fsS http://127.0.0.1:18080/ -o /dev/null
```

Le ultime letture Docker/HTTP richiedono un deployment già esistente: non avviano
il modello. Il dry-run mostra soltanto il comando proposto, non prova che un
container preesistente lo usi. I test simulano timeout e incompatibilità senza
attendere ore, generare risposte, avviare OpenCode o invocare Docker reale.

Il test opt-in `tests/smoke_agent.py` produce invece inferenza, modifica una
fixture e mantiene 900 s di limite: non eseguirlo come controllo innocuo durante
lezioni o preparazione documentale. La readiness completa dell'agente richiede
load → health → generation → OpenCode → tool → edit → post-edit test → PASS;
i controlli mock non sostituiscono tale prova. Evidenze datate in
[VALIDATION.md](VALIDATION.md).

## Migrazione e cancellazione

Il launcher confronta Cmd, immagine, mount e binding del container esistente.
Una configurazione precedente senza --timeout è incompatibile: il launcher la
rifiuta, senza sostituzione automatica. Un semplice restart non cambia i flag.
La procedura di manutenzione separata è in [INSTALLATION.md](INSTALLATION.md).
Se Hermes condivide il namespace del server, occorre coordinare anche il suo
riaggancio dopo una sostituzione, preservando i volumi e un solo modello attivo.

Per annullare usare Stop nel client o /stop in Hermes. La chiusura del socket
non garantisce l'arresto istantaneo di un batch CPU; nel collaudo storico è stato
osservato un rilascio ritardato. Non sono introdotti riavvii periodici o watchdog
che riavviino il server al solo superamento del tempo di generazione.

Backup, dati familiari e dettagli di rollback appartengono al deployment e non
vengono pubblicati. Pubblicare i sorgenti già applicati non richiede cambiare
il container funzionante. Nessuna stabilità a 128K effettivi o continuità Telegram
per sei ore viene dedotta da prove brevi.
