# Skolske obvody §44 — demo analyza nad realnymi datami

## Aktualny stav projektu

Projekt `skolske-obvody-44` uz ma realnu datovu kostru pre mesto Presov:

- VZN mesta Presov so skolskymi obvodmi,
- zoznam ulic priradenych k jednotlivym skolam,
- register adries a stavieb,
- geokodovane adresy a ulice,
- skoly a ich polohy,
- vrstvy pre mapu,
- deterministicky engine, ktory hodnoti podmienky §44 zakona c. 321/2025 Z. z.

Posledny dolezity posun je `streets pivot`: obvody sa uz nemaju prezentovat ako sporne alebo umele plosne polygony. Zakladna mapa ma ukazovat skolsky obvod ako farebnu siet ulic priradenych ku skole. To je spravne, lebo VZN v praxi definuje obvody cez ulice a adresy, nie cez dokonale GIS hranice.

Aktualna produkcna linia ma navyse dolezity princip: engine je jediny zdroj pravdy. GUI nema samo vymyslat porusenia, farby, prekryvy ani dodatocne polygony. GUI ma kreslit to, co vypocital engine z dat.

## Co teraz potrebujeme

Tato aplikacia ma byt demo. Jej ciel nie je dokazat, ze v Presove realne existuju vsetky typy poruseni. Ciel je ukazat, aku funkcionalitu bude mat agent alebo portal, ked dostane kompletne vstupne data.

Preto rozdelujeme vstupy na dve vrstvy:

1. **Realne podklady**  
   Tie nemenime a nekrivime. Patria sem VZN, ulice, adresy, geokody, skoly, poloha ulic a realne dostupne verejne zdroje.

2. **Demo doplnkove data**  
   Tie doplnime tam, kde realny svet alebo dostupne dataset-y neposkytuju vsetky situacie, ktore chceme ukazat. Demo data nesmu obist engine. Naopak, musia byt vlozene ako vstup pre engine, aby engine poctivo vypocital vysledok.

Inymi slovami: nefejkujeme vysledky. Prisposobime demo vstupy tak, aby skutocny engine ukazal vsetky typy vystupov.

## Hlavny princip

Realne data su kostra. Mock data su scenar. Engine je sudca. GUI je iba okno.

Tento princip musi ostat tvrdy:

- realne VZN ulice a adresy ostavaju oznacene ako realne,
- demo scenare su explicitne oznacene ako demo vstupy,
- engine nad nimi bezi rovnako ako nad realnymi vstupmi,
- scorecard, nalezy, mapa a detail skoly beru vysledok z engine,
- ziadne UI hardcody typu "tuto vykresli cerveny prekryv" alebo "tuto ukaz porusenie".

## Ako ma vyzerat demo vrstva

### 1. Ciste obvody ako ulice, nie ako sporne polygony

Zakladna mapa ma ostavat postavena na realnych VZN uliciach. Kazdy skolsky obvod je siet ulic vo farbe svojej skoly. Ak je ulica v dvoch obvodoch, samo o sebe to nie je porusenie. Porusenie moze vzniknut az vtedy, ked ta ista cela adresa, teda ulica plus cislo, patri do dvoch obvodov.

Pre demo mozeme doplnit jednoduche pomocne geometrie len ako vstupne data pre analyzu, napriklad zony pre MRK alebo demo minority. Nemaju byt kreslene ako manualne UI dekoracie. Ak sa maju zobrazit, musia prejst cez datovu vrstvu a engine.

### 2. Segregacia a inkluzia

Najsilnejsi a najrealistickejsi demo scenar je vyclenenie marginalizovanej skupiny. Pre Presov mozeme pouzit realny koncept Atlasu MRK, ale demo nemusi presne rekonstruovat hranicu kazdej lokality.

Potrebujeme dodat vstup:

- lokalita marginalizovanej skupiny,
- vztah lokality k uliciam alebo adresam,
- informacia, ci deti z tejto lokality patria do beznej skoly alebo su de facto odklonene inde,
- vysvetlenie, preco engine vyhodnotil signal segregacie alebo inkluzne riziko.

Mapa potom ukaze napriklad: "tato skupina adries patri do obvodu A, ale pridelenie alebo dostupnost smeruje deti mimo beznej skoly". Dolezite je, aby to engine vyhodnotil z demo vstupov, nie aby sme to len nakreslili.

### 3. Kapacita skoly

Kapacitne data pre skoly nemame v dostatocnej kvalite. Preto ich doplnime ako demo vstup:

- kapacita skoly,
- pocet ziakov alebo odhad dopytu v obvode,
- prah pre upozornenie na pretazenie.

Engine potom vypocita signal typu: skola ma kapacitu 560, ale obvod generuje 712 ziakov. Tento signal je vhodny pre planovanie a demo, ale nema automaticky tvrdit pravne porusenie, ak §44 hovori o inom type podmienky.

### 4. Prilis vzdialena skola

Vzdialenost ukazeme cez vybrane demo adresy. Nemusime dokazat, ze kazda adresa v Presove ma presny routing. Staci pripravit reprezentativne adresy v obvode:

- adresa dietata,
- pridelena skola,
- vzdialenost alebo cas cesty,
- vysledok Pa/Pb/Pc podla metodiky.

Ak chceme ukazat dlhu cestu, nevymyslime hotovy nalez. Vytvorime demo adresu alebo demo routing vstup, engine spocita vzdialenost/cas/prestupy a az potom GUI ukaze vysledok.

### 5. Narocna cesta

Pre narocnu cestu potrebujeme samostatny scenar:

- prestupy v MHD,
- nebezpecny usek,
- cesta cez frekventovanu komunikaciu,
- absencia bezpecneho prechodu alebo podchodu.

Aj tu plati, ze demo moze pouzit zjednodusene vstupy. Napriklad "tato trasa ma dva prestupy" alebo "tato trasa prekroci bariery". Ale engine musi byt ten, kto rozhodne, ci ide o riziko.

### 6. Jazykova mensina

Jazyk nie je priamo §44 semafor. Ma byt zobrazeny ako podnet mimo §44. Demo moze ukazat hypoteticku jazykovu mensinu v Presove:

- skupina adries potrebuje vyucovanie v jazyku X,
- pridelena skola tento jazyk neposkytuje,
- dostupna skola s jazykom X je mimo obvodu alebo prilis daleko.

Vystup: "podnet mimo §44", nie cerveny zakonny verdikt. To je dolezite, aby demo neposuvalo pravnu interpretaciu tam, kde zakon priamo nehovori.

### 7. Prekryv obvodov

Prekryv nechceme robit cez plosne polygony. V demo staci ukazat jasny pripad rovnakej celej adresy v dvoch obvodoch:

- rovnaka ulica,
- rovnake cislo domu,
- dve rozne priradenia ku skolam.

Mapa to moze vizualne ukazat farebnou bodkou alebo markerom na ulici. Engine vyhodnoti strukturalny problem. Shared street bez rovnakeho cisla domu ostava v poriadku.

## Co treba doplnit do dat

Navrhujem pripravit samostatny demo seed, ktory bude vedla realnych tabuliek:

- `demo_scenarios`: zoznam demo scenarov a ich popis,
- `demo_localities`: demo lokality MRK alebo jazykovej mensiny,
- `demo_capacity_inputs`: kapacity a pocty ziakov,
- `demo_route_inputs`: vzdialenost, cas, prestupy, bariery,
- `demo_address_assignments`: vybrane adresy pre overlap alebo vzdialenost,
- `demo_flags`: jasne oznacenie, ktore vstupy su demo.

Realne tabulky sa nemenia. Demo tabulky alebo demo stlpce iba doplnia chybajuce informacie pre engine.

## Co ma engine robit v dalsom kroku

Engine ma nad realnymi plus demo vstupmi vytvorit tieto vysledky:

- tvrde §44 pravidla: PASS / FAIL / INCOMPLETE,
- rizikove indikatory: PASS / RISK / FAIL podla metodiky,
- analyticke signaly: SIGNAL / NO_SIGNAL,
- podnety mimo §44: napriklad jazyk,
- provenienciu pri kazdom vystupe: realne data alebo demo vstup,
- kratke vysvetlenie pre uradnika.

Semafor musi ostat pravne disciplinovany:

- RED len pri tvrdom strukturalnom poruseni,
- ORANGE pri rizikovych indikatoroch,
- GREEN pri splnenom stave,
- Pe/Pf a jazyk ako oddelene signaly alebo podnety, ak nemaju byt priamym zakonnym verdiktom.

## Co ma GUI ukazat

GUI ma zobrazit:

- mapu ulic podla skolskych obvodov,
- skoly ako body,
- vybrane demo adresy alebo lokality,
- detail obvodu s vysvetlenim kazdej podmienky,
- register nalezov,
- filter na typ porusenia: segregacia, kapacita, vzdialenost, narocna cesta, jazyk, prekryv adresy,
- jasne, ale nevtierave oznacenie, ze cast vstupov je demo.

Na obrazovke nema byt chaos z oznaceni "demo" pri kazdom riadku. Staci jeden hlavny demo banner a pri detailnom dokaze jasna proveniencia: "Zdroj: realne VZN" alebo "Zdroj: demo vstup".

## Akceptacne kriteria

Hotove to bude vtedy, ked:

- realne VZN/adresne data ostanu nezmenene,
- demo vstupy budu oddelene a explicitne oznacene,
- engine po spusteni vypocita vsetky demo scenare,
- GUI nebude mat manualne dokreslene porusenia mimo engine,
- na mape bude viditelna aspon jedna ukazka kazdeho typu scenara,
- detail obvodu bude vediet vysvetlit, odkial sa vysledok vzal,
- register nalezov bude filtrovat typy problemov,
- jazyk bude jasne oznaceny ako podnet mimo §44,
- prekryv bude viazany na celu adresu, nie na zdielanu ulicu,
- pred merge prejde Playwright dokaz a reviewer gate.

## Navrhovany dalsi coding brief

Implementovat "Step 2: demo analysis layer".

Praca ma prebehnut v jednej koherentnej vetve, nie po malych izolovanych opravach:

1. Navrhnut demo input schema.
2. Naplnit demo seed tak, aby pokryl vsetky scenare.
3. Upravit engine checkery, aby citali demo vstupy a stale vracali standardny verdict.
4. Znovu zapnut compliance display cez existujuci gate.
5. Napojit mapu, detail a register nalezov len na engine vystupy.
6. Overit browserom, screenshotmi a DB dotazmi.
7. Dat cez GPT-5.5 reviewer pred merge.

Toto je najlepsia cesta, lebo demo bude vyzerat bohato, ale nebude klamat o mechanike. Budeme mat realnu kostru Presova, nad nou kontrolovane demo vstupy a nad tym skutocny engine.
