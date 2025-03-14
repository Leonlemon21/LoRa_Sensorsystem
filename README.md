# LoRaWAN-basiertes Sensorsystem

## 📌 Projektbeschreibung
Dieses Projekt ist im Rahmen einer Bachelorarbeit entstanden. Hierbei wurde das Ziel verfolgt ein LoRaWAN basiertes Sensorsystem zu bauen zur Brandwache von verschiedenen Risikogebieten.
Hierbei wurde der Fokus auf ein funktionierenden Prototyp gesetzt um die Technologie für verschiedene Use Cases zu testen.
Hier finden Sie einen Workshopplan mit dessen Hilfe man eigene LoRa Node bauen kann und eine Anleitung wie man diese Geräte aufsetzt um diese zu verwenden.

## 🚀 Features
- Energieeffiziente Datenübertragung
- Hohe Reichweite
- Kostengünstiger als Fertigbauten

## 🛠️ Aufbau & Installation & Verwendung
Sobald Sie den Node gemäß dem bereitgestellten Bauplan aufgebaut und dieselben Sensoren verwendet haben, können Sie Ihre Arduino IDE starten. Falls Sie die Arduino IDE noch nicht installiert haben, empfehlen wir Ihnen, den Link in den weiterführenden Quellen zu verwenden, um sie herunterzuladen.

Sobald Sie die Arduino IDE geöffnet haben, müssen zunächst die erforderlichen Libraries und Boards installiert werden. Hierzu empfehlen wir Ihnen, einen Blick in die Datei „Hinweis.txt“ zu werfen, um die IDE entsprechend einzurichten.

Im nächsten Schritt erstellen Sie ein Profil bei The Things Network (TTN). Sobald Sie Ihr Profil bei The Things Network erstellt haben, wechseln Sie in Ihre Konsole und erstellen dort eine neue Applikation. Normalerweise ist die Einrichtung intuitiv; falls Sie jedoch eine visuelle Anleitung wünschen, steht Ihnen ein Link zu einem erklärenden YouTube-Video zur Verfügung.

Nachdem Sie die Applikation erstellt haben, richten Sie die Endgeräte („End Devices“) ein. Dies können Sie ebenfalls im oben erwähnten Video nachvollziehen.

Nachdem alle Schritte abgeschlossen sind, öffnen Sie die Datei „Combined_M.ino“. Nun müssen Sie sicherstellen, dass das ESP32-Board weiß, mit wem es kommunizieren soll. Dazu tragen Sie im Code die Werte für DevEUI, AppEUI und AppKey ein. Sobald Sie dies erledigt haben, schließen Sie Ihr Board an Ihren Computer an und kompilieren die Datei. Anschließend sollten Sie in der TTN-Konsole sehen können, dass Ihr Gerät Daten an TTN sendet.

Im nächsten Schritt machen wir die empfangenen Daten lesbar. Gehen Sie dazu in Ihre Applikation und wählen Sie auf der linken Seite im Dropdown-Menü den Punkt „Payload formatters“ und anschließend „Uplink“ aus. Dort wählen Sie bitte „Custom JavaScript formatter“ und fügen den Code aus der Datei „Parser.txt“ ein. Speichern Sie abschließend Ihre Änderungen.

Nun müssen wir uns den MQTT Explorer herunterladen, um die empfangenen Informationen nutzbar zu machen. Parallel dazu können wir bereits die notwendigen API-Keys in TTN generieren. Dafür gehen wir links im Dropdown-Menü auf „API Keys“, erstellen einen neuen API-Key und vergeben dabei alle benötigten Rechte.

Anschließend öffnen Sie den MQTT Explorer. Dort werden Sie nun aufgefordert, sich mit den entsprechenden Informationen anzumelden. Alle benötigten Zugangsdaten und Informationen finden Sie in TTN.

Nachdem wir nun sämtliche Daten über MQTT empfangen, können wir uns der GUI zuwenden. Ähnlich wie zuvor beim ESP32-Board müssen wir nun der GUI mitteilen, woher sie ihre Informationen beziehen soll. Öffnen Sie dementsprechend im GUI ordner die main.py Datei. Geben Sie im Code unter dem Abschnitt „MQTT“ alle relevanten Informationen ein, um die Verbindung zum Server herzustellen und nun können Sie die Python Datei ausführen oder sich eine EXE erstellen lassen.

Dafür müssen Sie di folgenden Befehle in ihrer Hauptkonsole ausführen: 
PyInstaller installieren:
Öffne ein Terminal (oder das PyCharm-Terminal) und führe folgenden Befehl aus:

  pip install pyinstaller

In dein Projektverzeichnis wechseln:
Navigiere in der Konsole in das Verzeichnis, in dem deine Hauptdatei (z. B. main.py) liegt mit dem cd Befehl.

EXE erstellen:
Führe Sie den folgenden Befehl aus:

  pyinstaller --onefile --windowed main.py

Damit sind Sie auch schon fertig. Im unteren Abschnitt der GUI können Sie nun sämtliche Informationen Ihrer Sensoren einsehen, während der obere Bereich als Planungstool genutzt werden kann.

## 📬 Kontakt
Falls Sie Vorschläge oder Ideen haben das System in anderen Bereichen zu verwenden oder Sie hatten Spaß bei der Umsetzung des Systems. Können Sie uns über diese Kontaktdaten erreichen:
- leon.oparin@uni-potsdam.de
- tobias.pottek@uni-potsdam.de

## 📚 Weiterführende Quellen
Hier finden Sie alle Links die im Verlaufe der Aufsetzung des Systems benötigt oder Hilfreich sein werden.
- https://www.thethingsnetwork.org/get-started
- https://mqtt-explorer.com/
- https://www.arduino.cc/en/software
- https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers?tab=downloads
- https://www.youtube.com/watch?v=HH5uIWuMXxA&t=773s (Zur Einrichtung der Applikation und End Devices)
