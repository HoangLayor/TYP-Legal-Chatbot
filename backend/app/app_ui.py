"""
app_ui.py
Giao diện Web tối giản cho Vietnamese Law Question Answering Chatbot.
(Phiên bản không lưu lịch sử chat)
"""

import asyncio
import streamlit as st
import sys
import os

# --- THỦ THUẬT SỬA LỖI ĐƯỜNG DẪN IMPORT ---
# Trỏ đường dẫn gốc của Python lùi ra ngoài 1 cấp (thư mục backend)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
# ------------------------------------------
# --- Import Pipeline của bạn ---
# (Đảm bảo đường dẫn này khớp với file thực tế)
from app.rag.pipeline_v0 import RAGPipeline

# --- Cấu hình giao diện ---
st.set_page_config(page_title="Trợ lý Pháp lý VN", page_icon="⚖️", layout="centered")
st.title("Trợ lý Hỏi đáp Pháp luật Việt Nam")
st.caption("Phiên bản Test: Hybrid Search & Reranker (Không lưu lịch sử)")

# --- Hàm chạy Backend Async ---
# def get_bot_response(user_query: str):
#     async def _run():
#         pipeline = RAGPipeline()
#         # Hàm run() của bạn trả về answer (text) và sources (list dict)
#         return await pipeline.run(session_id = "test", query=user_query)
    
#     return asyncio.run(_run())


# --- TẠO ĐƯỜNG ỐNG (EVENT LOOP) VĨNH CỬU ---
# Dùng cache của Streamlit để giữ cho Loop này sống mãi mãi qua các lần chat
@st.cache_resource
def get_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop



# --- Hàm chạy Backend Async ---
def get_bot_response(user_query: str):
    # 1. Xin lại cái đường ống vĩnh cửu
    loop = get_async_loop()
    asyncio.set_event_loop(loop) # Gắn nó vào luồng hiện tại của Streamlit
    
    async def _run():
        pipeline = RAGPipeline()
        return await pipeline.run(session_id = "test", query=user_query)
    
    # 2. Dùng run_until_complete thay vì asyncio.run
    # Lệnh này chạy xong sẽ KHÔNG đập vỡ đường ống, giữ an toàn cho Qdrant!
    return loop.run_until_complete(_run())



# --- Ô nhập câu hỏi ---
if prompt := st.chat_input("Nhập câu hỏi pháp lý của bạn..."):
    
    # In câu hỏi của người dùng
    with st.chat_message("user"):
        st.markdown(prompt)

    # Xử lý và in câu trả lời của Bot
    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu cơ sở dữ liệu pháp luật..."):
            try:
                # Gọi thẳng xuống pipeline
                result = get_bot_response(prompt)
                answer = result.answer       # Hoặc có thể là result.response, result.content...
                sources = result.sources
                # Hiển thị câu trả lời từ LLM
                st.markdown(answer)
                
                # Hiển thị tài liệu trích dẫn (nếu có)
                # if sources:
                #     with st.expander("Nguồn tài liệu pháp luật trích dẫn"):
                #         for idx, doc in enumerate(sources):
                #             # Trích xuất metadata an toàn
                #             metadata = doc.get("metadata", {})
                #             filename = metadata.get("filename", "Không rõ nguồn")
                #             score = doc.get("score", 0.0)
                            
                #             # Lấy text (tùy thuộc vào chỗ lưu của bạn ở các file trước)
                #             text = doc.get("text") or metadata.get("text", "")
                            
                #             st.markdown(f"**[{idx + 1}] {filename}** *(Điểm: {score:.4f})*\n> {text[:300]}...")
                #             st.divider() # Kẻ vạch ngang phân cách các tài liệu cho dễ nhìn

            except Exception as e:
                st.error(f"Hệ thống gặp sự cố: {e}")