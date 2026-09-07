from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Photometric thresholds use uint8 grayscale; geometry is in canonical UI-icon units."""

    analysis_height: int = 720
    opencv_threads: int = 1
    anchor_threshold: float = 0.78
    esc_threshold: float = 0.70
    index_threshold: float = 0.85
    candle_threshold: float = 0.86
    entry_threshold: float = 0.88
    star_threshold: float = 0.91
    classification_margin: float = 0.025
    core_brightness: int = 90
    particle_brightness: int = 110
    text_contrast: int = 6
    poll_interval: float = 0.06
    transition_timeout: float = 2.5
    stable_seconds: float = 0.24
    page_transition_settle_seconds: float = 1.3
    friend_click_settle_seconds: float = 0.9 + 0.3
    light_key_settle_seconds: float = 0.3
    friend_close_settle_seconds: float = 0.2
    index_reset_extra_presses: int = 2
    index_reset_key_interval: float = 0.06
    max_index_reset_batches: int = 2
    retries: int = 3
    max_pages: int = 40
    max_actions_per_page: int = 100
    max_recoveries: int = 2
