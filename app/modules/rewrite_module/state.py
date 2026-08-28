from app.modules.state import AppState

class RewriteState(AppState, total=False):
    rewrite_query: str  # query đã rewrite, độc lập với ngữ cảnh,, tùy biến theo case



