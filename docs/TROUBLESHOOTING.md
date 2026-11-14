# Diagnostica

```bash
python3 localcode.py status
python3 localcode.py logs
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/v1/models
curl --compressed http://127.0.0.1:18080/ > /tmp/argo-webui.html
python3 localcode.py stats
docker stats --no-stream argo-forge-lfm25
```

La Web UI compressa richiede supporto gzip: `curl` senza `--compressed` può
ricevere 415; i browser normali lo supportano. `/health` risponde 503 durante
il caricamento. Il launcher attende fino a 600 secondi, senza ridurre 131072.
Se scade l'attesa, il container rimane ispezionabile tramite log e status.

Memoria insufficiente: controllare `free -h`, Docker stats e gli eventi OOM del
container. Liberare carichi concorrenti; il launcher non cambia il contesto.
Su Ivy Bridge i prompt lunghi possono richiedere tempi elevati; aumentare gli
step senza necessità può produrre esecuzioni di ore. Non promettere prestazioni
interattive su tutto il contesto.

Porta occupata: individuare il servizio con `ss -ltn`; non eliminarlo. Container
precedente attivo: arrestarlo solo con una decisione esplicita dell'utente.
Configurazione incompatibile: il launcher non rimuove né sostituisce container.
Docker non accessibile: predisporre i permessi amministrativamente; non usare
sudo automaticamente. Illegal instruction: verificare di usare build Ivy Bridge
e OpenCode baseline.

Tool calling: una risposta testuale non prova l'integrazione. Occorrono chiamata
shell reale, modifica effettiva e test post-modifica verde. Il server condivide
uno slot: evitare richieste Web UI durante la verifica dell'agente.
