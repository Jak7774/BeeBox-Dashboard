import ure
import urequests
import network
import time
import wifi_config # With Wifi and URL
import wifi_utils # Wifi Connection Function

# ================= Fetch & Parse HTML =================
def fetch_webpage(url="http://beedata.bee-box.co.uk/"):
    try:
        response = urequests.get(url)
        html = response.text
        response.close()
        return html
    except Exception as e:
        print("Error fetching webpage:", e)
        return None

# === Extract a value by class name from HTML chunk ===
def extract_values_by_class(html, cls, unit):
    values = []
    start_tag = f'class="list-group-item {cls}"'
    start_idx = 0
    while True:
        idx = html.find(start_tag, start_idx)
        if idx == -1:
            break
        # Find the closing >
        gt_idx = html.find(">", idx)
        if gt_idx == -1:
            break
        # Find the closing </li>
        end_idx = html.find("</li>", gt_idx)
        if end_idx == -1:
            break
        li_text = html[gt_idx+1:end_idx].strip()
        if ":" in li_text:
            label, value = li_text.split(":")
            values.append((label.strip(), value.replace(unit, "").strip()))
        start_idx = end_idx + 5  # move past this </li>
    return values

# ================= Parse HTML by hive =================
def parse_html_by_hive(html):
    hives = []
    hive_marker = '<h3>Beehive ID:'
    
    # Find all positions of hive headers
    positions = []
    pos = 0
    while True:
        idx = html.find(hive_marker, pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + len(hive_marker)
    positions.append(len(html))  # add end of page for the last hive

    # Extract each hive block
    for i in range(len(positions)-1):
        start = positions[i]
        end = positions[i+1]
        hive_html = html[start:end]

        # Hive ID
        hive_id = None
        id_end = hive_html.find('</h3>')
        if id_end != -1:
            hive_id = hive_html[len(hive_marker):id_end].strip()

        # Temperatures
        temp_classes = ["temp-brood","temp-super","temp-roof","temp-outside"]
        temperatures = {}
        for cls in temp_classes:
            vals = extract_values_by_class(hive_html, cls, "°C")
            if vals:
                temperatures[vals[0][0]] = vals[0][1]

        # Humidities
        hum_classes = ["humid-outside","humid-roof"]
        humidities = {}
        for cls in hum_classes:
            vals = extract_values_by_class(hive_html, cls, "%")
            if vals:
                humidities[vals[0][0]] = vals[0][1]

        # Weight
        weight = None
        for line in hive_html.splitlines():
            if "Weight:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    weight = parts[1].split("kg")[0].strip()
                    break

        hives.append({
            "id": hive_id,
            "temperature": temperatures,
            "humidity": humidities,
            "weight": weight
        })

    return hives


# ===== Fetch all hive data =====
def get_hive_data():
    wifi_utils.connect_to_wifi()
    html = fetch_webpage()
    if not html:
        return []

    raw_hives = parse_html_by_hive(html)
    formatted_hives = []

    for hive in raw_hives:
        # Convert to lists of tuples and filter out 'None'
        temps = [(k, v) for k, v in hive["temperature"].items() if v != "None"]
        hums = [(k, v) for k, v in hive["humidity"].items() if v != "None"]
        formatted_hives.append({
            "id": hive["id"],
            "temperature": temps,
            "humidity": hums,
            "weight": hive["weight"]
        })

    return formatted_hives

