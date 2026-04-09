from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.generator import PromptBuilder, Generator
from app.rag.reranker import BGEReranker
from app.rag.hybrid_search import HybridSearcher

logger = get_logger(__name__)
settings = get_settings()

class GenerateData:
    def __init__(self,  generator: Generator | None = None, 
                        prompt: PromptBuilder | None = None, 
                        reranker: BGEReranker | None = None, 
                        search: HybridSearcher | None = None):
        self.generator = generator or Generator()
        self.prompt = prompt or PromptBuilder()
        self.reranker = reranker or BGEReranker()
        self.searcher = search or HybridSearcher()

    async def get_context(self, query : str, top_k : int = 20, top_n : int = 5, filter: dict | None = None):
        search_result = await self.searcher.search(query = query, top_k = top_k, filter = filter)
        ranked_result = await self.reranker.rerank(query = query, results = search_result, top_n = top_n)
        # context = self.prompt.build_messages(query = query, ranked_results = ranked_result, history = [])
        context_parts, index = [], 1
        for results in ranked_result:
            context_parts.append(self.prompt._format_chunk(result = results, index = index))
            index += 1
        context = "\n".join(context_parts)
        return context

    async def get_answer(self, query : str, top_k : int = 20, top_n : int = 5, filter: dict | None = None):
        search_result = await self.searcher.search(query = query, top_k = top_k, filter = filter)
        ranked_result = await self.reranker.rerank(query = query, results = search_result, top_n = top_n)
        answer = await self. generator.generate(query = query, ranked_results = ranked_result, history = [])
        return answer


if __name__ == "__main__":
    import asyncio
    import json
    import pprint

    generatedata = GenerateData()

    async def get_data(query: str):
        context = await generatedata.get_context(query=query)
        answer = await generatedata.get_answer(query=query)
        return context, answer

    async def main():
        with open("/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/evaluation/data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # pprint.pprint(data["question"])
        
        contexts_list = []
        answers_list = []
        
        for question in data["question"]:
            ctx, ans = await get_data(query=question)
            contexts_list.append(ctx)
            answers_list.append(ans)
            
        print("Đã lấy xong toàn bộ dữ liệu!")
        
        data["contexts"] = contexts_list
        data["answer"] = answers_list
        output_path = "/teamspace/studios/this_studio/TYP-Legal-Chatbot/backend/app/evaluation/data_with_answers.json"

        # Mở file ở chế độ ghi ("w" - write)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        print(f"Đã lưu thành công file JSON tại: {output_path}")

    # Khởi chạy toàn bộ luồng chương trình
    asyncio.run(main())

