import streamlit as st
import google.generativeai as genai

# ===== CONFIG =====
API_KEY = "AIzaSyBYaxmhg2_GOw-dyWIeF3ZTG6gxxW-EXVk"
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")

st.title("Chat với Gemini 🤖")

# ===== SESSION =====
if "messages" not in st.session_state:
    st.session_state.messages = []

# ===== HIỂN THỊ CHAT =====
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ===== INPUT =====
prompt = st.chat_input("Nhập câu hỏi...")

if prompt:
    # user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # gọi Gemini
    with st.chat_message("assistant"):
        with st.spinner("Đang suy nghĩ..."):
            try:
                response = model.generate_content(prompt)
                reply = response.text
            except Exception as e:
                reply = f"Lỗi: {e}"

            st.markdown(reply)

    # lưu lại
    st.session_state.messages.append({"role": "assistant", "content": reply})