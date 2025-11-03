# Importa la classe dal tuo file Kinai_API.py
from Kinai_API import KinAPI  
import json

# 1. Inizializza l'API client con l'IP del server
# Ho presunto che la porta sia 5173 come nell'esempio localhost
SERVER_URL = "http://94.177.160.183:5173" 
api = KinAPI(SERVER_URL)

# 2. Effettua il login (sostituisci con le tue credenziali)
print(f"Tentativo di login a {SERVER_URL}...")

# ⬇️ ⬇️ MODIFICA QUESTE RIGHE CON LE TUE CREDENZIALI ⬇️ ⬇️
email = "rossi@kin.ai" 
password = "password"
# ⬆️ ⬆️ -------------------------------------------- ⬆️ ⬆️

login_result = api.login(email, password) 

if "error" in login_result:
    print(f"❌ Login fallito: {login_result['error']}")
    exit(1) # Esce dallo script se il login fallisce

print(f"✓ Login effettuato come: {login_result['user']['email']}")
print("-" * 30)

# 3. Ottieni la lista di tutti i giocatori
print("Recupero di tutti i giocatori...")
players_result = api.get_all_players()

if "error" in players_result:
    print(f"❌ Errore nel recupero dei giocatori: {players_result['error']}")
    players_list = [] # Crea una lista vuota per evitare errori successivi
else:
    players_list = players_result.get("data", [])
    print(f"✓ Trovati {len(players_list)} giocatori.")
    for player in players_list:
        print(f"  - ID Giocatore: {player.get('id')}")
    
print("-" * 30)

# 4. Ottieni i dati di un giocatore specifico
# Usiamo l'ID del primo giocatore della lista come esempio
if players_list:
    try:
        player_id_to_fetch = players_list[0].get("id")
        print(f"Recupero dettagli per il giocatore ID: {player_id_to_fetch}...")
        
        player_result = api.get_player(player_id_to_fetch)
        
        if "error" in player_result:
            print(f"❌ Errore nel recupero del giocatore {player_id_to_fetch}: {player_result['error']}")
        else:
            player_data = player_result.get("data")
            print(f"✓ Dati del giocatore {player_id_to_fetch}:")
            # Usa json.dumps per stampare il dizionario in modo leggibile
            print(json.dumps(player_data, indent=2))

    except Exception as e:
        print(f"Errore durante il recupero del giocatore specifico: {e}")
else:
    print("Nessun giocatore trovato, impossibile recuperare dettagli specifici.")

# 5. Logout (opzionale, ma buona pratica)
print("-" * 30)
print("Effettuando il logout...")
api.logout()
print("✓ Logout completato.")