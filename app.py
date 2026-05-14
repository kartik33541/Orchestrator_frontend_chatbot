import streamlit as st
import requests
import json

st.set_page_config(page_title="AI Travel Orchestrator", layout="wide", page_icon="✈️")

# Custom CSS for Premium UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
    }

    /* Horizontal Scroll for Images */
    .image-grid {
        display: flex;
        gap: 15px;
        overflow-x: auto;
        padding: 10px 0;
        scrollbar-width: none;
    }
    .image-grid::-webkit-scrollbar { display: none; }
    .image-card {
        flex: 1 0 350px;
        height: 280px;
        border-radius: 16px;
        object-fit: cover;
        box-shadow: 0 8px 25px rgba(0,0,0,0.4);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .image-card:hover { 
        transform: translateY(-5px) scale(1.02);
        box-shadow: 0 12px 35px rgba(0,0,0,0.5);
    }

    /* Glassmorphism Cards */
    .travel-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }
    .travel-card:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: #38bdf8;
    }

    .card-title { color: #38bdf8; font-weight: 800; font-size: 1.2rem; margin-bottom: 5px; }
    .card-subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; }
    .card-price { color: #4ade80; font-weight: 800; font-size: 1.1rem; }
    .card-tag { 
        display: inline-block; 
        padding: 3px 10px; 
        background: rgba(56, 189, 248, 0.2); 
        color: #38bdf8; 
        border-radius: 20px; 
        font-size: 0.8rem; 
        margin-top: 10px;
    }

    /* Safety Box */
    .safety-container {
        border-left: 5px solid #fbbf24;
        background: rgba(251, 191, 36, 0.05);
        padding: 15px;
        border-radius: 0 12px 12px 0;
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

if "trip_state" not in st.session_state:
    st.session_state.trip_state = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{"role": "assistant", "content": "Hi! Where would you like to travel? (e.g., Indore to Raipur for 4 days, budget 20,000)"}]

st.title("✈️ AI Travel Orchestrator")

import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def run_orchestrator(query: str):
    payload = {"query": query, "state": st.session_state.trip_state}
    with st.spinner("The Swarm is researching..."):
        try:
            response = requests.post(f"{BACKEND_URL}/chat", json=payload) 
            data = response.json()
            new_state = data.get("state", {})
            st.session_state.trip_state = new_state
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
            st.rerun()
        except Exception as e:
            st.error(f"Backend Error: {e}")

# --- UI Renderers ---

def render_image_grid(photos):
    if not photos: return
    html = '<div class="image-grid">'
    for p in photos[:4]:
        html += f'<img src="{p["url"]}" class="image-card" title="{p.get("title", "")}">'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_safety(safety):
    if not safety: return
    st.markdown(f"""
    <div class="safety-container">
        <div style="font-weight: 800; color: #fbbf24; margin-bottom: 10px;">⚠️ Safety & Guidelines</div>
        <div style="margin-bottom: 10px;">{safety.get('summary')}</div>
        <ul style="margin: 0; padding-left: 20px;">
            {''.join([f'<li>{item}</li>' for item in safety.get('advice', [])])}
        </ul>
    </div>
    """, unsafe_allow_html=True)

def render_hub_notification(notification):
    if not notification: return
    st.warning(f"💡 **Transport Note:** {notification}")

def render_transport_card(t, msg_idx, card_idx):
    is_flight = "airline" in t
    icon = "✈️" if is_flight else "🚆"
    title = t.get("airline") or t.get("name") or "Transport"
    subtitle = f"{t.get('departure', '')} - {t.get('arrival', '')}"
    price = f"₹{t.get('price', 0)}"
    st.markdown(f"""
    <div class="travel-card">
        <div class="card-title">{icon} {title}</div>
        <div class="card-subtitle">{subtitle}</div>
        <div class="card-price">{price}</div>
        <div class="card-tag">{t.get('source_hub', t.get('number', 'Direct'))}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"📌 Select {title}", key=f"sel_t_{msg_idx}_{card_idx}"):
        st.session_state.chat_history.append({"role": "user", "content": f"I choose transport: {title}"})
        run_orchestrator(f"I choose transport: {title}")

def render_hotel_card(h, msg_idx, card_idx):
    name = h.get('name')
    st.markdown(f"""
    <div class="travel-card">
        <div class="card-title">🏨 {name}</div>
        <div class="card-subtitle">⭐ {h.get('rating', '4.0/5')} | 📍 {h.get('location', 'Central')}</div>
        <div class="card-price">₹{h.get('price_per_night', 0)} / night</div>
        <div class="card-tag">{' • '.join(h.get('amenities', [])[:2])}</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button(f"🏨 Select {name[:15]}...", key=f"sel_h_{msg_idx}_{card_idx}"):
        st.session_state.chat_history.append({"role": "user", "content": f"I choose hotel: {name}"})
        run_orchestrator(f"I choose hotel: {name}")

def render_activity_card(a, msg_idx, card_idx, is_food=False):
    icon = "🍛" if is_food else "🎭"
    st.markdown(f"""
    <div class="travel-card">
        <div class="card-title">{icon} {a.get('name')}</div>
        <div class="card-subtitle">{a.get('cuisine') or a.get('category') or 'Must visit'}</div>
        <div class="card-price">{a.get('price') or a.get('price_estimate') or 'Free entry'}</div>
    </div>
    """, unsafe_allow_html=True)

# Main Chat Loop
for msg_idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Hub Notification (Prominent Alert)
        if msg.get("hub_notification"):
            render_hub_notification(msg["hub_notification"])
        
        if msg.get("raw_options"):
            opts = msg["raw_options"]
            
            # 1. Photos
            render_image_grid(opts.get("photos", []))
            
            # 2. Weather & Safety (Only for Destination)
            if opts.get("weather"):
                w = opts["weather"]
                st.markdown(f"🌤️ **Weather in {w.get('location')}:** {w.get('condition')} | {w.get('temperature_c')}°C")
            
            render_safety(opts.get("safety", {}))
            
            # 3. Dynamic Tabs for Data (Grouped by City)
            tab_transport, tab_hotels, tab_exp = st.tabs(["🚆 Global Transport", "🏨 Hotels by City", "🎭 Experience by City"])
            
            with tab_transport:
                cols = st.columns(3)
                all_t = opts.get("flights", []) + opts.get("trains", [])
                if not all_t: st.info("No global transport options found.")
                for idx, t in enumerate(all_t[:6]):
                    with cols[idx % 3]: render_transport_card(t, msg_idx, idx)
            
            with tab_hotels:
                hotel_groups = opts.get("hotels", {})
                if isinstance(hotel_groups, dict):
                    for city, hotels in hotel_groups.items():
                        st.markdown(f"#### 📍 Hotels in {city}")
                        cols = st.columns(2)
                        for idx, h in enumerate(hotels[:4]):
                            with cols[idx % 2]: render_hotel_card(h, msg_idx, f"{city}_{idx}")
                else:
                    st.info("Searching for hotels...")
            
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
                else:
                    st.info("Exploring experiences...")

        # Proposed Package Section (Enriched Multi-City)
        if msg.get("package"):
            pkg = msg["package"]
            st.markdown("---")
            st.markdown("### 🏆 AI Recommended Multi-City Package")
            
            if pkg.get("transport"):
                st.markdown("#### 🚆 Arrival/Departure")
                render_transport_card(pkg["transport"], msg_idx, 999)
            
            for s_idx, stop in enumerate(pkg.get("stops", [])):
                city = stop.get("city")
                st.markdown(f"### 📍 Stop {s_idx + 1}: {city}")
                st.info(stop.get("city_summary", ""))
                
                p_cols = st.columns([1, 1, 1])
                with p_cols[0]:
                    if stop.get("hotel"): 
                        st.markdown("**🏨 Stay**")
                        render_hotel_card(stop["hotel"], msg_idx, f"pkg_h_{s_idx}")
                with p_cols[1]:
                    if stop.get("activities"): 
                        st.markdown("**🎭 Activity**")
                        render_activity_card(stop["activities"][0], msg_idx, f"pkg_a_{s_idx}")
                with p_cols[2]:
                    if stop.get("restaurants"): 
                        st.markdown("**🍛 Dining**")
                        render_activity_card(stop["restaurants"][0], msg_idx, f"pkg_r_{s_idx}", is_food=True)
            
            if st.button("✅ Confirm & Finalize Itinerary", key=f"conf_{msg_idx}"):
                st.session_state.chat_history.append({"role": "user", "content": "Confirmed. Generate my itinerary."})
                st.session_state.trip_state["next_action"] = "confirm"
                run_orchestrator("generate itinerary")

        # Itinerary Section
        if msg.get("itinerary"):
            itin = msg["itinerary"]
            if isinstance(itin, str):
                try: itin = json.loads(itin)
                except: pass
            
            if isinstance(itin, dict):
                st.markdown("### 📅 Your Personalized Itinerary")
                for day in itin.get("days", []):
                    with st.expander(f"Day {day.get('day_number', '?')}: {day.get('title', '')}"):
                        st.write(f"🌅 **Morning:** {day.get('morning')}")
                        st.write(f"☀️ **Afternoon:** {day.get('afternoon')}")
                        st.write(f"🌙 **Evening:** {day.get('evening')}")

# Input
if prompt := st.chat_input("E.g., Plan a trip to Kota, or 'Find me cheaper hotels'"):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    run_orchestrator(prompt)