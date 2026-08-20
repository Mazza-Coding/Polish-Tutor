from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, Label, RadioButton, RadioSet, Static

from polish_tutor.course import CourseCatalog
from polish_tutor.db import Database, Profile, ProgressDatabaseError
from polish_tutor.engine import (
    DoneItem,
    FormIntroductionItem,
    IntroductionItem,
    ReviewItem,
    StudyEngine,
    SubmissionResult,
    SubmissionStatus,
    WaitingItem,
)
from polish_tutor.models import PromptKind, SelfForm
from polish_tutor.scheduling import Clock, format_interval


class SetupScreen(Screen[None]):
    BINDINGS = [Binding("ctrl+q", "app.quit", "Quit", priority=True)]

    def __init__(self, profile: Profile | None) -> None:
        super().__init__()
        self.profile = profile

    def compose(self) -> ComposeResult:
        masculine = self.profile is None or self.profile.self_form is SelfForm.MASCULINE
        feminine = self.profile is not None and self.profile.self_form is SelfForm.FEMININE
        with Container(id="setup-card"):
            yield Label("Polish Typing Tutor", id="setup-title")
            yield Static(
                "Choose the Polish form to practise when you speak about yourself.",
                markup=False,
            )
            yield RadioSet(
                RadioButton("Masculine self-reference", value=masculine, id="masculine"),
                RadioButton("Feminine self-reference", value=feminine, id="feminine"),
                id="self-form",
            )
            yield Static(
                "There is no daily limit. Due reviews take priority; otherwise "
                "the next eligible objective starts immediately.",
                markup=False,
            )
            yield Static("", id="setup-error", markup=False)
            yield Button("Save and study", variant="primary", id="save-setup")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(RadioSet).focus()

    @on(Button.Pressed, "#save-setup")
    def save_button(self) -> None:
        self._save()

    def _save(self) -> None:
        radio = self.query_one("#self-form", RadioSet)
        pressed = radio.pressed_button
        error = self.query_one("#setup-error", Static)
        if pressed is None:
            error.update("Choose a self-reference form.")
            return
        self_form = SelfForm.MASCULINE if pressed.id == "masculine" else SelfForm.FEMININE
        self.app.complete_setup(Profile(self_form))  # type: ignore[attr-defined]


class ResetProgressScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="reset-card"):
            yield Label("Delete all progress?", id="reset-title")
            yield Static(
                "This permanently deletes every card, review, and learned form. "
                "Your self-reference choice will be kept.",
                id="reset-warning",
                markup=False,
            )
            yield Label("Type DELETE and press Enter to confirm.")
            yield Input(placeholder="DELETE", id="reset-confirmation")
            yield Static("Esc: cancel", id="reset-help", markup=False)
            yield Static("", id="reset-error", markup=False)

    def on_mount(self) -> None:
        self.query_one("#reset-confirmation", Input).focus()

    @on(Input.Submitted, "#reset-confirmation")
    def confirm_reset(self, event: Input.Submitted) -> None:
        if event.value == "DELETE":
            self.dismiss(True)
            return
        self.query_one("#reset-error", Static).update(
            "Nothing was deleted. Type uppercase DELETE exactly, or press Esc."
        )

    def action_cancel(self) -> None:
        self.dismiss(False)


class PauseScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,enter", "resume", "Resume", priority=True),
        Binding("r", "reset_progress", "Delete progress", priority=True),
        Binding("q", "quit_app", "Quit", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="pause-card"):
            yield Label("Paused", id="pause-title")
            yield Static(
                "Enter or Esc: resume\nR: delete all progress\nQ: save and quit",
                id="pause-help",
                markup=False,
            )
            yield Static("", id="pause-error", markup=False)

    def action_resume(self) -> None:
        self.dismiss()

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_reset_progress(self) -> None:
        self.app.push_screen(ResetProgressScreen(), callback=self._finish_reset)

    async def _finish_reset(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        app = self.app
        try:
            app.database.reset_progress()  # type: ignore[attr-defined]
        except ProgressDatabaseError as error:
            self.query_one("#pause-error", Static).update(str(error))
            return
        await self.dismiss()
        if isinstance(app.screen, StudyScreen):
            app.screen.show_next()
            app.screen.query_one("#feedback", Static).update("All study progress deleted.")


class StudyScreen(Screen[None]):
    BINDINGS = [
        Binding("tab", "hint", "Hint", priority=True),
        Binding("ctrl+r", "reveal", "Reveal", priority=True),
        Binding("escape", "pause", "Pause", priority=True),
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
    ]

    def __init__(self, engine: StudyEngine) -> None:
        super().__init__()
        self.engine = engine
        self.item: (
            IntroductionItem | FormIntroductionItem | ReviewItem | WaitingItem | DoneItem | None
        ) = None
        self.awaiting_continue = False

    def compose(self) -> ComposeResult:
        yield Static("", id="status", markup=False)
        with Container(id="study-card"):
            yield Static("", id="phase", markup=False)
            yield Static("", id="context", markup=False)
            yield Static("", id="prompt", markup=False)
            yield Static("", id="model", markup=False)
            yield Input(placeholder="Type Polish here", id="answer")
            yield Static("", id="feedback", markup=False)
        yield Static(
            "Enter submit/continue  ·  Tab hint  ·  Ctrl+R reveal  ·  Esc pause  ·  Ctrl+Q quit",
            id="keys",
            markup=False,
        )

    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)
        self.show_next()

    def _tick(self) -> None:
        if isinstance(self.item, WaitingItem):
            if self.engine.clock.now() >= self.item.due:
                self.show_next()
            else:
                remaining = max(0, round((self.item.due - self.engine.clock.now()).total_seconds()))
                self.query_one("#prompt", Static).update(f"Next recall in {remaining}s")
        elif (
            isinstance(self.item, DoneItem)
            and self.item.next_due is not None
            and self.engine.clock.now() >= self.item.next_due
        ):
            self.show_next()

    def _update_status(self) -> None:
        status = self.engine.status()
        self.query_one("#status", Static).update(
            f"Due {status.due_now}  ·  Introduced {status.introduced_concepts}/"
            f"{status.total_concepts}"
            f"  ·  Ready words {status.ready_concepts}/{status.total_concepts}"
        )

    def show_next(self) -> None:
        self.awaiting_continue = False
        self.item = self.engine.next_item()
        self._update_status()
        answer = self.query_one("#answer", Input)
        answer.value = ""
        answer.disabled = False
        answer.placeholder = "Type Polish here"
        self.query_one("#feedback", Static).update("")
        self.query_one("#model", Static).update("")

        if isinstance(self.item, IntroductionItem):
            objective = self.item.objective
            unit = self.engine.catalog.units[objective.unit_id]
            self.query_one("#phase", Static).update(f"NEW · {unit.title}")
            self.query_one("#context", Static).update(objective.model.english)
            self.query_one("#prompt", Static).update("Copy the Polish model:")
            self.query_one("#model", Static).update(objective.model.polish.text)
        elif isinstance(self.item, FormIntroductionItem):
            variant = self.item.variant
            unit = self.engine.catalog.units[self.item.objective.unit_id]
            self.query_one("#phase", Static).update(f"NEW FORM · {unit.title}")
            if variant.kind is PromptKind.TRANSLATION:
                self.query_one("#context", Static).update(variant.prompt)
                instruction = "Copy the Polish model:"
            else:
                self.query_one("#context", Static).update(variant.context or "")
                instruction = f"{variant.prompt}\nCopy the missing Polish form:"
            self.query_one("#prompt", Static).update(instruction)
            self.query_one("#model", Static).update(self.item.answer.text)
        elif isinstance(self.item, ReviewItem):
            variant = self.item.variant
            unit = self.engine.catalog.units[self.item.objective.unit_id]
            label = "CLOZE" if variant.kind is PromptKind.CLOZE else "ENGLISH → POLISH"
            self.query_one("#phase", Static).update(f"{label} · {unit.title}")
            self.query_one("#context", Static).update(variant.context or "")
            self.query_one("#prompt", Static).update(variant.prompt)
        elif isinstance(self.item, WaitingItem):
            self.query_one("#phase", Static).update("SHORT REVIEW PENDING")
            self.query_one("#context", Static).update("Stay here, or quit and return later.")
            self.query_one("#prompt", Static).update(f"Next recall in {self.item.seconds}s")
            answer.placeholder = "Press Enter to recheck"
        else:
            assert isinstance(self.item, DoneItem)
            self.query_one("#phase", Static).update("NEXT REVIEW SCHEDULED")
            if self.item.next_due:
                local_due = self.item.next_due.astimezone()
                delta = self.item.next_due - self.engine.clock.now()
                detail = (
                    f"Next review in {format_interval(delta)} "
                    f"({local_due.strftime('%Y-%m-%d %H:%M')})."
                )
            else:
                detail = "No review is currently scheduled."
            self.query_one("#context", Static).update(detail)
            self.query_one("#prompt", Static).update(
                "The tutor will continue automatically when it is due. Press Enter to recheck now."
            )
            answer.placeholder = "Press Enter to recheck"
        answer.focus()

    @on(Input.Submitted, "#answer")
    def submit_answer(self, event: Input.Submitted) -> None:
        if self.awaiting_continue or isinstance(self.item, (WaitingItem, DoneItem)):
            self.show_next()
            return
        result = self.engine.submit(event.value)
        self._show_result(result)

    def _show_result(self, result: SubmissionResult) -> None:
        answer = self.query_one("#answer", Input)
        feedback = self.query_one("#feedback", Static)
        feedback.update(result.message)
        answer.value = ""
        if result.status is SubmissionStatus.REVEAL and result.canonical:
            self.query_one("#model", Static).update(result.canonical)
            answer.placeholder = "Copy the revealed answer"
        elif result.status is SubmissionStatus.RETRY:
            answer.placeholder = "Try again"
        else:
            if result.canonical:
                self.query_one("#model", Static).update(f"✓ {result.canonical}")
            answer.placeholder = "Press Enter to continue"
            self.awaiting_continue = True
            self._update_status()
        answer.focus()

    def action_hint(self) -> None:
        result = self.engine.request_hint()
        if result:
            self._show_result(result)

    def action_reveal(self) -> None:
        result = self.engine.reveal()
        if result:
            self._show_result(result)

    def action_pause(self) -> None:
        self.app.push_screen(PauseScreen())


class PolishTutorApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = "Polish Typing Tutor"

    def __init__(
        self,
        *,
        catalog: CourseCatalog,
        database: Database,
        engine: StudyEngine,
        clock: Clock,
        force_setup: bool = False,
    ) -> None:
        super().__init__()
        self.catalog = catalog
        self.database = database
        self.engine = engine
        self.clock = clock
        self.force_setup = force_setup

    def on_mount(self) -> None:
        profile = self.database.get_profile()
        if profile is None or self.force_setup:
            self.push_screen(SetupScreen(profile))
        else:
            self.push_screen(StudyScreen(self.engine))

    def complete_setup(self, profile: Profile) -> None:
        self.database.save_profile(profile, self.clock.now())
        self.switch_screen(StudyScreen(self.engine))
