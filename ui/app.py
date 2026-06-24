import os
import sys
import base64
import json
import logging
import streamlit as st
from PIL import Image
import io
import requests


# Add parent directory to path to import agents & security
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.orchestrator import run_city_botanist_workflow, call_mcp_tool_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citybotanist.ui")

def get_translated_details(plant_name: str, english_text: str, target_lang: str) -> str:
    static_translations = {
        "Himalayan Blackberry": {
            "description": {
                "Hindi": "एक आक्रामक लेकिन अत्यधिक उत्पादक कांटेदार झाड़ी। देर से गर्मियों में स्वादिष्ट, मीठे काले बेर पैदा करता है। शहरी भोजन खोजने के लिए अत्यधिक लोकप्रिय।",
                "Telugu": "ఒక ఆక్రమణశీల కానీ ఆకురాల్చే ముళ్ళ పొద. వేసవి చివరలో రుచికరమైన, తీపి నల్లటి బెర్రీలను ఉత్పత్తి చేస్తుంది. పట్టణ ప్రాంతాలలో ఆహార సేకరణకు అత్యంత ప్రజాదరణ పొందింది."
            },
            "warnings": {
                "Hindi": "कांटे खरोंच का कारण बन सकते हैं। वाहन उत्सर्जन के कारण सड़कों के पास के बेरों को अच्छी तरह धोना चाहिए।",
                "Telugu": "ముళ్ళు గీతలు పడేలా చేయవచ్చు. వాహనాల ఉద్గారాల కారణంగా రోడ్ల సమీపంలో ఉన్న బెర్రీలను బాగా కడగాలి."
            }
        },
        "Dandelion": {
            "description": {
                "Hindi": "एक बहुत ही आम शहरी जड़ी बूटी। पौधे के सभी भाग खाद्य हैं: पत्तियां, जड़ें और फूल। विटामिन ए, सी और के से भरपूर।",
                "Telugu": "చాలా సాధారణమైన పట్టణ మూలిక. ఈ మొక్క యొక్క అన్ని భాగాలు తినదగినవి: ఆకులు, వేర్లు మరియు పువ్వులు. విటమిన్లు ఎ, సి మరియు కె అధికంగా ఉంటాయి."
            },
            "warnings": {
                "Hindi": "कोई नहीं। सामान्य भोजन खोजने के लिए अत्यधिक सुरक्षित। सुनिश्चित करें कि वे कीटनाशकों के छिड़काव वाले क्षेत्रों या उच्च-कुत्ता-यातायात क्षेत्रों से एकत्र न किए जाएं।",
                "Telugu": "ఏమీ లేవు. సాధారణ ఆహార సేకరణకు అత్యంత సురక్షితం. కీటకనాశినులు చల్లిన ప్రాంతాల నుండి లేదా కుక్కల సంచారం ఎక్కువగా ఉన్న ప్రదేశాల నుండి వీటిని సేకరించకుండా చూసుకోండి."
            }
        },
        "Poison Ivy": {
            "description": {
                "Hindi": "एक वुडी पर्णपाती बेल। पत्तियां तीन के समूहों में बढ़ती हैं ('तीन की पत्तियां, इसे रहने दें')। लकड़ी को कभी भी न खाएं और न ही जलाएं।",
                "Telugu": "ఒక కాండం కలిగిన ఆకురాల్చే తీగ. ఆకులు మూడు సమూహాలుగా పెరుగుతాయి ('మూడు ఆకులు ఉంటే, వదిలేయండి'). ఈ చెక్కను ఎప్పుడూ తినకూడదు లేదా కాల్చకూడదు."
            },
            "warnings": {
                "Hindi": "संपर्क और पाचन पर अत्यधिक जहरीला। इसमें यूरुशियोल होता है, एक तेल जो गंभीर, खुजलीदार और दर्दनाक त्वचा की सूजन और छाले का कारण बनता है। स्पर्श या उपभोग न करें।",
                "Telugu": "తాకడం మరియు జీర్ణం చేసుకోవడం వల్ల అత్యంత విషపూరితం. ఉరుషియోల్ అనే నూనెను కలిగి ఉంటుంది, ఇది తీవ్రమైన, దురద మరియు బాధాకరమైన చర్మ వాపు మరియు పొక్కులను కలిగిస్తుంది. తాకవద్దు లేదా తినవద్దు."
            }
        }
    }
    
    # Check if we have static translation
    for name, langs in static_translations.items():
        if name.lower() in plant_name.lower():
            field_type = "description" if "desc" in english_text.lower() or english_text == "description" else "warnings"
            if target_lang in langs[field_type]:
                return langs[field_type][target_lang]
                
    # Try live Gemini key if available
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key and len(english_text) > 1:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        prompt = f"Translate the following botanical text to {target_lang}. Return only the exact translation, do not explain or add introductory text:\n\n{english_text}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=6)
            if r.status_code == 200:
                translation = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if translation:
                    return translation
        except Exception:
            pass
            
    return english_text

# Page Configuration
st.set_page_config(
    page_title="City Botanist - Urban Foraging Safety Agent",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Nature Aesthetic
st.markdown("""
<style>
    /* Title and main headers */
    h1, h2, h3 {
        color: #1B5E20 !important;
        font-family: 'Outfit', 'Inter', sans-serif;
    }
    
    /* Custom banner containers */
    .banner-safe {
        background-color: #E8F5E9;
        border-left: 5px solid #2E7D32;
        padding: 20px;
        border-radius: 8px;
        color: #1B5E20;
        margin-bottom: 20px;
    }
    .banner-unsafe {
        background-color: #FFEBEE;
        border-left: 5px solid #C62828;
        padding: 20px;
        border-radius: 8px;
        color: #C62828;
        margin-bottom: 20px;
    }
    .banner-pending {
        background-color: #FFFDE7;
        border-left: 5px solid #FBC02D;
        padding: 20px;
        border-radius: 8px;
        color: #F57F17;
        margin-bottom: 20px;
    }
    
    /* Dashboard card styling */
    .dashboard-card {
        background-color: #F1F8E9;
        border: 1px solid #DCEDC8;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# App Title & Subtitle
st.title("🌿 City Botanist")
st.caption("AI-powered urban foraging assistant checking plant identity and municipal safety databases.")

# Sidebar Controls
st.sidebar.header("Foraging Controls")

# Predefined Seattle parks database mapping for easy demo testing
seattle_parks = {
    "Discovery Park (Pristine - Safe)": (47.6572, -122.4172),
    "Cal Anderson Park (Urban - Safe)": (47.6174, -122.3195),
    "Seward Park (Old Growth - Safe)": (47.5500, -122.2600),
    "Golden Gardens Park (Beach - Safe)": (47.6900, -122.4020),
    "Volunteer Park (Pesticide Sprayed - Unsafe)": (47.6300, -122.3150),
    "Myrtle Edwards Park (Sprayed Yesterday - Unsafe)": (47.6186, -122.3586),
    "Jefferson Park (Sprayed 5 Days Ago - Unsafe)": (47.5680, -122.3050),
    "Gas Works Park (Soil Contamination - Unsafe)": (47.6456, -122.3344),
    "Olympic Sculpture Park (Industrial History)": (47.6160, -122.3540),
    "Green Lake Park (Sprayed 20 Days Ago - Safe)": (47.6786, -122.3418),
    "Detect My Location...": "detect",
    "Custom Location...": None
}

selected_location = st.sidebar.selectbox(
    "Select Location",
    list(seattle_parks.keys()),
    index=0
)

# Coordinates Inputs
if selected_location == "Custom Location...":
    lat_val = st.sidebar.number_input("Latitude", min_value=-90.0, max_value=90.0, value=47.6062, format="%.6f")
    lon_val = st.sidebar.number_input("Longitude", min_value=-180.0, max_value=180.0, value=-122.3321, format="%.6f")
elif selected_location == "Detect My Location...":
    from streamlit_geolocation import streamlit_geolocation
    location = streamlit_geolocation()
    if location and location.get("latitude") is not None:
        lat_val = float(location["latitude"])
        lon_val = float(location["longitude"])
        st.sidebar.success(f"📍 Detected Location:\nLatitude: {lat_val:.6f}\nLongitude: {lon_val:.6f}")
    else:
        lat_val, lon_val = 47.6062, -122.3321  # Default fallback if loading or denied
        st.sidebar.warning("Awaiting browser location access permission... (Please allow location access when prompted by your browser).")
else:
    coords = seattle_parks[selected_location]
    lat_val, lon_val = coords
    st.sidebar.info(f"📍 GPS Coordinates:\nLatitude: {lat_val}\nLongitude: {lon_val}")

# Safety preferences
st.sidebar.subheader("Safety Preferences")
pesticide_window = st.sidebar.slider("Pesticide Spraying Safe Window (days)", min_value=7, max_value=30, value=14)
max_lead_level = st.sidebar.number_input("Max Soil Lead Level (ppm)", min_value=10, max_value=400, value=80)

# How to use section in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📖 How to Use")
st.sidebar.markdown(
    "1. Choose a **foraging location** in the sidebar.\n"
    "2. Upload an image of a plant.\n"
    "3. Review the agent's workflow and final **safety report**.\n"
    "4. Acknowledge warnings if dangerous lookalikes are detected.\n"
    "5. Ask follow-up questions in the chat box."
)

st.sidebar.warning(
    "⚠️ **Disclaimer:** Educational purposes only. Urban environments contain pollutants. "
    "Consult local experts and do not rely solely on AI for consumption."
)

# API Status indicator
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if api_key:
    st.sidebar.success("🔗 Gemini API: Connected")
else:
    st.sidebar.info("🔗 Gemini API: Mock Mode (Offline)")

# Welcome Screen & Layout splits
col_main, col_dash = st.columns([2, 1])

with col_main:
    st.subheader("📸 Upload Plant Image")
    
    uploaded_file = st.file_uploader(
        "Drag and drop image file...",
        type=["jpg", "jpeg", "png", "webp"]
    )
    
    # Process image input
    img_base64 = None
    display_image = None
    
    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        display_image = Image.open(io.BytesIO(file_bytes))
        st.image(display_image, width=300)
        img_base64 = base64.b64encode(file_bytes).decode("utf-8")
        # Add filename as metadata to assist mock identification
        img_base64 = f"data:image/jpeg;base64,{img_base64};filename={uploaded_file.name}"
        
        # Auto-run analysis when a new file is uploaded
        if "last_analyzed_file" not in st.session_state or st.session_state.last_analyzed_file != uploaded_file.name:
            st.session_state.last_analyzed_file = uploaded_file.name
            st.session_state.lookalike_approved = False
            
            with st.spinner("Analyzing Foraging Safety..."):
                result = run_city_botanist_workflow(
                    image_base64=img_base64,
                    latitude=lat_val,
                    longitude=lon_val,
                    human_approved_lookalike=st.session_state.lookalike_approved
                )
                st.session_state.agent_result = result
        
    # Run Agent analysis button
    run_clicked = st.button("🚀 Analyze Safety", type="primary", disabled=(img_base64 is None))
    
    # Store session states for results and approvals
    if "agent_result" not in st.session_state:
        st.session_state.agent_result = None
    if "lookalike_approved" not in st.session_state:
        st.session_state.lookalike_approved = False
        
    # Handle user action
    if run_clicked:
        st.session_state.lookalike_approved = False  # Reset approval
        
        # UI Agent Workflow Visualizer
        with st.status("Analyzing Urban Foraging Safety...", expanded=True) as status:
            st.write("🔍 Running input checks & validating coordinate ranges...")
            status.update(label="Vision Agent: Running...", state="running")
            st.write("📷 Vision Agent identifying plant species from image...")
            
            # Simulate slight delay for real-agent feels
            import time
            time.sleep(0.5)
            
            status.update(label="Location Agent: Running...", state="running")
            st.write("🗺️ Location Agent checking municipal pesticide spraying logs and soil safety archives...")
            st.write("🌤️ Weather Agent checking weather forecast conditions...")
            time.sleep(0.5)
            
            status.update(label="Safety Agent: Running...", state="running")
            st.write("⚖️ Safety Agent synthesizing edibility, location safety, and lookalikes...")
            
            # Execute workflow
            result = run_city_botanist_workflow(
                image_base64=img_base64,
                latitude=lat_val,
                longitude=lon_val,
                human_approved_lookalike=st.session_state.lookalike_approved
            )
            
            st.session_state.agent_result = result
            status.update(label="Analysis Completed!", state="complete", expanded=False)
            
    # Check if a lookalike checkpoint has halted execution
    if st.session_state.agent_result and st.session_state.agent_result.get("checkpoint_required", False):
        st.markdown(f"""
        <div class="banner-pending">
            <h3>⚠️ Lookalike Alert Checkpoint Required</h3>
            <p>{st.session_state.agent_result['checkpoint_message']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        confirm_lookalike = st.checkbox("✅ I verify that I have checked the stem, root bulb, and scent characteristics to rule out the toxic lookalikes.")
        
        if confirm_lookalike:
            if st.button("Resume Analysis", type="primary"):
                st.session_state.lookalike_approved = True
                with st.spinner("Resuming Safety Synthesis..."):
                    result = run_city_botanist_workflow(
                        image_base64=img_base64,
                        latitude=lat_val,
                        longitude=lon_val,
                        human_approved_lookalike=True
                    )
                    st.session_state.agent_result = result
                st.rerun()

    # Display final results
    if st.session_state.agent_result and not st.session_state.agent_result.get("checkpoint_required", False):
        res = st.session_state.agent_result
        
        if not res.get("success", False):
            st.error(f"❌ Analysis Failed: {res.get('error', 'Unknown error')}")
            with st.expander("⚙️ Agent Chain Trace (Failure Details)", expanded=True):
                for step in res.get("workflow_steps", []):
                    st.text(f" - {step}")
        else:
            decision = res.get("decision", "DO NOT EAT")
            
            # Display Banner
            name_hindi = res.get('name_hindi', 'Unknown')
            name_telugu = res.get('name_telugu', 'Unknown')
            
            # Display Plant Name prominently at the very top of the results
            st.markdown(f"# 🌿 {res.get('plant_name', 'Unknown')}")
            st.markdown(f"**Scientific Name:** *{res.get('scientific_name', 'Unknown')}* | **Hindi Name:** *{name_hindi}* | **Telugu Name:** *{name_telugu}*")
            st.markdown("---")
            
            if decision == "SAFE TO EAT":
                st.markdown(f"""
                <div class="banner-safe">
                    <h2>🟢 SAFE TO FORAGE & EAT</h2>
                    <p>Verified safe for foraging at this location. Confidence: {res.get('confidence', 0.0)*100:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="banner-unsafe">
                    <h2>🔴 DO NOT EAT</h2>
                    <p>Safety restriction enforced. Confidence: {res.get('confidence', 0.0)*100:.1f}%</p>
                </div>
                """, unsafe_allow_html=True)
                
            # Display Agent Reports Tabs
            tab_safety, tab_vision, tab_location, tab_steps = st.tabs([
                "🛡️ Safety Verdict", 
                "👁️ Vision Agent Details", 
                "🌍 Location Agent Details", 
                "⚙️ Agent Chain Trace"
            ])
            
            with tab_safety:
                st.markdown(res.get("safety_report", ""))
                
            with tab_vision:
                st.markdown(res.get("vision_report", "No vision reports compiled."))
                
            with tab_location:
                st.markdown(res.get("location_report", "No location reports compiled."))
                
            with tab_steps:
                st.write("Execution trace:")
                for step in res.get("workflow_steps", []):
                    st.text(f" - {step}")
                    
            # Interactive Chat Box for Follow-up
            st.write("---")
            st.subheader("💬 Ask Follow-up Questions")
            
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
                
            # Display Chat History
            for chat in st.session_state.chat_history:
                with st.chat_message(chat["role"]):
                    st.write(chat["text"])
                    
            # Chat input
            user_msg = st.chat_input("Ask about preparation, cooking methods, medicinal history, or similar species...")
            if user_msg:
                st.session_state.chat_history.append({"role": "user", "text": user_msg})
                
                with st.chat_message("user"):
                    st.write(user_msg)
                    
                with st.chat_message("assistant"):
                    with st.spinner("Agent generating response..."):
                        # Process follow-up message using safety/vision context
                        response_text = ""
                        if api_key:
                            # Use Gemini to generate a response about the identified plant
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                            headers = {"Content-Type": "application/json"}
                            prompt_full = (
                                f"You are the City Botanist AI assistant. The user has just run an analysis "
                                f"and identified '{res.get('plant_name', 'Unknown')}' ({res.get('scientific_name', 'Unknown')}). The safety decision was '{decision}'.\n"
                                f"User question: {user_msg}\n"
                                f"Please answer their question accurately. Keep it educational and always add a warning if they ask about eating it."
                            )
                            payload = {"contents": [{"parts": [{"text": prompt_full}]}]}
                            try:
                                r = requests.post(url, headers=headers, json=payload, timeout=8)
                                if r.status_code == 200:
                                    response_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                            except Exception as ex:
                                response_text = f"API call failed: {ex}. Mock answer applied."
                                
                        if not response_text:
                            # Resilient mock conversational responses
                            user_lower = user_msg.lower()
                            if "cook" in user_lower or "prepare" in user_lower or "eat" in user_lower:
                                if res.get("plant_name") == "Stinging Nettle":
                                    response_text = "Stinging Nettles must be boiled for at least 2 minutes or thoroughly dried to neutralize the stingers. Once boiled, they are delicious in tea, pesto, or as a spinach substitute!"
                                elif res.get("plant_name") == "Dandelion":
                                    response_text = "Dandelion greens are bitter but edible raw. You can blanch them to reduce bitterness, or roast the roots to make a caffeine-free coffee substitute."
                                elif decision == "SAFE TO EAT":
                                    response_text = f"Since the plant '{res.get('plant_name')}' is safe and edible, make sure you wash it thoroughly under cold water. Avoid raw consumption in huge amounts unless well-known. Cooking generally reduces risks of bacterial contamination."
                                else:
                                    response_text = f"Remember, this plant was flagged as **DO NOT EAT**! I strongly recommend against cooking or preparing this specimen for safety reasons."
                            elif "benefit" in user_lower or "medicinal" in user_lower or "healthy" in user_lower:
                                response_text = f"Historically, {res.get('plant_name')} has been used in folk medicine. However, we cannot make absolute health claims. Always consult with a registered herbalist or physician before using wild plants for health benefits."
                            else:
                                response_text = f"Good question! Regarding '{res.get('plant_name')}', foragers typically note that correct local identification is key. Remember that urban foraging always carries inherent risks from environmental toxins."
                                
                        st.write(response_text)
                        st.session_state.chat_history.append({"role": "assistant", "text": response_text})

# Right Panel: Safety Dashboard with Risk Factors
with col_dash:
    st.subheader("🛡️ Safety Dashboard")
    
    if st.session_state.agent_result and not st.session_state.agent_result.get("checkpoint_required", False) and st.session_state.agent_result.get("success", False):
        res = st.session_state.agent_result
        decision = res.get("decision", "DO NOT EAT")
        
        # Display Language Dropdown Selector
        display_lang = st.selectbox(
            "🌐 Translate Details / भाषा चुनें / భాష ఎంచుకోండి",
            ["English", "Hindi", "Telugu"],
            index=0
        )
        
        # Plant Details Translation Card
        plant_name = res.get("plant_name", "Unknown")
        name_hindi = res.get("name_hindi", "Unknown")
        name_telugu = res.get("name_telugu", "Unknown")
        scientific_name = res.get("scientific_name", "Unknown")
        
        raw_desc = res.get("structured_data", {}).get("description", "No description available.")
        raw_warn = res.get("structured_data", {}).get("toxicity_warnings", "None.")
        
        if display_lang == "Hindi":
            desc_text = get_translated_details(plant_name, raw_desc, "Hindi")
            warn_text = get_translated_details(plant_name, raw_warn, "Hindi")
            st.markdown(f"""
            <div class="dashboard-card" style="background-color: #E8F5E9; border-color: #A5D6A7; color: #1B5E20;">
                <h4>🌿 पौधा विवरण (Plant Details)</h4>
                <p><b>नाम:</b> {name_hindi}<br>
                <b>वैज्ञानिक नाम:</b> <i>{scientific_name}</i><br>
                <b>विवरण:</b> {desc_text}<br>
                <b>चेतावनी:</b> {warn_text}</p>
            </div>
            """, unsafe_allow_html=True)
        elif display_lang == "Telugu":
            desc_text = get_translated_details(plant_name, raw_desc, "Telugu")
            warn_text = get_translated_details(plant_name, raw_warn, "Telugu")
            st.markdown(f"""
            <div class="dashboard-card" style="background-color: #E8F5E9; border-color: #A5D6A7; color: #1B5E20;">
                <h4>🌿 మొక్క వివరాలు (Plant Details)</h4>
                <p><b>పేరు:</b> {name_telugu}<br>
                <b>శాస్త్రీయ నామం:</b> <i>{scientific_name}</i><br>
                <b>వివరణ:</b> {desc_text}<br>
                <b>హెచ్చరికలు:</b> {warn_text}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="dashboard-card" style="background-color: #E8F5E9; border-color: #A5D6A7; color: #1B5E20;">
                <h4>🌿 Plant Details</h4>
                <p><b>Name:</b> {plant_name}<br>
                <b>Scientific Name:</b> <i>{scientific_name}</i><br>
                <b>Description:</b> {raw_desc}<br>
                <b>Warnings:</b> {raw_warn}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Load local tool logs or coordinates to fetch details
        pesticide_report = call_mcp_tool_sync("city_data_mcp.py", "check_pesticide_spraying", {"latitude": lat_val, "longitude": lon_val})
        soil_report = call_mcp_tool_sync("city_data_mcp.py", "get_soil_contamination", {"latitude": lat_val, "longitude": lon_val})
        
        # Render Cards
        # 1. Pesticide Card
        sprayed = pesticide_report.get("sprayed", False)
        card_class = "🔴" if sprayed else "🟢"
        sprayed_text = f"Recent Spraying: **{pesticide_report.get('chemical', 'None')}** ({pesticide_report.get('days_ago')} days ago)" if sprayed else "Pesticide Spraying: **None (Safe)**"
        st.markdown(f"""
        <div class="dashboard-card">
            <h4>{card_class} Pesticide Schedule</h4>
            <p>{sprayed_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. Soil Card
        lead = soil_report.get("lead_level", 0.0)
        soil_safe = soil_report.get("safe", True)
        soil_card = "🟢" if soil_safe else "🔴"
        soil_text = f"Lead Level: **{lead} ppm** (Threshold: 80 ppm)<br>Source: {soil_report.get('contamination_source')}"
        st.markdown(f"""
        <div class="dashboard-card">
            <h4>{soil_card} Soil Contamination</h4>
            <p>{soil_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 3. Lookalike Check
        lookalike_card = "🟢" if not res.get("checkpoint_required", False) else "🟡"
        lookalikes = res.get("structured_data", {}).get("lookalikes", [])
        lookalike_text = f"lookalikes registered: {', '.join(lookalikes)}" if lookalikes else "No toxic lookalikes registered."
        st.markdown(f"""
        <div class="dashboard-card">
            <h4>{lookalike_card} Lookalike Database</h4>
            <p>{lookalike_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Hashed Coordinates Log
        st.markdown(f"""
        <div class="dashboard-card" style="background-color:#EFEFEF; border:1px solid #CCC;">
            <h5>📍 Location Privacy protection</h5>
            <p style="font-size:0.8em; word-break: break-all;">
                Hashed Coordinate ID (sent to logs):<br>
                <code>{res.get('user_location_hash', 'None')}</code>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        st.info("Upload an image and run the safety analysis to populate the environmental safety dashboard cards.")


