"""Entry point for deploying the Gradio demo to Hugging Face Spaces."""

from demos.gradio.app import build_interface

app = build_interface()

if __name__ == "__main__":
    app.launch()
