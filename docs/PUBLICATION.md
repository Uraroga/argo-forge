# Preparazione della distribuzione pubblica

Questa procedura prepara file revisionabili. Non autorizza né esegue commit,
push, modifica remota, installazione o manutenzione dei servizi attivi.

## File inclusi e materiali locali

`distribution-files.txt` è l'elenco esplicito di sorgenti e documentazione da
revisionare. L'audit confronta tale elenco con i file Git tracciati e non tracciati
non ignorati; segnala differenze prima di leggere i candidati inattesi. Se un
file privato fosse già tracciato, .gitignore non lo rimuoverebbe dalla storia:
il confronto col manifest deve fallire e richiedere una revisione separata.
L'audit controlla anche le esclusioni con --no-index: un file ignorato ma già
tracciato viene rifiutato prima di leggerlo, anche se dichiarato nel manifest.

Backup, evidenze, modelli, binari, cache, database, sessioni, conversazioni,
log e `docs/reports/codex/` restano locali. I rapporti operativi non sono stati
cancellati o riscritti: la sintesi pubblica delle verifiche è in
[VALIDATION.md](VALIDATION.md). Non preparare un archivio dell'intera directory
come alternativa a questa selezione: includerebbe dati ignorati da Git.

Non è necessario un .env per il launcher. L'eventuale `.env.example` può essere
incluso solo con commenti, valori vuoti o `REPLACE_ME`; gli altri .env restano
esclusi. Il launcher non carica automaticamente un dotenv. La costante MODEL
contiene ancora il percorso del deployment di riferimento, già presente nel
codice pubblico: non viene generalizzata cambiando la configurazione in uso.
Gli esempi dei documenti usano percorsi e account generici.

## Contesto Docker effettivamente ammesso

Per `docker build -f Dockerfile .`, dalla radice, il contratto è:

```dockerignore
**
!Dockerfile
!.dockerignore
```

**Soltanto `.dockerignore` e `Dockerfile` sono ammessi dal filesystem locale.**
Il Dockerfile acquisisce il commit upstream nello stage build e usa COPY soltanto
fra stage; non ha bisogno del modello o dei sorgenti Python nel contesto.
La regola nega anche categorie non ancora previste nella lista Git, compresi
archivi riservati e nuovi file nascosti.

L'audit verifica esattamente queste tre regole, rifiuta un
`Dockerfile.dockerignore` che le scavalcherebbe e rifiuta COPY/ADD locali o stage
non verificati. Non è un parser Dockerignore generico: se cambia il contratto,
occorre rivedere insieme policy e controllo. Gli esclusi non vengono aperti,
attraversati o estratti per calcolare l'elenco ammesso. Questa è una verifica
statica del contesto per il comando indicato, **non una build eseguita** né una
verifica di Dockerfile alternativi o contesti passati da stdin.

Semantica ufficiale: [contesto e Dockerignore](https://docs.docker.com/build/concepts/context/#dockerignore-files).
Non confondere la distribuzione Git con il contesto Docker: i sorgenti pubblici
sono necessari ai client e ai test, ma non alla compilazione di llama.cpp nello
stage dell'immagine.

## Comandi di revisione non distruttivi

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
python3 -B tools/audit_distribution.py
python3 -B tools/audit_distribution.py --json
git diff --check
git diff --stat
git diff --cached --stat
```

L'output JSON elenca soltanto i nomi pubblici approvati e i due file del contesto.
La ricerca di segreti è euristica, limitata ai candidati testuali: nessun pattern
ad alta confidenza non significa assenza assoluta di password o dati personali.
I valori sospetti non sono stampati; archivi e alberi esclusi non sono letti.
Rivedere comunque diff, file nuovi e contenuti di eventuali esempi.

I controlli dei container, se necessari, sono solo inspect e GET diagnostici.
Non eseguire start, restart, stop, build o smoke dell'agente per preparare uno
staging. L'audit non crea pacchetti o file .env e non invoca Docker o Git mutante.
Anche una successiva pubblicazione richiede autorizzazione esplicita e revisione
dei file: questa fase lascia working tree e staging disponibili al revisore.

## Riproducibilità e limiti

I valori dei timeout sono deterministici: 21600 s e 21600000 ms; i test verificano
rifiuto dei container incompatibili e protezioni preesistenti senza Docker reale.
llama.cpp è fissato a un commit, OpenCode e il plugin shell alla versione 1.18.20,
le dipendenze npm sono nel lockfile. Non sono stati aggiornati o riscaricati.

Questo rende riproducibili configurazione e controlli, non certifica una nuova
immagine bit per bit: base image e pacchetti apt possono evolvere. Il modello GGUF
rimane esterno e non è scaricato o ridistribuito da questa procedura. Le
prestazioni e la durata delle richieste restano quelle descritte in
[TIMEOUTS.md](TIMEOUTS.md), senza garanzie globali di sei ore.
