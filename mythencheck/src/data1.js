/* Inhalte Teil 1: Wissenschaft & Natur, Gesundheit & Medizin.
   Format: facts = [Überschrift, Text]; sources = [Typ, Angabe, URL]; quiz = [Frage, [richtig, falsch, falsch, falsch], Erklärung].
   Die erste Antwortoption ist immer die richtige; die Reihenfolge wird zur Laufzeit gemischt. */
var TOPICS_1 = [
{
id:"klima", cat:"natur",
title:"Der Klimawandel ist nicht menschengemacht",
short:"Sonne, natürliche Zyklen, „CO₂ ist doch nur 0,04 Prozent“: Warum die Erwärmung trotzdem auf uns zurückgeht.",
tags:["Klimalüge","CO2","Sonne","IPCC","Erderwärmung","Klimaleugnung"],
claim:"Die aktuelle Erwärmung sei natürlich, etwa durch die Sonne oder durch Klimazyklen. CO₂ sei mit rund 0,04 Prozent viel zu gering konzentriert, um etwas zu bewirken, und im Mittelalter sei es ohnehin wärmer gewesen. Die „Klimalüge“ diene Politik und Wirtschaft nur als Vorwand für Steuern und Verbote.",
origin:[
"Zweifel am menschengemachten Klimawandel wurden ab den späten 1980er Jahren gezielt gestreut, unter anderem von Denkfabriken und Teilen der fossilen Industrie. Die Wissenschaftshistoriker Naomi Oreskes und Erik Conway zeigten, dass dabei dieselben Strategien zum Einsatz kamen wie zuvor bei der Tabakindustrie: Unsicherheit inszenieren, wo die Forschung längst einig ist.",
"In Deutschland ist die Ablehnung der Klimaforschung heute vor allem im rechtspopulistischen Spektrum verankert. Das Grundsatzprogramm der AfD von 2016 erklärt, das Klima wandle sich, „solange die Erde existiert“, die Klimaschutzpolitik beruhe auf „hypothetischen Klima-Modellen“, und Kohlendioxid sei „kein Schadstoff“."
],
kernel:"Das Klima hat sich in der Erdgeschichte tatsächlich immer wieder gewandelt, etwa durch Schwankungen der Erdbahn. Gerade deshalb lässt sich die heutige Erwärmung gut einordnen: Laut Weltklimarat ist die globale Oberflächentemperatur seit 1970 schneller gestiegen als in jedem anderen 50-Jahres-Zeitraum der mindestens letzten 2000 Jahre.",
facts:[
["Der Weltklimarat ist eindeutig","„Es ist eindeutig, dass der Einfluss des Menschen die Atmosphäre, den Ozean und die Landflächen erwärmt hat“, heißt es im Sechsten Sachstandsbericht des IPCC (2021). Die beste Schätzung für den menschengemachten Anteil an der Erwärmung von 1850 bis 1900 bis zum Zeitraum 2010 bis 2019 lautet 1,07 °C (wahrscheinliche Spanne 0,8 bis 1,3 °C). Natürliche Einflüsse wie Sonne und Vulkane trugen nur zwischen minus 0,1 und plus 0,1 °C bei."],
["Über 99 Prozent Konsens","Eine Auswertung von 88.125 klimabezogenen Fachartikeln, die seit 2012 erschienen sind, ergab: Der Konsens über den menschengemachten Klimawandel liegt in der begutachteten Fachliteratur bei über 99 Prozent (Lynas et al. 2021)."],
["Die Sonne scheidet als Ursache aus","Die Sonnenaktivität zeigt seit Jahrzehnten einen leicht fallenden Trend, während die Temperaturen stark gestiegen sind. Zudem kühlt die Stratosphäre ab, während sich die untere Atmosphäre erwärmt. Genau dieses Muster erzeugen Treibhausgase; eine stärkere Sonne würde beide Schichten erwärmen."],
["Wenig Gas, große Wirkung","CO₂ macht nur rund 0,04 Prozent der Luft aus, absorbiert aber Wärmestrahlung sehr wirksam. Diesen Effekt beschrieben schon John Tyndall (1859) und Svante Arrhenius (1896). Die Konzentration stieg von etwa 280 ppm vor der Industrialisierung auf rund 430 ppm im Jahr 2025 (Messstation Mauna Loa), also um mehr als die Hälfte. Die Isotopenzusammensetzung des zusätzlichen CO₂ verrät seine Herkunft aus fossilen Brennstoffen."],
["Früher wärmer? Nicht überall zugleich","Mittelalterliche Warmzeit und Kleine Eiszeit verliefen regional und zeitlich versetzt. Die heutige Erwärmung erfasst dagegen fast den ganzen Globus: Für mehr als 98 Prozent der Erdoberfläche war das 20. Jahrhundert die wärmste Periode der letzten 2000 Jahre (Neukom et al. 2019)."],
["Neue Rekorde","2024 war mit 1,60 °C über dem vorindustriellen Niveau das bisher wärmste Jahr der Messgeschichte. Im Dreijahresmittel 2023 bis 2025 lag die globale Temperatur erstmals über der 1,5-Grad-Marke (Copernicus-Klimadienst)."]
],
sources:[
["Bericht","IPCC (2021): Climate Change 2021. The Physical Science Basis. Summary for Policymakers. Sechster Sachstandsbericht, Arbeitsgruppe I.","https://www.ipcc.ch/report/ar6/wg1/chapter/summary-for-policymakers/"],
["Studie","Lynas, M., Houlton, B. Z., Perry, S. (2021): Greater than 99% consensus on human caused climate change in the peer-reviewed scientific literature. Environmental Research Letters 16, 114005.","https://ui.adsabs.harvard.edu/abs/2021ERL....16k4005L/abstract"],
["Studie","Neukom, R. et al. (2019): No evidence for globally coherent warm and cold periods over the preindustrial Common Era. Nature 571, S. 550 bis 554.","https://link.springer.com/10.1038/s41586-019-1401-2"],
["Behörde","Copernicus-Klimadienst / ECMWF (Januar 2026): 2025 was the third-warmest year on record.","https://www.ecmwf.int/node/31031"],
["Faktencheck","Klimafakten.de: Faktencheck zum Grundsatzprogramm der AfD.","https://www.klimafakten.de/sites/default/files/downloads/faktencheckafd-grundsatzprogramm.pdf"],
["Buch","Rahmstorf, S., Schellnhuber, H. J. (2019): Der Klimawandel. Diagnose, Prognose, Therapie. 9. Auflage. C. H. Beck, München.","https://d-nb.info/1189939045"],
["Buch","Oreskes, N., Conway, E. M. (2010): Merchants of Doubt. Bloomsbury Press. Deutsche Ausgabe: Die Machiavellis der Wissenschaft. Das Netzwerk des Leugnens. Wiley-VCH, Weinheim 2014.","https://d-nb.info/1049503333"],
["Medien","DER SPIEGEL: Werteunion und die Neue Rechte: Koalition der Klimawandelleugner.","https://www.spiegel.de/wissenschaft/mensch/koalition-der-klimawandelleugner-a-c1a03be4-8921-4898-a4f3-a11a1c814008"],
["Medien","DER SPIEGEL International: AfD Hopes to Win Votes by Opposing Climate Protection.","https://www.spiegel.de/international/germany/afd-seeks-votes-by-opposing-climate-protection-a-1265494.html"]
],
quiz:[
["Wie groß ist laut Weltklimarat die beste Schätzung des menschengemachten Anteils an der Erwärmung (Zeitraum 2010 bis 2019 gegenüber 1850 bis 1900)?",["1,07 °C","0,1 °C","0,4 °C","2,5 °C"],"Der IPCC beziffert den menschengemachten Anteil auf 1,07 °C. Das entspricht praktisch der gesamten beobachteten Erwärmung; natürliche Faktoren lagen nahe null."],
["Welcher Befund spricht klar gegen die Sonne als Hauptursache der Erwärmung?",["Die Stratosphäre kühlt ab, während sich die untere Atmosphäre erwärmt","Die Sonne ist seit 1980 deutlich heller geworden","Sonnenflecken erzeugen CO₂","Die Erwärmung betrifft nur die Südhalbkugel"],"Eine stärkere Sonne würde alle Schichten der Atmosphäre erwärmen. Die Abkühlung der Stratosphäre ist der Fingerabdruck von Treibhausgasen. Außerdem ist die Sonnenaktivität seit Jahrzehnten leicht rückläufig."],
["Warum kann ein Gas mit nur rund 0,04 Prozent Anteil das Klima verändern?",["Weil CO₂ Wärmestrahlung absorbiert und wieder abstrahlt","Weil CO₂ schwerer als Luft ist und Hitze am Boden staut","Weil CO₂ die Ozonschicht zerstört","Gar nicht, die Wirkung ist erfunden"],"Entscheidend ist nicht die Menge, sondern die physikalische Eigenschaft: CO₂ absorbiert Infrarotstrahlung. Das ist seit dem 19. Jahrhundert im Labor gemessen."]
]
},
{
id:"flache-erde", cat:"natur",
title:"Die Erde ist eine Scheibe",
short:"Die Antarktis als Eiswall, NASA-Fotos als Fälschung: Was Flacherdler glauben und warum schon die Antike es besser wusste.",
tags:["Flat Earth","Flacherde","Scheibe","NASA","Eiswall"],
claim:"Die Erde sei eine flache Scheibe, umgeben von einem Eiswall, den wir Antarktis nennen. Die Kugelgestalt sei eine Lüge von NASA und Regierungen, Satellitenbilder seien gefälscht, und die Schwerkraft gebe es in dieser Form nicht.",
origin:[
"Die moderne Flacherde-Bewegung geht auf den Engländer Samuel Rowbotham zurück, der ab Mitte des 19. Jahrhunderts seine „Zetetische Astronomie“ verbreitete. 1956 gründete Samuel Shenton die Flat Earth Society. Einen enormen Aufschwung erlebte die Idee seit Mitte der 2010er-Jahre durch Videos auf YouTube und in sozialen Netzwerken.",
"Pikant: Der verbreitete Glaube, die Menschen des Mittelalters hätten die Erde für eine Scheibe gehalten, ist selbst eine Legende des 19. Jahrhunderts. Gebildete wussten seit der Antike, dass die Erde eine Kugel ist."
],
facts:[
["Seit über 2000 Jahren vermessen","Eratosthenes von Kyrene berechnete im 3. Jahrhundert v. Chr. aus dem unterschiedlichen Sonnenstand in Syene und Alexandria den Erdumfang. Heute kennen wir ihn präzise: rund 40.075 Kilometer am Äquator. Schon Aristoteles bemerkte, dass man von Ägypten aus Sterne sieht, die in Europa nie zu sehen sind, und der Erdschatten auf dem Mond ist bei jeder Mondfinsternis rund."],
["Der Horizont verschluckt Schiffe","Schiffe verschwinden hinter dem Horizont von unten nach oben: zuerst der Rumpf, zuletzt die Mastspitze. Wer höher steht, sieht weiter. Beides folgt direkt aus der Krümmung der Erdoberfläche."],
["Zeitzonen und fremde Sterne","Wenn in Berlin Mittag ist, herrscht in Sydney tiefe Nacht. Auf der Südhalbkugel sieht man Sternbilder wie das Kreuz des Südens, die von Mitteleuropa aus nie aufgehen. Unter einer gemeinsamen Himmelskuppel über einer Scheibe wäre beides nicht erklärbar."],
["Flugrouten über den Süden","Es gibt Nonstop-Flüge von Sydney nach Santiago de Chile. Auf der üblichen Flacherde-Karte mit dem Nordpol in der Mitte wäre diese Strecke mehr als doppelt so lang wie in Wirklichkeit; kein heutiges Verkehrsflugzeug hätte dafür die nötige Reichweite."],
["Ihr eigenes Experiment","In der Dokumentation „Behind the Curve“ (2018) prüfte ein Flacherdler mit einem rund 20.000 Dollar teuren Ringlaser-Kreisel, ob sich die Erde dreht. Das Gerät zeigte eine Drift von 15 Grad pro Stunde: exakt die Erdrotation von 360 Grad in 24 Stunden."],
["Mit bloßem Auge sichtbar","Die Internationale Raumstation ISS umrundet die Erde in rund 400 Kilometern Höhe etwa alle 93 Minuten. Ihre Überflüge lassen sich vorausberechnen und vom eigenen Balkon aus beobachten."]
],
sources:[
["Medien","Quarks (WDR), Science Cops Folge 88: Die Akte Flache Erde.","https://www.quarks.de/podcast/quarks-science-cops-folge-88-die-akte-flache-erde/"],
["Medien","Executive Traveller: Qantas’ Sydney to Santiago flights make triumphant return (Nonstop-Verbindung).","https://www.executivetraveller.com/news/qantas-restarts-sydney-santiago-chile"],
["Buch","Garwood, C. (2007): Flat Earth. The History of an Infamous Idea. Pan Books. ISBN 978-1-4050-4702-9.",""],
["Buch","Russell, J. B. (1991): Inventing the Flat Earth. Columbus and Modern Historians.",""],
["Medien","Newsweek (2019): Bericht über die Experimente in der Netflix-Dokumentation „Behind the Curve“.","https://newsweek.com/behind-curve-netflix-ending-light-experiment-mark-sargent-documentary-movie-1343362"],
["Behörde","Bundeszentrale für politische Bildung: Reichsbürger, Mondlandung, Reptiloide, Flacherde.","https://www.bpb.de/themen/medien-journalismus/wahre-welle/270429/reichsbuerger-mondlandung-reptiloide-flacherde/"]
],
quiz:[
["Wer berechnete schon im 3. Jahrhundert v. Chr. den Umfang der Erde?",["Eratosthenes von Kyrene","Galileo Galilei","Isaac Newton","Nikolaus Kopernikus"],"Eratosthenes verglich den Sonnenstand in Syene und Alexandria und berechnete daraus den Erdumfang, fast 1800 Jahre vor Kopernikus."],
["Welches Ergebnis lieferte der Kreiselversuch eines Flacherdlers in der Doku „Behind the Curve“?",["Eine Drift von 15 Grad pro Stunde, also genau die Erdrotation","Keinerlei Bewegung","Eine Drift von 1 Grad pro Tag","Das Gerät ging kaputt"],"15 Grad pro Stunde ergeben 360 Grad in 24 Stunden. Der Versuch bestätigte unfreiwillig die Rotation der Erde."],
["Was wussten Gelehrte im Mittelalter über die Form der Erde?",["Dass die Erde eine Kugel ist","Sie hielten sie mehrheitlich für eine Scheibe","Sie hielten sie für einen Würfel","Sie hatten keinerlei Vorstellung davon"],"Die Kugelgestalt war seit der Antike Lehrstoff. Die Idee vom „Scheiben-Mittelalter“ ist eine Legende des 19. Jahrhunderts."]
]
},
{
id:"mondlandung", cat:"natur",
title:"Die Mondlandung war inszeniert",
short:"Wehende Flagge, fehlende Sterne, tödliche Strahlung? Was gegen das Studio-Märchen spricht.",
tags:["Apollo","Mond","NASA","Moon Hoax","Kubrick"],
claim:"Die USA hätten die Mondlandungen von 1969 bis 1972 in einem Filmstudio inszeniert, um den Wettlauf ins All gegen die Sowjetunion zu gewinnen. Belege seien die „wehende“ Flagge, fehlende Sterne auf den Fotos und die tödliche Strahlung der Van-Allen-Gürtel.",
origin:[
"Populär wurde die Idee durch Bill Kaysings Buch „We Never Went to the Moon“ von 1976. Eine Fernsehsendung des US-Senders Fox brachte sie 2001 einem Millionenpublikum nahe.",
"Bemerkenswert: Die Sowjetunion verfolgte die Missionen mit eigener Überwachungstechnik und hätte jeden Grund gehabt, einen Betrug ihres Rivalen zu entlarven. Stattdessen berichtete die Große Sowjetische Enzyklopädie die Landungen als Tatsache."
],
facts:[
["Zwölf Menschen auf dem Mond","Bei sechs Landungen (Apollo 11, 12, 14, 15, 16 und 17) betraten zwischen 1969 und 1972 zwölf Astronauten den Mond. Sie brachten rund 382 Kilogramm Gestein mit, das bis heute in Laboren auf der ganzen Welt untersucht wird und sich deutlich von irdischem Gestein unterscheidet."],
["Spiegel auf dem Mond","An den Landestellen von Apollo 11, 14 und 15 stehen Retroreflektoren. Observatorien schießen bis heute Laserpulse darauf und messen so die Entfernung zwischen Erde und Mond auf Zentimeter genau."],
["Fotos aus dem Orbit","Die NASA-Sonde Lunar Reconnaissance Orbiter fotografiert seit 2009 die Landestellen. Auf Aufnahmen von 2011 sind Abstiegsstufen, zurückgelassene Geräte, Fußpfade der Astronauten und die Spuren des Mondautos zu erkennen."],
["Flagge und Sterne","Die Flagge hing an einer Stange mit waagrechtem Querstück am oberen Ende. Sie bewegte sich nur, wenn die Astronauten den Mast drehten, und schwang im Vakuum ohne bremsende Luft lange nach. Sterne fehlen auf den Fotos, weil die Kameras auf die grell beleuchtete Mondoberfläche belichtet waren."],
["Die Strahlung war beherrschbar","Die Crews durchquerten die Van-Allen-Gürtel binnen weniger Stunden. Die gemessenen Hautdosen lagen je nach Mission bei etwa 0,2 bis gut 1 rad und damit unter den empfohlenen Jahreshöchstwerten für beruflich strahlenexponierte Personen."],
["Zu viele Mitwisser","Der Physiker David Robert Grimes schätzte 2016, dass rund 411.000 Menschen (die Zahl der NASA-Beschäftigten 1965) hätten schweigen müssen. Eine solche Verschwörung wäre seinem Modell zufolge nach etwa 3,7 Jahren aufgeflogen."]
],
sources:[
["Medien","Spektrum der Wissenschaft: 10 Mythen über die Mondlandungen.","https://www.spektrum.de/wissen/10-mythen-ueber-die-mondlandungen/1301190"],
["Medien","Quarks (WDR), Science Cops: Die Mär von der falschen Mondlandung.","https://www.quarks.de/podcast/die-mondlandung-quarks-science-cops/"],
["Bericht","National Academies of Sciences: Kapitel zu den rund 382 Kilogramm Apollo-Proben.","https://www.nap.edu/read/25312/chapter/4"],
["Medien","Space.com: Why Is the Apollo Reflector Experiment Still Operating, 50 Years Later?","https://www.space.com/apollo-retroreflector-experiment-still-going-50-years-later.html"],
["Behörde","NASA Science: Apollo 11 Landing Site, Aufnahmen des Lunar Reconnaissance Orbiter.","https://science.nasa.gov/resource/apollo-11-landing-site"],
["Medien","NPR (2011): Tracks, Equipment Left By Apollo Missions Visible In New Moon Photos.","https://www.npr.org/blogs/thetwo-way/2011/09/06/140216986/tracks-equipment-left-by-apollo-missions-visible-in-new-moon-photos"],
["Behörde","NASA, Apollo Lunar Surface Journal: Working on the Moon, Radiation (Strahlendosen der Apollo-Crews).","https://www.nasa.gov/wp-content/uploads/static/history/alsj/WOTM/WOTM-Radiation.html"],
["Studie","Grimes, D. R. (2016): On the Viability of Conspiratorial Beliefs. PLOS ONE 11(1), e0147905.","https://doi.org/10.1371/journal.pone.0147905"],
["Medien","DER SPIEGEL (2019): Laserreflektoren auf dem Mond: Die Anti-Verschwörungstheorie-Maschinen.","https://www.spiegel.de/wissenschaft/weltall/laserreflektoren-auf-dem-mond-die-anti-verschwoerungstheorie-maschinen-a-1278583.html"],
["Medien","DER SPIEGEL: „Vom ersten Tag an gab es Zweifler“. Mondlandung, Chemtrails, Reichsflugscheibe: Verschwörungstheorien im Check.","https://www.spiegel.de/wissenschaft/weltall/mondlandung-chemtrail-reichsflugscheibe-verschwoerungstheorien-im-check-a-1277763.html"]
],
quiz:[
["Was messen Observatorien bis heute mit Hilfe der Apollo-Retroreflektoren?",["Die Entfernung zwischen Erde und Mond","Die Temperatur auf dem Mond","Die Strahlung im All","Nichts, es gibt dort keine Reflektoren"],"Laserpulse werden von den Spiegeln zurückgeworfen. Aus der Laufzeit ergibt sich die Entfernung auf Zentimeter genau."],
["Warum sind auf vielen Apollo-Fotos keine Sterne zu sehen?",["Die Kameras waren auf die hell beleuchtete Oberfläche belichtet","Weil die Fotos im Studio entstanden","Weil es vom Mond aus keine Sterne gibt","Weil die NASA sie wegretuschierte"],"Bei kurzer Belichtungszeit für helle Motive bleiben schwache Lichtquellen wie Sterne unsichtbar. Das kennt jeder, der nachts eine beleuchtete Straße fotografiert."],
["Welcher Staat hätte am meisten Interesse gehabt, einen Betrug aufzudecken, und berichtete die Landungen trotzdem als Tatsache?",["Die Sowjetunion","Kanada","Frankreich","Japan"],"Die Sowjetunion war der direkte Konkurrent im Wettlauf zum Mond und verfolgte die Flüge mit eigener Technik. Einen Betrug hätte sie propagandistisch ausgeschlachtet; ihre Staatsenzyklopädie beschrieb die Landungen dagegen als Tatsache."]
]
},
{
id:"chemtrails", cat:"natur",
title:"Chemtrails: Gift aus dem Flugzeug",
short:"Lange weiße Streifen am Himmel sollen ein geheimes Sprühprogramm beweisen. Die Physik erklärt sie längst.",
tags:["Kondensstreifen","Aluminium","Barium","Geoengineering","Sprühen"],
claim:"Flugzeuge versprühten heimlich Chemikalien wie Aluminium oder Barium, um das Wetter zu manipulieren, die Bevölkerung zu vergiften oder unfruchtbar zu machen. Erkennbar sei das an Streifen, die lange am Himmel stehen bleiben und Gittermuster bilden.",
origin:[
"Die Erzählung entstand Ende der 1990er Jahre in den USA, befeuert durch Radiosendungen und eine Studienarbeit an der Air University der US-Luftwaffe von 1996 mit dem Titel „Weather as a Force Multiplier: Owning the Weather in 2025“. Die Luftwaffe selbst bezeichnete deren Inhalte als fiktive Zukunftsszenarien.",
"Über das Internet verbreitete sich die Idee weltweit. In Deutschland beantworten Behörden wie das Umweltbundesamt seit Jahren Anfragen besorgter Bürgerinnen und Bürger dazu."
],
kernel:"Es gibt tatsächlich Forschung zu Geoengineering, etwa zur Idee, Sonnenlicht mit Partikeln in der Stratosphäre zu reflektieren. Diese Forschung findet öffentlich statt, ist politisch umstritten und wird bisher nicht großflächig angewendet. Mit den Kondensstreifen von Linienflugzeugen hat sie nichts zu tun.",
facts:[
["Kondensstreifen sind Physik","Triebwerke stoßen heißen, wasserdampfreichen Abgasstrahl aus, der in Reiseflughöhe bei Temperaturen von meist unter etwa minus 40 °C zu Eiskristallen gefriert. Ist die Luft dort sehr feucht, bleiben die Streifen stundenlang bestehen und breiten sich zu Schleierwolken aus; in trockener Luft verschwinden sie schnell."],
["Gitter durch Flugrouten","Über Mitteleuropa kreuzen sich viele Flugrouten. Wind verschiebt und verbiegt die Streifen. So entstehen Gitter- und Bogenmuster, ohne dass jemand etwas versprüht."],
["76 von 77 Fachleuten","In einer Befragung (Shearer et al. 2016) gaben 76 von 77 Atmosphärenchemikern und Geochemikern an, keinerlei Hinweise auf ein geheimes Sprühprogramm gefunden zu haben. Die vorgebrachten „Belege“ ließen sich mit bekannter Physik und Chemie erklären."],
["Behörden sehen keine Belege","Das Umweltbundesamt stellt fest, dass es für ein gezieltes Einbringen von Aluminiumverbindungen in die Atmosphäre und für sogenannte Chemtrails keinerlei wissenschaftliche Belege gibt."],
["Die „Beweisfotos“","Das Recherchezentrum Correctiv verfolgte 2021 30 virale Chemtrail-Fotos zurück und fand bei 29 den Ursprung. Häufig zeigen sie Wassertanks, die bei Testflügen als Ballast dienen, oder schlicht Kondensstreifen."]
],
sources:[
["Medien","Quarks (WDR): Kondensstreifen oder Chemtrails. Werden wir manipuliert?","https://www.quarks.de/umwelt/klimawandel/kondensstreifen-oder-chemtrails-werden-wir-manipuliert/"],
["Faktencheck","Lead Stories (2022): It is not Air Force policy to control the weather by 2025.","https://leadstories.com/hoax-alert/2022/11/fact-check-it-is-not-air-force-policy-to-control-the-weather-by-2025.html"],
["Studie","Shearer, C., West, M., Caldeira, K., Davis, S. J. (2016): Quantifying expert consensus against the existence of a secret, large-scale atmospheric spraying program. Environmental Research Letters 11, 084011.","https://doi.org/10.1088/1748-9326/11/8/084011"],
["Behörde","Umweltbundesamt: Chemtrails. Gefährliche Experimente in der Atmosphäre oder bloße Fiktion?","https://www.umweltbundesamt.de/publikationen/chemtrails-gefaehrliche-experimente-atmosphaere"],
["Faktencheck","Correctiv (2021): Nein, diese Fotos beweisen nicht, dass es Chemtrails gibt.","https://correctiv.org/faktencheck/2021/05/05/nein-diese-fotos-beweisen-nicht-dass-es-chemtrails-gibt/"],
["Medien","DER SPIEGEL (2016): Chemtrails: Forscher sagen, es gibt sie nicht.","https://www.spiegel.de/wissenschaft/mensch/chemtrails-forscher-sagen-es-gibt-sie-nicht-a-1107738.html"],
["Medien","DER SPIEGEL (2023): Kleine Anfrage der AfD: Sächsische Staatskanzlei muss sich mit Chemtrails befassen.","https://www.spiegel.de/politik/deutschland/afd-in-sachsen-staatskanzlei-muss-sich-nach-kleiner-anfrage-mit-chemtrails-befassen-a-5d295473-0a4c-4cda-a958-2e9ef1b61f6d"]
],
quiz:[
["Warum bleiben manche Kondensstreifen stundenlang sichtbar?",["Weil die Luft in Reiseflughöhe sehr kalt und feucht ist, sodass die Eiskristalle nicht verdunsten","Weil dem Treibstoff Chemikalien beigemischt sind","Weil die Flugzeuge besonders langsam fliegen","Weil nachts weniger Wind weht"],"Ob ein Streifen schnell verschwindet oder sich ausbreitet, hängt von Temperatur und Feuchtigkeit der umgebenden Luft ab, nicht von geheimen Zusätzen."],
["Wie viele von 77 befragten Fachleuten fanden 2016 keine Hinweise auf ein geheimes Sprühprogramm?",["76","38","12","Keiner"],"76 von 77 Experten sahen keine Hinweise. Die Studie wollte bewusst eine objektive wissenschaftliche Grundlage für die öffentliche Debatte schaffen."],
["Was zeigen virale Chemtrail-„Beweisfotos“ aus Flugzeugkabinen häufig tatsächlich?",["Wassertanks, die bei Testflügen als Ballast dienen","Sprühdüsen für Aluminium","Klimaanlagen für Passagiere","Lagerräume für Barium"],"Bei Erprobungsflügen simulieren Wassertanks die Beladung. Fotos davon werden aus dem Zusammenhang gerissen."]
]
},
{
id:"haarp", cat:"natur",
title:"HAARP steuert das Wetter",
short:"Eine Forschungsanlage in Alaska soll Fluten, Dürren und Erdbeben auslösen. Was sie tatsächlich erforscht.",
tags:["Wettermanipulation","Alaska","Ahrtal","Flut","Ionosphäre"],
claim:"Mit der Antennenanlage HAARP in Alaska ließe sich das Wetter steuern. Unwetter, Dürren, Erdbeben und auch die Flutkatastrophe im Ahrtal 2021 seien gezielt ausgelöst worden. Manche Varianten behaupten sogar Gedankenkontrolle.",
origin:[
"HAARP (High-frequency Active Auroral Research Program) wurde ab 1993 in Gakona, Alaska, als militärisch finanziertes Forschungsprojekt aufgebaut; die US-Luftwaffe betrieb die Anlage bis 2015. Die militärische Finanzierung und das ungewöhnliche Antennenfeld machten die Anlage früh zur Projektionsfläche.",
"Nach nahezu jedem Extremwetter tauchen in sozialen Netzwerken HAARP-Behauptungen auf, so auch nach der Flut im Juli 2021 in Rheinland-Pfalz und Nordrhein-Westfalen."
],
facts:[
["Forschung an der Ionosphäre","HAARP sendet Kurzwellen in die Ionosphäre, die elektrisch leitende Schicht der Hochatmosphäre ab etwa 70 bis 80 Kilometern Höhe. Untersucht wird deren Physik, die zum Beispiel für Funkverbindungen und Satellitennavigation wichtig ist."],
["Wetter entsteht viel weiter unten","Wolken, Regen und Stürme entstehen in der Troposphäre, also in der untersten Schicht der Atmosphäre, die an den Polen etwa 8 und am Äquator etwa 18 Kilometer hoch reicht. Die Sendeleistung von HAARP (rund 3,6 Megawatt) ist winzig im Vergleich zu den Energiemengen eines einzigen Gewitters, die um viele Größenordnungen größer sind."],
["Offen für Besucher","Seit August 2015 betreibt die University of Alaska Fairbanks die Anlage. Forschende aus aller Welt können dort Experimente durchführen, und es gibt regelmäßig Tage der offenen Tür."],
["Die Ahrtal-Flut ist erklärbar","Im Juli 2021 blieb das Tief „Bernd“ tagelang fast ortsfest und lud enorme Regenmengen ab. Die Forschungsgruppe World Weather Attribution kam zu dem Ergebnis, dass der Klimawandel solche Starkregen in der Region 1,2- bis 9-mal wahrscheinlicher und 3 bis 19 Prozent intensiver gemacht hat."],
["Erdbeben entstehen im Gestein","Erdbeben entstehen durch Spannungen in der Erdkruste in Kilometern Tiefe. Radiowellen dringen nicht ins Gestein ein und können dort keine Spannungen erzeugen."]
],
sources:[
["Behörde","HAARP (University of Alaska Fairbanks): Häufige Fragen, u. a. Sendeleistung 3,6 Megawatt.","https://haarp.gi.alaska.edu/faq"],
["Behörde","University of Alaska Fairbanks (2016): HAARP ready for business under UAF management.","https://uaf.edu/news/archives/news-archives-2010-2021/haarp-ready-business-uaf-management.php"],
["Medien","ARRL (2015): HAARP Facility Will Be Transferred to the University of Alaska Fairbanks on August 11.","https://www.arrl.org/news/haarp-facility-will-be-transferred-to-the-university-of-alaska-fairbanks-on-august-11"],
["Studie","World Weather Attribution (2021): Heavy rainfall which led to severe flooding in Western Europe made more likely by climate change.","https://www.worldweatherattribution.org/heavy-rainfall-which-led-to-severe-flooding-in-western-europe-made-more-likely-by-climate-change"],
["Medien","tagesschau.de Faktenfinder (2023): Erdbeben in Marokko: Falsche Videos und Verschwörungsansätze.","https://www.tagesschau.de/faktenfinder/marokko-erdbeben-falsche-videos-100.html"]
],
quiz:[
["In welcher Schicht der Atmosphäre forscht HAARP?",["In der Ionosphäre, ab etwa 70 bis 80 Kilometern Höhe","In der Troposphäre, wo das Wetter entsteht","Im Erdmantel","Jenseits der Mondumlaufbahn"],"HAARP untersucht die Ionosphäre. Das Wetter spielt sich dagegen in der viel tiefer liegenden Troposphäre ab."],
["Wer betreibt HAARP seit 2015?",["Die University of Alaska Fairbanks","Die NATO","Die Vereinten Nationen","Ein privater Ölkonzern"],"Die US-Luftwaffe übergab die Anlage im August 2015 an die Universität, die dort zivile Forschung betreibt."],
["Was führte im Juli 2021 zu den extremen Regenmengen im Ahrtal?",["Ein nahezu ortsfestes Tiefdruckgebiet, dessen Starkregen durch den Klimawandel wahrscheinlicher wurde","Radiowellen aus Alaska","Ein Dammbruch in Belgien","Versprühte Chemikalien"],"Tief „Bernd“ blieb tagelang über der Region. Attributionsstudien zeigen, dass der Klimawandel solche Ereignisse wahrscheinlicher und heftiger macht."]
]
},
{
id:"5g", cat:"natur",
title:"5G macht krank und verbreitet Corona",
short:"Funkmasten brannten, weil Menschen an einen Zusammenhang glaubten. Den gibt es nicht.",
tags:["Mobilfunk","Strahlung","Funkmast","Corona","Elektrosmog"],
claim:"Die Mobilfunktechnik 5G schade der Gesundheit, schwäche das Immunsystem oder verursache sogar COVID-19. Die Pandemie sei nur ein Vorwand, um die Folgen der 5G-Strahlung zu vertuschen.",
origin:[
"Ängste vor Mobilfunk gibt es seit den 1990er Jahren. Anfang 2020 verknüpften Influencer und Verschwörungsseiten den 5G-Ausbau in Wuhan mit dem Ausbruch der Pandemie.",
"Die Folgen waren real: In Großbritannien und den Niederlanden wurden 2020 Dutzende Mobilfunkmasten in Brand gesetzt, Beschäftigte von Telekommunikationsfirmen wurden bedroht."
],
facts:[
["Viren funken nicht","Viren sind biologische Partikel, die sich nur in lebenden Zellen vermehren und von Mensch zu Mensch über Tröpfchen und Aerosole übertragen werden. Radiowellen können sie weder erzeugen noch transportieren."],
["Pandemie ohne 5G","Das Coronavirus verbreitete sich auch in vielen Ländern, die gar kein 5G-Netz hatten, etwa im Iran. Zudem können Viren nicht über Funkwellen übertragen werden."],
["Zu wenig Energie für Schäden am Erbgut","Mobilfunk nutzt nichtionisierende Strahlung. Ihre Energie reicht nicht aus, um chemische Bindungen oder das Erbgut zu schädigen. Der einzige gesicherte biologische Effekt ist eine leichte Gewebeerwärmung, und die Grenzwerte liegen deutlich darunter."],
["Keine Belege unterhalb der Grenzwerte","Nach Angaben der Bundesregierung und des Bundesamts für Strahlenschutz sind sich die Expertengremien einig: Es gibt keine Nachweise schädlicher Wirkungen unterhalb der geltenden Grenzwerte."],
["Keine exotischen Frequenzen","5G nutzt in Deutschland vor allem Frequenzen um 3,6 Gigahertz, also in einem ähnlichen Bereich wie WLAN mit 2,4 und 5 Gigahertz."]
],
sources:[
["Behörde","Bundesnetzagentur: Frequenzauktion 2019 (2-GHz- und 3,6-GHz-Bereich für 5G).","https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Breitband/MobilesBreitband/Frequenzauktion/2019/Auktion2019-node.html"],
["Studie","ICNIRP (2020): Guidelines for Limiting Exposure to Electromagnetic Fields (100 kHz to 300 GHz). Health Physics 118(5), S. 483 bis 524.","https://doi.org/10.1097/HP.0000000000001210"],
["Behörde","Bundesregierung: Beeinträchtigt 5G unsere Gesundheit? Strahlenschutz bei 5G.","https://www.bundesregierung.de/breg-de/suche/strahlenschutz-bei-5g-1829042"],
["Medien","DutchNews (2020): Counter-terrorism service alerted as arsonists set fire to telecom masts.","https://dutchnews.nl/news/2020/04/counter-terrorism-service-alerted-as-arsonists-set-fire-to-telecom-masts"],
["Medien","tagesschau.de Faktenfinder: 5G unter Feuer.","https://www.tagesschau.de/faktenfinder/5g-corona-mobilfunk-101.html"]
],
quiz:[
["Warum kann 5G kein Virus übertragen?",["Viren sind biologische Partikel; Radiowellen können sie weder erzeugen noch transportieren","Weil 5G zu langsam ist","Weil Viren nur über Kabel reisen","Weil 5G-Masten Virenfilter haben"],"Viren brauchen lebende Zellen, um sich zu vermehren, und werden über Tröpfchen und Aerosole übertragen. Funkwellen sind elektromagnetische Schwingungen ohne Materie."],
["Welcher biologische Effekt von Funkwellen ist wissenschaftlich gesichert?",["Eine leichte Gewebeerwärmung, die durch Grenzwerte begrenzt wird","Schäden am Erbgut","Eine Schwächung des Immunsystems","Das Auslösen von Lungenentzündungen"],"Die Grenzwerte sind so festgelegt, dass die Erwärmung deutlich unter einem gesundheitlich relevanten Niveau bleibt."],
["Welche reale Folge hatte der 5G-Corona-Mythos im Jahr 2020?",["Brandanschläge auf Mobilfunkmasten, etwa in Großbritannien und den Niederlanden","Die Abschaltung aller 5G-Netze in Europa","Ein weltweites 5G-Verbot der WHO","Keine"],"Der Mythos hatte handfeste Folgen: Masten brannten, Techniker wurden bedroht."]
]
},
{
id:"phantomzeit", cat:"natur",
title:"Das erfundene Mittelalter",
short:"Karl der Große eine Kunstfigur, fast 300 Jahre frei erfunden? Ein sehr deutscher Mythos, den Baumringe und Sterne widerlegen.",
tags:["Phantomzeit","Illig","Karl der Große","Kalender","Mittelalter"],
claim:"Die Jahre von etwa 614 bis 911 n. Chr. habe es nie gegeben. Mächtige um Kaiser Otto III. hätten sie um das Jahr 1000 nachträglich erfunden; Karl der Große sei eine Kunstfigur. Wir lebten also in Wahrheit fast 300 Jahre früher, als der Kalender behauptet.",
origin:[
"Der Publizist Heribert Illig stellte die These 1991 vor und machte sie mit Büchern wie „Hat Karl der Große je gelebt?“ (1994) und „Das erfundene Mittelalter“ (1996) bekannt.",
"Ein zentrales Argument Illigs ist die Kalenderreform von 1582: Papst Gregor XIII. ließ nur zehn Tage überspringen, obwohl seit Einführung des Julianischen Kalenders unter Caesar rechnerisch etwa 13 Tage Abweichung aufgelaufen wären."
],
facts:[
["Das Kalender-Argument geht nicht auf","Die gregorianische Reform sollte den Frühlingsanfang auf den Stand des Konzils von Nicäa im Jahr 325 zurücksetzen, nicht auf den Stand zu Caesars Zeit. Zwischen 325 und 1582 waren etwa zehn Tage Abweichung aufgelaufen, genau die zehn gestrichenen Tage."],
["Antike Finsternisse passen","Überlieferte Sonnen- und Mondfinsternisse der Antike stimmen mit modernen astronomischen Rückrechnungen überein. Fehlten fast 300 Jahre, lägen sie um Jahrhunderte daneben."],
["Baumringe kennen keine Lücke","Lückenlose Jahrring-Chronologien wie die Hohenheimer Eichen- und Kiefernchronologie reichen über 12.000 Jahre zurück. Eine Lücke im Frühmittelalter gibt es darin nicht, und mit ihnen kalibrierte Radiokarbondaten passen dazu."],
["Die Welt außerhalb Europas","Die islamische Zeitrechnung beginnt mit der Hidschra 622, mitten in der angeblichen Phantomzeit. Die chinesische Tang-Dynastie (618 bis 907) ist durch eigene Chroniken belegt. All diese unabhängigen Überlieferungen hätten mitgefälscht werden müssen."]
],
sources:[
["Medien","Spektrum der Wissenschaft, Lexikon der Geowissenschaften: Kalenderreform.","https://www.spektrum.de/lexikon/geowissenschaften/kalenderreform/7935"],
["Medien","Encyclopaedia Britannica: Ten Days That Vanished. The Switch to the Gregorian Calendar.","https://britannica.com/story/ten-days-that-vanished-the-switch-to-the-gregorian-calendar"],
["Medien","taz: 300 Jahre erstunken und erlogen (zu Illigs Thesen).","https://taz.de/300-Jahre-erstunken-und-erlogen/!1493257/"],
["Studie","Friedrich, M. et al. (2004): The 12,460-year Hohenheim oak and pine tree-ring chronology from central Europe. Radiocarbon 46(3), S. 1111 bis 1122.","https://doi.org/10.1017/S003382220003304X"],
["Medien","Medievalists.net (2020): Why the Phantom Time Hypothesis is wrong.","https://www.medievalists.net/2020/04/why-phantom-time-hypothesis-wrong/"],
["Medien","Discover Magazine: What Is the Truth Behind the Controversial Phantom Time Hypothesis?","https://discovermagazine.com/the-sciences/what-is-the-truth-behind-the-controversial-phantom-time-hypothesis"],
["Medien","Saltzwedel, J. (2012): Gestrichene Jahrhunderte. Die abstruse These vom „erfundenen Mittelalter“. SPIEGEL Geschichte 6/2012.","https://www.spiegel.de/spiegel/spiegelgeschichte/d-89662035.html"]
],
quiz:[
["Welche Zeitspanne soll laut Heribert Illig erfunden sein?",["Etwa 614 bis 911 n. Chr.","Etwa 1200 bis 1500","Die gesamte Antike","1933 bis 1945"],"Illig behauptet, rund 297 Jahre des Frühmittelalters seien nachträglich in die Geschichte eingefügt worden."],
["Warum ließ Papst Gregor XIII. 1582 nur zehn Tage überspringen?",["Die Reform sollte den Stand des Konzils von Nicäa (325) wiederherstellen","Weil 297 Jahre fehlten","Weil Kaiser Otto III. es so verfügt hatte","Aus einem Rechenfehler"],"Bezugspunkt war das Konzil von Nicäa, nicht Caesars Zeit. Seit 325 waren genau etwa zehn Tage aufgelaufen."],
["Welches Ereignis, mit dem eine bis heute genutzte Zeitrechnung beginnt, fällt mitten in die angebliche Phantomzeit?",["Die Hidschra Mohammeds 622","Die Gründung Roms","Die Französische Revolution","Die Geburt Christi"],"Die islamische Zeitrechnung zählt ab 622. Sie hätte zusammen mit Chroniken aus China und Byzanz mitgefälscht werden müssen."]
]
},
{
id:"impf-autismus", cat:"gesundheit",
title:"Impfungen verursachen Autismus",
short:"Eine gefälschte Studie von 1998 wirkt bis heute nach. Millionen Kinder in großen Studien zeigen: kein Zusammenhang.",
tags:["Impfgegner","MMR","Masern","Wakefield","Aluminium","Thiomersal"],
claim:"Impfungen, vor allem die Kombinationsimpfung gegen Masern, Mumps und Röteln (MMR), oder Zusatzstoffe wie Aluminium und Quecksilberverbindungen lösten Autismus aus. Behörden und Pharmaindustrie würden das vertuschen.",
origin:[
"Ausgangspunkt war eine Studie des britischen Arztes Andrew Wakefield mit nur zwölf Kindern, 1998 in der Fachzeitschrift The Lancet erschienen. Der Journalist Brian Deer deckte später Datenmanipulation und Interessenkonflikte auf: Wakefield wurde unter anderem von Anwälten bezahlt, die gegen Impfstoffhersteller vorgehen wollten.",
"The Lancet zog die Studie 2010 zurück, Wakefield verlor im selben Jahr seine Zulassung als Arzt. Das British Medical Journal bezeichnete die Arbeit 2011 als Betrug. Die Angst vor der MMR-Impfung hält sich dennoch bis heute."
],
note:"Aktuell: Im November 2025 änderte die US-Gesundheitsbehörde CDC unter Gesundheitsminister Robert F. Kennedy Jr. ihre Webseite und bezeichnet die Aussage „Impfungen verursachen keinen Autismus“ dort nicht mehr als evidenzbasiert. Neue Studien lagen dieser Änderung nicht zugrunde. Die US-Kinderärztevereinigung AAP verweist auf mehr als 40 Studien mit über 5,6 Millionen Menschen, die keinen Zusammenhang zeigen.",
facts:[
["657.461 Kinder, kein erhöhtes Risiko","Eine landesweite dänische Kohortenstudie (Hviid et al. 2019) verfolgte 657.461 Kinder. Ergebnis: kein erhöhtes Autismusrisiko nach der MMR-Impfung (Hazard Ratio 0,93), auch nicht bei Kindern mit Risikofaktoren wie autistischen Geschwistern."],
["Über 1,2 Millionen Kinder in einer Metaanalyse","Eine Metaanalyse (Taylor et al. 2014) wertete Kohortenstudien mit 1.256.407 Kindern aus. Weder Impfungen allgemein noch MMR, Thiomersal oder Quecksilber waren mit Autismus verbunden."],
["Auch Aluminium entlastet","Eine Studie mit rund 1,2 Millionen dänischen Kindern (Andersson et al. 2025) fand keinen Zusammenhang zwischen der Aluminiummenge aus Impfstoffen und 50 chronischen Erkrankungen, darunter Autismus und ADHS."],
["Warum der Eindruck entsteht","Erste Anzeichen von Autismus fallen oft im zweiten Lebensjahr auf, also in dem Alter, in dem die MMR-Impfung gegeben wird (in Deutschland erste Dosis mit 11 Monaten). Zeitliche Nähe ist aber kein Beleg für eine Ursache."],
["Die realen Folgen","Nach der Wakefield-Studie sanken in mehreren Ländern die Impfquoten, Masern kehrten zurück. Weltweit verhinderte die Masernimpfung von 2000 bis 2023 schätzungsweise 60 Millionen Todesfälle."]
],
sources:[
["Studie","Hviid, A. et al. (2019): Measles, Mumps, Rubella Vaccination and Autism. A Nationwide Cohort Study. Annals of Internal Medicine 170(8), S. 513 bis 520.","https://pubmed.ncbi.nlm.nih.gov/30831578/"],
["Studie","Taylor, L. E., Swerdfeger, A. L., Eslick, G. D. (2014): Vaccines are not associated with autism. An evidence-based meta-analysis of case-control and cohort studies. Vaccine 32(29), S. 3623 bis 3629.","https://pubmed.ncbi.nlm.nih.gov/24814559/"],
["Studie","Andersson, N. W. et al. (2025): Aluminum-Adsorbed Vaccines and Chronic Diseases in Childhood. A Nationwide Cohort Study. Annals of Internal Medicine.","https://doi.org/10.7326/ANNALS-25-00997"],
["Studie","Godlee, F., Smith, J., Marcovitch, H. (2011): Wakefield’s article linking MMR vaccine and autism was fraudulent. BMJ 342, c7452.","https://doi.org/10.1136/bmj.c7452"],
["Behörde","CDC, MMWR (2024): Progress Toward Measles Elimination, Worldwide, 2000 bis 2023.","https://www.cdc.gov/mmwr/volumes/73/wr/mm7345a4.htm"],
["Medien","PBS NewsHour (2025): CDC vaccine safety webpage changed to contradict scientific conclusion that vaccines don’t cause autism.","https://www.pbs.org/newshour/health/cdc-vaccine-safety-webpage-changed-to-contradict-scientific-conclusion-that-vaccines-dont-cause-autism"],
["Medien","DER SPIEGEL: Zurückgezogene Studie: Das offizielle Ende eines Impf-Skandals.","https://www.spiegel.de/wissenschaft/medizin/0,1518,675592,00.html"],
["Medien","DER SPIEGEL: Forschungsskandal: Britischer Autismus-Arzt erhält Berufsverbot.","https://www.spiegel.de/wissenschaft/medizin/forschungsskandal-britischer-autismus-arzt-erhaelt-berufsverbot-a-696472.html"]
],
quiz:[
["Wie viele Kinder umfasste Wakefields Studie von 1998?",["12","1.200","657.461","50.000"],"Die Studie stützte sich auf nur zwölf Kinder, war manipuliert und wurde 2010 zurückgezogen."],
["Was ergab die dänische Studie mit 657.461 Kindern (2019)?",["Kein erhöhtes Autismusrisiko durch die MMR-Impfung","Ein doppelt so hohes Risiko","Ein leicht erhöhtes Risiko nur bei Jungen","Sie wurde wegen Fälschung zurückgezogen"],"Die Hazard Ratio lag bei 0,93, ein erhöhtes Risiko war nicht erkennbar, auch nicht in Risikogruppen."],
["Warum glauben manche Eltern an einen Zusammenhang?",["Erste Autismus-Anzeichen werden oft im selben Alter bemerkt, in dem geimpft wird","Weil Impfstoffe Autismus-Gene enthalten","Weil Ärztinnen und Ärzte es offiziell bestätigen","Weil es Autismus erst seit Einführung der Impfung gibt"],"Zwei Ereignisse im selben Lebensalter wirken leicht wie Ursache und Wirkung. Große Studien zeigen, dass kein solcher Zusammenhang besteht."]
]
},
{
id:"plandemie", cat:"gesundheit",
title:"Corona war harmlos oder geplant",
short:"„Nicht schlimmer als eine Grippe“ oder eine inszenierte „Plandemie“? Die Zahlen sind eindeutig, offen ist nur die Frage nach dem Ursprung.",
tags:["Plandemie","Covid","Corona","Event 201","Querdenken","Laborunfall","Grippe"],
claim:"COVID-19 sei nicht gefährlicher als eine Grippe gewesen, die Todeszahlen seien aufgebläht. Die Pandemie sei von Eliten wie Bill Gates oder dem Weltwirtschaftsforum geplant worden; als Beweis gilt die Pandemie-Übung „Event 201“ vom Oktober 2019.",
origin:[
"Das Video „Plandemic“ verbreitete sich im Mai 2020 millionenfach. In Deutschland trugen die Querdenken-Bewegung und zahlreiche Telegram-Kanäle die Erzählung auf die Straße.",
"Sie verband Kritik an Schutzmaßnahmen mit älteren Mythen über eine geheime Weltregierung und lief später in Erzählungen über Impfungen weiter."
],
kernel:"Über den Ursprung von SARS-CoV-2 wird ernsthaft gestritten, und manche Schutzmaßnahmen werden im Rückblick zu Recht kritisch bewertet. Daraus folgt aber weder, dass das Virus harmlos war, noch dass die Pandemie geplant wurde.",
facts:[
["Millionen Tote weltweit","Die Weltgesundheitsorganisation schätzt die Übersterblichkeit allein in den Jahren 2020 und 2021 auf rund 14,8 Millionen Menschen (Msemburi et al., Nature 2023)."],
["Deutschland: Tausende an, nicht nur mit Corona","Laut Todesursachenstatistik des Statistischen Bundesamts starben 2020 39.758 und 2021 71.331 Menschen an COVID-19 als Grundleiden. Zum Vergleich: Für die besonders schwere Grippewelle 2017/18 schätzte das Robert Koch-Institut rund 25.100 zusätzliche Todesfälle."],
["Event 201 war keine Prognose","Das Johns Hopkins Center for Health Security spielte im Oktober 2019 mit Weltwirtschaftsforum und Gates-Stiftung eine Pandemie mit einem fiktiven Virus durch. Die Veranstalter stellten klar, dass sie keine Vorhersage getroffen haben. Solche Übungen gab es schon lange vorher, etwa „Dark Winter“ (2001) oder „Clade X“ (2018)."],
["Ursprung offen, Plan nicht belegt","Das Beratergremium SAGO der WHO hält eine Übertragung vom Tier auf den Menschen für am besten belegt, kann einen Laborunfall aber mangels Daten aus China nicht ausschließen (Juni 2025). Der Bundesnachrichtendienst kam schon 2020 auf Basis von Indizien zu der Einschätzung, ein Laborunfall sei zu 80 bis 95 Prozent wahrscheinlich (bekannt seit März 2025). Beide Szenarien beschreiben ein Unglück, keine geplante Pandemie."]
],
sources:[
["Primärquelle","Johns Hopkins Center for Health Security: Übersicht der Pandemie-Übungen (Dark Winter, Clade X, Event 201).","https://www.centerforhealthsecurity.org/our-work/exercises"],
["Medien","CBS News (2020): Viral coronavirus conspiracy video „Plandemic“ removed from Facebook and YouTube.","https://www.cbsnews.com/news/plandemic-coronavirus-conspiracy-removed-facebook-youtube"],
["Medien","Pharmazeutische Zeitung: Vorletzte Grippewelle war tödlichste in 30 Jahren (RKI-Schätzung 25.100).","https://www.pharmazeutische-zeitung.de/vorletzte-grippewelle-war-toedlichste-in-30-jahren/"],
["Studie","Msemburi, W. et al. (2023): The WHO estimates of excess mortality associated with the COVID-19 pandemic. Nature 613, S. 130 bis 137.","https://doi.org/10.1038/s41586-022-05522-2"],
["Behörde","Statistisches Bundesamt (2021): Pressemitteilung zur Todesursachenstatistik 2020.","https://www.destatis.de/DE/Presse/Pressemitteilungen/2021/12/PD21_563_12.html"],
["Behörde","WHO (27. Juni 2025): WHO Scientific Advisory Group issues report on origins of COVID-19.","https://www.who.int/news/item/27-06-2025-who-scientific-advisory-group-issues-report-on-origins-of-covid-19"],
["Faktencheck","Full Fact: Event 201 didn’t predict the Covid-19 pandemic.","https://fullfact.org/health/event-201-coronavirus-pandemic/"],
["Medien","ZDF (ZDFinfo): Verschwörungswelten. Plandemie, The Great Reset und QAnon.","https://www.zdf.de/dokus/verschwoerungswelten-100"],
["Medien","DER SPIEGEL: Coronavirus-Verschwörungstheorien: Die Gerüchte-Pandemie.","https://www.spiegel.de/wissenschaft/medizin/coronavirus-verschwoerungstheorien-die-geruechte-pandemie-a-0e7d1ffb-9aa8-49c7-a0b4-5fb8fd7db593"],
["Medien","tagesschau.de Faktenfinder: Gerüchte und Fakes: Coronavirus als angebliche Verschwörung.","https://www.tagesschau.de/faktenfinder/fakes-geruechte-coronavirus-101.html"]
],
quiz:[
["Wie hoch schätzt die WHO die weltweite Übersterblichkeit in den Jahren 2020 und 2021?",["Rund 14,8 Millionen Menschen","Rund 150.000 Menschen","Rund 1,5 Millionen Menschen","Rund 150 Millionen Menschen"],"Die WHO-Schätzung von rund 14,8 Millionen umfasst auch Todesfälle, die in offiziellen COVID-Statistiken fehlten."],
["Was war „Event 201“?",["Eine Planspiel-Übung mit einem fiktiven Virus","Ein geheimes Treffen zur Planung der Pandemie","Ein Patent auf das Coronavirus","Eine WHO-Notfallsitzung im Januar 2020"],"Pandemie-Planspiele gehören seit Jahrzehnten zur Gesundheitsvorsorge. Event 201 verwendete ein erfundenes Virus mit anderen Eigenschaften."],
["Was sagt das WHO-Gremium SAGO 2025 zum Ursprung von SARS-CoV-2?",["Eine Übertragung vom Tier ist am besten belegt, ein Laborunfall ist aber nicht ausgeschlossen","Die Pandemie wurde nachweislich geplant","Das Virus stammt sicher aus einem US-Labor","Das Virus existiert nicht"],"Die Ursprungsfrage ist wissenschaftlich offen. Keines der ernsthaft diskutierten Szenarien spricht für eine absichtlich geplante Pandemie."]
]
},
{
id:"corona-impfung", cat:"gesundheit",
title:"Die Corona-Impfung tötet massenhaft",
short:"„Plötzlich und unerwartet“, „Turbokrebs“, Massensterben: Was Milliarden Impfdosen zeigen, inklusive der echten, seltenen Nebenwirkungen.",
tags:["mRNA","Impfschaden","plötzlich und unerwartet","Turbokrebs","Died Suddenly","Myokarditis","Biontech"],
claim:"Die mRNA-Impfstoffe seien nicht ausreichend getestet und lösten massenhaft plötzliche Todesfälle, Herzprobleme und aggressiven „Turbokrebs“ aus. Die Impfkampagne sei in Wahrheit ein Programm zur Bevölkerungsreduktion.",
origin:[
"Ab 2021 sammelten Telegram-Kanäle Todesanzeigen mit dem Zusatz „plötzlich und unerwartet“ und deuteten sie als Impffolgen, obwohl diese Formulierung seit Jahrzehnten üblich ist.",
"Der US-Film „Died Suddenly“ (2022) verbreitete die Erzählung international. Die Nachrichtenagentur AP und andere zeigten, dass er Todesfälle präsentierte, die zum Teil vor der Pandemie lagen oder Ungeimpfte betrafen."
],
kernel:"Wie jedes wirksame Medikament haben auch COVID-19-Impfstoffe Nebenwirkungen, darunter sehr seltene schwere wie Herzmuskelentzündungen. Diese wurden erkannt, öffentlich gemacht und führten zu angepassten Empfehlungen. Genau das zeigt, dass die Überwachung funktioniert.",
facts:[
["Groß angelegt getestet","Die Zulassungsstudie des Impfstoffs von BioNTech und Pfizer umfasste rund 43.500 Teilnehmende und zeigte eine Wirksamkeit von 95 Prozent gegen symptomatische Erkrankung (Polack et al. 2020)."],
["Millionen Leben gerettet","Einer Modellstudie zufolge verhinderten die Impfungen im ersten Jahr der Impfkampagne weltweit schätzungsweise 14,4 Millionen Todesfälle, auf Basis der Übersterblichkeit sogar 19,8 Millionen (Watson et al. 2022)."],
["Echte Nebenwirkungen werden erfasst","Herzmuskelentzündungen treten selten auf, vor allem bei jungen Männern nach der zweiten Dosis. Das Paul-Ehrlich-Institut registrierte bei 18- bis 29-jährigen Männern rund 9 Verdachtsfälle pro 100.000 Dosen von Comirnaty und über 25 bei Spikevax. Die Ständige Impfkommission empfahl deshalb ab November 2021 für unter 30-Jährige nur noch Comirnaty."],
["Kein Mechanismus für „Turbokrebs“","Für einen durch mRNA-Impfstoffe ausgelösten „Turbokrebs“ gibt es weder Belege noch einen plausiblen Mechanismus; den Begriff kennt die Medizin nicht. Impfstoff-mRNA gelangt nicht in den Zellkern und wird im Körper innerhalb von Tagen abgebaut. Das Erbgut kann sie nicht verändern."],
["„Plötzlich und unerwartet“ gab es immer","Am plötzlichen Herztod sterben in Deutschland nach Angaben der Deutschen Herzstiftung jedes Jahr rund 65.000 Menschen. Die Formulierung in Todesanzeigen ist kein Indiz für eine bestimmte Ursache."]
],
sources:[
["Medien","Pharmazeutische Zeitung (2021): STIKO empfiehlt kein Moderna mehr für unter 30-Jährige.","https://www.pharmazeutische-zeitung.de/stiko-empfiehlt-kein-moderna-mehr-fuer-unter-30-jaehrige-129343/"],
["Faktencheck","Correctiv (2021): Es gibt keine Hinweise, dass mRNA-Impfstoffe die menschliche DNA verändern.","https://correctiv.org/faktencheck/2021/01/20/es-gibt-keine-hinweise-dass-mrna-impfstoffe-gegen-covid-19-die-menschliche-dna-veraendern/"],
["Studie","Polack, F. P. et al. (2020): Safety and Efficacy of the BNT162b2 mRNA Covid-19 Vaccine. New England Journal of Medicine 383, S. 2603 bis 2615.","https://pubmed.ncbi.nlm.nih.gov/33301246/"],
["Studie","Watson, O. J. et al. (2022): Global impact of the first year of COVID-19 vaccination. A mathematical modelling study. The Lancet Infectious Diseases 22(9), S. 1293 bis 1302.","https://pubmed.ncbi.nlm.nih.gov/35753318/"],
["Behörde","Arzneimittelkommission der deutschen Ärzteschaft: Drug Safety Mail 2021-57 zu Myokarditis nach mRNA-Impfung.","https://www.akdae.de/arzneimittelsicherheit/drug-safety-mail/newsdetail/drug-safety-mail-2021-57"],
["Faktencheck","AP (2023, via KSL): „Died suddenly“ posts twist tragedies to push vaccine lies.","https://www.ksl.com/article/50572002"],
["Medien","tagesschau.de Faktenfinder: Gezielte Panikmache mit „Impfmassaker“.","https://www.tagesschau.de/faktenfinder/impfungen-todesfaelle-101.html"],
["Medien","tagesschau.de Faktenfinder: Kein Nachweis für vermehrte Impfnebenwirkungen.","https://www.tagesschau.de/faktenfinder/corona-impfnebenwirkungen-101.html"]
],
quiz:[
["Welche seltene Nebenwirkung von mRNA-Impfstoffen ist belegt?",["Herzmuskelentzündung, vor allem bei jungen Männern","„Turbokrebs“","Eine Veränderung des Erbguts","Unfruchtbarkeit bei allen Geimpften"],"Myokarditis ist eine bekannte, seltene Nebenwirkung. Die Behörden reagierten mit angepassten Empfehlungen für junge Menschen."],
["Wie viele Todesfälle verhinderten die COVID-19-Impfungen im ersten Jahr laut Watson et al. (2022) schätzungsweise?",["Rund 14,4 Millionen","Rund 14.000","Keine","Rund eine Milliarde"],"Auf Basis gemeldeter Todesfälle kommt die Studie auf 14,4 Millionen, auf Basis der Übersterblichkeit auf 19,8 Millionen verhinderte Todesfälle."],
["Warum ist „plötzlich und unerwartet“ in Todesanzeigen kein Beleg für Impfschäden?",["Die Formulierung ist seit Jahrzehnten üblich, plötzliche Todesfälle gab es immer","Weil sie nur bei Ungeimpften verwendet wird","Weil Zeitungen sie seit 2021 verbieten","Weil sie erst seit 2021 existiert"],"Allein am plötzlichen Herztod sterben in Deutschland jährlich rund 65.000 Menschen. Das Sammeln von Anzeigen beweist nichts über Ursachen."]
]
},
{
id:"gates-chip", cat:"gesundheit",
title:"Bill Gates will uns chippen und dezimieren",
short:"Mikrochips in Impfstoffen und ein Plan zur Bevölkerungsreduktion: Wie aus Zitaten und Forschungsprojekten ein Mythos wurde.",
tags:["Bill Gates","Mikrochip","Bevölkerungsreduktion","Gates-Stiftung","Überwachung","666"],
claim:"Bill Gates wolle mit Impfungen Mikrochips zur Überwachung einpflanzen und die Weltbevölkerung gezielt reduzieren. Er habe das in einem Vortrag sogar selbst zugegeben.",
origin:[
"Gates finanziert über seine Stiftung seit Jahrzehnten Impfprogramme und warnte 2015 öffentlich vor Pandemien. Das machte ihn 2020 zur Zielscheibe.",
"In einer Umfrage von Yahoo News und YouGov im Mai 2020 hielten 44 Prozent der befragten Anhänger der US-Republikaner die Chip-Geschichte für wahr."
],
facts:[
["Das Zitat im Zusammenhang","In einem TED-Vortrag über CO₂-Emissionen sagte Gates 2010, mit sehr guter Arbeit bei Impfstoffen, Gesundheitsversorgung und reproduktiver Gesundheit ließe sich das Bevölkerungswachstum um „vielleicht 10 oder 15 Prozent“ senken. Gemeint ist ein bekannter Effekt: Wenn weniger Kinder sterben, bekommen Familien weniger Kinder. Es geht um langsameres Wachstum, nicht um Tote."],
["Tinte statt Chip","Mit Geld der Gates-Stiftung entwickelten Forschende einen unsichtbaren Farbstoff aus Quantenpunkten, der per Mikronadel-Pflaster unter die Haut gebracht wird und einen Impfnachweis speichern kann (McHugh et al. 2019). Er ist nur mit einer angepassten Smartphone-Kamera aus nächster Nähe lesbar, sendet nichts, kann nicht orten, wurde an Ratten und isolierter Haut getestet und war nie Teil eines COVID-19-Impfstoffs."],
["Die Physik spricht dagegen","Ein Ortungschip bräuchte eine Stromquelle, eine Antenne und eine Funkverbindung. Nichts davon passt unbemerkt durch die feine Kanüle einer Impfspritze, und ein Funksender ohne Energiequelle kann nichts senden."],
["Die „666“-Patentnummer","Eine Microsoft-Patentanmeldung zu einem Kryptowährungssystem trägt die fortlaufende Nummer WO2020060606. Die Ziffernfolge ist Zufall der Nummerierung und hat mit Impfstoffen nichts zu tun."],
["Was tatsächlich finanziert wird","Die Gates-Stiftung ist Gründungspartner der Impfallianz Gavi, die nach eigenen Angaben dazu beigetragen hat, seit 2000 mehr als eine Milliarde Kinder zu impfen."]
],
sources:[
["Faktencheck","Snopes: Did Bill Gates say vaccines could reduce population? (Wortlaut und Kontext des TED-Zitats).","https://www.snopes.com/bill-gates-vaccinations-depopulation/"],
["Faktencheck","Snopes: Does Microsoft Own Patent „666“ About Implanting Microchips in People?","https://www.snopes.com/fact-check/microsoft-own-patent-666"],
["Primärquelle","Gavi (2023): Vaccine Alliance reaches more than one billion children.","https://www.gavi.org/news/media-room/vaccine-alliance-reaches-more-one-billion-children"],
["Studie","McHugh, K. J. et al. (2019): Biocompatible near-infrared quantum dots delivered to the skin by microneedle patches record vaccination. Science Translational Medicine 11(523), eaay7162.","https://pubmed.ncbi.nlm.nih.gov/31852802/"],
["Medien","Rice University (2019): Quantum-dot tattoos hold vaccination record.","https://news.rice.edu/news/2019/quantum-dot-tattoos-hold-vaccination-record"],
["Faktencheck","PolitiFact (2021): Bill Gates didn’t say he wanted to use vaccines to reduce the population.","https://politifact.com/factchecks/2021/oct/11/blog-posting/bill-gates-didnt-say-he-wanted-use-vaccines-reduce/"],
["Medien","Yahoo News (2020): New Yahoo News/YouGov poll shows coronavirus conspiracy theories spreading on the right.","https://news.yahoo.com/new-yahoo-news-you-gov-poll-shows-coronavirus-conspiracy-theories-spreading-on-the-right-may-hamper-vaccine-efforts-152843610.html"],
["Medien","tagesschau.de Faktenfinder: Mythen zum Coronavirus: Gates als globales Feindbild.","https://www.tagesschau.de/faktenfinder/feindbild-gates-101.html"],
["Medien","FOCUS Online: Arm nach Covid-19-Impfung magnetisch? Nein, wir bekommen keine Mikrochips eingesetzt.","https://www.focus.de/gesundheit/news/vermeintlicher-beweis-fuer-mikrochip-theorie-einstichstelle-nach-impfung-magnetisch-experte-erklaert-das-netz-phaenomen_id_13335189.html"]
],
quiz:[
["Was meinte Gates 2010 mit „vielleicht 10 oder 15 Prozent senken“?",["Ein geringeres Bevölkerungswachstum, weil bei sinkender Kindersterblichkeit weniger Kinder geboren werden","Die Tötung von 15 Prozent der Menschheit","Weniger Impfungen in armen Ländern","Eine Steuer auf Kinder"],"Der demografische Zusammenhang ist gut belegt: Wo Kinder überleben, sinken die Geburtenraten. Das Wachstum verlangsamt sich, ohne dass jemand stirbt."],
["Was entwickelten Forschende 2019 mit Förderung der Gates-Stiftung tatsächlich?",["Einen unsichtbaren Farbstoff unter der Haut, der einen Impfnachweis speichert","Einen GPS-Chip im Impfstoff","Einen 5G-Empfänger","Ein Gerät zum Gedankenlesen"],"Der Farbstoff aus Quantenpunkten sendet keine Daten und kann nicht orten. Er wurde nie in einem COVID-19-Impfstoff eingesetzt."],
["Warum lässt sich kein Ortungschip unbemerkt mit einer Impfung injizieren?",["Er bräuchte Stromquelle, Antenne und Funkverbindung, die nicht durch eine dünne Kanüle passen","Weil Chips im Kühlschrank kaputtgehen","Weil die WHO es verboten hat","Weil Chips zu teuer sind"],"Ortung erfordert Energie und eine Funkverbindung zu einem Empfänger. Das ist mit einem Partikel in einer Impfkanüle physikalisch nicht machbar."]
]
},
{
id:"ivermectin", cat:"gesundheit",
title:"Ivermectin heilt Corona, wird aber unterdrückt",
short:"Ein Wurmmittel als verschwiegenes Wundermittel? Große, sorgfältige Studien haben es gründlich geprüft.",
tags:["Ivermectin","Wurmmittel","Pharma","Corona","Therapie"],
claim:"Das preiswerte Antiparasitikum Ivermectin heile COVID-19 zuverlässig. Pharmaindustrie und Behörden unterdrückten das Mittel, weil sich mit billigen Medikamenten kein Geld verdienen lasse.",
origin:[
"Den Anstoß gab eine australische Laborstudie von 2020 (Caly et al.): Ivermectin hemmte das Virus in Zellkulturen. Kleine, teils fehlerhafte Studien schienen eine Wirkung zu bestätigen. Eine vielzitierte ägyptische Studie zog der Preprint-Server Research Square im Juli 2021 wegen ethischer Bedenken zurück, nachdem Plagiate und Auffälligkeiten in den Daten aufgefallen waren.",
"In sozialen Netzwerken und bei einigen Ärztinnen und Ärzten wurde Ivermectin zum Symbol des Widerstands gegen „das System“."
],
facts:[
["Die Laborkonzentration ist unerreichbar","Die Wirkung in der Zellkultur trat bei Konzentrationen auf, die mit zugelassenen Dosen im menschlichen Blut nicht annähernd erreicht werden, je nach Berechnung um ein Vielfaches nicht."],
["TOGETHER-Studie","In einer randomisierten, placebokontrollierten Studie mit 1.358 Patientinnen und Patienten in Brasilien senkte Ivermectin das Risiko für einen Krankenhausaufenthalt nicht (Reis et al. 2022)."],
["ACTIV-6-Studie","In der US-Studie ACTIV-6 mit 1.591 ausgewerteten Teilnehmenden führte Ivermectin nicht zu einer schnelleren Genesung (Naggie et al. 2022). Auch eine höhere Dosis brachte in einer Folgeauswertung keinen Nutzen."],
["Warum kleine Studien täuschten","Kleine Studien ohne Placebogruppe sind anfällig für Zufallsbefunde. Zudem fanden Forschende, dass positive Effekte vor allem aus Regionen stammten, in denen viele Menschen mit Zwergfadenwürmern infiziert sind. Ivermectin bekämpft diese Würmer, die bei Kortisonbehandlung gefährlich werden können; ein Nutzen gegen das Coronavirus selbst folgt daraus nicht."],
["Billige Mittel werden sehr wohl empfohlen","Das alte, günstige Kortisonpräparat Dexamethason wurde 2020 umgehend in Behandlungsleitlinien aufgenommen, nachdem die große RECOVERY-Studie gezeigt hatte, dass es die Sterblichkeit beatmeter Patientinnen und Patienten um etwa ein Drittel senkt."]
],
sources:[
["Studie","Bitterman, A. et al. (2022): Comparison of Trials Using Ivermectin for COVID-19 Between Regions With High and Low Prevalence of Strongyloidiasis. JAMA Network Open.","https://pmc.ncbi.nlm.nih.gov/articles/PMC8938718"],
["Medien","Pharmazeutische Zeitung: Was der Zwergfadenwurm mit Corona zu tun hat.","https://www.pharmazeutische-zeitung.de/was-der-zwergfadenwurm-mit-corona-zu-tun-hat-132165/"],
["Studie","Reis, G. et al. (2022): Effect of Early Treatment with Ivermectin among Patients with Covid-19. New England Journal of Medicine 386, S. 1721 bis 1731.","https://doi.org/10.1056/NEJMoa2115869"],
["Medien","Deutsches Ärzteblatt (2022): COVID-19: Ivermectin bleibt auch in US-Studie ohne relevante Wirkung.","https://www.aerzteblatt.de/nachrichten/135034/COVID-19-Ivermectin-bleibt-auch-in-US-Studie-ohne-relevante-Wirkung"],
["Studie","Caly, L. et al. (2020): The FDA-approved drug ivermectin inhibits the replication of SARS-CoV-2 in vitro. Antiviral Research 178, 104787.","https://pmc.ncbi.nlm.nih.gov/articles/7129059"],
["Studie","RECOVERY Collaborative Group (2021): Dexamethasone in Hospitalized Patients with Covid-19. New England Journal of Medicine 384, S. 693 bis 704.","https://pmc.ncbi.nlm.nih.gov/articles/PMC7383595/"],
["Medien","DER SPIEGEL: Entwurmungsmittel in Österreich ausverkauft, weil FPÖ-Chef es bei Corona empfiehlt.","https://www.spiegel.de/wirtschaft/unternehmen/ivomectin-entwurmungsmittel-in-oesterreich-ausverkauft-weil-fpoe-chef-es-bei-corona-empfiehlt-a-42689153-8d8b-4e52-bab1-e86a293fd1b8"]
],
quiz:[
["Warum war die Laborwirkung von Ivermectin kein Beleg für eine Therapie?",["Die nötige Konzentration ist im menschlichen Blut mit zugelassenen Dosen nicht erreichbar","Weil Labore keine Viren untersuchen dürfen","Weil die Zellen von Tieren stammten","Weil die Studie geheim gehalten wurde"],"Was in der Petrischale wirkt, muss im Körper erreichbar sein. Bei Ivermectin lag die wirksame Konzentration weit über dem, was Menschen sicher erreichen."],
["Was zeigte die große TOGETHER-Studie mit 1.358 Patientinnen und Patienten?",["Keine Senkung des Risikos für Krankenhausaufenthalte","Eine Heilungsrate von 100 Prozent","Schwere Nebenwirkungen bei allen Teilnehmenden","Sie wurde von Behörden verboten"],"Randomisierte, placebokontrollierte Studien sind der Goldstandard. Mehrere davon fanden keinen relevanten Nutzen."],
["Welches günstige, alte Medikament wurde 2020 gegen schweres COVID-19 empfohlen, weil es in einer großen Studie wirkte?",["Dexamethason","Ivermectin","Hydroxychloroquin","Chlordioxid"],"Dexamethason ist billig und seit Jahrzehnten patentfrei. Es wurde trotzdem sofort empfohlen, weil die Daten überzeugten."]
]
},
{
id:"viren", cat:"gesundheit",
title:"Viren gibt es gar nicht",
short:"Der Masern-Prozess um 100.000 Euro wird bis heute falsch erzählt. Kein Gericht hat entschieden, dass es keine Viren gibt.",
tags:["Lanka","Masern","Virusleugnung","BGH","Terraintheorie","Bardens"],
claim:"Krankmachende Viren seien nie nachgewiesen worden; Krankheiten entstünden durch Gifte, Lebensumstände oder seelische Ursachen. Der Bundesgerichtshof habe sogar bestätigt, dass es das Masernvirus nicht gebe.",
origin:[
"In Deutschland prägt vor allem der Biologe Stefan Lanka diese Idee. 2011 lobte er 100.000 Euro für den Nachweis des Masernvirus in einer wissenschaftlichen Publikation aus. Der Arzt David Bardens legte sechs Fachartikel vor und klagte.",
"Das Landgericht Ravensburg gab Bardens 2015 recht. Das Oberlandesgericht Stuttgart hob das Urteil 2016 auf, weil Lanka einen Nachweis in einer einzigen Publikation verlangt hatte, nicht in mehreren. Der Bundesgerichtshof wies die Beschwerde dagegen ab (Az. I ZR 62/16), ohne selbst in der Sache zu entscheiden."
],
facts:[
["Ein Streit um Formulierungen","Das Oberlandesgericht entschied ausschließlich über die Bedingungen der Auslobung. Über die Existenz des Masernvirus hat kein Gericht geurteilt."],
["Seit 1954 im Labor gezüchtet","John Enders und Thomas Peebles züchteten das Masernvirus 1954 in Zellkultur. Daraus entstand der erste Masernimpfstoff, der 1963 zugelassen wurde."],
["Sichtbar und vermessen","Mit dem Elektronenmikroskop wurden Viren schon Ende der 1930er-Jahre sichtbar gemacht, zuerst das Tabakmosaikvirus. Heute bestimmen Forschende ihre Struktur bis auf atomare Ebene, etwa das Spike-Protein von SARS-CoV-2 (Wrapp et al. 2020), und entschlüsseln ihr Erbgut durch Sequenzierung."],
["Impfungen beweisen die Wirkung","Ein Impfstoff, der gezielt gegen ein Virus gerichtet ist, könnte nicht wirken, wenn es das Virus nicht gäbe. Die Zahl der Masern-Todesfälle sank weltweit von geschätzt 800.000 im Jahr 2000 auf rund 107.500 im Jahr 2023; die Impfung verhinderte in diesem Zeitraum schätzungsweise 60 Millionen Todesfälle."]
],
sources:[
["Medien","Tagesspiegel: Das Virus gibt es gar nicht? Verschwörungstheorien verbreiten sich schnell und können tödliche Konsequenzen haben.","https://tagesspiegel.de/gesellschaft/das-virus-gibt-es-gar-nicht-verschwoerungstheorien-verbreiten-sich-schnell-und-koennen-toedliche-konsequenzen-haben/25632922.html"],
["Faktencheck","Correctiv (2019): Nein, dieses Gerichtsurteil beweist nicht, dass das Masern-Virus nicht existiert.","https://correctiv.org/faktencheck/medizin-und-gesundheit/2019/11/25/nein-dieses-gerichtsurteil-beweist-nicht-dass-das-masern-virus-nicht-existiert/"],
["Medien","Legal Tribune Online: Streit um die Existenz des Masernvirus vor dem BGH.","https://www.lto.de/recht/nachrichten/n/streit-existenz-masern-virus-nichtzulassungsbeschwerde-bgh-auslobung-wette"],
["Behörde","CDC, MMWR (2024): Progress Toward Measles Elimination, Worldwide, 2000 bis 2023.","https://www.cdc.gov/mmwr/volumes/73/wr/mm7345a4.htm"],
["Studie","Wrapp, D. et al. (2020): Cryo-EM structure of the 2019-nCoV spike in the prefusion conformation. Science 367, S. 1260 bis 1263.","https://pmc.ncbi.nlm.nih.gov/articles/7164637"],
["Studie","Enders, J. F., Peebles, T. C. (1954): Propagation in tissue cultures of cytopathogenic agents from patients with measles. Proceedings of the Society for Experimental Biology and Medicine 86(2), S. 277 bis 286.","https://pubmed.ncbi.nlm.nih.gov/13177653/"],
["Medien","DER SPIEGEL: Posse um Masernvirus: Impfgegner muss Arzt 100.000 Euro zahlen (Urteil des Landgerichts).","https://www.spiegel.de/gesundheit/diagnose/existenz-des-masernvirus-stefan-lanka-verliert-vor-gericht-a-1023189.html"],
["Medien","DER SPIEGEL: Streit um Existenz von Masernviren: Impfgegner siegt vor Gericht (Berufung zu den Bedingungen der Auslobung).","https://www.spiegel.de/panorama/justiz/masern-wette-impfgegner-muss-nicht-zahlen-a-1077601.html"]
],
quiz:[
["Worüber entschied das Oberlandesgericht Stuttgart im Masern-Prozess 2016?",["Über die Bedingungen der Auslobung: Lanka hatte eine einzige Publikation als Nachweis verlangt","Dass es das Masernvirus nicht gibt","Dass Masernimpfungen verboten werden","Dass Lanka 100.000 Euro zahlen muss"],"Es ging um Vertragsrecht, nicht um Biologie. Wissenschaftliche Fragen klären Gerichte ohnehin nicht."],
["Wann wurde das Masernvirus erstmals in Zellkultur gezüchtet?",["1954","2011","1890","Nie"],"John Enders und Thomas Peebles gelang das 1954; Enders hatte zuvor schon für die Kultivierung des Poliovirus den Nobelpreis erhalten."],
["Wie viele Masern-Todesfälle verhinderte die Impfung laut Schätzung von 2000 bis 2023?",["Rund 60 Millionen","Rund 6.000","Keine","Rund 600"],"Die gemeinsame Schätzung von WHO und CDC liegt bei rund 60,3 Millionen verhinderten Todesfällen."]
]
},
{
id:"krebs", cat:"gesundheit",
title:"Die Krebsheilung wird verheimlicht",
short:"Pharmakonzerne sollen das Heilmittel unterdrücken, Krebs sei ein seelischer Konflikt. Beides kostet Menschenleben.",
tags:["Krebs","Pharma","Germanische Neue Medizin","Hamer","Alternativmedizin","Chemotherapie"],
claim:"Es gebe längst eine einfache Heilung gegen Krebs, etwa durch Vitamine, Natron oder Aprikosenkerne, doch Pharmakonzerne verdienten an der Chemotherapie und hielten sie geheim. Nach der „Germanischen Neuen Medizin“ entstehe Krebs durch seelische Konflikte und heile von selbst, sobald der Konflikt gelöst sei.",
origin:[
"Die „Germanische Neue Medizin“ geht auf den Arzt Ryke Geerd Hamer zurück, der 1986 seine Approbation verlor und unter anderem in Deutschland, Österreich und Frankreich zu Haftstrafen verurteilt wurde. Seine Lehre ist mit antisemitischen Verschwörungsmythen durchsetzt; die Schulmedizin bezeichnete er als „jüdische Medizin“. Hamer starb am 2. Juli 2017 in Norwegen.",
"Bekannt wurde 1995 der Fall der sechsjährigen Olivia Pilhar aus Österreich. Sie hatte einen Wilms-Tumor, einen bösartigen Nierentumor, der bei rechtzeitiger Behandlung zu rund 90 Prozent heilbar ist. Ihre Eltern lehnten nach Hamers Lehre Chemotherapie und Operation ab, worauf ihnen das Sorgerecht für ihre Tochter entzogen wurde. Erst die so durchgesetzte Chemotherapie rettete ihr Leben; die Eltern wurden 1997 wegen fahrlässiger Körperverletzung verurteilt."
],
facts:[
["Krebs ist nicht eine Krankheit","Unter „Krebs“ fasst man Hunderte verschiedene Erkrankungen mit unterschiedlichen Ursachen, Mutationen und Verläufen zusammen; die Deutsche Krebshilfe spricht von mehr als 300 bekannten Krebsarten. Schon deshalb kann es nicht die eine Pille gegen Krebs geben."],
["Fortschritt ist messbar","In den USA sank die Krebssterberate von 1991 bis 2022 um 34 Prozent; dadurch wurden schätzungsweise 4,5 Millionen Todesfälle verhindert (American Cancer Society 2025)."],
["Viele Krebsarten sind heilbar","Von Kindern mit akuter lymphatischer Leukämie überleben in Ländern mit guter Versorgung heute rund 90 Prozent langfristig. Bei Hodenkrebs liegen die Heilungschancen bei früher Erkennung bei über 90 Prozent."],
["Ein Geheimnis ließe sich nicht halten","Krebsforschung findet weltweit an Universitäten, in Kliniken und in konkurrierenden Firmen und Staaten statt. Wer ein einfaches Heilmittel fände, gewänne Nobelpreis und Milliardenmarkt. Der Physiker David Robert Grimes schätzte, eine Unterdrückung würde mehr als 700.000 Mitwisser erfordern."],
["Alternativmedizin kostet Leben","Eine Studie mit Krebspatientinnen und Krebspatienten in den USA ergab: Wer ausschließlich auf alternative Medizin setzte, hatte ein etwa 2,5-fach erhöhtes Sterberisiko (Johnson et al. 2018)."]
],
sources:[
["Medien","Der Standard (2017): Wunderheiler Ryke Geerd Hamer ist tot (mit Fall Olivia).","https://www.derstandard.at/2000060791912/wunderheiler-ryke-geerd-hamer-ist-tot"],
["Medien","ORF Wien: „Goldenes Brett“ geht an „germanischen“ Arzt.","https://wien.orf.at/v2/news/stories/2801420/"],
["Medien","Deutsches Ärzteblatt: Leukämie, Überlebensrate bei Kindern weiter gestiegen.","https://www.aerzteblatt.de/themen/leukaemie/leukaemie-ueberlebensrate-bei-kindern-weiter-gestiegen-1a02a939-6d04-44c8-89e2-186b41e73621"],
["Medien","Apotheke Adhoc: Krebshilfe im Kampf gegen Krebs (mehr als 300 Krebsarten).","https://www.apotheke-adhoc.de/nachrichten/detail/pharmazie/krebshilfe-im-kampf-gegen-krebs/"],
["Studie","Siegel, R. L. et al. (2025): Cancer statistics, 2025. CA: A Cancer Journal for Clinicians 75(1).","https://doi.org/10.3322/caac.21871"],
["Studie","Johnson, S. B. et al. (2018): Use of Alternative Medicine for Cancer and Its Impact on Survival. Journal of the National Cancer Institute 110(1), S. 121 bis 124.","https://academic.oup.com/jnci/article/110/1/121/4064136"],
["Medien","Apotheken Umschau: Pseudomedizin mit tödlichen Folgen. Was hinter der Germanischen Neuen Medizin steckt.","https://www.apotheken-umschau.de/therapie/germanische-neue-medizin-lebensgefaehrliche-pseudomedizin-und-ihre-folgen-1251777.html"],
["Medien","Deutsches Ärzteblatt (2017): Krebsheiler will Approbation zurück, Gericht lehnt ab.","https://www.aerzteblatt.de/nachrichten/73179/Krebsheiler-will-Approbation-zurueck-Gericht-lehnt-ab"],
["Studie","Grimes, D. R. (2016): On the Viability of Conspiratorial Beliefs. PLOS ONE 11(1), e0147905.","https://doi.org/10.1371/journal.pone.0147905"],
["Medien","tagesschau.de (BR-Recherche): „Germanische Neue Medizin“: Gefährlicher Medizin-Mythos breitet sich aus.","https://www.tagesschau.de/investigativ/br-recherche/pseudomedizin-hamer-100.html"],
["Medien","DER SPIEGEL (1995): Kampf gegen die Stärksten (zum Fall Olivia Pilhar).","https://www.spiegel.de/wissenschaft/kampf-gegen-die-staerksten-a-4cc989f4-0002-0001-0000-000009208312"]
],
quiz:[
["Warum gibt es nicht „die eine“ Krebsheilung?",["Weil Krebs Hunderte verschiedene Erkrankungen mit unterschiedlichen Ursachen umfasst","Weil die Pharmaindustrie sie versteckt","Weil Krebs ansteckend ist","Weil Krebsforschung verboten ist"],"Leukämie, Melanom und Darmkrebs unterscheiden sich in Ursachen und Biologie grundlegend und brauchen unterschiedliche Therapien."],
["Wie stark erhöhte die ausschließliche Nutzung alternativer Medizin das Sterberisiko in einer Studie von 2018?",["Etwa um das 2,5-Fache","Gar nicht","Das Risiko halbierte sich","Um ein Prozent"],"Patientinnen und Patienten, die auf wirksame Therapien verzichteten, starben deutlich häufiger."],
["Was rettete der kleinen Olivia Pilhar 1995 das Leben?",["Eine gerichtlich durchgesetzte Chemotherapie","Die Germanische Neue Medizin","Aprikosenkerne","Ein Umzug nach Spanien"],"Ihr Tumor war bereits sehr groß. Erst die Chemotherapie, die gegen den Willen der Eltern durchgesetzt wurde, rettete sie."]
]
}
];
