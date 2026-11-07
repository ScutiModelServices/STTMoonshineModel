"""The options the admin page can change. Each can still start from its environment variable; a saved value wins."""

from engine import COMPUTE_TYPES, DEFAULT_MODEL, MODELS
from settings import Setting

SETTINGS = [
    Setting("update_check_hours", "Check for updates every (hours)", "float", 6.0, "SERVICE_UPDATE_CHECK_HOURS", 0, 720,
            help="0 = only when you press Check now"),
    Setting("max_inflight", "Calls allowed to wait for the model", "int", 0, "SERVICE_MAX_INFLIGHT", 0, 10000,
            help="Per replica; more get 429. 0 = 4"),
    Setting("cache_size", "Answers kept per replica", "int", 256, "SERVICE_CACHE_SIZE", 0, 100000,
            help="The last answers for the same audio and options, sent again without transcribing. Decoding is deterministic, so every request is kept. 0 = off"),
    Setting("max_seconds", "Longest audio per call (seconds)", "int", 150, "SERVICE_MAX_SECONDS", 1, 900,
            help="Longer audio gets 413. Keep it under what the caller's own timeout allows at the model's speed"),
    Setting("model", "Base model", "text", DEFAULT_MODEL, "SERVICE_MODEL", restart=True, blank=False,
            help=f"One of {', '.join(MODELS)}. base is more accurate, tiny is about twice as fast. After a restart, download it from the Updates card"),
    Setting("compute_type", "Number format", "text", "float", "SERVICE_COMPUTE_TYPE", restart=True, blank=False,
            help=f"One of {', '.join(COMPUTE_TYPES)}. quantized is smaller and faster on a CPU, with a little less accuracy"),
    Setting("warm", "Load the model at start", "bool", True, "SERVICE_WARM", restart=True),
]
