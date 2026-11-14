# Installazione

Requisiti: Docker accessibile all'utente senza sudo, Python 3, Bash, modello già
presente nel percorso fissato. Non scaricare nuovamente il GGUF.

L'immagine locale esistente `local/llama-cpp-lfm25:latest` viene riutilizzata.
Il Dockerfile del repository fissa lo stesso commit dell'immagine verificata:
`61dbf49228c8a96b72e40c89d93cb7c003411f8c`.
La directory esterna `/home/sergio/Progetti/llama-cpp-lfm25/` non viene modificata.

Una ricompilazione è facoltativa e costosa; usare un tag separato per non
sovrascrivere l'immagine esistente:

```bash
docker build -t local/argo-forge-lfm25:rebuild .
```

La build usa due job, `-march=ivybridge`, AVX/F16C abilitati,
AVX2/FMA/BMI/BMI2 disabilitati, backend GPU disabilitati, server con Web UI.
Il launcher continua a utilizzare l'immagine locale verificata: il tag separato
serve a valutare una ricompilazione prima di adottarla esplicitamente nel codice.

## OpenCode

Versione fissata: **1.18.20**, come la dipendenza del tool compatto.
Su Ivy Bridge usare la release **linux-x64-baseline**, non la variante AVX2:

```bash
mkdir -p opencode-local/bin
curl -fL https://github.com/anomalyco/opencode/releases/download/v1.18.20/opencode-linux-x64-baseline.tar.gz -o /tmp/argo-opencode.tar.gz
tar -xzf /tmp/argo-opencode.tar.gz -C opencode-local/bin
opencode-local/bin/opencode --version
cd opencode-local
npm ci --ignore-scripts
cd ..
```

`npm ci` richiede Node/npm già installati; non vengono installati pacchetti di
sistema automaticamente. Binari e node_modules sono ignorati da Git.
In alternativa impostare `OPENCODE_BIN` al binario baseline già disponibile.
La prima esecuzione può scaricare dipendenze software del provider; nessuna
inferenza viene inviata a provider remoti. Non serve login OpenCode.

```bash
python3 -m unittest discover -s tests -v
python3 localcode.py dry-run
python3 localcode.py start
```

Il container `argo-forge-lfm25` ha un nome distinto dal precedente
`llama-cpp-lfm25`. Se il precedente è attivo il launcher rifiuta l'avvio;
fermarlo esplicitamente prima di avviare Argo Forge. Nessun container viene
rimosso. Una configurazione del container incompatibile causa un errore e
richiede una decisione manuale, non una ricreazione automatica.

## Smoke test opzionale dell'agente

```bash
python3 tests/smoke_agent.py
```

Esegue inferenza reale (può richiedere minuti), crea una piccola fixture nel
repository con un test inizialmente rosso, concede esplicitamente la shell al
solo task di prova, verifica modifica, integrità del test e risultato verde.
Controllare anche nell'output che OpenCode abbia chiamato la shell per il test
post-modifica. La fixture temporanea viene rimossa al termine; il server resta
attivo finché non si esegue `python3 localcode.py stop`. Non viene incluso nei
test unitari per evitare carichi CPU involontari.
