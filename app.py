import streamlit as st
from pdf2image import convert_from_path
import tempfile, os, json, requests
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import re
import json



# ── Setup API ──
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")
print("Loaded API key:", os.getenv("GOOGLE_API_KEY"))

# --- Simple Password Authentication ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "oizom4932":
            st.session_state["authenticated"] = True
            del st.session_state["password"]  # Remove password from session
        else:
            st.session_state["authenticated"] = False

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🔒 Authentication Required")
        st.text_input("Enter password", type="password", key="password", on_change=password_entered)
        if st.session_state.get("authenticated") is False and "password" in st.session_state:
            st.error("Incorrect password. Please try again.")
        st.stop()

check_password()

# ── Master Data ──
valid_products = [
    "OIZ-POLLUDRONE", "OIZ-ODOSENSE", "OIZ-DUSTROID",
    "OIZ-WEATHERCOM", "OIZ-WS/WD", "OIZ-RAINFALL"
]

product_sensors = {
    "OIZ-POLLUDRONE": ["PM", "CO", "CO2", "SO2", "NO", "NO2", "O3", "TVOC", "TEMP_HUM", "TEMP_HUM_PRES", "NOISE", "UV"],
    "OIZ-DUSTROID":   ["PM", "TEMP_HUM", "TEMP_HUM_PRES"],
    "OIZ-ODOSENSE":   ["SO2", "NO2", "TVOC", "TEMP_HUM", "TEMP_HUM_PRES"],
    "OIZ-WEATHERCOM": ["WSD", "RAIN", "UV", "TEMP_HUM", "TEMP_HUM_PRES", "NOISE"],
    "OIZ-WS/WD":      ["WSD"],
    "OIZ-RAINFALL":   ["RAIN"]
}

name_variants = {
    "CO":            [("Carbon monoxide")],
    "CO2":           [("Carbon dioxide")],
    "SO2":           [("Sulfur dioxide")],
    "NO":            [("Nitric oxide")],
    "NO2":           [("Nitrogen dioxide")],
    "O3":            [("Ozone")],
    "TVOC":          [("Total Volatile Organic Compounds")],
    "TEMP_HUM":      [("Temperature"),("Humidity")],
    "TEMP_HUM_PRES": [("Pressure")],
    "UV":            [("Light intensity"),("UV Radiation"),("Visible Light Intensity"),("UV"),("Light")],
    "NOISE":         [("Noise")],
    "WSD":           [("Wind speed"), ("Wind direction"), ("Wind speed and direction"), ("Direction sensor"), ("Direction")],
    "RAIN":          [("Rainfall"),("Rain")],
    "PM":            [("PM1"),("PM2.5"),("PM10"),("PM100"),("Industrial Dust"),("PM SENSOR"),("PM Sensor")],
    "H2S":           [("Hydrogen Sulfide")],
    "CL2":           [("Chlorine")],
    "NH3":           [("Ammonia")],
    "CH4":           [("Methane")],
    "CH2O":          [("Formaldehyde")],
    "CH3SH":         [("Methyl Mercaptan")],
    "HCL":           [("Hydrochloric Acid")],
    "O2":            [("Oxygen")],
    "HC":            [("Hydrocarbons")],
    "CLO2":          [("Chlorine Dioxide")],
    "BTEX":          [("Benzene"),("Toluene"),("Ethylbenzene"),("Xylene")]
}

sensor_variants = {
    "CO":            [("OZCO_1", "CO: 0-5 ppm"), ("OZCO_2", "CO: 0-100 ppm"), ("OZCO_3", "CO: 0-1000 ppm"), ("OZCO_4", "CO: 0-50 ppm"), ("OZCO_5", "CO: 0-10 ppm")],
    "CO2":           [("OZCO2_1", "CO2: 0-5000 ppm")],
    "SO2":           [("OZSO2_1", "SO2: 0-10 ppm"), ("OZSO2_2", "SO2: 0-100 ppm"), ("OZSO2_3", "SO2: 0-2000 ppm"), ("OZSO2_4", "SO2: 0-20 ppm")],
    "NO":            [("OZNO_1", "NO: 0-5 ppm"), ("OZNO_2", "NO: 0-100 ppm"), ("OZNO_3", "NO: 0-10 ppm")],
    "NO2":           [("OZNO2_1", "NO2: 0-10 ppm"), ("OZNO2_2", "NO2: 0-100 ppm"), ("OZNO2_3", "NO2: 0-500 ppm"), ("OZNO2_4", "NO2: 0-10 ppm")],
    "O3":            [("OZO3_1", "O3: 0-10 ppm"), ("OZO3_2", "O3: 0-8 ppm")],
    "TVOC":          [("OZTVOC_1", "TVOC: 0-40 ppm"), ("OZTVOC_2", "TVOC: 0-200 ppm")],
    "TEMP_HUM":      [("OZTEMP_HUM_1", "Temperature: -40 to 125°C, Humidity: 100% Rh")],
    "TEMP_HUM_PRES": [("OZTEMP_HUM_PRES_4", "Temperature: -40 to 125°C, Humidity: 100% Rh, Pressure: 300-1100 hPa")],
    "UV":            [("OZUV_1", "Light: 0-100000 Lux, UV: 0.1-100000 uW/cm², Visible: 0-5000 Lux")],
    "NOISE":         [("OZN_2", "Noise: Up to 140 dB")],
    "WSD":           [("OZWSD_1", "Wind: 0-40m/s, Direction: 0-359°")],
    "RAIN":          [("OZRAIN_1", "Rainfall")],
    "PM":            [("OZPM_1", "PM1, PM2.5 (5000 μg/m³), PM10, PM100 (30 mg/m³)"), ("OZPM_2", "Industrial Dust: 0-30000 μg/m³")],
    "H2S":           [("OZH2S_1", "H2S: 0-1.5 ppm"), ("OZH2S_2", "H2S: 0-50 ppm"), ("OZH2S_3", "H2S: 0-200 ppm"), ("OZH2S_4", "H2S: 0-2000 ppm"), ("OZH2S_5", "H2S: 0-10 ppm")],
    "CL2":           [("OZCL2_1", "Cl2: 0-20 ppm"), ("OZCL2_2", "Cl2: 0-50 ppm")],
    "NH3":           [("OZNH3_1", "NH3: 0-20 ppm"), ("OZNH3_2", "NH3: 0-100 ppm"), ("OZNH3_3", "NH3: 0-1000 ppm"), ("OZNH3_4", "NH3: 0-10 ppm")],
    "CH4":           [("OZCH4_1", "CH4: 500-1500 ppm"), ("OZCH4_2", "CH4: 50-1000000 ppm")],
    "CH2O":          [("OZCH2O_1", "CH2O: 0-10 ppm"), ("OZCH2O_2", "CH2O: 0-50 ppm")],
    "CH3SH":         [("OZCH3SH_1", "CH3SH: 0-10 ppm")],
    "HCL":           [("OZHCl_1", "HCl: 0-50 ppm"), ("OZHCl_2", "HCl: 0-100 ppm")],
    "O2":            [("OZO2_1", "O2: 0-25 %VOL")],
    "HC":            [("OZHC_1", "HC/VOC: 0-20 ppm")],
    "CLO2":          [("OZCLO2_1", "ClO2: 0-1 ppm")],
    "BTEX":          [("OZBTEX_1", "BTEX: 0-10 ppm")]
}

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "uploaded_pdf_name" not in st.session_state:
    st.session_state.uploaded_pdf_name = None
if "mode" not in st.session_state:
    st.session_state.mode = "Manual"
if "manual_payload" not in st.session_state:
    st.session_state.manual_payload = None
if "automatic_payload" not in st.session_state:
    st.session_state.automatic_payload = None
if "extracted_meta" not in st.session_state:
    st.session_state.extracted_meta = {}
if "gemini_json" not in st.session_state:
    st.session_state.gemini_json = {}
if "final_dropdown_selections" not in st.session_state:
    st.session_state.final_dropdown_selections = {}
if "webhook_sent" not in st.session_state:
    st.session_state.webhook_sent = False

# ── UI Setup ──
st.set_page_config("📄 PO Sensor Configurator", layout="wide")
st.title("📄 PO Sensor Extractor")


# ── Sidebar: PDF Preview ──
with st.sidebar:
    st.markdown("### PDF Preview")
    zoom_scale = 1.5

    # Sidebar styling with scroll and zoom
    st.sidebar.markdown(f"""
    <style>
    [data-testid="stSidebar"] > div:first-child {{
        transform: scale({zoom_scale});
        transform-origin: top left;
        width: calc(100% / {zoom_scale});
        height: 100vh;
        overflow-x: auto !important;
        overflow-y: auto !important;
        padding-right: 30px;
        white-space: nowrap;
    }}
    img {{
        max-width: none !important;
        height: auto;
        display: block;
    }}
    </style>
    """, unsafe_allow_html=True)



# ── Main: Minimal Form Inputs ──
with st.form("metadata_form"):
    org                   = st.text_input("🏢 Organization Name")
    am_name               = st.selectbox(
    "👤 Account Manager",
        [
            "JAINAM MEHTA",
            "SAMARPIT GARG",
            "ADITYARAJSINH GOHIL",
            "AARSH PATEL",
            "DEVAL SONI",
            "KAREENA SHARMA",
            "SHIKSHA",
            "ADIT SONI",
            "PRIYANKA"
        ]
    )    
    delivery_terms       = st.selectbox(
        "📦 Delivery Terms",
        [
            "2 TO 3 WEEKS",
            "3 TO 4 WEEKS",
            "4 TO 5 WEEKS",
            "10 TO 12 WORKING DAYS",
            "WITH IN WEEK"
        ])
    expected_shipment_date= st.date_input("📅 Expected Shipment Date")  # renamed to stay consistent
    usecase               = st.selectbox("🎯 Use Case", ["ENVIZOM", "Bioreactor Plants", "Airports", "Cement Industries", "Coal Washing facilities", "Construction", "Dairy Farms", "Detecting Forest Fires","Dust Suppression Automation","Fertilizers", "Flood and Water Monitoring","Food processing plants", "Highway Monitoring", "Hospitals", "Industrial Fenceline monitoring", "Landfills", "Manufacturing Plant", "Meat Processing Plants", "Mining Sites", "Oil Refinery", "Ports", "Poultry / Cattle Farms", "Pulp and Paper Industries", "Quarries / Mining", "Research Activities", "Roadside Traffic", "School/Universities", "Smart Campus", "Smart City", "Solid Waste", "Textile Industries", "Thermal Power Plants", "Tunnel", "Wastewater treatment", "Demo"])
    Solar_panel = st.selectbox("☀️ Solar Panel", ["Yes", "No"])
    solar_PSU_Cable = st.selectbox("🔌 Solar PSU + Solar Cable", ["Yes", "No"])
    Battery_backup = st.selectbox("🔋 Batter Backup ", ["yes", "No"])
    Simcard_installation = st.selectbox("📶 simcard installation responsibility", ["Yes", "No"])
    Data_Communication = st.multiselect(label='Data comunication:',options=["GSM", "WIFI", "Ethernet", "ModBus", "Relay"],default= ["GSM", "WIFI", "Ethernet", "ModBus", "Relay"])
    Country = st.text_input("🌍 Country")
    logistics = st.selectbox("🚚 Logistics", ["Dispatch", "Pickup"])
    MCERT_Required = st.selectbox("📜 MCERT Required", ["Yes", "No"])
    uploaded_pdf          = st.file_uploader("📎 Upload PO PDF", type="pdf")
    st.session_state.mode = st.radio("Choose Mode", ["Manual", "Automatic"], horizontal=True)
    mode = st.session_state.mode
    submit = st.form_submit_button("Run")

def load_images_from_bytes(pdf_bytes, dpi=150):
    """Converts PDF bytes into a list of PIL Images."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    
    try:
        # Use poppler_path if you have it configured, otherwise it uses system's PATH
        with pdfplumber.open(tmp_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    finally:
        os.remove(tmp_path)
        
    return images
def extract_from_images(images):
                """Extracts data by sending a list of PIL Images to Gemini."""

                prompt = """
You are an expert in air-quality document parsing. Given a PO or quotation in image or PDF format, extract structured JSON as follows:

{
  "products": [
    {
      "name": "PRODUCT_NAME",
      "quantity": 1,
      "product_type": "LITE | SMART | PRO | MAX | CUSTOM",
      "sensors": [
        { "item": "Original sensor string", "flag": "true_by_code" | "true_by_name" | null }
      ]
    }
  ],
  "po_number": "...",
  "billing_address": "...",
  "billing_country": "...",
  "shipping_address": "...",
  "shipping_country": "..."
}

---

🎯 Extraction Rules:

1. Only extract for these products: OIZ-POLLUDRONE, OIZ-ODOSENSE, OIZ-DUSTROID, OIZ-WEATHERCOM, OIZ-POLLUSENSE.
2. If a sensor contains code (e.g., OZCO_1), return only the code in `"item"` with `"flag": "true_by_code"`.
3. If no code but matches known names (e.g., CO, PM2.5, Temperature), use `"flag": "true_by_name"`.
4. For joined names with `/`, `,`, `and`, or `&`, split them into individual entries.
5. Deduplicate and always keep the original sensor string in `"item"`.

---

📌 Special Handling:

-If any code like OZLI_1 or OZVLI_1 appears, treat it as OZUV_1.
 { "item": "OZUV_1", "flag": "true_by_code" }
- **Wind speed and direction** 
  If any phrase like "Wind Speed and Direction", "Wind Speed / Direction", "Wind speed & direction" or similar appears (even alone), extract: 
  { "item": "Wind speed and Direction", "flag": "true_by_name" }

- **Particulate Matter (PM)**  
- If the text includes "PM1", "PM2.5", "PM10", and "PM100" (in any order), even with other words (e.g., "Heated Inlet"), extract:
  { "item": "PM1, PM2.5, PM10, PM100", "flag": "true_by_name" }

- If the text includes phrases like "PM sensor", "Particulate Matter Sensor", or "Dust Sensor", extract:
  { "item": "PM sensor", "flag": "true_by_name" }

- Avoid extracting PM1, PM2.5, PM10 separately if they appear together.
📌 PM SPARE SENSOR HANDLING:

- If any phrase contains **"Oizom PM sensor"**, **"PM sensor (spare)"**, or **"spare PM sensor"** — extract:
  {
    "item": "Oizom PM sensor (spare sensor)",
    "flag": "true_by_name"
  }

- It should provide a dropdown for selecting one of the variants from OZPM_1, OZPM_2.


---

✅ Return only valid JSON. No markdown, comments, or extra text.
"""
                results = []
                for img in images:
                    res = model.generate_content([prompt, text])
                    try:
                        clean = res.text.strip("```json").strip("```")
                    #print("cleaned json : ", clean)
                        results = json.loads(clean)
                    #print("result json : ", results)
                    except:
                        continue
            # Choose best or merge all
                return results if isinstance(results, dict) else (results[0] if results else {})

    # ------------------ Sensor Code Extractor ------------------
def extract_ozcode(sensor_item):
    match = re.search(r"(OZ[A-Z0-9_]+)", sensor_item.upper())
    return match.group(1) if match else None

    # ------------------ Normalize Name ------------------
def normalize_name(item):
    item = item.upper().strip()
    # ✅ Step 1: Check direct symbol match
    if item in name_variants:
        return item

    # ✅ Step 2: Partial/alias match for longer strings (e.g., "Carbon Monoxide")
    for symbol, aliases in name_variants.items():
        for alias in aliases:
            if alias.upper() in item:
                return symbol
    
    # ✅ NEW: Try splitting by space, slash, etc., and check partials
    parts = re.split(r"[ /,&()-]+", item)
    for word in parts:
        for symbol, aliases in name_variants.items():
            for alias in aliases:
                if alias.upper() == word.strip():
                    return symbol
                
    return None

# ── Function to handle Automatic Mode logic ──
def process_automatic_mode(gemini_json, org, am_name, delivery_terms, expected_shipment_date, usecase, Solar_panel, solar_PSU_Cable, Battery_backup, Simcard_installation, Data_Communication, Country, logistics, MCERT_Required):
    """
    Renders the UI for automatic mode, including dropdowns, and generates the final payload.
    This function is designed to be called on every script rerun.
    """
    st.subheader("📝 Automatic Mode: Confirm Sensor Variants")
    
    if 'automatic_dropdowns' not in st.session_state:
        st.session_state.automatic_dropdowns = {}
    
    final_products = []
    for prod_idx, prod in enumerate(gemini_json.get("products", [])):
        confirmed = []
        added_codes = set()
        grouped_by_symbol = {}
        
        # This part of the code is copied from your existing `if submit:` block
        for sensor in prod.get("sensors", []):
            item = sensor["item"].strip()
            
            def extract_ozcodes(sensor_item):
                return re.findall(r"(OZ[A-Z0-9_]+)", sensor_item.upper())

            # 1. OZCODE Based Confirmation
            ozcodes = extract_ozcodes(item) 
            if ozcodes:
                for ozcode in ozcodes:
                    if ozcode not in added_codes:
                        confirmed.append({"item": ozcode, "flag": "true_by_code"})
                        added_codes.add(ozcode)
                continue

            # 2. Normalize and check in sensor_variants
            symbol = normalize_name(item)
            if symbol and symbol in sensor_variants:
                if len(sensor_variants[symbol]) == 1:
                    code = sensor_variants[symbol][0][0]
                    if code not in added_codes:
                        confirmed.append({"item": code, "flag": "true_by_name"})
                        added_codes.add(code)
                else:
                    grouped_by_symbol.setdefault(symbol, []).append(item)
                continue

            # 3. Not found → skip
            continue
        
        # 4. User Dropdown Selection for multi-options
        for symbol, items in grouped_by_symbol.items():
            variants = [v[0] + " -> " + v[1] for v in sensor_variants[symbol]]
            for i, item in enumerate(items):
                prod_name = prod.get('name') or 'UnknownProduct'
                dropdown_key = f"{prod_name.replace(' ', '_')}_{symbol}_{i}"
                
                # Check if this dropdown has a stored selection
                if dropdown_key not in st.session_state.automatic_dropdowns:
                    st.session_state.automatic_dropdowns[dropdown_key] = variants[0]

                st.warning(f"❓ Confirm Variants for **{prod_name}** - Detected: '{item}'")
                
                selected_variant = st.selectbox(
                    f"Choose variant for '{item}'",
                    options=variants,
                    index=variants.index(st.session_state.automatic_dropdowns[dropdown_key]),
                    key=dropdown_key
                )
                
                st.session_state.automatic_dropdowns[dropdown_key] = selected_variant
                
                selected_code = selected_variant.split(" -> ")[0]
                if selected_code and selected_code not in added_codes:
                    confirmed.append({"item": selected_code, "flag": "true_by_name"})
                    added_codes.add(selected_code)

        # Final combined product block
        final_products.append({
            "product_name": prod["name"].split('-')[-1],
            "product_version": "1.1",
            "quantity": prod.get("quantity", 1),
            "product_type": prod.get("product_type", "SMART"),
            "sensors": [s["item"] for s in confirmed]
        })
    
    # Store the final payload in session state
    st.session_state.automatic_payload = {
        "organization": org,
        "account_manager": am_name,
        "delivery_terms": delivery_terms,
        "expected_shipment_date": expected_shipment_date.strftime("%Y-%m-%d"),
        "usecase": usecase,
        "solar_panel": Solar_panel,
        "solar_PSU_Cable": solar_PSU_Cable,
        "battery_backup": Battery_backup,
        "simcard_installation": Simcard_installation,
        "data_communication": Data_Communication,
        "country": Country,
        "logistics": logistics,
        "mcert_required": MCERT_Required,
        "po_number": gemini_json.get("po_number", ""),
        "billing_address": gemini_json.get("billing_address", ""),
        "billing_country": gemini_json.get("billing_country", ""),
        "shipping_address": gemini_json.get("shipping_address", ""),
        "shipping_country": gemini_json.get("shipping_country", ""),
        "products": final_products 
    }


# Step 3: On Run - check mode and run correct section
if submit:
    # Reset payloads on new submission
    st.session_state.manual_payload = None
    st.session_state.automatic_payload = None
    st.session_state.webhook_sent = False
    # Ensure the uploaded file exists before proceeding
    # 2. Handle file upload and store its bytes and name
    if not uploaded_pdf:
        st.error("Please upload a PDF file.")
    else:
        # Check if a new file has been uploaded. If so, update the session state.
        if st.session_state.uploaded_pdf_name != uploaded_pdf.name:
            st.session_state.pdf_bytes = uploaded_pdf.read()
            st.session_state.uploaded_pdf_name = uploaded_pdf.name
            st.session_state.extracted_meta = {}
            st.session_state.gemini_json = {}

        images = load_images_from_bytes(st.session_state.pdf_bytes)
        st.sidebar.image(images[0], caption="Preview", use_container_width=True)
        if mode == "Manual":
            with st.spinner("🔍 Extracting products & metadata from PO PDF..."):


                prompt = f"""
You are a document parser. From the uploaded PO PDF image, extract:
- products: list of product names from {valid_products}, each with its quantity
- po_number
- billing_address
- billing_country
- shipping_address
- shipping_country

Ignore unrelated lines (e.g. FREIGHT, SENSOR, GAS SAMPLING SYSTEM).

Return strictly in this JSON format:
{{
  "products": [
    {{ "name": "OIZ-POLLUDRONE", "quantity": 2 }},
    {{ "name": "OIZ-WS/WD",      "quantity": 1 }}
  ],
  "po_number": "12345",
  "billing_address": "...",
  "billing_country": "...",
  "shipping_address": "...",
  "shipping_country": "..."
}}
"""
            extracted = None
            for img in images:
                try:
                    res = model.generate_content([prompt, img])
                    candidate = json.loads(res.text.strip("```json\n").strip("```"))
                    if "products" in candidate:
                        extracted = candidate
                        break
                except Exception:
                    continue

            # always store a dict
            st.session_state.extracted_meta = extracted if isinstance(extracted, dict) else {
                "products": [],
                "po_number": "",
                "billing_address": "",
                "billing_country": "",
                "shipping_address": "",
                "shipping_country": ""
            }

            # ── Configure Each Product ──
            # ── Normalize extracted products ──
            meta_raw = st.session_state.extracted_meta
            if isinstance(meta_raw, str):
                try:
                    meta = json.loads(meta_raw)
                except json.JSONDecodeError:
                    meta = {}
            else:
                meta = meta_raw or {}

            # Build a list of {"name":…, "quantity":…}
            raw_products = meta.get("products", [])
            normalized = []
            for item in raw_products:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("product") or ""
                    qty  = item.get("quantity", 1)
                elif isinstance(item, str):
                    name = item
                    qty  = 1
                else:
                    continue
                if name:
                    normalized.append({"name": name, "quantity": qty})

            # ── Configure Each Product ──
            product_configs = []
            for idx, prod_info in enumerate(normalized, start=1):
                name     = prod_info["name"]
                quantity = prod_info["quantity"]

                with st.expander(f"⚙️ {name}", expanded=True):
                    st.write(f"**Quantity from PO:** {quantity}")
                    version = st.selectbox(
                        "🔢 Product Version",
                        ["1", "1.1", "1.2", "6.2", "6.3"],
                        key=f"ver_{idx}"
                    )
                    ptype = st.selectbox(
                        "🏷️ Product Type",
                        ["LITE", "SMART", "PRO", "MAX", "CUSTOM"],
                        key=f"type_{idx}"
                    )

                    allowed = product_sensors.get(name, [])
                    sensors_selected = []
                    for fam in allowed:
                        variants = sensor_variants.get(fam, [])

                        options = ["Not Needed"]  # default option
                        if variants:
                            options += [f"{code} → {desc}" for code, desc in variants]

                        choice = st.selectbox(
                            f"Select variant for {fam}",
                            options,
                            key=f"{name}_{fam}"
                        )

                        if choice != "Not Needed":
                            selected_code = choice.split(" → ")[0]
                            sensors_selected.append(selected_code)

                    product_configs.append({
                        "product_name":    name,
                        "product_version": version,
                        "quantity":        quantity,
                        "product_type":    ptype,
                        "sensors":         sensors_selected
                    })

            # ── Final JSON & Webhook ──
            if product_configs:
                st.session_state.manual_payload = {
                    "organization":           org,
                    "account_manager":        am_name,
                    "delivery_terms":         delivery_terms,
                    "expected_shipment_date": expected_shipment_date.strftime("%Y-%m-%d"),
                    "usecase":                usecase,
                    "solar_panel":            Solar_panel,
                    "solar_PSU_Cable":        solar_PSU_Cable,
                    "battery_backup":         Battery_backup,
                    "simcard_installation":   Simcard_installation,
                    "data_communication":     Data_Communication,
                    "country":                Country,
                    "logistics":              logistics,
                    "mcert_required":         MCERT_Required,
                    "po_number":              meta.get("po_number", ""),
                    "billing_address":        meta.get("billing_address", ""),
                    "billing_country":        meta.get("billing_country", ""),
                    "shipping_address":       meta.get("shipping_address", ""),
                    "shipping_country":       meta.get("shipping_country", ""),
                    "products":               product_configs
               }

            
        elif mode == "Automatic":
            # ------------------ Gemini Prompt + Extract Function -----------------
            with st.spinner("Running Gemini and matching..."):
                # Use the 'images' list that was already loaded
                gemini_json = extract_from_images(images)
        
            st.subheader("✅ Gemini Extracted Data")
            st.json(gemini_json)

                # Store Gemini JSON in session to use outside spinner
            st.session_state.gemini_json = gemini_json
    pass

# Renders the dropdowns and final JSON for Automatic mode, if the data exists.
if st.session_state.mode == "Automatic" and st.session_state.gemini_json:
    process_automatic_mode(
        st.session_state.gemini_json,
        org, am_name, delivery_terms, expected_shipment_date,
        usecase, Solar_panel, solar_PSU_Cable, Battery_backup,
        Simcard_installation, Data_Communication, Country, logistics,
        MCERT_Required
    )
        
# --- MANUAL MODE RESULTS ---
if st.session_state.manual_payload:
    # Use the unified function to display results
    st.subheader("📥 Final JSON (Manual)")
    st.json(st.session_state.manual_payload)
    st.download_button(
        "⬇ Download JSON",
        data=json.dumps(st.session_state.manual_payload, indent=2),
        file_name="sensor_output.json",
        key=f"download_json_{datetime.now().isoformat()}"
    )
    if st.button("📤 Send to Webhook (Manual)"):
        webhook_url = "https://agent.oizom.com/webhook-test/04c9dbd0-d0a2-4ab0-8a46-175491d98258"
        try:
            resp = requests.post(webhook_url, json=st.session_state.manual_payload)
            if resp.status_code == 200:
                st.session_state.webhook_sent = True
                st.success("✅ Sent successfully!")
            else:
                st.error(f"❌ Error: {resp.status_code} — {resp.text}")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

    if st.session_state.webhook_sent:
        st.success("✅ Sent successfully!")
        pass

# --- AUTOMATIC MODE RESULTS ---
if st.session_state.automatic_payload:
    # Use the unified function to display results
    st.subheader("📥 Final JSON (Automatic)")
    st.json(st.session_state.automatic_payload)
    #st.json(final_json)
    st.download_button(
        "⬇ Download JSON",
        data=json.dumps(st.session_state.automatic_payload, indent=2),
        file_name="sensor_output.json",
        key=f"download_json_{datetime.now().isoformat()}"
    )
    if st.button("📤 Send to Webhook (Automatic)"):
        webhook_url = "https://agent.oizom.com/webhook-test/04c9dbd0-d0a2-4ab0-8a46-175491d98258"
        try:
            resp = requests.post(webhook_url, json=st.session_state.automatic_payload)
            if resp.status_code == 200:
                st.session_state.webhook_sent = True
                st.success("✅ Sent successfully!")
            else:
                st.error(f"❌ Error: {resp.status_code} — {resp.text}")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")
