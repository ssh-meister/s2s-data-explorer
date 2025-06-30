import json
import html
import pathlib
from typing import Dict, List
import base64
import mimetypes
import math

import panel as pn

# Enable Panel
pn.extension()

###############################################################################
# CONFIGURATION
###############################################################################
# Path to the manifest describing a single conversation.  Update this path or
# provide a different one when launching Panel, e.g.:
#   panel serve tts_chat_explorer.py --args my_manifest.json
DEFAULT_META_MANIFEST = pathlib.Path(__file__).with_name("example_meta_manifest.json")

###############################################################################
# HELPER FUNCTIONS
###############################################################################

def _escape(text: str) -> str:
    """HTML-escape *text* for safe insertion into attribute/body."""
    return html.escape(str(text), quote=True)


def _fmt_time(seconds: float | int) -> str:
    """Return m:ss.xx string for *seconds*."""
    try:
        sec = float(seconds)
    except Exception:
        return str(seconds)

    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:05.2f}"


def _audio_tag(file_path: str | pathlib.Path) -> str:
    """Return an <audio> HTML tag with base64-embedded audio if path exists."""

    if not file_path:
        return ""

    p = pathlib.Path(file_path)
    if not p.exists():
        return ""

    mime, _ = mimetypes.guess_type(str(p))
    if mime is None:
        mime = "audio/wav"

    try:
        data_b64 = base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return ""

    return (
        f"<audio controls class='turn-audio'>"
        f"<source src='data:{mime};base64,{data_b64}' type='{mime}' />"
        "</audio>"
    )


def _build_message(turn: Dict, user_nick: str, agent_nick: str) -> str:
    """Return an HTML snippet representing a single chat bubble."""

    is_user = turn.get("speaker", "").upper() == "USER"
    nick = user_nick if is_user else agent_nick
    css_class = "user" if is_user else "agent"

    # Build tooltip containing all additional turn fields
    tooltip_lines = [
        f"{k}: {v}" for k, v in turn.items()
        if k not in ("speaker", "utterance")
    ]
    tooltip = _escape("\n".join(tooltip_lines))

    audio_html = _audio_tag(turn.get("audio_filepath", ""))

    return (
        f"<div class='bubble {css_class}' data-meta=\"{tooltip}\" title=\"{_escape('Details')}\">"
        f"<span class='nick'>{_escape(nick)}</span><br/>"
        f"{_escape(turn.get('utterance', ''))}"
        f"<div class='ts'>{_escape(_fmt_time(turn.get('start_time', 0)))}</div>"
        f"{audio_html}"
        "</div>"
    )


def _chat_html(manifest: Dict) -> str:
    """Assemble full chat column HTML."""
    bubbles = [
        _build_message(t, manifest.get("user_speaker", "User"), manifest.get("agent_speaker", "Agent"))
        for t in manifest.get("turns", [])
    ]
    return "<div class='chat'>" + "\n".join(bubbles) + "</div>"


def _read_meta_manifest(meta_path: pathlib.Path) -> List[Dict]:
    """Read meta manifest (JSON-lines)."""
    entries: List[Dict] = []
    with meta_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _load_conversation(entry: Dict, base_dir: pathlib.Path) -> Dict:
    """Load conversation manifest and fix relative paths."""

    meta_file = base_dir / entry["metadata_path"]
    manifest = json.loads(meta_file.read_text())

    # Fix per-turn audio paths
    manifest_dir = meta_file.parent
    for turn in manifest.get("turns", []):
        fp = turn.get("audio_filepath")
        if fp and not pathlib.Path(fp).is_absolute():
            turn["audio_filepath"] = str((manifest_dir / fp).resolve())

    # Also fix conversation-level audio path
    audio_fp = entry.get("wav_path")
    if audio_fp and not pathlib.Path(audio_fp).is_absolute():
        audio_fp = str((base_dir / audio_fp).resolve())

    manifest["audio_file"] = audio_fp
    manifest["conversation_id"] = entry.get("conversation_id", manifest.get("conversation_id"))
    manifest["user_speaker"] = entry.get("user_speaker", manifest.get("user_speaker", "USER"))
    manifest["agent_speaker"] = entry.get("agent_speaker", manifest.get("agent_speaker", "AGENT"))

    return manifest


###############################################################################
# Duration helper
###############################################################################

#def _compute_total_duration(meta_entry: Dict, base_dir: pathlib.Path) -> float:
#    """Compute total conversation duration from its manifest file."""
#
#    manifest_path = base_dir / meta_entry["metadata_path"]
#    try:
#        data = json.loads(manifest_path.read_text())
#        return sum(t.get("duration", 0) for t in data.get("turns", []))
#    except Exception:
#        return 0.0


###############################################################################
# MAIN APP
###############################################################################

def create_app(meta_manifest_path: pathlib.Path = DEFAULT_META_MANIFEST) -> pn.template.BootstrapTemplate:
    """Return a Panel Template ready to be served with list of conversations."""

    base_dir = meta_manifest_path.parent
    entries = _read_meta_manifest(meta_manifest_path)
    if not entries:
        raise ValueError("Meta manifest appears empty or unreadable.")

    # Pre-compute total_duration for each entry
    #for e in entries:
    #    e["total_duration"] = _compute_total_duration(e, base_dir)

    # Widgets to be updated -----------------------------------------------
    # Conversation header (title + audio) will live inside the main area
    chat_pane = pn.pane.HTML(sizing_mode="stretch_both", styles=dict(overflow_y="auto", height="70vh"))

    # Per-conversation widgets (updated on selection)
    conv_title_pane = pn.pane.HTML("<h4>Select a conversation</h4>", sizing_mode="stretch_width")
    audio_widget = pn.pane.Audio(width=300)  # Empty initially, will set .object later

    # Header row shown above the chat area
    conv_header_row = pn.Row(conv_title_pane, audio_widget, css_classes=["conv-header"])

    # Template -------------------------------------------------------------
    template = pn.template.BootstrapTemplate(
        # Show manifest basename in the global header
        title=meta_manifest_path.name,
        sidebar=[],
        # Place the conversation header row above the chat body
        main=[conv_header_row, chat_pane],
    )

    # Filter widgets -------------------------------------------------------
    min_turns = min(e["num_turns"] for e in entries)
    max_turns = max(e["num_turns"] for e in entries)

    min_dur = min(e["total_duration"] for e in entries)
    max_dur = max(e["total_duration"] for e in entries)

    turns_slider = pn.widgets.IntRangeSlider(
        name="Num Turns", start=min_turns, end=max_turns, value=(min_turns, max_turns)
    )

    dur_slider = pn.widgets.RangeSlider(
        name="Duration (s)", start=math.floor(min_dur), end=math.ceil(max_dur), step=1,
        value=(math.floor(min_dur), math.ceil(max_dur))
    )

    # Conversation selector with pagination --------------------------------
    page_size = 25  # number of conversations per page
    conv_select = pn.widgets.RadioButtonGroup(name="Conversations", orientation="vertical")
    page_slider = pn.widgets.IntSlider(name="Page", start=1, end=1, value=1)

    # Will hold the conversation IDs after filters are applied
    conv_ids: List[str] = []

    # Helper to update list shown for current page
    def _update_page_options(*events):
        if not conv_ids:
            conv_select.options = []
            return

        page_idx = page_slider.value if isinstance(page_slider.value, int) else 1
        page_idx = max(1, min(page_idx, math.ceil(len(conv_ids) / page_size)))
        start = (page_idx - 1) * page_size
        end = start + page_size
        conv_select.options = conv_ids[start:end]

        if conv_select.value not in conv_select.options:
            # Assign first option if current selection is out of page bounds
            if conv_select.options:
                conv_select.value = conv_select.options[0]  # type: ignore[assignment]

    # Assemble sidebar layout
    sidebar_column = pn.Column(
        "### Filters",
        turns_slider,
        dur_slider,
        pn.Spacer(height=10),
        page_slider,
        conv_select,
    )
    template.sidebar.append(sidebar_column)  # type: ignore[attr-defined]

    # Update function ------------------------------------------------------
    def _apply_filters(*events):
        nonlocal conv_ids
        # Guard against undefined widget values during initialization
        if not isinstance(turns_slider.value, tuple) or not isinstance(dur_slider.value, tuple):
            return
        lo_t, hi_t = turns_slider.value
        lo_d, hi_d = dur_slider.value

        filtered = [
            e for e in entries
            if lo_t <= e["num_turns"] <= hi_t and lo_d <= e["total_duration"] <= hi_d
        ]

        conv_ids = [e["conversation_id"] for e in filtered]

        # Update pagination slider
        num_pages = max(1, math.ceil(len(conv_ids)/page_size))
        page_slider.end = num_pages
        if not isinstance(page_slider.value, int) or page_slider.value > num_pages:
            page_slider.value = 1

        # Refresh page options
        _update_page_options()

    turns_slider.param.watch(_apply_filters, "value")
    dur_slider.param.watch(_apply_filters, "value")

    # Watch page changes once (after helper defined)
    page_slider.param.watch(_update_page_options, "value")

    def _update_view(event=None):
        conv_id = conv_select.value
        if conv_id is None:
            return
        entry = next(it for it in entries if it["conversation_id"] == conv_id)
        manifest = _load_conversation(entry, base_dir)

        chat_pane.object = _chat_html(manifest)

        # Update audio (may be slow for large files)
        audio_fp = manifest.get("audio_file") or ""
        if audio_fp and pathlib.Path(audio_fp).exists():
            audio_widget.object = pathlib.Path(audio_fp)
        else:
            audio_widget.object = ""  # Clear

        # Update title immediately for snappier response
        conv_title_pane.object = f"<h4>Conversation: {conv_id}</h4>"

    conv_select.param.watch(_update_view, "value")

    # Initialize filters and view
    _apply_filters()
    _update_view()

    # Minimal CSS styling remains below -----------------------------------
    _style_css = """
        .chat               {display:flex;flex-direction:column;gap:8px;padding:10px;}
        .bubble             {border-radius:8px;padding:10px 14px;max-width:75%;position:relative;}
        .bubble.user        {align-self:flex-start;background:#DCF8C6;}
        .bubble.agent       {align-self:flex-end;background:#FFFFFF;border:1px solid #ccc;}
        .bubble:hover       {opacity:0.9;}
        .nick               {font-weight:600;font-size:0.85em;}
        .ts                 {font-size:0.70em;color:#555;margin-top:4px;text-align:right;}
        .turn-audio         {width:200px;margin-top:4px;}
        /* Custom tooltip using data-meta attribute */
        .bubble[data-meta]::after {
            content: attr(data-meta);
            white-space: pre-line;
            display: none;
            position: absolute;
            left: 0;
            top: 100%;
            background: #ffffe1;
            color: #000;
            padding: 6px 8px;
            border: 1px solid #AAA;
            border-radius: 4px;
            box-shadow: 0 2px 6px rgba(0,0,0,.15);
            z-index: 20;
            max-width: 280px;
        }

        .bubble[data-meta]:hover::after {
            display: block;
        }

        /* Header separator */
        .conv-header        {border-bottom:1px solid #AAA;padding-bottom:6px;margin-bottom:10px;gap:16px;align-items:center;}
    """
    pn.config.raw_css.append(_style_css)  # type: ignore[attr-defined]
    return template


###############################################################################
# ENTRY POINT FOR `panel serve`
###############################################################################

if __name__.startswith("bokeh"):
    pn.config.raw_css.append("body {background:#F5F5F5;}")  # type: ignore[attr-defined]

    # Allow passing an alternative manifest via command-line args
    import sys

    meta_arg = None
    if len(sys.argv) > 1:
        meta_arg = pathlib.Path(sys.argv[1])
        if not meta_arg.exists():
            raise FileNotFoundError(f"Provided meta manifest {meta_arg} does not exist.")

    app = create_app(meta_arg or DEFAULT_META_MANIFEST)
    app.servable() 
