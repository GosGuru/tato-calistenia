"""Fail-closed Promptfoo placeholder for evaluating existing synthetic outputs."""


def call_api(prompt, options=None, context=None):
    """Never generate or retrieve a response, regardless of supplied arguments."""
    raise RuntimeError('Inference disabled: supply existing synthetic outputs only')
