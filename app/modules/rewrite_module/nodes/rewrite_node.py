
from langchain_core.messages import trim_messages

from app.model.llm import llm
from app.prompt.load_prompt import load_prompt
from app.modules.rewrite_module.state import RewriteState


async def rewrite_query(state: RewriteState) -> RewriteState:
    """
    Rewrite the query based on the context.
    """
    raw_query = state.get("raw_query", "")
    history = trim_messages(
        state["history"],
        max_tokens=4,          # token_counter=len nên đây là SỐ MESSAGE
        token_counter=len,
        strategy="last",
        start_on="human",      # cửa sổ luôn bắt đầu ở lượt người dùng
        include_system=False,
    )
    ctx_card = state.get("ctx_card", {})

    try:
        # Build and invoke the prompt | llm chain
        chain = load_prompt("rewrite/rewrite_node") | llm
        response = await chain.ainvoke({
            "message": raw_query,
            "history": history,
            "ctx_card": ctx_card,
        })
        rewritten_query = response.content.strip()

        # Update the state with the rewritten query
        state["rewrite_query"] = rewritten_query

    except Exception as e:
        print(f"Error occurred while rewriting query: {e}")
        state["rewrite_query"] = raw_query

    return state
