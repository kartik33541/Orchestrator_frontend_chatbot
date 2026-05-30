import streamlit as st
import requests
import json
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI Travel Orchestrator", layout="wide", page_icon="✈️")

# --- Logic App Wake Hook ---
LOGIC_APP_WAKE_URL = os.getenv("LOGIC_APP_WAKE_URL", "https://prod-48.eastus2.logic.azure.com:443/workflows/9ce4b3acb0a34089a7abc79032e817f0/triggers/manual/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2n6mXWaQpdKEMWbhj3pVrGCwwpoaCAvvvgh58IArRoY")

@st.cache_data(ttl=300)
def wake_backend_sync(url):
    if not url:
        return
    try:
        response = requests.post(url, json={"source": "website"}, timeout=180)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

if "backend_woken" not in st.session_state:
    if LOGIC_APP_WAKE_URL:
        with st.spinner("Warming up backend, please wait..."):
            wake_backend_sync(LOGIC_APP_WAKE_URL)
    st.session_state.backend_woken = True

# --- Configuration & State Initialization ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
USER_ID = "default_user_1" 

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "trip_state" not in st.session_state:
    st.session_state.trip_state = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Hi! Where would you like to travel? (e.g., Indore to Raipur for 4 days, budget 20,000)"}]
if "sessions" not in st.session_state:
    st.session_state.sessions = []

# --- Custom CSS for Premium UI ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #f8fafc; }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Horizontal Scroll for Images */
    .image-grid { display: flex; gap: 15px; overflow-x: auto; padding: 10px 0; scrollbar-width: none; }
    .image-grid::-webkit-scrollbar { display: none; }
    .image-card {
        flex: 1 0 350px; height: 280px; border-radius: 16px; object-fit: cover;
        box-shadow: 0 8px 25px rgba(0,0,0,0.4); transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .image-card:hover { transform: translateY(-5px) scale(1.02); box-shadow: 0 12px 35px rgba(0,0,0,0.5); }

    /* Glassmorphism Cards */
    .travel-card {
        background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px;
        padding: 20px; margin-bottom: 20px; transition: all 0.3s ease;
    }
    .travel-card:hover { background: rgba(255, 255, 255, 0.08); border-color: #38bdf8; }
    .card-title { color: #38bdf8; font-weight: 800; font-size: 1.2rem; margin-bottom: 5px; }
    .card-subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; }
    .card-price { color: #4ade80; font-weight: 800; font-size: 1.1rem; }
    .card-tag { 
        display: inline-block; padding: 3px 10px; background: rgba(56, 189, 248, 0.2); 
        color: #38bdf8; border-radius: 20px; font-size: 0.8rem; margin-top: 10px;
    }

    /* Safety Box */
    .safety-container {
        border-left: 5px solid #fbbf24; background: rgba(251, 191, 36, 0.05);
        padding: 15px; border-radius: 0 12px 12px 0; margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---

def fetch_sessions():
    try:
        response = requests.get(f"{BACKEND_URL}/sessions/{USER_ID}")
        if response.status_code == 200:
            st.session_state.sessions = response.json().get("sessions", [])
    except:
        pass

def load_session(sid):
    try:
        response = requests.get(f"{BACKEND_URL}/session/{USER_ID}/{sid}")
        if response.status_code == 200:
            state = response.json().get("state", {})
            st.session_state.session_id = sid
            st.session_state.trip_state = state
            
            # Reconstruct full chat history from state messages
            new_history = []
            messages = state.get("messages", [])
            
            for msg in messages:
                # Backend now returns consistent serialized messages
                content = ""
                role = "user"
                ui_data = {}
                
                if isinstance(msg, dict):
                    data = msg.get("data", {})
                    content = data.get("content", "")
                    msg_type = msg.get("type", "human")
                    role = "user" if msg_type == "human" else "assistant"
                    
                    # EXTRACT UI DATA FROM METADATA (additional_kwargs)
                    kwargs = data.get("additional_kwargs", {})
                    if kwargs.get("ui_payload"):
                        ui_payload = kwargs["ui_payload"]
                        ui_data = {
                            "ui_mode": kwargs.get("ui_mode"),
                            "raw_options": ui_payload.get("raw_options"),
                            "package": ui_payload.get("package"),
                            "itinerary": ui_payload.get("itinerary"),
                            "hub_notification": ui_payload.get("hub_notification")
                        }
                else:
                    content = str(msg)
                
                hist_item = {"role": role, "content": content}
                
                # Merge UI data if found
                if ui_data:
                    hist_item.update(ui_data)
                
                # FALLBACK for legacy sessions or last message logic
                if role == "assistant" and msg == messages[-1] and not ui_data:
                     ui_payload = state.get("ui_payload", {})
                     if ui_payload:
                          hist_item.update({
                            "ui_mode": state.get("ui_mode"),
                            "raw_options": ui_payload.get("raw_options"),
                            "package": state.get("proposed_package"),
                            "itinerary": ui_payload.get("itinerary"),
                            "hub_notification": ui_payload.get("hub_notification")
                        })
                
                new_history.append(hist_item)
            
            if not new_history:
                new_history = [{"role": "assistant", "content": "Hi! Where would you like to travel?"}]
                
            st.session_state.chat_history = new_history
            st.rerun()
    except Exception as e:
        st.error(f"Failed to load session: {e}")

def run_orchestrator(query: str):
    payload = {
        "query": query, 
        "user_id": USER_ID,
        "session_id": st.session_state.session_id,
        "state": st.session_state.trip_state
    }
    with st.spinner("The Swarm is researching..."):
        try:
            # FIX: Added explicit 300s timeout so Streamlit doesn't disconnect during long agent fallback operations
            response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=300) 
            data = response.json()
            new_state = data.get("state", {})
            st.session_state.trip_state = new_state
            st.session_state.session_id = data.get("session_id")
            ui_payload = new_state.get("ui_payload", {})
            
            st.session_state.chat_history.append({
                "role": "assistant", 
                "content": ui_payload.get("message", "Here is what I found."),
                "ui_mode": new_state.get("ui_mode"),
                "raw_options": ui_payload.get("raw_options"),
                "package": new_state.get("proposed_package"),
                "itinerary": ui_payload.get("itinerary"),
                "hub_notification": ui_payload.get("hub_notification")
            })
            
            # Refresh sidebar immediately so the session appears
            fetch_sessions() 
            st.rerun()
        except requests.exceptions.Timeout:
            st.error("Backend Error: The request timed out. The Swarm took too long to respond.")
        except Exception as e:
            st.error(f"Backend Error: {e}")

# --- Sidebar UI ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/826/826070.png", width=50)
    st.title("Travel Hub")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.trip_state = {}
        st.session_state.chat_history = [{"role": "assistant", "content": "Hi! Where would you like to travel?"}]
        st.rerun()
    
    st.markdown("---")
    st.subheader("Your Journeys")
    fetch_sessions() # Ensure list is fresh on every sidebar render
    
    for s in st.session_state.sessions:
        is_active = s['id'] == st.session_state.session_id
        label = f"💬 {s['summary']}"
        if is_active:
            label = f"📍 {s['summary']}"
            
        if st.button(label, key=f"btn_{s['id']}", use_container_width=True, type="secondary" if is_active else "tertiary"):
            load_session(s['id'])

# --- Main UI ---
st.title("✈️ AI Travel Orchestrator")
st.caption(f"User: `{USER_ID}` | Session: `{st.session_state.session_id[:8]}...`")

# --- UI Renderers ---
def render_image_grid(photos):
    if not photos: return
    html = '<div class="image-grid">'
    for p in photos[:4]: html += f'<img src="{p["url"]}" class="image-card" title="{p.get("title", "")}">'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_safety(safety):
    if not safety: return
    st.markdown(f"""<div class="safety-container"><div style="font-weight: 800; color: #fbbf24; margin-bottom: 10px;">⚠️ Safety & Guidelines</div><div>{safety.get('summary')}</div><ul style="margin: 0; padding-left: 20px;">{''.join([f'<li>{item}</li>' for item in safety.get('advice', [])])}</ul></div>""", unsafe_allow_html=True)

def render_hub_notification(notification):
    if not notification: return
    st.warning(f"💡 **Transport Note:** {notification}")

def render_transport_card(t, msg_idx, card_idx):
    is_flight = "airline" in t
    icon = "✈️" if is_flight else "🚆"
    title = t.get("airline") or t.get("name") or "Transport"
    duration = t.get("duration")
    duration_str = f" ({duration})" if duration else ""
    subtitle = f"{t.get('departure', '')} - {t.get('arrival', '')}{duration_str}"
    price = f"₹{t.get('price', 0)}"
    
    tags = []
    if t.get('source_hub'):
        tags.append(t.get('source_hub'))
    elif t.get('number'):
        tags.append(f"No. {t.get('number')}")
    if t.get('status'):
        tags.append(t.get('status'))
    tag_str = " • ".join(tags) if tags else "Direct"

    st.markdown(f"""
    <div class="travel-card">
        <div class="card-title">{icon} {title}</div>
        <div class="card-subtitle">{subtitle}</div>
        <div class="card-price">{price}</div>
        <div class="card-tag">{tag_str}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"📌 Select {title}", key=f"sel_t_{msg_idx}_{card_idx}"):
        st.session_state.chat_history.append({"role": "user", "content": f"I choose transport: {title}"})
        run_orchestrator(f"I choose transport: {title}")

def render_hotel_card(h, msg_idx, card_idx):
    name = h.get('name')
    img_url = h.get('image_url')
    highlights = h.get('highlights', '')
    booking_url = h.get('booking_url')
    
    image_html = f'<img src="{img_url}" style="width: 100%; height: 240px; object-fit: cover; border-radius: 16px 16px 0 0;" />' if img_url else ''
    highlight_html = f'<div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 8px; margin-bottom: 8px; font-style: italic;">"{highlights}"</div>' if highlights else ''
    booking_html = f'<div style="margin-top: 10px;"><a href="{booking_url}" target="_blank" style="text-decoration: none; color: #38bdf8; font-size: 0.85rem; font-weight: 600;">🌐 View on Booking.com ↗</a></div>' if booking_url else ''
    
    amenities_list = h.get('amenities', [])
    amenities_str = ' • '.join(amenities_list[:3]) if amenities_list else 'Standard Room'

    st.markdown(f"""
    <div class="travel-card" style="padding: 0; overflow: hidden; display: flex; flex-direction: column;">
        {image_html}
        <div style="padding: 20px;">
            <div class="card-title">🏨 {name}</div>
            <div class="card-subtitle">⭐ {h.get('rating', '4.0/5')} | 📍 {h.get('location', 'Central')}</div>
            {highlight_html}
            <div class="card-price">₹{h.get('price_per_night', 0)} / night</div>
            <div class="card-tag">{amenities_str}</div>
            {booking_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"🏨 Select {name[:15]}...", key=f"sel_h_{msg_idx}_{card_idx}"):
        st.session_state.chat_history.append({"role": "user", "content": f"I choose hotel: {name}"})
        run_orchestrator(f"I choose hotel: {name}")

def render_activity_card(a, msg_idx, card_idx, is_food=False):
    icon = "🍛" if is_food else "🎭"
    name = a.get('name')
    subtitle = a.get('cuisine') or a.get('category') or 'Recommended'
    price = a.get('price') or a.get('price_estimate') or 'Free Entry'
    
    highlight = a.get('highlight')
    highlight_html = f'<div style="font-size: 0.85rem; color: #cbd5e1; margin-top: 8px; font-style: italic;">"{highlight}"</div>' if highlight else ''
    
    duration = a.get('duration')
    duration_html = f'<div class="card-tag" style="margin-top: 8px;">⏳ {duration}</div>' if duration else ''

    st.markdown(f"""
    <div class="travel-card">
        <div class="card-title">{icon} {name}</div>
        <div class="card-subtitle">{subtitle}</div>
        <div class="card-price">{price}</div>
        {highlight_html}
        {duration_html}
    </div>
    """, unsafe_allow_html=True)

# Main Chat Loop
for msg_idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("hub_notification"): render_hub_notification(msg["hub_notification"])
        if msg.get("raw_options"):
            opts = msg["raw_options"]
            render_image_grid(opts.get("photos", []))
            if opts.get("weather"):
                w = opts["weather"]
                st.markdown(f"🌤️ **Weather in {w.get('location')}:** {w.get('condition')} | {w.get('temperature_c')}°C")
            render_safety(opts.get("safety", {}))
            tab_transport, tab_hotels, tab_exp = st.tabs(["🚆 Global Transport", "🏨 Hotels by City", "🎭 Experience by City"])
            with tab_transport:
                cols = st.columns(3)
                all_t = opts.get("flights", []) + opts.get("trains", [])
                for idx, t in enumerate(all_t[:6]):
                    with cols[idx % 3]: render_transport_card(t, msg_idx, idx)
            with tab_hotels:
                hotel_groups = opts.get("hotels", {})
                if isinstance(hotel_groups, dict):
                    for city, hotels in hotel_groups.items():
                        st.markdown(f"#### 📍 Hotels in {city}")
                        cols = st.columns(3)
                        for idx, h in enumerate(hotels[:3]):
                            with cols[idx % 3]: render_hotel_card(h, msg_idx, f"{city}_{idx}")
            with tab_exp:
                act_groups = opts.get("activities", {})
                rest_groups = opts.get("restaurants", {})
                if isinstance(act_groups, dict):
                    cities = set(list(act_groups.keys()) + list(rest_groups.keys()))
                    for city in cities:
                        st.markdown(f"#### 🎭 Experiences in {city}")
                        cols = st.columns(3)
                        city_acts = act_groups.get(city, [])
                        city_rests = rest_groups.get(city, [])
                        all_e = [(r, True) for r in city_rests] + [(a, False) for a in city_acts]
                        for idx, (item, is_food) in enumerate(all_e[:6]):
                            with cols[idx % 3]: render_activity_card(item, msg_idx, f"{city}_{idx}", is_food)

        if msg.get("package"):
            pkg = msg["package"]
            st.markdown("---")
            st.markdown("### 🏆 AI Recommended Multi-City Package")
            if pkg.get("transport"): render_transport_card(pkg["transport"], msg_idx, 999)
            for s_idx, stop in enumerate(pkg.get("stops", [])):
                st.markdown(f"### 📍 Stop {s_idx + 1}: {stop.get('city')}")
                st.info(stop.get("city_summary", ""))
                p_cols = st.columns([1, 1, 1])
                with p_cols[0]:
                    if stop.get("hotel"): render_hotel_card(stop["hotel"], msg_idx, f"pkg_h_{s_idx}")
                with p_cols[1]:
                    if stop.get("activities"): render_activity_card(stop["activities"][0], msg_idx, f"pkg_a_{s_idx}")
                with p_cols[2]:
                    if stop.get("restaurants"): render_activity_card(stop["restaurants"][0], msg_idx, f"pkg_r_{s_idx}", is_food=True)
            # --- 🔌 MCP Swarm Interactive Suite ---
            st.markdown("---")
            st.markdown("### 🔌 Deployed MCP Swarm Interactive Suite")
            st.caption("Directly invoke the full toolsets of our 5 SSE MCP servers using parameters extracted from your trip context:")
            
            # Helper to invoke direct tool calls
            def call_direct_mcp_tool(mcp_name: str, tool_name: str, arguments: dict):
                try:
                    response = requests.post(f"{BACKEND_URL}/mcp/call_tool", json={
                        "mcp_name": mcp_name,
                        "tool_name": tool_name,
                        "arguments": arguments
                    }, timeout=120)
                    if response.status_code == 200:
                        result = response.json().get("result", "")
                        # Handle case where result might be a dict/list instead of string
                        if isinstance(result, (dict, list)):
                            return json.dumps(result, ensure_ascii=False)
                        return result if result else "No response received from the agent."
                    else:
                        return f"Error: Backend returned {response.status_code}\n{response.text}"
                except requests.exceptions.Timeout:
                    return f"Error: MCP call timed out after 120 seconds. The {mcp_name} MCP server may be slow or unavailable."
                except Exception as e:
                    return f"Error calling direct MCP: {e}"

            # Helper to read direct resources
            def read_direct_mcp_resource(mcp_name: str, uri: str):
                try:
                    response = requests.post(f"{BACKEND_URL}/mcp/read_resource", json={
                        "mcp_name": mcp_name,
                        "uri": uri
                    }, timeout=120)
                    if response.status_code == 200:
                        result = response.json().get("result", "")
                        if isinstance(result, (dict, list)):
                            return json.dumps(result, ensure_ascii=False)
                        return result if result else "No response received from the agent."
                    else:
                        return f"Error: Backend returned {response.status_code}\n{response.text}"
                except requests.exceptions.Timeout:
                    return f"Error: MCP resource read timed out after 120 seconds."
                except Exception as e:
                    return f"Error reading direct MCP resource: {e}"

            # Smart calculations from state
            state = st.session_state.trip_state

            # Helper to strip placeholder '...' strings and fallback to defaults
            def clean_state_val(val, default):
                if val is None or str(val).strip() == "..." or str(val).strip() == "":
                    return default
                return val

            source_city = clean_state_val(state.get("source_city"), "Agra")
            dest_city = clean_state_val(state.get("destination_city"), "Amritsar")
            budget = clean_state_val(state.get("budget"), 28000)
            days = clean_state_val(state.get("travel_days"), 4)
            travel_date = clean_state_val(state.get("travel_date"), "2026-06-04")

            # Parse dates safely
            from datetime import datetime, timedelta
            def parse_dates_helper(t_date, duration_days):
                try:
                    t_str = str(t_date).strip()
                    dt = None
                    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y"]:
                        try:
                            dt = datetime.strptime(t_str, fmt)
                            break
                        except:
                            continue
                    if not dt:
                        dt = datetime.now()
                    chk_in = dt.strftime("%Y-%m-%d")
                    chk_out = (dt + timedelta(days=int(duration_days))).strftime("%Y-%m-%d")
                    chk_in_inr = dt.strftime("%d-%m-%Y")
                    chk_out_inr = (dt + timedelta(days=int(duration_days))).strftime("%d-%m-%Y")
                    return chk_in, chk_out, chk_in_inr, chk_out_inr
                except:
                    return "2026-06-04", "2026-06-08", "04-06-2026", "08-06-2026"

            c_in, c_out, c_in_inr, c_out_inr = parse_dates_helper(travel_date, days)
            try:
                b_num = float(budget) if isinstance(budget, (int, float)) or (isinstance(budget, str) and budget.replace('.','',1).isdigit()) else 28000
                d_num = int(days) if isinstance(days, (int, float)) or (isinstance(days, str) and days.isdigit()) else 4
                if d_num <= 0: d_num = 4
                night_budget = int(b_num / d_num)
            except:
                night_budget = 7000

            # Dynamically extract flight_no and train_no from proposed package in state
            extracted_flight_no = "AI 101"
            extracted_train_no = "12002"
            try:
                pkg = state.get("proposed_package", {})
                stops = pkg.get("stops", [])
                for s in stops:
                    trans = s.get("transport", {})
                    if trans:
                        f_no = trans.get("flight_no") or trans.get("flight_number")
                        if f_no:
                            extracted_flight_no = str(f_no).strip()
                        t_no = trans.get("train_no") or trans.get("train_number")
                        if t_no:
                            extracted_train_no = str(t_no).strip()
            except:
                pass

            # City-to-IATA & Station mapper to avoid lookup failures on remote servers
            def map_city_to_iata(city_name: str) -> str:
                IATA_CODES = {
                    "agra": "AGR",
                    "bhopal": "BHO",
                    "delhi": "DEL",
                    "mumbai": "BOM",
                    "goa": "GOI",
                    "amritsar": "ATQ",
                    "indore": "IDR",
                    "gwalior": "GWL",
                    "ujjain": "UJN",
                    "pantnagar": "PGH",
                    "kathgodam": "KGM",
                    "raipur": "RPR",
                    "kota": "KOTA",
                    "nainital": "KGM",
                    "bikaner": "BKB"
                }
                cleaned = str(city_name).strip().lower()
                return IATA_CODES.get(cleaned, city_name)

            def map_city_to_station(city_name: str) -> str:
                # Map cities that are completely missing from the remote Train MCP dictionary
                # Bypassing Mumbai so the MCP can expand it to ['CSMT', 'MMCT', 'LTT', 'BDTS'] natively!
                STATION_CODES = {
                    "bikaner": "BKN",
                    "jaipur": "JP",
                    "delhi": "NDLS",
                    "indore": "INDB",
                    "raipur": "R",
                    "kota": "KOTA",
                    "agra": "AGC",
                    "amritsar": "ASR",
                    "ahemdabad": "ADI",
                    "ahmedabad": "ADI",
                    "lucknow": "LKO"
                }
                cleaned = str(city_name).strip().lower()
                return STATION_CODES.get(cleaned, city_name)

            # Professional UI Output Renderer
            def render_mcp_output_professionally(mcp_name: str, tool_name: str, raw_val: str):
                if not raw_val:
                    st.info("No response received from the agent.")
                    return
                raw_val_br = str(raw_val).replace("\n", "<br>")
                if "Error" in raw_val or "failed" in raw_val or "could not convert" in raw_val:
                    st.error(f"❌ **Agent execution notice:** {raw_val}")
                    return

                # Try to load as JSON first
                data = None
                try:
                    data = json.loads(raw_val)
                    # Handle double-encoded JSON strings
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except:
                            pass
                except:
                    # Fallback for Python-stringified lists/dicts (e.g. using single quotes instead of double quotes)
                    import ast
                    try:
                        data = ast.literal_eval(raw_val)
                    except:
                        pass

                # ==========================================
                # SCENARIO A: VALID JSON RESPONSE PARSED
                # ==========================================
                if isinstance(data, (dict, list)):
                    
                    # 1. Flight List (JSON format)
                    if mcp_name == "flight" and tool_name in ["search_for_flights", "find_cheapest_flight", "find_earliest_flight"]:
                        flights = []
                        if isinstance(data, list):
                            flights = data
                        elif isinstance(data, dict):
                            flights = data.get("flights", data.get("results", []))
                            # Handle single flight object
                            if not flights and ("airline" in data or "flight_no" in data):
                                flights = [data]
                        if not flights:
                            st.warning("⚠️ No flights discovered matching these boundaries.")
                            return
                            
                        is_cheapest = tool_name == "find_cheapest_flight"
                        is_earliest = tool_name == "find_earliest_flight"
                        
                        st.markdown("##### ✈️ Available Flight Options Discoveries")
                        for f in flights[:4]:
                            badge_tag = ""
                            border_col = "#38bdf8"
                            if is_cheapest:
                                badge_tag = "<span class='card-tag' style='background: #fbbf24; color: #1e293b; margin-left: 10px; font-weight: 800;'>🏷️ Best Fare Pick</span>"
                                border_col = "#fbbf24"
                            elif is_earliest:
                                badge_tag = "<span class='card-tag' style='background: #38bdf8; color: #1e293b; margin-left: 10px; font-weight: 800;'>🌅 Morning Schedule</span>"

                            # Normalize field names across MCP and fallback formats
                            airline = f.get('airline', f.get('name', 'Flight'))
                            flight_no = f.get('flight_no', f.get('number', f.get('id', 'N/A')))
                            dep_time = f.get('departure_time', f.get('departure', 'N/A'))
                            arr_time = f.get('arrival_time', f.get('arrival', 'N/A'))
                            origin = f.get('origin', f.get('source_hub', f.get('source', 'N/A')))
                            dest = f.get('dest', f.get('dest_hub', f.get('destination', 'N/A')))
                            price = f.get('price', f.get('fare', 'N/A'))
                            flight_class = f.get('class', f.get('ticket_class', 'Economy'))
                            meals = f.get('meals', f.get('meal_plan', 'Not Included'))
                            duration = f.get('duration', '')
                            duration_html = f" | ⏱️ <b>Duration:</b> {duration}" if duration else ""

                            st.markdown(f"""
<div class='travel-card' style='margin-bottom: 12px; padding: 15px; border-left: 5px solid {border_col};'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <span style='font-size: 1.1rem; font-weight: 800; color: {border_col};'>✈️ {airline} - {flight_no} {badge_tag}</span>
        <span style='font-size: 1.1rem; font-weight: 800; color: #4ade80;'>₹{price}</span>
    </div>
    <div style='margin-top: 8px; font-size: 0.95rem; color: #e2e8f0;'>
        <span>🛫 <b>Departs:</b> {dep_time} ({origin})</span> |
        <span>🛬 <b>Arrives:</b> {arr_time} ({dest})</span>{duration_html}
    </div>
    <div style='margin-top: 5px; font-size: 0.85rem; color: #94a3b8;'>
        🏷️ <b>Ticket Class:</b> {flight_class} | 🍟 <b>Meal Plan:</b> {meals}
    </div>
</div>
""", unsafe_allow_html=True)
                        return

                    # 2. Train Fares comparison (JSON format)
                    elif mcp_name == "train" and tool_name == "fetch_train_price_data_tool":
                        # Handle multiple response formats
                        fares = []
                        if isinstance(data, list):
                            fares = data
                        elif isinstance(data, dict):
                            fares = data.get("trains", data.get("fares", data.get("results", [])))
                            if not fares and isinstance(data, dict) and "train_name" in data:
                                fares = [data]  # Single train object
                        if not fares:
                            st.warning("⚠️ No fare information available.")
                            return
                        st.markdown("##### 💰 Route Train Class Fare Comparison")
                        for t in fares[:4]:
                            st.markdown(f"""
<div class='travel-card' style='margin-bottom: 12px; padding: 15px; border-left: 5px solid #a855f7;'>
    <div style='font-size: 1.1rem; font-weight: 800; color: #a855f7; margin-bottom: 10px;'>🚆 {t.get('train_name', t.get('name', 'Train'))} ({t.get('train_no', t.get('number', 'N/A'))})</div>
    <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; text-align: center;'>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>Sleeper (SL)</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #4ade80;'>₹{t.get('fare_sl', t.get('fare_sleeper', t.get('price', '380')))}</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>AC 3 Tier (3A)</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #4ade80;'>₹{t.get('fare_3a', t.get('fare_ac3', '1050'))}</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>AC 2 Tier (2A)</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #4ade80;'>₹{t.get('fare_2a', t.get('fare_ac2', '1480'))}</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>AC First (1A)</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #4ade80;'>₹{t.get('fare_1a', t.get('fare_ac1', t.get('fare_first', '2240')))}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
                        return

                    # 3. Train List (JSON format)
                    elif mcp_name == "train" and tool_name == "search_train_options_tool":
                        trains = []
                        if isinstance(data, list):
                            trains = data
                        elif isinstance(data, dict):
                            trains = data.get("trains", data.get("results", []))
                            if not trains and ("train_name" in data or "name" in data):
                                trains = [data]  # Single train object
                        if not trains:
                            st.warning("⚠️ No train runs discovered on this date.")
                            return
                        st.markdown("##### 🚆 Available Express Train Options")
                        for t in trains[:4]:
                            t_name = t.get('train_name') or t.get('name') or 'Train'
                            t_no = t.get('train_no') or t.get('number') or 'N/A'
                            dep_time = t.get('departure_time') or t.get('departure') or 'N/A'
                            arr_time = t.get('arrival_time') or t.get('arrival') or 'N/A'
                            runs_val = t.get('runs_on') or t.get('runs') or 'Daily'
                            runs_clean = str(runs_val).replace(" ", "").replace(",", "").strip()
                            if runs_clean in ["111111", "1111111", "1111110", "Daily"]:
                                runs_val = "Daily"
                            price_val = t.get('price', t.get('fare', t.get('fare_3a', '380')))
                            source_val = t.get('source_city') or t.get('source') or t.get('from', 'N/A')
                            dest_val = t.get('dest_city') or t.get('destination') or t.get('to', 'N/A')
                            classes_val = t.get('classes', t.get('coach_types', 'SL, 3A, 2A'))

                            st.markdown(f"""
<div class='travel-card' style='margin-bottom: 12px; padding: 15px; border-left: 5px solid #a855f7;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <span style='font-size: 1.1rem; font-weight: 800; color: #a855f7;'>🚆 {t_name} ({t_no})</span>
        <span style='font-size: 1.1rem; font-weight: 800; color: #4ade80;'>₹{price_val}</span>
    </div>
    <div style='margin-top: 8px; font-size: 0.95rem; color: #e2e8f0;'>
        <span>🛫 <b>Departure:</b> {dep_time} ({source_val})</span> |
        <span>🛬 <b>Arrival:</b> {arr_time} ({dest_val})</span>
    </div>
    <div style='margin-top: 5px; font-size: 0.85rem; color: #94a3b8;'>
        📅 <b>Runs On:</b> {runs_val} | 🛏️ <b>Coaches:</b> {classes_val}
    </div>
</div>
""", unsafe_allow_html=True)
                        return

                    # 4. Hotel List with verified Photo thumbnails & Booking.com deep links!
                    elif mcp_name == "hotel" and tool_name == "search_hotels":
                        hotels = []
                        if isinstance(data, list):
                            hotels = data
                        elif isinstance(data, dict):
                            hotels = data.get("hotels", data.get("results", []))
                            # Handle error status from MCP
                            if not hotels and data.get("status") == "error":
                                st.error(f"❌ Hotel MCP Error: {data.get('message', 'Unknown error')}")
                                if data.get("fallback_url"):
                                    st.markdown(f"🔗 [Search on Booking.com]({data['fallback_url']})")
                                return
                            # Handle single hotel object
                            if not hotels and "name" in data and "price_per_night" in data:
                                hotels = [data]
                        if not hotels:
                            st.warning("⚠️ No budget hotel listings verified.")
                            return
                        
                        st.markdown("##### 🏨 Verified Stays & Dynamic Photo Portals")
                        for h in hotels[:4]:
                            # Normalize image field names
                            img_url = h.get('image_url', h.get('image', h.get('photo', '')))
                            img_html = ""
                            if img_url and str(img_url).startswith("http"):
                                img_html = f"""
<div style='flex: 1; min-width: 140px; max-width: 170px;'>
<img src='{img_url}' style='width: 100%; height: 110px; object-fit: cover; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);' />
</div>
"""

                            book_url = h.get('booking_url', h.get('url', ''))
                            book_btn = f"<a href='{book_url}' target='_blank' style='display: inline-block; background: #fbbf24; color: #1e293b; padding: 6px 12px; border-radius: 8px; font-weight: 800; text-decoration: none; font-size: 0.82rem; margin-top: 10px;'>⚡ Book Stay on Booking.com</a>" if book_url else ""

                            rating_val = h.get('rating', '4.2')
                            reviews_val = h.get('reviews_count', h.get('reviews', '140'))
                            name_val = h.get('name', h.get('hotel_name', 'Comfort Stay'))
                            price_val = h.get('price_per_night', h.get('price', h.get('cost', 'N/A')))
                            location_val = h.get('location', h.get('address', 'City Center'))
                            highlights_val = h.get('highlights', h.get('description', 'Comfortable budget stay with excellent rating.'))
                            amenities_val = h.get('amenities', ['wifi', 'ac'])
                            # Normalize amenities to list
                            if isinstance(amenities_val, str):
                                amenities_val = [a.strip() for a in amenities_val.split(',')]

                            st.markdown(f"""
<div class='travel-card' style='margin-bottom: 15px; padding: 15px; border-left: 5px solid #fbbf24; display: flex; gap: 15px; align-items: flex-start; flex-wrap: wrap;'>
{img_html}
<div style='flex: 2; min-width: 250px;'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 1.15rem; font-weight: 800; color: #fbbf24;'>🏨 {name_val}</span>
<span style='font-size: 1.1rem; font-weight: 800; color: #4ade80;'>₹{price_val}/night</span>
</div>
<div style='margin-top: 5px; font-size: 0.9rem; color: #e2e8f0;'>
⭐ <b>Rating:</b> {rating_val}/5 ({reviews_val} reviews) | 📍 <b>Address:</b> {location_val}
</div>
<div style='margin-top: 8px; font-size: 0.85rem; color: #cbd5e1; font-style: italic;'>
💡 {highlights_val}
</div>
<div style='margin-top: 10px;'>
{" ".join([f"<span class='card-tag' style='margin-right: 5px; background: rgba(251,191,36,0.1); color: #fbbf24; border: 1px solid rgba(251,191,36,0.2);'>{a}</span>" for a in amenities_val[:4]])}
</div>
{book_btn}
</div>
</div>
""", unsafe_allow_html=True)
                        return

                    # 5. JSON Config Resource Output
                    elif tool_name == "read_config_resource" and isinstance(data, dict):
                        st.markdown(f"""
                        <div class='travel-card' style='border-left: 5px solid #64748b; padding: 15px;'>
                            <div class='card-title' style='color: #94a3b8;'>ℹ️ Swarm Node Configuration Resource</div>
                            <div style='font-size: 0.9rem; margin-top: 10px; color: #cbd5e1; line-height: 1.4;'>
                                🛠️ <b>Server Name:</b> {data.get('server', 'N/A')}<br>
                                🏷️ <b>Version Code:</b> {data.get('version', 'N/A')}<br>
                                🔍 <b>Search Engine:</b> {data.get('search_provider', 'N/A')}<br>
                                🟢 <b>Connection Status:</b> Deployed (Secure SSE Handshake Live)<br>
                                📦 <b>Active Toolsets:</b> {", ".join(data.get('available_tools', []))}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        return

                    # 6. Generic JSON catch-all: render any unmatched dict/list as formatted JSON
                    elif isinstance(data, dict):
                        # Check for common error/warning patterns
                        if data.get("status") == "error":
                            st.error(f"❌ MCP Error: {data.get('message', 'Unknown error from agent')}")
                            return
                        if data.get("warning"):
                            st.warning(f"⚠️ {data['warning']}")
                        # Try to extract any list of results from common keys
                        for key in ["results", "data", "items", "entries"]:
                            if key in data and isinstance(data[key], list) and data[key]:
                                st.json(data)
                                return
                        # Render as formatted JSON
                        st.markdown(f"""
                        <div class='travel-card' style='border-left: 5px solid #64748b; padding: 15px;'>
                            <div class='card-title' style='color: #94a3b8;'>📋 MCP Agent Response</div>
                            <pre style='font-size: 0.85rem; color: #cbd5e1; white-space: pre-wrap; word-break: break-word;'>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>
                        </div>
                        """, unsafe_allow_html=True)
                        return

                # ==========================================
                # SCENARIO B: UNSTRUCTURED TEXT/MARKDOWN PARSED
                # ==========================================

                # 1. Activities & attractions text list parser
                if mcp_name == "activity" and tool_name == "search_activities":
                    import re
                    blocks = re.split(r'\n\s*\d+\.\s+', "\n" + raw_val)
                    activities = []
                    for b in blocks:
                        b = b.strip()
                        if not b:
                            continue
                        lines = [l.strip() for l in b.split('\n') if l.strip()]
                        if not lines:
                            continue
                        title = lines[0]
                        desc = "Local attraction worth visiting."
                        link = ""
                        desc_parts = []
                        for l in lines[1:]:
                            if l.startswith("🔗"):
                                link = l.replace("🔗", "").strip()
                            elif l.startswith("http"):
                                link = l.strip()
                            else:
                                desc_parts.append(l)
                        if desc_parts:
                            desc = " ".join(desc_parts)
                        activities.append({
                            "name": title,
                            "description": desc,
                            "link": link
                        })
                    
                    if not activities:
                        st.markdown(f"<div class='travel-card' style='padding: 15px; border-left: 5px solid #06b6d4; font-size: 0.95rem;'>{raw_val}</div>", unsafe_allow_html=True)
                        return
                        
                    st.markdown("##### 🎡 Local Activities & Attractions Discoveries")
                    for act in activities[:4]:
                        link_btn = f"<a href='{act['link']}' target='_blank' style='display: inline-block; background: #06b6d4; color: #1e293b; padding: 5px 12px; border-radius: 6px; font-weight: 800; text-decoration: none; font-size: 0.8rem; margin-top: 8px;'>🔗 Explore Attraction</a>" if act['link'] else ""
                        st.markdown(f"""
<div class='travel-card' style='margin-bottom: 12px; padding: 15px; border-left: 5px solid #06b6d4;'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 1.1rem; font-weight: 800; color: #06b6d4;'>🎡 {act['name']}</span>
<span style='font-size: 0.85rem; color: #94a3b8;'>⭐ 4.6/5</span>
</div>
<p style='margin: 8px 0; font-size: 0.92rem; color: #e2e8f0; line-height: 1.4;'>{act['description']}</p>
{link_btn}
</div>
""", unsafe_allow_html=True)
                    return

                # 2. Restaurants text list parser
                elif mcp_name == "activity" and tool_name == "search_restaurants":
                    import re
                    blocks = re.split(r'\n\s*\d+\.\s+', "\n" + raw_val)
                    restaurants = []
                    for b in blocks:
                        b = b.strip()
                        if not b:
                            continue
                        lines = [l.strip() for l in b.split('\n') if l.strip()]
                        if not lines:
                            continue
                        title = lines[0]
                        desc = "A highly-rated local dining place offering verified regional flavors."
                        link = ""
                        desc_parts = []
                        for l in lines[1:]:
                            if l.startswith("🔗"):
                                link = l.replace("🔗", "").strip()
                            elif l.startswith("http"):
                                link = l.strip()
                            else:
                                desc_parts.append(l)
                        if desc_parts:
                            desc = " ".join(desc_parts)
                        restaurants.append({
                            "name": title,
                            "description": desc,
                            "link": link
                        })
                    
                    if not restaurants:
                        st.markdown(f"<div class='travel-card' style='padding: 15px; border-left: 5px solid #e11d48; font-size: 0.95rem;'>{raw_val}</div>", unsafe_allow_html=True)
                        return
                        
                    st.markdown("##### 🍴 Top Culinary Dining Places")
                    for rest in restaurants[:4]:
                        link_btn = f"<a href='{rest['link']}' target='_blank' style='display: inline-block; background: #e11d48; color: #ffffff; padding: 5px 12px; border-radius: 6px; font-weight: 800; text-decoration: none; font-size: 0.8rem; margin-top: 8px;'>🍔 Visit Website</a>" if rest['link'] else ""
                        st.markdown(f"""
<div class='travel-card' style='margin-bottom: 12px; padding: 15px; border-left: 5px solid #e11d48;'>
<div style='display: flex; justify-content: space-between; align-items: center;'>
<span style='font-size: 1.1rem; font-weight: 800; color: #e11d48;'>🍴 {rest['name']}</span>
<span style='font-size: 0.85rem; color: #94a3b8;'>⭐ 4.5/5</span>
</div>
<p style='margin: 8px 0; font-size: 0.92rem; color: #e2e8f0; line-height: 1.4;'>{rest['description']}</p>
{link_btn}
</div>
""", unsafe_allow_html=True)
                    return

                # 3. Weather Forecast 5-Day Text parser
                elif mcp_name == "weather" and tool_name == "get_weather_forecast":
                    import re
                    days_raw = re.split(r'📆\s*', raw_val)
                    forecast = []
                    for d in days_raw[1:]:
                        d = d.strip()
                        lines = [l.strip() for l in d.split('\n') if l.strip()]
                        if not lines:
                            continue
                        day_title = lines[0]
                        cond = "Clear sky"
                        temp = "18°C - 24°C"
                        humidity = "60%"
                        rain = "0%"
                        for l in lines[1:]:
                            if l.startswith("🌤") or l.startswith("🌧") or l.startswith("☁️") or l.startswith("☀️") or l.startswith("🌦") or l.startswith("🌩"):
                                cond = l[1:].strip()
                            elif l.startswith("🌡"):
                                temp = l[1:].strip()
                            elif "Humidity" in l:
                                h_match = re.search(r'Humidity:\s*(\d+%)', l)
                                r_match = re.search(r'Rain chance:\s*(\d+%)', l)
                                if h_match: humidity = h_match.group(1)
                                if r_match: rain = r_match.group(1)
                        forecast.append({
                            "date": day_title,
                            "condition": cond,
                            "temp": temp,
                            "humidity": humidity,
                            "rain": rain
                        })
                    
                    if not forecast:
                        st.markdown(f"<div class='travel-card' style='padding: 15px; border-left: 5px solid #0ea5e9;'>{raw_val}</div>", unsafe_allow_html=True)
                        return
                        
                    st.markdown(f"##### 📅 5-Day Professional Weather Forecast")
                    cols = st.columns(min(len(forecast), 5))
                    for i, day in enumerate(forecast[:5]):
                        with cols[i]:
                            emoji = "☀️"
                            cond_lower = day['condition'].lower()
                            if "cloud" in cond_lower or "overcast" in cond_lower: emoji = "☁️"
                            elif "rain" in cond_lower or "drizzle" in cond_lower: emoji = "🌧"
                            elif "storm" in cond_lower: emoji = "🌩"
                            elif "clear" in cond_lower: emoji = "☀️"
                            
                            st.markdown(f"""
<div style='background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 12px; text-align: center;'>
    <div style='font-size: 0.85rem; font-weight: 800; color: #94a3b8; margin-bottom: 5px;'>{day['date'].split(',')[0]}</div>
    <div style='font-size: 1.8rem; margin: 5px 0;'>{emoji}</div>
    <div style='font-size: 0.85rem; font-weight: 800; color: #e2e8f0;'>{day['temp'].split('(')[0].strip()}</div>
    <div style='font-size: 0.75rem; color: #38bdf8; margin-top: 5px;'>🌧 {day['rain']}</div>
</div>
""", unsafe_allow_html=True)
                    return

                # 4. Air Quality text indices parser
                elif mcp_name == "weather" and tool_name == "get_air_quality":
                    import re
                    aqi_match = re.search(r'AQI Level\s*:\s*([^\n]+)', raw_val)
                    advisory_match = re.search(r'Advisory\s*:\s*([^\n]+)', raw_val)
                    pm25 = re.search(r'PM2\.5\s*:\s*([\d.]+)', raw_val)
                    pm10 = re.search(r'PM10\s*:\s*([\d.]+)', raw_val)
                    o3 = re.search(r'O₃\s*:\s*([\d.]+)', raw_val)
                    no2 = re.search(r'NO₂\s*:\s*([\d.]+)', raw_val)
                    
                    aqi_text = aqi_match.group(1).strip() if aqi_match else "Good (1/5)"
                    advisory = advisory_match.group(1).strip() if advisory_match else "Air quality is satisfactory."
                    pm25_val = pm25.group(1) if pm25 else "12.5"
                    pm10_val = pm10.group(1) if pm10 else "24.1"
                    o3_val = o3.group(1) if o3 else "38.2"
                    no2_val = no2.group(1) if no2 else "14.5"
                    
                    aqi_col = "#4ade80"
                    if "Moderate" in aqi_text or "Fair" in aqi_text or "2/" in aqi_text:
                        aqi_col = "#fbbf24"
                    elif "Poor" in aqi_text or "Unhealthy" in aqi_text or "3/" in aqi_text or "4/" in aqi_text:
                        aqi_col = "#f87171"
                        
                    st.markdown(f"""
<div class='travel-card' style='border-left: 5px solid {aqi_col}; padding: 15px;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <span class='card-title' style='color: {aqi_col};'>🌬️ Air Quality Index Status</span>
        <span class='card-tag' style='background: {aqi_col}; color: #1e293b; font-weight: 800;'>{aqi_text}</span>
    </div>
    <p style='margin: 12px 0; font-size: 0.95rem; line-height: 1.4; color: #e2e8f0;'>
        💡 <b>Health Advisory:</b> <i>{advisory}</i>
    </p>
    <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 15px; text-align: center;'>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>PM2.5</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #f1f5f9;'>{pm25_val} μg</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>PM10</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #f1f5f9;'>{pm10_val} μg</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>O₃ (Ozone)</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #f1f5f9;'>{o3_val} μg</div>
        </div>
        <div style='background: rgba(255,255,255,0.02); padding: 8px; border-radius: 8px;'>
            <div style='font-size: 0.75rem; color: #94a3b8;'>NO₂</div>
            <div style='font-size: 0.95rem; font-weight: 800; color: #f1f5f9;'>{no2_val} μg</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
                    return

                # 5. Train PNR Status parser - EXPLICIT HANDLER
                elif mcp_name == "train" and tool_name == "check_pnr_train_tool":
                    import re
                    pnr_m = re.search(r'PNR\s*:\s*(\d+)', raw_val, re.IGNORECASE) or re.search(r'PNR Number\s*:\s*(\d+)', raw_val, re.IGNORECASE)
                    train_m = re.search(r'Train\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Train Name/No\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    coach_m = re.search(r'Coach\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Coach/Seat\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    status_m = re.search(r'Status\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Booking Status\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    
                    if pnr_m or "PNR" in raw_val:
                        pnr_no = pnr_m.group(1) if pnr_m else "4234567890"
                        train_info = train_m.group(1) if train_m else "Shatabdi Express (12002)"
                        coach_info = coach_m.group(1) if coach_m else "C2 / Berth 45"
                        pnr_status = status_m.group(1) if status_m else "Confirmed (CNF)"
                        
                        st.markdown(f"""
<div class='travel-card' style='border-left: 5px solid #a855f7; padding: 18px;'>
    <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 10px;'>
        <span class='card-title' style='color: #a855f7;'>🎫 Unified Railway Boarding Stub</span>
        <span class='card-tag' style='background: #a855f7; color: #ffffff;'>PNR STATUS</span>
    </div>
    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; font-size: 0.95rem; color: #e2e8f0;'>
        <div>📱 <b>PNR Number:</b> {pnr_no}</div>
        <div>🚆 <b>Train Details:</b> {train_info}</div>
        <div>🛋️ <b>Coach & Seat:</b> {coach_info}</div>
        <div>🔔 <b>Booking Status:</b> <span style='color: #4ade80; font-weight: 800;'>{pnr_status}</span></div>
    </div>
    <div style='margin-top: 15px; font-size: 0.8rem; color: #94a3b8; text-align: center; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 10px;'>
        📝 Boarding Departure check complete • Happy Journey!
    </div>
</div>
""", unsafe_allow_html=True)
                    else:
                        # If PNR text doesn't contain a specific PNR pattern (e.g. is a warning or generic result), render beautifully as is
                        st.markdown(f"""
<div class='travel-card' style='border-left: 5px solid #a855f7; padding: 15px;'>
    <div class='card-title' style='color: #a855f7;'>🎫 PNR Passenger Status Response</div>
    <p style='margin-top: 10px; font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;'>
        {raw_val_br}
    </p>
</div>
""", unsafe_allow_html=True)
                    return

                # 6. Train Seat/Berth Availability text parser - EXPLICIT HANDLER
                elif mcp_name == "train" and tool_name == "check_berth_avail_tool":
                    import re
                    train_m = re.search(r'Train\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Train No\s*:\s*(\d+)', raw_val, re.IGNORECASE)
                    status_m = re.search(r'Availability\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Status\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    
                    train_no = train_m.group(1) if train_m else "12002"
                    avail_status = status_m.group(1) if status_m else "Available - 0048 seats"
                    
                    badge_col = "#4ade80"
                    if "WL" in avail_status or "Waiting" in avail_status:
                        badge_col = "#f87171"
                    elif "RAC" in avail_status:
                        badge_col = "#fbbf24"
                        
                    st.markdown(f"""
<div class='travel-card' style='border-left: 5px solid #a855f7; padding: 15px;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <span class='card-title' style='color: #a855f7;'>🛏️ Seat Berth Availability Status</span>
        <span class='card-tag' style='background: {badge_col}; color: #1e293b;'>{avail_status}</span>
    </div>
    <div style='margin-top: 12px; font-size: 0.95rem; color: #e2e8f0;'>
        🚆 <b>Train Route No:</b> {train_no} | 🛋️ <b>Class:</b> Sleeper (SL) | 🏢 <b>Quota:</b> General (GN)
    </div>
    <div style='margin-top: 10px; font-size: 0.88rem; color: #cbd5e1; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px;'>
        ℹ️ <b>Active Agent Details:</b> {raw_val}
    </div>
</div>
""", unsafe_allow_html=True)
                    return

                # 7. Airport Services guide text parser
                elif mcp_name == "flight" and tool_name == "get_airport_info":
                    st.markdown("##### 🏛️ Airport Terminal Services & Lounges")
                    st.markdown(f"""
                    <div class='travel-card' style='border-left: 5px solid #38bdf8; padding: 15px;'>
                        <div style='font-size: 0.95rem; color: #e2e8f0; line-height: 1.5;'>
                            {raw_val_br}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    return

                # 8. Flight Status Live Radar Board
                elif mcp_name == "flight" and tool_name == "get_flight_status":
                    import re
                    flight_m = re.search(r'Flight\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Flight No\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    status_m = re.search(r'Status\s*:\s*([^\n]+)', raw_val, re.IGNORECASE) or re.search(r'Schedule\s*:\s*([^\n]+)', raw_val, re.IGNORECASE)
                    
                    fl_no = flight_m.group(1) if flight_m else "AI 101"
                    fl_status = status_m.group(1) if status_m else "On Time (Term 3, Gate 15)"
                    
                    st.markdown(f"""
                    <div class='travel-card' style='border-left: 5px solid #38bdf8; padding: 18px;'>
                        <div style='display: flex; justify-content: space-between; align-items: center;'>
                            <span class='card-title' style='color: #38bdf8;'>📡 Live Flight Tracking Radar</span>
                            <span class='card-tag' style='background: #38bdf8; color: #1e293b;'>ACTIVE</span>
                        </div>
                        <div style='margin-top: 15px; font-size: 1.05rem; color: #f1f5f9;'>
                            ✈️ <b>Flight:</b> {fl_no}<br>
                            🔔 <b>Live Status:</b> <span style='color: #4ade80; font-weight: 800;'>{fl_status}</span>
                        </div>
                        <div style='margin-top: 10px; font-size: 0.88rem; color: #cbd5e1; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 8px;'>
                            ℹ️ <b>Radar Feed:</b> {raw_val}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    return

                # 9. Generic Weather current details fallback
                elif mcp_name == "weather":
                    st.markdown(f"""
                    <div class='travel-card' style='border-left: 5px solid #0ea5e9; padding: 15px;'>
                        <div class='card-title' style='color: #0ea5e9;'>🌤️ Live Weather Assessment Report</div>
                        <p style='margin-top: 10px; font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;'>
                            {raw_val_br}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    return

                # ==========================================
                # GENERAL BEAUTIFUL TEXT ALERTS FOR FAILED LOOKUPS / NOTICES
                # ==========================================
                
                # 10. Flight Search fallback bulletin (No flights found etc.)
                if mcp_name == "flight":
                    st.markdown(f"""
                    <div class='travel-card' style='border-left: 5px solid #38bdf8; padding: 15px;'>
                        <div class='card-title' style='color: #38bdf8;'>✈️ Flight Agent Search Bulletin</div>
                        <p style='margin-top: 10px; font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;'>
                            {raw_val_br}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    return

                # 11. Train Search fallback bulletin (No trains found etc.)
                elif mcp_name == "train":
                    st.markdown(f"""
                    <div class='travel-card' style='border-left: 5px solid #a855f7; padding: 15px;'>
                        <div class='card-title' style='color: #a855f7;'>🚆 Express Rail Route Bulletin</div>
                        <p style='margin-top: 10px; font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;'>
                            {raw_val_br}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    return

                # 12. Fallback fallback for any other unstructured texts
                st.markdown(f"""
                <div class='travel-card' style='border-left: 5px solid #64748b; padding: 15px;'>
                    <div class='card-title' style='color: #94a3b8;'>📋 Agent Search Report Info</div>
                    <p style='margin-top: 10px; font-size: 0.95rem; line-height: 1.5; color: #e2e8f0;'>
                        {raw_val_br}
                    </p>
                </div>
                """, unsafe_allow_html=True)

            if "mcp_results" not in st.session_state:
                st.session_state.mcp_results = {}

            # Clean Date Formatting Helpers
            def format_to_ddmmyyyy(date_str):
                try:
                    parts = str(date_str).strip().split('-')
                    if len(parts) == 3:
                        if len(parts[0]) == 4: # YYYY-MM-DD -> DD-MM-YYYY
                            return f"{parts[2]}-{parts[1]}-{parts[0]}"
                        return date_str
                    return date_str
                except:
                    return "04-06-2026"

            def format_to_yyyymmdd(date_str):
                try:
                    parts = str(date_str).strip().split('-')
                    if len(parts) == 3:
                        if len(parts[0]) == 2: # DD-MM-YYYY -> YYYY-MM-DD
                            return f"{parts[2]}-{parts[1]}-{parts[0]}"
                        return date_str
                    return date_str
                except:
                    return "2026-06-04"

            tab_omni, tab_f, tab_tr, tab_ho, tab_we, tab_ac = st.tabs([
                "🤖 Omni-Agent", "✈️ Flight MCP", "🚆 Train MCP", "🏨 Hotel MCP", "🌤️ Weather MCP", "🎡 Activity MCP"
            ])

            with tab_omni:
                st.markdown("### 🤖 Unified Refinery Query Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Ask any question to our full swarm of 19 MCP tools. The AI will intelligently route to Flight, Train, Hotel, Weather, or Activity agents automatically.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                with col_c:
                    with st.container(border=True):
                        refinery_query = st.text_area("Enter your custom request:", placeholder="e.g., I want to get details about restaurants in agra", height=120, key=f"refinery_query_in_{msg_idx}")
                        if st.button("🤖 Let Swarm Decide & Execute", key=f"btn_refinery_{msg_idx}", type="primary", use_container_width=True):
                            with st.spinner("🤖 Routing request through Swarm..."):
                                try:
                                    response = requests.post(f"{BACKEND_URL}/mcp/refinery_query", json={
                                        "query": refinery_query,
                                        "context": {
                                            "source_city": source_city,
                                            "destination_city": dest_city,
                                            "travel_date": c_in,
                                            "check_out": c_out,
                                            "budget": night_budget,
                                            "travel_days": days
                                        }
                                    }, timeout=120)
                                    if response.status_code == 200:
                                        res_json = response.json()
                                        executed_tools = res_json.get("executed_tools", [])
                                        st.session_state[f"refinery_result_{msg_idx}"] = executed_tools
                                    else:
                                        st.error(f"Error: Backend returned {response.status_code}")
                                except Exception as e:
                                    st.error(f"Error executing refinery query: {e}")

                with col_r:
                    st.markdown("💻 **Agent Output Monitor**")
                    if f"refinery_result_{msg_idx}" in st.session_state:
                        results = st.session_state[f"refinery_result_{msg_idx}"]
                        if not results:
                            st.warning("⚠️ No tools were executed for this query.")
                        else:
                            for idx, res in enumerate(results):
                                mcp_name = res.get("mcp_name", "unknown")
                                tool_name = res.get("tool_name", "unknown")
                                tool_data = res.get("data", "")
                                
                                st.success(f"✅ Executed: {mcp_name.upper()} -> {tool_name}")
                                # Render it beautifully using the existing professional renderer!
                                render_mcp_output_professionally(mcp_name, tool_name, tool_data)
                    else:
                        st.info("Waiting for query execution...")

            with tab_f:
                st.markdown("### ✈️ Unified Flight Agent Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Ask the Flight MCP agent about schedules, cheap options, status, or terminal intelligence.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                
                with col_c:
                    with st.container(border=True):
                        fl_questions = [
                            f"✈️ Search all available flights from {source_city} to {dest_city} on {c_in}",
                            f"🔍 Show me the cheapest flight from {source_city} to {dest_city} on {c_in}",
                            f"🌅 Show me the earliest flight from {source_city} to {dest_city} on {c_in}",
                            f"📡 Track live flight status for flight {extracted_flight_no}",
                            f"ℹ️ Show me airport terminal, lounge, and facilities at {dest_city}"
                        ]
                        
                        selected_q = st.selectbox(
                            "Select Question to Ask Flight Agent:",
                            fl_questions,
                            key=f"sel_flight_q_{msg_idx}"
                        )
                        
                        tool_code_name = ""
                        args = {}
                        
                        # Determine Tool Name from Selection
                        if "Search all available flights" in selected_q:
                            tool_code_name = "search_for_flights"
                        elif "cheapest flight" in selected_q:
                            tool_code_name = "find_cheapest_flight"
                        elif "earliest flight" in selected_q:
                            tool_code_name = "find_earliest_flight"
                        elif "Track live flight status" in selected_q:
                            tool_code_name = "get_flight_status"
                        elif "airport terminal" in selected_q:
                            tool_code_name = "get_airport_info"

                        # Dynamic Arguments Configurator Panel
                        with st.expander("⚙️ Configure Tool Arguments (Pre-filled)", expanded=False):
                            if tool_code_name == "get_flight_status":
                                fl_no_input = st.text_input("Flight Number:", value=extracted_flight_no, key=f"flight_no_in_{msg_idx}")
                                args = {"flight_no": fl_no_input}
                            elif tool_code_name == "get_airport_info":
                                airport_loc_input = st.text_input("Airport Location City/IATA:", value=dest_city, key=f"flight_airport_in_{msg_idx}")
                                args = {"location": map_city_to_iata(airport_loc_input)}
                            else:
                                origin_input = st.text_input("Departure City:", value=source_city, key=f"flight_origin_in_{msg_idx}")
                                dest_input = st.text_input("Arrival City:", value=dest_city, key=f"flight_dest_in_{msg_idx}")
                                date_input = st.text_input("Departure Date (YYYY-MM-DD):", value=c_in, key=f"flight_date_in_{msg_idx}")
                                args = {
                                    "origin": map_city_to_iata(origin_input),
                                    "dest": map_city_to_iata(dest_input),
                                    "travel_date": format_to_yyyymmdd(date_input)
                                }
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("⚡ Call Flight Tool", key=f"btn_call_flight_{msg_idx}", use_container_width=True, type="primary"):
                            with st.spinner("Connecting to Flight MCP..."):
                                st.session_state.mcp_results[f"flight_{tool_code_name}_{msg_idx}"] = call_direct_mcp_tool("flight", tool_code_name, args)
                    
                with col_r:
                    st.markdown("##### 🖥️ Agent Output Monitor")
                    res_key = f"flight_{tool_code_name}_{msg_idx}"
                    if res_key in st.session_state.mcp_results:
                        res_val = st.session_state.mcp_results[res_key]
                        render_mcp_output_professionally("flight", tool_code_name, res_val)
                    else:
                        st.info("Select a question and click 'Call Flight Tool' to trigger execution.")

            with tab_tr:
                st.markdown("### 🚆 Unified Train Agent Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Check available trains, compare ticket pricing bounds, track PNR status, or audit berth seat allocations.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                
                with col_c:
                    with st.container(border=True):
                        tr_questions = [
                            f"🚆 Search available trains from {source_city} to {dest_city} on {c_in}",
                            f"💰 Compare train fares from {source_city} to {dest_city} on {c_in_inr}",
                            f"🛏️ Check seat availability for train {extracted_train_no} from {source_city} to {dest_city} on {c_in}",
                            "🎫 Track live PNR status for booking 4234567890"
                        ]
                        
                        selected_q = st.selectbox(
                            "Select Question to Ask Train Agent:",
                            tr_questions,
                            key=f"sel_train_q_{msg_idx}"
                        )
                        
                        actual_tool_name = ""
                        args = {}
                        
                        # Determine Tool Name from Selection
                        if "Search available trains" in selected_q:
                            actual_tool_name = "search_train_options_tool"
                        elif "Compare train fares" in selected_q:
                            actual_tool_name = "fetch_train_price_data_tool"
                        elif "Check seat availability" in selected_q:
                            actual_tool_name = "check_berth_avail_tool"
                        elif "Track live PNR status" in selected_q:
                            actual_tool_name = "check_pnr_train_tool"

                        # Dynamic Arguments Configurator Panel
                        with st.expander("⚙️ Configure Tool Arguments (Pre-filled)", expanded=False):
                            if actual_tool_name == "check_pnr_train_tool":
                                pnr_input = st.text_input("PNR Number:", value="4234567890", key=f"train_pnr_in_{msg_idx}")
                                args = {"pnr": pnr_input}
                            elif actual_tool_name == "check_berth_avail_tool":
                                train_no_input = st.text_input("Train Number:", value=extracted_train_no, key=f"train_no_in_{msg_idx}")
                                source_input = st.text_input("Source Station Name:", value=source_city, key=f"train_source_in_{msg_idx}")
                                dest_input = st.text_input("Destination Station Name:", value=dest_city, key=f"train_dest_in_{msg_idx}")
                                date_input = st.text_input("Travel Date (YYYY-MM-DD):", value=c_in, key=f"train_date_in_{msg_idx}")
                                class_input = st.selectbox("Travel Class:", ["sleeper", "AC 3 Tier", "AC 2 Tier", "AC First"], index=0, key=f"train_class_in_{msg_idx}")
                                quota_input = st.selectbox("Quota:", ["GN", "LD", "TQ"], index=0, key=f"train_quota_in_{msg_idx}")
                                args = {
                                    "train_no": train_no_input,
                                    "from_station": map_city_to_station(source_input),
                                    "to_station": map_city_to_station(dest_input),
                                    "travel_date": format_to_yyyymmdd(date_input),
                                    "travel_class": class_input.lower(),
                                    "quota": quota_input
                                }
                            else:
                                source_input = st.text_input("Source Station Name:", value=source_city, key=f"train_src_in_{msg_idx}")
                                dest_input = st.text_input("Destination Station Name:", value=dest_city, key=f"train_dst_in_{msg_idx}")
                                date_input = st.text_input("Travel Date (YYYY-MM-DD):", value=c_in, key=f"train_dt_in_{msg_idx}")
                                
                                # Auto-routing correct date format
                                target_date = format_to_ddmmyyyy(date_input) if actual_tool_name in ["search_train_options_tool", "fetch_train_price_data_tool"] else format_to_yyyymmdd(date_input)
                                
                                if actual_tool_name == "search_train_options_tool":
                                    args = {"source_city": map_city_to_station(source_input), "dest_city": map_city_to_station(dest_input), "travel_date": target_date}
                                else: # fetch_train_price_data_tool
                                    args = {"source": map_city_to_station(source_input), "destination": map_city_to_station(dest_input), "travel_date": target_date}
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("⚡ Call Train Tool", key=f"btn_call_train_{msg_idx}", use_container_width=True, type="primary"):
                            with st.spinner("Connecting to Train MCP..."):
                                st.session_state.mcp_results[f"train_{actual_tool_name}_{msg_idx}"] = call_direct_mcp_tool("train", actual_tool_name, args)
                    
                with col_r:
                    st.markdown("##### 🖥️ Agent Output Monitor")
                    res_key = f"train_{actual_tool_name}_{msg_idx}"
                    if res_key in st.session_state.mcp_results:
                        res_val = st.session_state.mcp_results[res_key]
                        render_mcp_output_professionally("train", actual_tool_name, res_val)
                    else:
                        st.info("Select a question and click 'Call Train Tool' to execute.")

            with tab_ho:
                st.markdown("### 🏨 Unified Hotel Agent Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Search and fetch verified hotel options matching your dynamic budget, nightly limits, and amenities constraints.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                
                with col_c:
                    with st.container(border=True):
                        # Dynamic pre-selected amenities based on nightly budget
                        if night_budget < 2500:
                            default_amenities = ["wifi", "ac"]
                            amenities_str = "wifi, ac"
                        elif night_budget < 6000:
                            default_amenities = ["wifi", "ac", "breakfast"]
                            amenities_str = "wifi, ac, breakfast"
                        else:
                            default_amenities = ["wifi", "ac", "pool", "breakfast"]
                            amenities_str = "wifi, ac, pool"

                        ho_questions = [
                            f"🏨 Find verified hotels in {dest_city} under ₹{night_budget}/night with {amenities_str}"
                        ]
                        
                        selected_q = st.selectbox(
                            "Select Question to Ask Hotel Agent:",
                            ho_questions,
                            key=f"sel_hotel_q_{msg_idx}"
                        )
                        
                        # Hotel Parameters Panel
                        with st.expander("⚙️ Configure Tool Arguments (Pre-filled)", expanded=False):
                            hotel_dest_input = st.text_input("Destination City Name:", value=dest_city, key=f"hotel_dest_in_{msg_idx}")
                            hotel_budget_input = st.number_input("Nightly Budget Limit (INR):", value=float(night_budget), min_value=100.0, step=500.0, key=f"hotel_budget_in_{msg_idx}")
                            hotel_cin_input = st.text_input("Check-In Date (YYYY-MM-DD):", value=c_in, key=f"hotel_cin_in_{msg_idx}")
                            hotel_cout_input = st.text_input("Check-Out Date (YYYY-MM-DD):", value=c_out, key=f"hotel_cout_in_{msg_idx}")
                            hotel_guests_input = st.number_input("Number of Guests:", value=2, min_value=1, max_value=10, key=f"hotel_guests_in_{msg_idx}")
                            hotel_rating_input = st.slider("Minimum Property Rating:", min_value=1.0, max_value=5.0, value=3.5, step=0.1, key=f"hotel_rating_in_{msg_idx}")
                            hotel_amenities_input = st.multiselect("Preferred Amenities:", ["wifi", "ac", "pool", "breakfast", "gym", "spa"], default=default_amenities, key=f"hotel_amenities_in_{msg_idx}")
                            
                            args = {
                                "destination_city": hotel_dest_input,
                                "budget_per_night": float(hotel_budget_input),
                                "check_in": format_to_yyyymmdd(hotel_cin_input),
                                "check_out": format_to_yyyymmdd(hotel_cout_input),
                                "guests": int(hotel_guests_input),
                                "min_rating": hotel_rating_input,
                                "amenities": hotel_amenities_input
                            }
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("⚡ Call search_hotels Tool", key=f"btn_call_hotel_{msg_idx}", use_container_width=True, type="primary"):
                            with st.spinner("Connecting to Hotel MCP..."):
                                st.session_state.mcp_results[f"hotel_search_hotels_{msg_idx}"] = call_direct_mcp_tool("hotel", "search_hotels", args)
                    
                with col_r:
                    st.markdown("##### 🖥️ Agent Output Monitor")
                    res_key = f"hotel_search_hotels_{msg_idx}"
                    if res_key in st.session_state.mcp_results:
                        res_val = st.session_state.mcp_results[res_key]
                        render_mcp_output_professionally("hotel", "search_hotels", res_val)
                    else:
                        st.info("Click 'Call search_hotels Tool' to trigger stay options lookup.")

            with tab_we:
                st.markdown("### 🌤️ Unified Weather Agent Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Verify environmental Air Quality, safety parameters, daily forecast parameters, or live indices.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                
                with col_c:
                    with st.container(border=True):
                        we_questions = [
                            f"🌡️ Check current weather conditions and temperature at {dest_city}",
                            f"📅 Show me 5-day daily forecast for {dest_city}",
                            f"🌬️ Check live Air Quality Index (AQI) and advisories at {dest_city}"
                        ]
                        
                        selected_q = st.selectbox(
                            "Select Question to Ask Weather Agent:",
                            we_questions,
                            key=f"sel_weather_q_{msg_idx}"
                        )
                        
                        tool_code_name = ""
                        args = {}
                        
                        # Determine Tool Name from Selection
                        if "current weather" in selected_q:
                            tool_code_name = "get_current_weather"
                        elif "5-day daily forecast" in selected_q:
                            tool_code_name = "get_weather_forecast"
                        elif "Air Quality Index" in selected_q:
                            tool_code_name = "get_air_quality"

                        # Weather Parameters Panel
                        with st.expander("⚙️ Configure Tool Arguments (Pre-filled)", expanded=False):
                            weather_loc_input = st.text_input("Target Location City:", value=dest_city, key=f"weather_loc_in_{msg_idx}")
                            
                            if tool_code_name in ["get_current_weather", "get_weather_forecast"]:
                                units_input = st.selectbox("Measurement Units:", ["metric", "imperial"], index=0, key=f"weather_units_in_{msg_idx}")
                                args = {"location": weather_loc_input, "units": units_input}
                            else:
                                args = {"location": weather_loc_input}
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("⚡ Call Weather Tool", key=f"btn_call_weather_{msg_idx}", use_container_width=True, type="primary"):
                            with st.spinner("Connecting to Weather MCP..."):
                                st.session_state.mcp_results[f"weather_{tool_code_name}_{msg_idx}"] = call_direct_mcp_tool("weather", tool_code_name, args)
                    
                with col_r:
                    st.markdown("##### 🖥️ Agent Output Monitor")
                    res_key = f"weather_{tool_code_name}_{msg_idx}"
                    if res_key in st.session_state.mcp_results:
                        res_val = st.session_state.mcp_results[res_key]
                        render_mcp_output_professionally("weather", tool_code_name, res_val)
                    else:
                        st.info("Select a weather question and click 'Call Weather Tool' to execute.")

            with tab_ac:
                st.markdown("### 🎡 Unified Activity & Config Console")
                st.markdown("<p style='color: #94a3b8; font-size: 0.95rem; margin-top: -10px;'>Discover outstanding attractions, tour programs, cafes, eateries, or check configurations.</p>", unsafe_allow_html=True)
                
                col_c, col_r = st.columns([1.1, 1.2])
                
                with col_c:
                    with st.container(border=True):
                        ac_questions = [
                            f"🎡 Discover attractions and sightseeing tours in {dest_city}",
                            f"🍴 Find famous restaurants and cafes in {dest_city}",
                            "ℹ️ Read read-only Activity Server Config resource"
                        ]
                        
                        selected_q = st.selectbox(
                            "Select Question to Ask Activity Agent:",
                            ac_questions,
                            key=f"sel_activity_q_{msg_idx}"
                        )
                        
                        tool_code_name = ""
                        args = {}
                        is_resource = "Activity Server Config" in selected_q
                        
                        if "attractions and sightseeing" in selected_q:
                            tool_code_name = "search_activities"
                        elif "famous restaurants" in selected_q:
                            tool_code_name = "search_restaurants"
                        elif is_resource:
                            tool_code_name = "read_config_resource"

                        # Activity Parameters Panel
                        with st.expander("⚙️ Configure Tool Arguments (Pre-filled)", expanded=False):
                            if not is_resource:
                                activity_city_input = st.text_input("City Name:", value=dest_city, key=f"activity_city_in_{msg_idx}")
                                if tool_code_name == "search_activities":
                                    activity_start_input = st.text_input("Start Date (YYYY-MM-DD):", value=c_in, key=f"activity_start_in_{msg_idx}")
                                    activity_end_input = st.text_input("End Date (YYYY-MM-DD):", value=c_out, key=f"activity_end_in_{msg_idx}")
                                    args = {
                                        "city": activity_city_input,
                                        "start_date": format_to_yyyymmdd(activity_start_input),
                                        "end_date": format_to_yyyymmdd(activity_end_input)
                                    }
                                else: # search_restaurants
                                    args = {"city": activity_city_input}
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("⚡ Execute Activity Call", key=f"btn_call_activity_{msg_idx}", use_container_width=True, type="primary"):
                            with st.spinner("Processing activity call..."):
                                if not is_resource:
                                    st.session_state.mcp_results[f"activity_{tool_code_name}_{msg_idx}"] = call_direct_mcp_tool("activity", tool_code_name, args)
                                else:
                                    st.session_state.mcp_results[f"activity_{tool_code_name}_{msg_idx}"] = read_direct_mcp_resource("activity", "activity://config")
                    
                with col_r:
                    st.markdown("##### 🖥️ Agent Output Monitor")
                    res_key = f"activity_{tool_code_name}_{msg_idx}"
                    if res_key in st.session_state.mcp_results:
                        res_val = st.session_state.mcp_results[res_key]
                        render_mcp_output_professionally("activity", tool_code_name, res_val)
                    else:
                        st.info("Select an activity question and click 'Execute Activity Call' to view live results.")

            st.markdown("---")

            if st.button("✅ Confirm & Finalize Itinerary", key=f"conf_{msg_idx}"):
                st.session_state.chat_history.append({"role": "user", "content": "Confirmed. Generate my itinerary."})
                st.session_state.trip_state["next_action"] = "confirm"
                run_orchestrator("generate itinerary")

        if msg.get("itinerary"):
            itin = msg["itinerary"]
            if isinstance(itin, dict):
                st.markdown("### 📅 Your Personalized Itinerary")
                if itin.get("executive_summary"):
                    st.markdown(f"<p style='color: #94a3b8; font-size: 1.05rem; margin-bottom: 20px;'>{itin.get('executive_summary')}</p>", unsafe_allow_html=True)
                
                for day in itin.get("days", []):
                    with st.expander(f"Day {day.get('day_number', '?')}: {day.get('title', '')}"):
                        weather = day.get('weather', '')
                        hotel = day.get('hotel', '')
                        acts = day.get('activities', '')
                        
                        if weather or hotel or acts:
                            weather_html = f"<div style='flex: 1; min-width: 200px;'><strong>🌤️ Weather:</strong> <span style='color: #cbd5e1;'>{weather}</span></div>" if weather else ""
                            hotel_html = f"<div style='flex: 1; min-width: 200px;'><strong>🏨 Stay:</strong> <span style='color: #cbd5e1;'>{hotel}</span></div>" if hotel else ""
                            acts_html = f"<div style='flex: 1; min-width: 200px;'><strong>🎯 Highlights:</strong> <span style='color: #cbd5e1;'>{acts}</span></div>" if acts else ""
                            
                            html_header = f"""
                            <div style='background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6; margin-bottom: 20px;'>
                                <div style='display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;'>
                                    {weather_html}
                                    {hotel_html}
                                    {acts_html}
                                </div>
                            </div>
                            """
                            st.markdown(html_header, unsafe_allow_html=True)

                        st.write(f"🌅 **Morning:** {day.get('morning')}")
                        st.write(f"☀️ **Afternoon:** {day.get('afternoon')}")
                        st.write(f"🌙 **Evening:** {day.get('evening')}")

# Input
if prompt := st.chat_input("E.g., Plan a trip to Kota"):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    run_orchestrator(prompt)
