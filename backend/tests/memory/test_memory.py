import asyncio

from app.memory.history_manager import HistoryManager
from app.memory.mongo_store import MongoStore
from app.memory.session import SessionManager


async def main():
    store = MongoStore("sessions")
    session_manager = SessionManager(store)
    history_manager = HistoryManager(store=store)

    print("=== TEST 1: CREATE SESSION ===")
    session_id = await session_manager.create_session(
        metadata={"user_id": "dung_test", "model": "gpt-test"}
    )
    print("Session ID:", session_id)

    print("\n=== TEST 2: SESSION EXISTS ===")
    exists = await session_manager.session_exists(session_id)
    print("Exists:", exists)

    print("\n=== TEST 3: SAVE MESSAGE ===")
    await history_manager.save_message(session_id, "user", "Xin chào")
    await history_manager.save_message(session_id, "assistant", "Chào Dũng")
    messages = await store.get_messages(session_id)
    print("Messages:", messages)

    print("\n=== TEST 4: SAVE EXCHANGE ===")
    await history_manager.save_exchange(
        session_id=session_id,
        user_query="Bạn là ai?",
        assistant_answer="Mình là AI assistant.",
        sources=[{"title": "demo"}],
    )
    messages = await store.get_messages(session_id)
    print("Messages after exchange:", len(messages))

    print("\n=== TEST 5: LOAD HISTORY ===")
    history = await history_manager.load_history(session_id)
    print("Loaded history:", len(history))
    for msg in history:
        print(msg["role"], "=>", msg["content"])

    print("\n=== TEST 6: LIST SESSIONS ===")
    sessions = await session_manager.list_sessions(page=0, page_size=10)
    print("Sessions:", sessions)

    print("\n=== TEST 7: CLEAR HISTORY ===")
    deleted = await history_manager.clear_history(session_id)
    print("Deleted:", deleted)

    print("\n=== TEST 8: CHECK AFTER DELETE ===")
    exists = await session_manager.session_exists(session_id)
    print("Exists after delete:", exists)


if __name__ == "__main__":
    asyncio.run(main())