import os
import json
import shutil  # Zum Kopieren von Dateien
import tkinter as tk
import paho.mqtt.client as mqtt
import serial
import threading
from tkinter import ttk, filedialog, Canvas, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps, ImageFilter
import datetime

# ===================== MQTT-Zugangsdaten =====================
MQTT_BROKER = ""
MQTT_PORT =
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
MQTT_TOPIC = ""
mqtt_client = None

SERIAL_PORT = "COM3"
BAUDRATE = 115200

# ===================== Sensor-Nummern-Verwaltung =====================
sensor_counter = 1
sensor_mapping = {}
marker_mapping = {}
selected_sensor = None

# ===================== Zeichen- und Eraser-Variablen =====================
draw_color = "red"
erase_mode = False
draw_mode = False

# ===================== Verwaltung der Zeichenaktionen =====================
draw_actions = []
item_to_action = {}  # item_to_action[item_id] = (action_index, dot_index)
undo_stack = []
redo_stack = []
current_action_index = None
current_erase = []

# ===================== Bild-Verwaltung =====================
original_image = None  # Das ursprünglich geladene Bild (PIL-Objekt)
manual_image = None  # Falls manuell resized, hier die manuelle Version
img_tk = None  # Globaler Verweis für das aktuell angezeigte PhotoImage
canvas_image = None  # Das Canvas-Item für das Hintergrundbild
image_file_path = ""  # Globaler Pfad zum aktuell geladenen Bild

manual_bg_resize = False  # Flag, ob das Bild manuell resized wurde

# ===================== Baseline-Werte für relative Skalierung =====================
baseline_canvas_width = 0  # Canvas-Größe beim Laden/Resizing
baseline_canvas_height = 0
baseline_bg_width = 0  # Bild-Größe (als Basis) beim Laden/Resizing
baseline_bg_height = 0

# ===================== Resize-Handle für manuelles Resizing =====================
resize_handle = None  # Das kleine Griff-Quadrat
resizing = False  # Flag, ob gerade manuell resized wird
handle_start_x = 0  # Mausstartposition beim Ziehen
handle_start_y = 0
start_bg_width = 0  # Ausgangsbreite des Bildes beim Ziehen
start_bg_height = 0  # Ausgangshöhe des Bildes beim Ziehen
bg_width = 0  # Aktuelle Breite des Hintergrundbildes
bg_height = 0  # Aktuelle Höhe des Hintergrundbildes
HANDLE_SIZE = 10  # Größe des Resize-Griffs (Quadrat)

# ===================== Automatisches Scaling =====================
old_width = 0
old_height = 0

# ===================== Undo für Bild-Resizing =====================
prev_bg_state = None

# ===================== Ordner "LoRaWan_Uebung" und Unterordner "Bilder" =====================
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
save_folder = os.path.join(desktop_path, "LoRaWan_Uebung")
os.makedirs(save_folder, exist_ok=True)
images_folder = os.path.join(save_folder, "Bilder")
os.makedirs(images_folder, exist_ok=True)

# ===================== GUI-Setup =====================
root = tk.Tk()
root.title("LoRaWAN TTN & USB Daten")
root.geometry("900x700")
root.state("zoomed")

main_frame = tk.Frame(root)
main_frame.pack(fill=tk.BOTH, expand=True)

# PanedWindow mit vertikaler Aufteilung, breiter Sash
splitter = tk.PanedWindow(main_frame, orient=tk.VERTICAL, sashwidth=20, sashcursor="sb_v_double_arrow")
splitter.pack(fill=tk.BOTH, expand=True)

# Oberer Frame (Canvas-Bereich) – 2/3 der Fensterhöhe
upper_frame = tk.Frame(splitter, bg="white")
splitter.add(upper_frame, height=466)

# Unterer Frame (Tabelle) – 1/3 der Fensterhöhe
lower_frame = tk.Frame(splitter, bg="lightgray")
splitter.add(lower_frame, height=234)

# Im oberen Frame: Aufteilung in Canvas und Button-Leiste
upper_canvas_frame = tk.Frame(upper_frame)
upper_canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
canvas = tk.Canvas(upper_canvas_frame, bg="white")
canvas.pack(fill=tk.BOTH, expand=True)

button_bar_frame = tk.Frame(upper_frame, bg="lightblue")
button_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)
for i in range(8):
    button_bar_frame.grid_columnconfigure(i, weight=1)

upload_button = tk.Button(button_bar_frame, text="Bild hochladen")
upload_button.grid(row=0, column=0, padx=5, pady=5)
color_button = tk.Button(button_bar_frame, text="Farbe wählen")
color_button.grid(row=0, column=1, padx=5, pady=5)
draw_button = tk.Button(button_bar_frame, text="Zeichnen")
draw_button.grid(row=0, column=2, padx=5, pady=5)
undo_button = tk.Button(button_bar_frame, text="← Zurück")
undo_button.grid(row=0, column=3, padx=5, pady=5)
redo_button = tk.Button(button_bar_frame, text="→ Vor")
redo_button.grid(row=0, column=4, padx=5, pady=5)
eraser_button = tk.Button(button_bar_frame, text="Radiergummi")
eraser_button.grid(row=0, column=5, padx=5, pady=5)
save_session_button = tk.Button(button_bar_frame, text="Session speichern")
save_session_button.grid(row=0, column=6, padx=5, pady=5)
load_session_button = tk.Button(button_bar_frame, text="Session laden")
load_session_button.grid(row=0, column=7, padx=5, pady=5)

# Tabelle im unteren Frame
tree_frame = tk.Frame(lower_frame)
tree_frame.pack(fill=tk.BOTH, expand=True)

columns = (
    "Sensorinformation",
    "bmeHum", "bmeHum Einschätzung",
    "bmePres", "bmePres Einschätzung",
    "bmeTemp", "bmeTemp Einschätzung",
    "ccsECO2", "ccsECO2 Einschätzung",
    "ccsTVOC", "ccsTVOC Einschätzung",
    "mq7Value", "mq7Value Einschätzung"
)

tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

for col in columns:
    if col == "Sensorinformation":
        header_text = "Sensorinfo"
    elif col == "bmeHum":
        header_text = "Luftfeuchtigkeit"
    elif col == "bmeHum Einschätzung":
        header_text = "LF Bewertung"
    elif col == "bmePres":
        header_text = "Luftdruck"
    elif col == "bmePres Einschätzung":
        header_text = "LD Bewertung"
    elif col == "bmeTemp":
        header_text = "Temperatur"
    elif col == "bmeTemp Einschätzung":
        header_text = "Temp Bewertung"
    elif col == "ccsECO2":
        header_text = "CO₂"
    elif col == "ccsECO2 Einschätzung":
        header_text = "CO₂ Bewertung"
    elif col == "ccsTVOC":
        header_text = "Total Volatile Organic Compounds"
    elif col == "ccsTVOC Einschätzung":
        header_text = "TVOC Bewertung"
    elif col == "mq7Value":
        header_text = "Kohlenmonoxid"
    elif col == "mq7Value Einschätzung":
        header_text = "CO Bewertung"
    else:
        header_text = col

    tree.heading(col, text=header_text)
    tree.column(col, width=110)

tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)


# ===================== Funktionen für Button-Kommandos =====================

def choose_color():
    global draw_color
    c = colorchooser.askcolor()[1]
    if c:
        draw_color = c


color_button.config(command=choose_color)


def toggle_drawing():
    global draw_mode, erase_mode
    draw_mode = not draw_mode
    erase_mode = False
    canvas.config(cursor="pencil" if draw_mode else "arrow")


draw_button.config(command=toggle_drawing)


def toggle_eraser():
    global erase_mode, draw_mode
    erase_mode = not erase_mode
    draw_mode = False
    canvas.config(cursor="dotbox" if erase_mode else "arrow")


eraser_button.config(command=toggle_eraser)


def upload_image():
    global original_image, manual_image, img_tk, canvas_image, image_file_path
    file_path = filedialog.askopenfilename(filetypes=[("Bilddateien", "*.png;*.jpg;*.jpeg;*.gif")])
    print("Ausgewählter Bildpfad:", file_path)  # Debug-Ausgabe
    if file_path:
        image_file_path = file_path  # Bildpfad speichern
        try:
            original_image = Image.open(file_path)
            print("Bild erfolgreich geladen.")
        except Exception as e:
            print("Fehler beim Öffnen des Bildes:", e)
            return

        # Aktualisiere die GUI, damit der Canvas die richtige Größe hat:
        root.update_idletasks()

        c_width = canvas.winfo_width()
        c_height = canvas.winfo_height()
        if c_width <= 0 or c_height <= 0:
            c_width, c_height = 800, 600
        print("Canvas-Größe:", c_width, c_height)

        resized_image = original_image.resize((c_width, c_height), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(resized_image)
        # Setze globale Bildgrößen:
        global bg_width, bg_height, manual_bg_resize, baseline_canvas_width, baseline_canvas_height, baseline_bg_width, baseline_bg_height
        bg_width, bg_height = c_width, c_height
        manual_bg_resize = False
        manual_image = None
        if canvas_image:
            canvas.delete(canvas_image)
        canvas_image = canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
        canvas.lower(canvas_image)
        baseline_canvas_width, baseline_canvas_height = c_width, c_height
        baseline_bg_width, baseline_bg_height = bg_width, bg_height
        create_resize_handle()
    else:
        print("Kein Bild ausgewählt.")

upload_button.config(command=upload_image)


def create_resize_handle():
    global resize_handle, bg_width, bg_height, HANDLE_SIZE
    if resize_handle:
        canvas.delete(resize_handle)
    x1 = bg_width - HANDLE_SIZE
    y1 = bg_height - HANDLE_SIZE
    x2 = bg_width
    y2 = bg_height
    resize_handle = canvas.create_rectangle(x1, y1, x2, y2, fill="gray", outline="black", tags=("resize_handle",))
    canvas.tag_bind(resize_handle, "<ButtonPress-1>", resize_handle_press)
    canvas.tag_bind(resize_handle, "<B1-Motion>", resize_handle_motion)
    canvas.tag_bind(resize_handle, "<ButtonRelease-1>", resize_handle_release)


def resize_handle_press(event):
    global resizing, handle_start_x, handle_start_y, start_bg_width, start_bg_height, prev_bg_state
    resizing = True
    handle_start_x = event.x
    handle_start_y = event.y
    start_bg_width = bg_width
    start_bg_height = bg_height
    prev_bg_state = {
        "bg_width": bg_width,
        "bg_height": bg_height,
        "manual_bg_resize": manual_bg_resize,
        "manual_image": manual_image,
        "baseline_bg_width": baseline_bg_width,
        "baseline_bg_height": baseline_bg_height,
        "bg_file": os.path.join("Bilder", os.path.basename(image_file_path))
    }


def resize_handle_motion(event):
    global bg_width, bg_height, original_image, manual_image, img_tk, manual_bg_resize
    global baseline_bg_width, baseline_bg_height
    if not resizing or original_image is None:
        return
    dx = event.x - handle_start_x
    dy = event.y - handle_start_y
    new_width = max(50, int(start_bg_width + dx))
    new_height = max(50, int(start_bg_height + dy))
    canvas_width = canvas.winfo_width()
    canvas_height = canvas.winfo_height()
    new_width = min(new_width, canvas_width)
    new_height = min(new_height, canvas_height)
    bg_width, bg_height = new_width, new_height
    manual_bg_resize = True
    baseline_bg_width, baseline_bg_height = bg_width, bg_height
    manual_image = original_image.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
    new_img_tk = ImageTk.PhotoImage(manual_image)
    canvas.itemconfig(canvas_image, image=new_img_tk)
    img_tk = new_img_tk
    x1 = bg_width - HANDLE_SIZE
    y1 = bg_height - HANDLE_SIZE
    x2 = bg_width
    y2 = bg_height
    canvas.coords(resize_handle, x1, y1, x2, y2)


def resize_handle_release(event):
    global resizing, prev_bg_state
    resizing = False
    dx = event.x - handle_start_x
    dy = event.y - handle_start_y
    if dx != 0 or dy != 0:
        new_state = {
            "bg_width": bg_width,
            "bg_height": bg_height,
            "manual_bg_resize": manual_bg_resize,
            "manual_image": manual_image,
            "baseline_bg_width": baseline_bg_width,
            "baseline_bg_height": baseline_bg_height,
            "bg_file": os.path.join("Bilder", os.path.basename(image_file_path))
        }
        undo_stack.append({
            "type": "resize",
            "prev_state": prev_bg_state,
            "new_state": new_state
        })
        redo_stack.clear()
    prev_bg_state = None


def add_marker(event):
    global selected_sensor

    # Marker nur setzen, wenn weder Zeichnen noch Radieren aktiv
    if draw_mode or erase_mode:
        return

    if selected_sensor is None:
        return

    # Falls der Sensor schon einen Marker hat, lösche ihn
    if selected_sensor in marker_mapping:
        canvas.delete(marker_mapping[selected_sensor])

    # Marker erstellen
    marker = canvas.create_oval(
        event.x - 5, event.y - 5,
        event.x + 5, event.y + 5,
        fill=draw_color, outline="black", tags=("drawn",)
    )
    marker_mapping[selected_sensor] = marker


def start_drawing(event):
    global current_action_index, current_erase
    if draw_mode:
        current_action_index = len(draw_actions)
        new_action = {
            "type": "draw",
            "action_id": current_action_index,
            "dots": []
        }
        draw_actions.append(new_action)
    elif erase_mode:
        current_erase = []
        # Sofortiges Auslösen der Erase-Logik beim Klick:
        draw_on_canvas(event)


def draw_on_canvas(event):
    global current_action_index, current_erase
    x, y = event.x, event.y
    if erase_mode:
        for item in canvas.find_overlapping(x - 5, y - 5, x + 5, y + 5):
            if item == canvas_image or item == resize_handle:
                continue
            if any(r["dot"]["item_id"] == item for r in current_erase):
                continue
            if item not in item_to_action:
                continue
            action_idx, dot_idx = item_to_action[item]
            dot_data = draw_actions[action_idx]["dots"][dot_idx]
            if dot_data is None:
                continue
            removed_info = {
                "action_index": action_idx,
                "dot": {
                    "item_id": dot_data["item_id"],
                    "coords": dot_data["coords"],
                    "color": dot_data["color"],
                    "rel_coords": dot_data["rel_coords"]
                }
            }
            current_erase.append(removed_info)
            draw_actions[action_idx]["dots"][dot_idx] = None
            del item_to_action[item]
            canvas.delete(item)
    elif draw_mode:
        radius = 2
        dot_id = canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=draw_color, outline=draw_color, tags=("drawn",)
        )
        abs_coords = canvas.coords(dot_id)
        rel_coords = [abs_coords[0] / baseline_bg_width,
                      abs_coords[1] / baseline_bg_height,
                      abs_coords[2] / baseline_bg_width,
                      abs_coords[3] / baseline_bg_height]
        dot_data = {
            "item_id": dot_id,
            "coords": abs_coords,
            "color": draw_color,
            "rel_coords": rel_coords
        }
        draw_actions[current_action_index]["dots"].append(dot_data)
        dot_index_in_action = len(draw_actions[current_action_index]["dots"]) - 1
        item_to_action[dot_id] = (current_action_index, dot_index_in_action)


def stop_drawing(event):
    global current_action_index, current_erase
    if draw_mode:
        undo_stack.append({
            "type": "draw",
            "action_id": current_action_index
        })
        redo_stack.clear()
        current_action_index = None
    elif erase_mode and current_erase:
        erase_action = {
            "type": "erase",
            "removed": current_erase[:]
        }
        undo_stack.append(erase_action)
        redo_stack.clear()
        current_erase = []


def apply_bg_state(state):
    global bg_width, bg_height, manual_bg_resize, manual_image
    global baseline_bg_width, baseline_bg_height, img_tk, image_file_path, original_image
    bg_width = state["bg_width"]
    bg_height = state["bg_height"]
    manual_bg_resize = state["manual_bg_resize"]
    baseline_bg_width = state["baseline_bg_width"]
    baseline_bg_height = state["baseline_bg_height"]

    # Lese den relativen Bildpfad, z.B. "Bilder/DeinBild.jpg"
    image_file_path = state.get("bg_file", "")
    base_image = None
    if image_file_path:
        # Verwende den in bg_state übergebenen session_folder oder save_folder als Fallback
        session_folder = state.get("session_folder", save_folder)
        full_path = os.path.join(session_folder, image_file_path)
        print("Lade Bild von:", full_path)  # Debug-Ausgabe
        if os.path.exists(full_path):
            base_image = Image.open(full_path)
        else:
            print("Bilddatei nicht gefunden:", full_path)
    if base_image is None and original_image is not None:
        print("Kein Bild aus Session gefunden, verwende original_image.")
        base_image = original_image
    if base_image is not None:
        resized_image = base_image.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
        new_img_tk = ImageTk.PhotoImage(resized_image)
        canvas.itemconfig(canvas_image, image=new_img_tk)
        img_tk = new_img_tk
        original_image = base_image
    else:
        print("Kein Bild zum Laden vorhanden!")
    create_resize_handle()


def undo():
    if not undo_stack:
        return
    last_action = undo_stack.pop()
    redo_stack.append(last_action)
    if last_action["type"] == "draw":
        action_id = last_action["action_id"]
        for dot in draw_actions[action_id]["dots"]:
            if dot is not None:
                item_id = dot["item_id"]
                canvas.delete(item_id)
                if item_id in item_to_action:
                    del item_to_action[item_id]
    elif last_action["type"] == "erase":
        for removed in last_action["removed"]:
            action_idx = removed["action_index"]
            dot_data = removed["dot"]
            new_item = canvas.create_oval(
                *dot_data["coords"],
                fill=dot_data["color"],
                outline=dot_data["color"],
                tags=("drawn",)
            )
            inserted = False
            for i in range(len(draw_actions[action_idx]["dots"])):
                if draw_actions[action_idx]["dots"][i] is None:
                    draw_actions[action_idx]["dots"][i] = {
                        "item_id": new_item,
                        "coords": dot_data["coords"],
                        "color": dot_data["color"],
                        "rel_coords": dot_data["rel_coords"]
                    }
                    item_to_action[new_item] = (action_idx, i)
                    inserted = True
                    break
            if not inserted:
                draw_actions[action_idx]["dots"].append({
                    "item_id": new_item,
                    "coords": dot_data["coords"],
                    "color": dot_data["color"],
                    "rel_coords": dot_data["rel_coords"]
                })
                new_idx = len(draw_actions[action_idx]["dots"]) - 1
                item_to_action[new_item] = (action_idx, new_idx)
    elif last_action["type"] == "resize":
        apply_bg_state(last_action["prev_state"])


undo_button.config(command=undo)


def redo():
    if not redo_stack:
        return
    last_action = redo_stack.pop()
    undo_stack.append(last_action)
    if last_action["type"] == "draw":
        action_id = last_action["action_id"]
        for i, dot in enumerate(draw_actions[action_id]["dots"]):
            if dot is not None:
                new_item = canvas.create_oval(
                    *dot["coords"],
                    fill=dot["color"],
                    outline=dot["color"],
                    tags=("drawn",)
                )
                dot["item_id"] = new_item
                item_to_action[new_item] = (action_id, i)
    elif last_action["type"] == "erase":
        for removed in last_action["removed"]:
            action_idx = removed["action_index"]
            dot_data = removed["dot"]
            found_index = None
            for i, dt in enumerate(draw_actions[action_idx]["dots"]):
                if dt is not None and dt["coords"] == dot_data["coords"] and dt["color"] == dot_data["color"]:
                    found_index = i
                    break
            if found_index is not None:
                item_id = draw_actions[action_idx]["dots"][found_index]["item_id"]
                canvas.delete(item_id)
                if item_id in item_to_action:
                    del item_to_action[item_id]
                draw_actions[action_idx]["dots"][found_index] = None
    elif last_action["type"] == "resize":
        apply_bg_state(last_action["new_state"])


redo_button.config(command=redo)


def on_canvas_configure(event):
    global old_width, old_height, img_tk, canvas_image, bg_width, bg_height
    global baseline_canvas_width, baseline_canvas_height, baseline_bg_width, baseline_bg_height

    if baseline_canvas_width == 0 or baseline_canvas_height == 0:
        return

    new_width = event.width
    new_height = event.height
    if old_width == 0 and old_height == 0:
        old_width, old_height = new_width, new_height
        return
    if new_width == old_width and new_height == old_height:
        return
    factor_x = new_width / baseline_canvas_width
    factor_y = new_height / baseline_canvas_height
    for action in draw_actions:
        for dot in action["dots"]:
            if dot is not None:
                rel = dot["rel_coords"]
                new_coords = [rel[0] * baseline_bg_width * factor_x,
                              rel[1] * baseline_bg_height * factor_y,
                              rel[2] * baseline_bg_width * factor_x,
                              rel[3] * baseline_bg_height * factor_y]
                dot["coords"] = new_coords
                canvas.coords(dot["item_id"], *new_coords)
    new_img_width = int(baseline_bg_width * factor_x)
    new_img_height = int(baseline_bg_height * factor_y)
    new_img_width = min(new_img_width, new_width)
    new_img_height = min(new_img_height, new_height)
    bg_width, bg_height = new_img_width, new_img_height
    base_image = manual_image if manual_bg_resize and manual_image is not None else original_image
    if base_image is not None:
        resized_image = base_image.resize((new_img_width, new_img_height), Image.Resampling.LANCZOS)
        new_img_tk = ImageTk.PhotoImage(resized_image)
        canvas.itemconfig(canvas_image, image=new_img_tk)
        img_tk = new_img_tk
        create_resize_handle()
    old_width, old_height = new_width, new_height


canvas.bind("<Configure>", on_canvas_configure)
canvas.bind("<ButtonPress-1>", start_drawing, add="+")
canvas.bind("<B1-Motion>", draw_on_canvas)
canvas.bind("<ButtonRelease-1>", stop_drawing, add="+")
canvas.bind("<Button-1>", lambda event: add_marker(event), add="+")


def on_mqtt_message(client, userdata, msg):
    print("on_mqtt_message wurde aufgerufen!")  # DEBUG
    try:
        # JSON dekodieren
        data = json.loads(msg.payload.decode())
        print("Empfangener Payload:", data)  # DEBUG

        # Aus TTN-Daten extrahieren:
        device_id = data["end_device_ids"]["device_id"]
        decoded_payload = data["uplink_message"].get("decoded_payload", {})

        # 6 Felder als Float:
        bmeHum = float(decoded_payload.get("bmeHum", 0.0))
        bmePres = float(decoded_payload.get("bmePres", 0.0))
        bmeTemp = float(decoded_payload.get("bmeTemp", 0.0))
        ccsECO2 = float(decoded_payload.get("ccsECO2", 0.0))
        ccsTVOC = float(decoded_payload.get("ccsTVOC", 0.0))
        mq7Value = float(decoded_payload.get("mq7Value", 0.0))

        # String für die Treeview-Zeile erstellen:
        #sensor_values_str = (
            #f"Hum: {bmeHum:.2f}, "
            #f"Pres: {bmePres:.2f}, "
            #f"Temp: {bmeTemp:.2f}, "
            #f"ECO2: {ccsECO2:.2f}, "
            #f"TVOC: {ccsTVOC:.2f}, "
            #f"MQ7: {mq7Value:.2f}"
        #)

        # Einschätzung (anpassen, wie benötigt)
        # bmeHum Bewertung:
        if bmeHum < 30:
            hum_einschätzung = "Niedrig"
        elif bmeHum > 70:
            hum_einschätzung = "Hoch"
        else:
            hum_einschätzung = "OK"

        # bmePres Bewertung (angenommener Normalbereich 990 - 1020 hPa):
        if bmePres < 990:
            pres_einschätzung = "Niedrig"
        elif bmePres > 1020:
            pres_einschätzung = "Hoch"
        else:
            pres_einschätzung = "OK"

        # bmeTemp Bewertung:
        if bmeTemp < 10:
            temp_einschätzung = "Niedrig"
        elif bmeTemp > 30:
            temp_einschätzung = "Hoch"
        else:
            temp_einschätzung = "OK"

        # ccsECO2 Bewertung:
        if ccsECO2 < 600:
            eco2_einschätzung = "Normal"
        elif ccsECO2 < 800:
            eco2_einschätzung = "Mäßig hoch"
        elif ccsECO2 < 1000:
            eco2_einschätzung = "Hoch"
        else:
            eco2_einschätzung = "Sehr hoch"

        # ccsTVOC Bewertung:
        if ccsTVOC < 150:
            tvoc_einschätzung = "Normal"
        elif ccsTVOC < 300:
            tvoc_einschätzung = "Mäßig hoch"
        elif ccsTVOC < 500:
            tvoc_einschätzung = "Hoch"
        else:
            tvoc_einschätzung = "Sehr hoch"

        # mq7Value Bewertung:
        if mq7Value < 0.3:
            mq7_einschätzung = "Normal"
        elif mq7Value < 0.7:
            mq7_einschätzung = "Mäßig hoch"
        else:
            mq7_einschätzung = "Hoch"

        # GUI-Update über den Hauptthread:
        root.after(0, lambda: tree.insert("", tk.END, values=(
            f"Gerät: {device_id}",
            f"{bmeHum:.2f}", hum_einschätzung,
            f"{bmePres:.2f}", pres_einschätzung,
            f"{bmeTemp:.2f}", temp_einschätzung,
            f"{ccsECO2:.2f}", eco2_einschätzung,
            f"{ccsTVOC:.2f}", tvoc_einschätzung,
            f"{mq7Value:.2f}", mq7_einschätzung
        )))

    except Exception as e:
        print("Fehler im on_mqtt_message Callback:", e)


def start_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.tls_set()  # TLS aktivieren
    mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.subscribe(MQTT_TOPIC)
    mqtt_client.loop_start()


root.after(100, start_mqtt)


# ===================== Session-Speicher-/Lade-Funktionen =====================

def save_session():
    from tkinter import filedialog
    session_filename = filedialog.asksaveasfilename(
        initialdir=save_folder,
        title="Session speichern",
        defaultextension=".json",
        filetypes=[("JSON Dateien", "*.json")]
    )
    if session_filename:
        coords = splitter.sash_coord(0)  # (x, y)
        sash_y = coords[1]
        saved_actions = []
        for action in draw_actions:
            act = {
                "type": action["type"],
                "action_id": action["action_id"],
                "dots": []
            }
            for d in action["dots"]:
                if d is not None:
                    act["dots"].append({
                        "coords": d["coords"],
                        "color": d["color"],
                        "rel_coords": d["rel_coords"]
                    })
            saved_actions.append(act)
        # Hintergrundbild-Zustand speichern:
        bg_file = ""
        if image_file_path and os.path.exists(image_file_path):
            # Generiere einen eindeutigen Dateinamen
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"{timestamp}_{os.path.basename(image_file_path)}"
            bg_file = os.path.join("Bilder", unique_filename)
            dest_path = os.path.join(images_folder, unique_filename)
            shutil.copy(image_file_path, dest_path)
        bg_state = {
            "bg_file": bg_file,
            "bg_width": bg_width,
            "bg_height": bg_height,
            "manual_bg_resize": manual_bg_resize,
            "baseline_bg_width": baseline_bg_width,
            "baseline_bg_height": baseline_bg_height
        }
        data_to_save = {
            "sash_y": sash_y,
            "draw_actions": saved_actions,
            "bg_state": bg_state
        }
        with open(session_filename, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        print("Session gespeichert in", session_filename)


save_session_button.config(command=save_session)


def load_session():
    from tkinter import filedialog
    session_filename = filedialog.askopenfilename(
        initialdir=save_folder,
        title="Session laden",
        filetypes=[("JSON Dateien", "*.json")]
    )
    if session_filename:
        # Ermittle den Ordner, in dem die Session-Datei liegt
        session_folder = os.path.dirname(session_filename)
        with open(session_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        sash_y = data.get("sash_y", None)
        if sash_y is not None:
            coords = splitter.sash_coord(0)
            splitter.sash_place(0, coords[0], sash_y)
        # Lösche aktuelle Zeichnungen (außer Hintergrundbild und Resize-Handle)
        for item in canvas.find_all():
            if item not in (canvas_image, resize_handle):
                canvas.delete(item)
        global draw_actions, item_to_action
        draw_actions = []
        item_to_action = {}
        for act in data.get("draw_actions", []):
            new_act = {
                "type": act["type"],
                "action_id": act["action_id"],
                "dots": []
            }
            for d in act["dots"]:
                new_item = canvas.create_oval(*d["coords"],
                                              fill=d["color"],
                                              outline=d["color"],
                                              tags=("drawn",))
                new_dot = {
                    "item_id": new_item,
                    "coords": d["coords"],
                    "color": d["color"],
                    "rel_coords": d["rel_coords"]
                }
                new_act["dots"].append(new_dot)
                if new_item not in item_to_action:
                    item_to_action[new_item] = (new_act["action_id"], len(new_act["dots"]) - 1)
            draw_actions.append(new_act)
        # Lade Hintergrundbild-Zustand:
        bg_state = data.get("bg_state", {})
        if bg_state:
            bg_state["session_folder"] = session_folder
            apply_bg_state(bg_state)
        # Aktualisiere Baseline-Werte nach dem Laden:
        global baseline_canvas_width, baseline_canvas_height, baseline_bg_width, baseline_bg_height
        baseline_canvas_width = canvas.winfo_width()
        baseline_canvas_height = canvas.winfo_height()
        baseline_bg_width = bg_width
        baseline_bg_height = bg_height
        print("Session geladen aus", session_filename)


load_session_button.config(command=load_session)


def on_close():
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)

root.mainloop()
