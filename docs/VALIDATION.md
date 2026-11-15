# Preparazione pubblica — aggiornamento del 15 novembre 2026

Il resoconto del 14 novembre riportato sotto è storico: il suo stato finale
«container fermi» non descrive lo stato corrente dei servizi. Successivamente
il deployment di riferimento è stato avviato con --timeout 21600 e collegato a
Hermes; i dati operativi di migrazione rimangono nei rapporti locali esclusi.

La preparazione pubblica preserva 21600 s server e 21600000 ms client, contesto
131072, due thread CPU, uno slot e bind localhost. Aggiunge verifiche mock sul
rifiuto delle configurazioni incompatibili e verifiche di distribuzione senza
build, installazioni, inferenza, manutenzione o modifica di Hermes.

I controlli automatici attuali si riproducono con:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/audit_distribution.py
```

Esito della preparazione del 15 novembre: **32/32 test automatici riusciti**.
L'audit ha verificato **23 file pubblicabili** e il contesto Docker composto
soltanto da **.dockerignore e Dockerfile**, senza leggere archivi riservati.
Questi numeri descrivono il set di file e test di questa revisione; l'audit
ristampa l'elenco corrente per la revisione successiva.

Il loro esito riguarda configurazione, isolamento dei materiali e comportamento
simulato del launcher. Non rinnova la readiness completa OpenCode del test
storico e non è un collaudo continuo di sei ore. Il test smoke opt-in conserva
900 s e il tool Bash non riceve un nuovo timeout implicito. Semantica e limiti
in [TIMEOUTS.md](TIMEOUTS.md); selezione dei file in
[PUBLICATION.md](PUBLICATION.md).

---

# Verifica locale — 14 novembre 2026

Verifica esplorativa su argo3, non benchmark comparativo.

- Immagine riutilizzata: `local/llama-cpp-lfm25:latest`, ID
  `sha256:b3cf0ad71d3d421a4005ccccf268cbd2ba5256bee8d477c4a1c2c3eea11963c1`.
- Commit estratto dall'immagine: `61dbf49228c8a96b72e40c89d93cb7c003411f8c`.
- Un solo GGUF montato read-only; nessun device GPU richiesto.
- Container precedente `llama-cpp-lfm25` preservato e fermo.
- Nuovo container `argo-forge-lfm25`, porta `127.0.0.1:18080`.
- Caricamento riuscito; `/health` e `/v1/models`: HTTP 200.
- `/props` conferma `n_ctx=131072`; log confermano uno slot da 131072.
- Web UI integrata: HTTP 200, HTML ricevuto con `curl --compressed`.
  Non è stato eseguito un test interattivo del browser.
- `/metrics` disponibile; log riportano tempi prompt/generazione.
- OpenCode baseline 1.18.20 avviato nel progetto temporaneo `agent-smoke/`
  ignorato da Git, con shell compatta e sei step, output massimo 512.
- Fixture iniziale: `add(2,3)` restituiva -1; unittest rosso.
- Chiamate shell reali osservate: elenco directory, lettura `calc.py`, lettura
  `test_calc.py`, modifica `return a - b` in `return a + b`, esecuzione
  `python3 -m unittest -v` dopo la modifica.
- Verifica indipendente successiva: `test_add ... ok`, `Ran 1 test`, `OK`;
  controlla sia `add(2,3)==5` sia `add(-2,2)==0`. Test originale invariato.

La catena load → health → generation → OpenCode → tool → edit → post-edit test
→ PASS è stata osservata per questa piccola fixture. Non dimostra affidabilità
su progetti complessi né qualità a 128K di prompt effettivo.

Il primo tentativo ha esaurito 512 token nel ragionamento senza tool; è stato
interrotto. La configurazione definitiva invia `reasoning_budget: 0` dalle
richieste OpenCode, senza cambiare il template nei pesi o il server della Web UI.

Controlli: otto unittest del launcher verdi, compilazione sintattica Python,
`git diff --check`, dry-run e `docker build --check` senza avvisi.
Non è stata eseguita una nuova compilazione completa dell'immagine. Accesso LAN
via tunnel documentato, non provato da un secondo host. Nessun benchmark esteso,
nessun download di pesi, nessuna modifica ai file esterni di configurazione
LFM2.5, nessuna rimozione di container o immagini preesistenti, nessun push.

Riavvio e arresto verificati sul nuovo container senza rimozione: dopo restart
`/health` torna pronto, stop termina con codice 0. Stato finale: entrambi i
container fermi; `python3 localcode.py start` rende nuovamente disponibile la UI.
Il task OpenCode ha raggiunto il limite di sei step dopo il test verde e ha
riportato il risultato positivo nel messaggio finale; non è stato necessario
alzare il budget per questa fixture.
