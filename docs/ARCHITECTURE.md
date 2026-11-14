# Architettura

`localcode.py` contiene una configurazione unica: percorso GGUF, immagine,
contesto 131072, due thread, uno slot, zero layer GPU, porta host localhost 18080.
Non esiste un registro di modelli. Docker monta esattamente un GGUF read-only.
`--jinja` abilita il template chat per il tool calling; `--metrics` espone le
statistiche. La Web UI è inclusa nell'immagine e condivide API e scheduler.

Il launcher attende `/health`, tollerando timeout, errori URL, reset di
connessione e JSON transitori malformati. Recupera il vero ID da `/v1/models`.
Un avvio concorrente del precedente server noto o di un container che monta lo
stesso GGUF viene rifiutato. Le operazioni di gestione richiedono l'etichetta
`localcode.managed=true`; stop non elimina il container.

OpenCode 1.18.20 riceve configurazione generata in memoria, provider consentito
solo `llama.cpp`, nessun MCP o plugin predefinito e una sola shell compatta.
Un XDG config home temporaneo separa la configurazione globale. La configurazione
di progetto è disabilitata per evitare fusioni di provider/plugin; le istruzioni
AGENTS.md del progetto non sono quindi caricate automaticamente: includere nel
task le istruzioni necessarie. Workspace e cwd restano il progetto invocante.
Aggiornamenti automatici, fetch del catalogo e condivisione sono disabilitati.

La shell richiede approvazione salvo `--auto-approve`. Può eseguire tutti i
comandi consentiti all'utente: non fornisce isolamento di sicurezza.
Le sessioni OpenCode possono contenere codice e output privati: non versionarle.
Il server non registra prompt su file tramite flag dedicati; i log Docker sono
ruotati a 10 MB × 2. Non salvare credenziali nel repository.

Il binding localhost e il tunnel SSH proteggono l'accesso dalla LAN. Nessuna
esposizione Internet è prevista. Come ogni servizio localhost senza login,
l'accesso resta consentito ai processi locali: usare browser e software fidati.

Il template del GGUF apre `<think>` per impostazione predefinita. Le richieste
OpenCode impostano `reasoning_budget: 0` per dedicare il piccolo budget di output
a tool e risposte; la Web UI conserva le proprie impostazioni di ragionamento.
Questa opzione non modifica il contesto o il container. Il passaggio di opzioni
personalizzate usa il provider [OpenAI Compatible di AI SDK](https://ai-sdk.dev/providers/openai-compatible-providers)
e la trasformazione verificata nel [codice OpenCode 1.18.20](https://github.com/anomalyco/opencode/blob/v1.18.20/packages/opencode/src/provider/transform.ts).
