"""Read the source-derived lesson notes without leaving the study session."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from polish_tutor.models import Unit


class LessonNotesScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,f2", "close", "Return to study", priority=True),
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
    ]
    DEFAULT_CSS = """
    LessonNotesScreen { background: $surface; }
    #lesson-notes-title { height: auto; padding: 1 2; text-style: bold; }
    #lesson-notes-body { height: 1fr; padding: 0 2; }
    #lesson-notes-help { height: auto; padding: 1 2; }
    """

    def __init__(self, unit: Unit) -> None:
        super().__init__()
        self.unit = unit

    def compose(self) -> ComposeResult:
        yield Static(self.unit.title, id="lesson-notes-title", markup=False)
        with VerticalScroll(id="lesson-notes-body"):
            for note in self.unit.notes or ("No source notes for this unit.",):
                yield Static(note + "\n", markup=False)
        yield Static(
            "Scroll to read. F2 or Esc: return. Notes count as a hint during a review.",
            id="lesson-notes-help", markup=False,
        )

    def action_close(self) -> None:
        self.dismiss()
