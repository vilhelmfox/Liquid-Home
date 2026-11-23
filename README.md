# Liquid Home v1.6 – opsætning uden filer

Liquid Home giver din iPad et glasagtigt ur og et dashboard med seks felter. Hele tilpasningen foregår fra telefonen via en QR kode.

## Hvorfor får jeg 404: Not Found?

Hvis adressen `http://homeassistant.local:8123/liquid_home/index.html` giver 404, er Liquid Home endnu **ikke indlæst og aktiveret** i Home Assistant, eller du bruger en gammel installation.

**Vigtigt:** En integration kan ikke selv vise en hjælpeside på sin Home Assistant adresse, før Home Assistant har startet integrationen. Derfor er denne vejledning også på GitHub, selv når den lokale adresse endnu ikke virker.

### Første installation (ingen filredigering)

1. Installér **HACS** i Home Assistant, hvis du ikke allerede har det.
2. Åbn **HACS → ⋮ → Custom repositories**.
3. Tilføj `https://github.com/vilhelmfox/Liquid-Home` som typen **Integration**.
4. Download **Liquid Home** i HACS.
5. **Genstart Home Assistant** under Indstillinger → System.
6. Åbn **Indstillinger → Enheder og tjenester → Tilføj integration** og søg efter **Liquid Home**.
7. Home Assistant viser en **automatisk genereret parringskode**. Du skal ikke selv finde på en. Gem den et sikkert sted, og tryk **Send**.
8. Åbn **http://homeassistant.local:8123/liquid_home/index.html** på iPad'en.
9. iPad'en viser en **QR kode**. Scan den med telefonens kamera for at åbne telefoneditoren.
10. På telefonen indtaster du den genererede parringskode én gang og vælger dine Home Assistant enheder fra listerne.

### Hvor finder jeg koden igen?

Åbn **Indstillinger → Enheder og tjenester → Liquid Home → Konfigurer**. Her kan du se koden og generere en ny, uden at redigere YAML eller filer.

QR koden på iPad'en åbner den rigtige telefoneditor til netop din iPad. Den indeholder ikke den hemmelige parringskode; koden indtastes kun på telefonen. En kodeændring tilbagekalder ikke allerede parrede enhedsnøgler.

### Hvis Liquid Home stadig viser 404

- Kontrollér, at integrationen er downloadet i HACS, og genstart Home Assistant.
- Kontrollér, at den også er tilføjet under **Enheder og tjenester**.
- Genindlæs siden på iPad'en.
- Se **Indstillinger → System → Logfiler**, og kig efter `liquid_home` fejl.

## Sikkerhed

Denne version er en prototype, som ikke er afprøvet på alle Home Assistant versioner. Forbindelsen via HTTP er ukrypteret, også ved brug af parringskoden og enhedsnøgler. Brug den kun på et betroet lokalnetværk. Giv aldrig Home Assistant direkte internetadgang gennem port 8123 uden korrekt beskyttelse.

Du behøver hverken Long-Lived Access Token eller at ændre `configuration.yaml` ved en ny installation.
