# Päiväkirja
 
Viikkopäiväkirjassa kuvataan projektin etenemistä viikkotasolla. 

---
 
## Viikko 05: Projektin ideointi ja suunnitelma
 
- Käytiin läpi useita mahdollisia projekti-ideoita: portfolio-generaattori, työpaikkailmoitus-matchaaja, lähdeviitetarkistin, akateemisen kielen hienosäätäjä, RAG-pohjainen kurssikirjabotti sekä matemaattisten kaavojen digitointityökalu
- Ideoista valittiin GitHub AI-projektimanageri ja portfolio-generaattori, koska se yhdistää käytännönläheisesti GitHub-integraation, tekoälyn ja mikropalveluarkkitehtuurin
- Laadittiin projektisuunnitelma: määriteltiin keskeiset toiminnallisuudet, teknologiapinot ja MVP-rajaus
- MVP:ksi rajattiin kolme ydintoimintoa: commit-analyysi, automaattinen README-päivitys ja portfolio-generaattori — laajemmat ominaisuudet siirrettiin myöhempiin versioihin
- Sovittiin alustavasti työnjaosta: backend, frontend, AI-integraatio ja deployment
 
![](images/jonintunnit/1.png)
 
---
 
## Viikko 06: Projektin pohja ja GitHub API -tutustuminen
 
- Alustettiin projektin kansiorakenne GitHubiin ja luotiin repositorio yhteiskehitystä varten
- Tutustuttiin GitHub REST API:n toimintaan ja selvitettiin miten API-yhteys saadaan toimimaan projektissa
- Tutkittiin autentikointi API-kutsuissa ja miten token-pohjainen autentikointi konfiguroidaan
- Hahmoteltiin mikropalveluarkkitehtuurin rakennetta projektin tarpeisiin
 
![](images/jonintunnit/2.png)
 
---

## Viikko 07: Mikropalveluarkkitehtuuri ja analyysipalvelun aloitus
 
- Jatkettiin GitHub API -yhteyden tutkimista ja selvitettiin käytännössä miten kutsut rakennetaan ja autentikoidaan projektissa
- Perehdyttiin API-vastausten rakenteeseen ja siihen, mitä dataa repositorioista saadaan ulos
- Tehtiin arkkitehtuuripäätös: projekti toteutetaan neljänä erillisenä mikropalveluna selkeän vastuunjaon saavuttamiseksi
- Aloitettiin ensimmäisen mikropalvelun, analyysipalvelun, suunnittelu ja rakentaminen
- Hahmoteltiin analyysipalvelun rooli kokonaisarkkitehtuurissa — se vastaa AI-pohjaisen analyysin tuottamisesta GitHub-datasta
 
![](images/jonintunnit/3.png)
 
---

## Viikko 08: Backend-palvelut valmiiksi ja tietokantasuunnittelu
 
- Rakennettiin docs-palvelun ja portfolio-palvelun perusrunko — molemmat saatiin toimintakuntoon
- Saatiin kaikki neljä backend-mikropalvelua (GitHub-, analyysi-, docs- ja portfolio-palvelu) finaaliin eli perusrakenne toimii kaikissa
- Pohdittiin tietokantaratkaisua ja selvitettiin mitä dataa tarvitsee tallentaa ja miten
- Suunniteltiin tietokantaskeema projektin tarpeisiin ja aloitettiin sen toteutus SQLitellä
- Merkittävä viikko kokonaisuuden kannalta — koko backend-kerros hahmottui toimivaksi kokonaisuudeksi
 
![](images/jonintunnit/4.png)

---

## Viikko 09: Tietokantaintegraatio kaikkiin palveluihin
 
- Integroitiin tietokanta GitHub-palveluun — palvelu osaa nyt tallentaa ja hakea dataa SQLitestä
- Lisättiin tietokantaintegraatio analyysipalveluun — AI-analyysit tallentuvat tietokantaan
- Lisättiin tietokantaintegraatio docs-palveluun — generoitu dokumentaatio persistoidaan
- Lisättiin tietokantaintegraatio portfolio-palveluun — portfolio-kuvaukset tallennetaan tietokantaan
- Kaikki neljä mikropalvelua käyttävät nyt yhteistä SQLite-tietokantaa jaetun moduulin kautta
 
![](images/jonintunnit/5.png)

---

## Viikko 10: Docker-persistenssi, issues-integraatio ja backend MVP valmis
 
- Saatiin Docker toimimaan tietokannan kanssa — aiemmin sovellus toimi vain lokaalisti, nyt tietokanta persistoituu Docker-volumena konttien välillä
- Päivitettiin README ja Docker-konfiguraatio vastaamaan muuttunutta rakennetta
- Integroitiin Heidin tekemä issues-toiminnallisuus backendiin — GitHub-palvelu hakee ja tallentaa nyt myös issuset tietokantaan
- Toteutettiin next steps -ominaisuus analyysipalveluun — uusi endpoint joka pyytää Geminiä analysoimaan projektin tilan ja ehdottamaan konkreettisia seuraavia kehitysaskelia
- Lisättiin status-endpoint GitHub-palveluun — kertoo onko repositoriolle tehty analyysejä ja kuinka monta
- Backend MVP valmis: kaikki neljä mikropalvelua toimivat tietokannalla, Dockerissa ja kaikki suunnitellut ominaisuudet on toteutettu
- Aloitettiin projektiraportin kirjoittaminen — ensimmäiset sisällöt arkkitehtuuri- ja menetelmädokumentteihin
 
![](images/jonintunnit/6.png)
 
---
 
## Viikko 11: Dokumentaation jatkaminen
 
- Jatkettiin projektiraportin kirjoittamista — täydennettiin arkkitehtuuri- ja menetelmädokumentteja
- Lisättiin projektin README-tiedostoja selventämään rakennetta ja käyttöönottoa
- Raporttisisältöä täydennettiin ja laajennettiin
 
![](images/jonintunnit/7.png)
 
---
 
## Viikko 12: Raportin syventäminen ja tulosalustan pohdinta
 
- Kirjoitettiin sisältöä data-aineisto- ja pohdintatiedostoihin
- Pohdittiin ja alustettiin saaduista tuloksista — hahmoteltiin mitä projekti on tuottanut ja miten tuloksia esitetään
- Lisättiin satulua — täydennettiin raportin osia lisäsisällöllä
 
![](images/jonintunnit/8.png)
 
---
 
## Viikko 13: Raportin viimeistelyä ja testidatan keruu sekä testitiedostot
 
- Kirjoitettiin data-aineisto-, arkkitehtuuri-, menetelmä- ja pohdintadokumentit lähes valmiiksi ja vietiin GitHubiin
- Päivitettiin README-tiedostoja ja varmistettiin että unohdetut tiedostot löytyvät
- Ajettiin kaikki testitiedostot ja kerättiin testidataa dokumentaatiota varten — tietokantarivimäärät, testien läpäisytulokset ja AI-vastausten laatu
- Tehtiin manuaalisia curl-testejä live-kontteja vasten eri repositorioilla (`torvalds/linux`, `facebook/react`, `microsoft/vscode`)
- Tulokset kirjattiin projektin tulokset-dokumenttiin
 
![](images/jonintunnit/9.png)
 
---

## Viikko 14: Videoesityksen valmistelu ja tulokset
 
- Tehtiin esitysslaidit tulevaa videoesitystä varten — käytiin läpi projektin rakenne, arkkitehtuuri ja backend-toteutus
- Täytettiin tulokset-dokumenttia testiajon datalla — kirjattiin tietokantarivimäärät, testien läpäisytulokset ja AI-generoitujen sisältöjen pituudet
 
![](images/jonintunnit/10.png)
 
---
 
## Viikko 15: Projektin loppudemo
 
- Nauhoitettiin videoesitys — Joni kävi läpi projektin johdannon, arkkitehtuurin ja backend-toteutuksen slaidien avulla, Heidi esitteli Streamlit-frontendin
- Projekti saatettiin loppuun
 
**Tunnit viikolla 15:** 2h
 
---