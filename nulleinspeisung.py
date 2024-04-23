#!/usr/bin/env python3
import requests, time, sys
from requests.auth import HTTPBasicAuth


# Diese Daten müssen angepasst werden:
serial = "123456789" # Seriennummer des Hoymiles Wechselrichters
maximum_wr = 600 # Maximale Ausgabe des Wechselrichters
minimum_wr = 100 # Minimale Ausgabe des Wechselrichters
puffer = 100   # offset of the min overproducing - used to be sure not to recieve any power from supplier if there is enough power at home
sleeptimer = 5 # count of seconds to sleep until next check

dtu_ip = '192.168.xxx.xxx' # IP Adresse von OpenDTU
dtu_nutzer = 'admin' # OpenDTU Nutzername
dtu_passwort = 'xxxxxxx' # OpenDTU Passwort

shelly_ip = '192.168.xxx.xxx' # IP Adresse von Shelly 3EM


while True:
    try:
        # Nimmt Daten von der openDTU Rest-API und übersetzt sie in ein json-Format
        r = requests.get(url = f'http://{dtu_ip}/api/livedata/status/inverters' ).json()

        # Selektiert spezifische Daten aus der json response
        reachable   = r['inverters'][0]['reachable'] # Ist DTU erreichbar?
        producing   = int(r['inverters'][0]['producing']) # Produziert der Wechselrichter etwas?
        altes_limit = int(r['inverters'][0]['limit_absolute']) # Altes Limit
        power       = r['total']['Power']['v'] # Abgabe BKW AC in Watt
    except:
        print('Fehler beim Abrufen der Daten von openDTU')
    try:
        # Nimmt Daten von der Shelly 3EM Rest-API und übersetzt sie in ein json-Format
        jsonResponse = requests.get(f'http://{shelly_ip}/rpc/EM.GetStatus?id=0', headers={'Content-Type': 'application/json'}).json()
        phase_a     = jsonResponse['a_act_power']
        phase_b     = jsonResponse['b_act_power']
        phase_c     = jsonResponse['c_act_power']
        grid_sum    = phase_a + phase_b + phase_c # Aktueller Bezug - rechnet alle Phasen zusammen
    except:
        print('Fehler beim Abrufen der Daten von Shelly 3EM')

    # Werte setzen
    print(f'\nBezug: {round(grid_sum, 1)} W, Produktion: {round(power, 1)} W, Verbrauch: {round(grid_sum + power, 1)} W')
    if reachable:
        setpoint = grid_sum + altes_limit + puffer # Neues Limit in Watt

        # Fange oberes Limit ab 
        # wenn Strombezug vom Netzbetreiber => maximum
        if setpoint > maximum_wr or grid_sum > 0:
            setpoint = maximum_wr
            print(f'Setpoint auf Maximum: {maximum_wr} W')
        # Fange unteres Limit ab
        elif setpoint < minimum_wr:
            setpoint = minimum_wr
            print(f'Setpoint auf Minimum: {minimum_wr} W')
        else:
            print(f'Setpoint berechnet: {round(grid_sum, 1)} W + {round(altes_limit, 1)} W - 5 W = {round(setpoint, 1)} W')

        if setpoint != altes_limit:
            print(f'Setze Inverterlimit von {round(altes_limit, 1)} W auf {round(setpoint, 1)} W... ', end='')
            # Neues Limit setzen
            try:
                r = requests.post(
                    url = f'http://{dtu_ip}/api/limit/config',
                    data = f'data={{"serial":"{serial}", "limit_type":0, "limit_value":{setpoint}}}',
                    auth = HTTPBasicAuth(dtu_nutzer, dtu_passwort),
                    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                )
                print(f'Konfiguration gesendet ({r.json()["type"]})')
            except:
                print('Fehler beim Senden der Konfiguration')

    sys.stdout.flush() # write out cached messages to stdout
    time.sleep(sleeptimer) # wait
