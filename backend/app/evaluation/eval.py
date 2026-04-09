import os
from datasets import Dataset
from ragas import evaluate
from dotenv import load_dotenv
import json

# SỬA LỖI 1: Import các Class (Viết hoa chữ cái đầu) từ module gốc ragas.metrics
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextRecall,
    ContextPrecision
)
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# --- 1. CẤU HÌNH GEMINI API ---
# Thay thế bằng API Key thật của bạn
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")                   #type: ignore

gemini_llm = ChatGoogleGenerativeAI(model="gemma-4-31b-it") 
gemini_embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

# --- 2. CHUẨN BỊ DỮ LIỆU ---
# data = {
#     "question": [
#         "Người đi xe máy vượt đèn đỏ thì bị xử phạt như thế nào?",
#         "Tốc độ tối đa của ô tô trong khu đông dân cư là bao nhiêu?"
#     ],
#     "answer": [
#         "Theo Nghị định 100, phạt tiền từ 800.000 đồng đến 1.000.000 đồng, tước GPLX 1-3 tháng.",
#         "Tốc độ tối đa là 50 km/h hoặc 60 km/h tùy thuộc vào việc có dải phân cách cứng hay không."
#     ],
#     "contexts": [
#         ["Điểm e, Khoản 4, Điều 6 NĐ 100/2019: Phạt tiền từ 800k - 1 triệu đối với xe mô tô vượt đèn đỏ...", 
#          "Ngoài ra tước GPLX từ 01 tháng đến 03 tháng."],
#         ["Thông tư 31/2019/TT-BGTVT quy định tốc độ tối đa..."]
#     ],
#     "ground_truth": [
#         "Phạt 800.000 - 1.000.000 VNĐ và tước Giấy phép lái xe từ 1 - 3 tháng.",
#         "50 km/h nếu đường hai chiều không dải phân cách, 60 km/h nếu đường đôi có dải phân cách cứng."
#     ]
# }

with open("/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/evaluation/data_with_answers.json", "r", encoding = "utf-8") as f:
    data = json.load(f)

# Chuyển đổi dữ liệu sang định dạng Dataset của Hugging Face
dataset = Dataset.from_dict(data)


# --- 3. THỰC HIỆN ĐÁNH GIÁ ---
# SỬA LỖI 2: Khởi tạo trực tiếp các đối tượng (thêm dấu () đằng sau)
metrics = [
    Faithfulness(), 
    AnswerRelevancy(), 
    ContextRecall(), 
    ContextPrecision()
]

print("Đang tiến hành chấm điểm bằng Gemini...")
result = evaluate(
    dataset=dataset,
    metrics=metrics,
    llm=gemini_llm,                
    embeddings=gemini_embeddings   
)

# --- 4. XUẤT KẾT QUẢ ---
df_result = result.to_pandas() #type: ignore
print("\nKết quả đánh giá:")
print(df_result.head())

# Lưu file CSV
df_result.to_csv('rag_evaluation_results.csv', index=False)
print("\nĐã lưu kết quả vào file 'rag_evaluation_results.csv'")