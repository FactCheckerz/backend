"""
Gradio UI. Talks to the FastAPI backend over HTTP rather than importing the
pipeline directly — keeps the API independently testable/deployable (e.g. you
could point a real WhatsApp bot at the same /verify endpoint later) and means
the demo UI can't silently diverge from what the API actually returns.

Run the API first: uvicorn main:app --port 8000
Then:              python app.py
"""
import os

import httpx
import gradio as gr

API_BASE = "http://127.0.0.1:8000"
MEDIA_TIMEOUT = 600  # audio/video: download + transcription/OCR can take a while


def render(data):
    if not data.get("claims"):
        return "No checkable medical claim found in this message.", "", ""

    c = data["claims"][0]  # demo UI shows the first extracted claim
    verdict_md = (
        f"### Verdict: **{c['verdict']}**  \n"
        f"Confidence: {c['confidence']:.0%}  \n"
        f"Claim checked: *{c['claim']}*"
    )
    evidence_md = "\n".join(
        f"- [{e['nli_label'].upper()}] {e.get('source','')}: {e['text'][:200]}..."
        for e in c["evidence_detail"]
    )
    return verdict_md, c["explanation"], evidence_md


def check_text(message: str):
    resp = httpx.post(f"{API_BASE}/verify", json={"text": message, "input_type": "text"}, timeout=120)
    resp.raise_for_status()
    return render(resp.json())


def check_file(file_path: str, media_type: str):
    if not file_path:
        return "Upload a file first.", "", ""
    with open(file_path, "rb") as f:
        resp = httpx.post(
            f"{API_BASE}/verify/upload",
            files={"file": (os.path.basename(file_path), f)},
            data={"input_type": media_type},
            timeout=MEDIA_TIMEOUT,
        )
    resp.raise_for_status()
    return render(resp.json())


def check_url(url: str, media_type: str):
    if not url:
        return "Paste a link first.", "", ""
    resp = httpx.post(
        f"{API_BASE}/verify",
        json={"text": "", "input_type": media_type, "url": url},
        timeout=MEDIA_TIMEOUT,
    )
    resp.raise_for_status()
    return render(resp.json())


with gr.Blocks(title="Medical Misinformation Checker") as demo:
    gr.Markdown("# Medical Misinformation Detection & Fact Verification")

    with gr.Tabs():
        with gr.Tab("Text"):
            inp = gr.Textbox(label="Paste the forwarded message", lines=5)
            btn = gr.Button("Check claim", variant="primary")
            verdict_out = gr.Markdown()
            explanation_out = gr.Textbox(label="AI-generated explanation", lines=4)
            evidence_out = gr.Markdown(label="Evidence")
            btn.click(check_text, inputs=inp, outputs=[verdict_out, explanation_out, evidence_out])

        with gr.Tab("Upload video/audio"):
            file_inp = gr.File(label="Upload a video or audio file", type="filepath")
            file_type = gr.Radio(["video", "audio"], value="video", label="Media type")
            file_btn = gr.Button("Check claim", variant="primary")
            file_verdict_out = gr.Markdown()
            file_explanation_out = gr.Textbox(label="AI-generated explanation", lines=4)
            file_evidence_out = gr.Markdown(label="Evidence")
            file_btn.click(
                check_file,
                inputs=[file_inp, file_type],
                outputs=[file_verdict_out, file_explanation_out, file_evidence_out],
            )

        with gr.Tab("Reel / YouTube link"):
            url_inp = gr.Textbox(label="Paste a YouTube / Reel / video link")
            url_type = gr.Radio(["video", "audio"], value="video", label="Media type")
            url_btn = gr.Button("Check claim", variant="primary")
            url_verdict_out = gr.Markdown()
            url_explanation_out = gr.Textbox(label="AI-generated explanation", lines=4)
            url_evidence_out = gr.Markdown(label="Evidence")
            url_btn.click(
                check_url,
                inputs=[url_inp, url_type],
                outputs=[url_verdict_out, url_explanation_out, url_evidence_out],
            )

if __name__ == "__main__":
    demo.launch()
