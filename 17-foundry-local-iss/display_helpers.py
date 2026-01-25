"""Display helpers for the ISS Daily Reports Chatbot (dark mode optimized)."""

from IPython.display import display, Markdown, HTML
import json


def show_welcome():
    """Display welcome message."""
    display(Markdown("""
# ISS Daily Reports Chatbot

**Foundry Local** powered assistant - runs entirely locally using ONNX Runtime.
"""))


def show_model_loading(model_alias: str):
    """Display model loading status."""
    display(Markdown(f"Loading model: **{model_alias}** (first run may take a few minutes to download)"))


def show_model_ready(model_id: str, endpoint: str):
    """Display model ready status."""
    display(Markdown(f"Model ready: `{model_id}` at `{endpoint}`"))


def show_user_message(message: str):
    """Display user message."""
    display(HTML(f"""
<div style="background: rgba(33, 150, 243, 0.15); padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid #64B5F6;">
    <span style="color: #64B5F6; font-weight: 600;">You:</span>
    <span style="color: #E0E0E0;"> {message}</span>
</div>
"""))


def show_assistant_message(message: str):
    """Display assistant message with proper formatting."""
    import html as html_module
    import re
    
    # Escape HTML first
    safe_message = html_module.escape(message)
    
    # Convert markdown-style lists to HTML
    lines = safe_message.split('\n')
    formatted_lines = []
    in_list = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- '):
            if not in_list:
                formatted_lines.append('<ul style="margin: 8px 0; padding-left: 20px;">')
                in_list = True
            formatted_lines.append(f'<li style="margin: 4px 0;">{stripped[2:]}</li>')
        else:
            if in_list:
                formatted_lines.append('</ul>')
                in_list = False
            if stripped:
                formatted_lines.append(f'{stripped}<br>')
            else:
                formatted_lines.append('<br>')
    
    if in_list:
        formatted_lines.append('</ul>')
    
    formatted_message = '\n'.join(formatted_lines)
    
    display(HTML(f"""
<div style="background: rgba(156, 39, 176, 0.15); padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid #BA68C8;">
    <div style="color: #BA68C8; font-weight: 600;">ISS Assistant:</div>
    <div style="margin-top: 8px; color: #E0E0E0; line-height: 1.6;">{formatted_message}</div>
</div>
"""))


def show_function_call(name: str, arguments: dict):
    """Display function call being executed."""
    args_str = json.dumps(arguments) if arguments else "{}"
    display(HTML(f"""
<div style="background: rgba(255, 152, 0, 0.2); padding: 10px 14px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #FF9800;">
    <span style="color: #FFB74D; font-weight: 600;">Calling:</span>
    <code style="color: #FF9800; margin-left: 8px;">{name}({args_str})</code>
</div>
"""))


def show_function_result_preview(result: str, max_length: int = 300):
    """Display a preview of function result."""
    import html
    preview = result[:max_length] + "..." if len(result) > max_length else result
    preview = html.escape(preview)
    display(HTML(f"""
<div style="background: rgba(76, 175, 80, 0.15); padding: 10px 14px; border-radius: 6px; margin: 4px 0 12px 0; border-left: 4px solid #4CAF50;">
    <span style="color: #81C784; font-weight: 600;">Result:</span>
    <pre style="color: #A5D6A7; margin: 6px 0 0 0; font-size: 0.85em; white-space: pre-wrap;">{preview}</pre>
</div>
"""))


def show_error(message: str):
    """Display error message."""
    display(HTML(f"""
<div style="background: rgba(244, 67, 54, 0.15); padding: 12px; border-radius: 8px; margin: 8px 0; border-left: 4px solid #E57373;">
    <span style="color: #E57373; font-weight: 600;">Error:</span>
    <span style="color: #E0E0E0;"> {message}</span>
</div>
"""))


def show_no_function_call():
    """Display warning when model didn't use function calling."""
    display(HTML("""
<div style="background: rgba(244, 67, 54, 0.15); padding: 10px 14px; border-radius: 6px; margin: 8px 0; border-left: 4px solid #E57373;">
    <span style="color: #E57373; font-weight: 600;">No function call detected</span>
</div>
"""))
